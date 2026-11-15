import json
from types import SimpleNamespace

import intelligence.extractor as ex
import llm.groq_client as g
from intelligence.cache import clear_cache
from rag.citation_validator import validate_and_format_citations
from rag.query_expansion import expand_query


def doc(page, text, sim=0.8, ctype="text"):
    return SimpleNamespace(page_content=text, metadata={"chunk_id": f"c{page}", "page": page, "section": "S",
                                                        "similarity": sim, "chunk_type": ctype})


def test_json_mode_failure_falls_back_to_plain_call(monkeypatch):
    calls = []

    def fake_invoke(llm, messages, retries=4):
        calls.append(llm)
        if llm == "json":
            raise RuntimeError("Error code: 400 - Failed to validate JSON ... json_validate_failed")
        return SimpleNamespace(content='Here you go: {"a": {"value": "x"}} thanks')
    monkeypatch.setattr(g, "invoke_with_retry", fake_invoke)
    monkeypatch.setattr(g, "get_llm", lambda json_mode=False, **k: "json" if json_mode else "plain")
    assert g.invoke_json([]) == {"a": {"value": "x"}}
    assert calls == ["json", "plain"]


def test_other_errors_are_not_retried(monkeypatch):
    monkeypatch.setattr(g, "invoke_with_retry", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("401 invalid api key")))
    monkeypatch.setattr(g, "get_llm", lambda **k: None)
    try:
        g.invoke_json([])
        assert False
    except RuntimeError as e:
        assert "api key" in str(e)


def test_ground_labels_fixes_wrong_page_and_flags_unverified():
    labels = {"S1": doc(1, "Estimated Cost put to Tender: Rs. 32,96,951/-"),
              "S2": doc(3, "4. Earnest Money: Rs. 65,939/- 5. Period 03 (Three) Month")}
    assert ex.ground_labels("Rs. 65,939/-", ["S1"], labels) == (["S2"], True)       # cited page lacked the figure
    assert ex.ground_labels("Rs. 99,999/-", ["S1"], labels) == ([], False)          # figure nowhere: unverified
    assert ex.ground_labels("Enlisted contractors", ["S1"], labels) == (["S1"], True)  # no figures: unchanged


def test_extractor_uses_grounded_refs(monkeypatch):
    docs = [doc(1, "Estimated Cost put to Tender: Rs. 32,96,951/-"), doc(3, "Earnest Money: Rs. 65,939/-")]
    monkeypatch.setattr(ex, "retrieve_multi", lambda *a, **k: docs)
    monkeypatch.setattr(ex, "invoke_json", lambda messages, model=None: {
        "emd": {"value": "Rs. 65,939/-", "refs": ["S1"], "found": True},
        "title": {"value": "Renovation work", "refs": ["S1"], "found": True},
        "estimated_cost": {"value": "Rs. 12,34,567/-", "refs": ["S1"], "found": True}})
    clear_cache("fixtest")
    out = ex.run_group("fixtest", "key_info", refresh=True)
    by = {f["key"]: f for f in out["fields"]}
    assert by["emd"]["pages"] == [3] and by["emd"]["verified"]
    assert by["title"]["pages"] == [1]
    assert not by["estimated_cost"]["verified"] and "not found in the retrieved" in by["estimated_cost"]["value"]
    assert by["estimated_cost"]["confidence"]["label"] == "low"
    clear_cache("fixtest")


def test_bare_labels_are_converted():
    labels = {"S1": doc(7, "x"), "S2": doc(9, "y")}
    r = validate_and_format_citations("| Condition | Source |\n| Proof | S1 |\n| Other | S2 |\nAlso [S1].", labels)
    assert "S1" not in r["answer"] and "S2" not in r["answer"]
    assert r["answer"].count("[1]") == 2 and "[2]" in r["answer"]
    assert r["citations"]["total"] == r["citations"]["valid"] == 3 and r["confidence"]["score"] > 0.4


def test_query_expansion():
    assert "schedule of quantities" in expand_query("what is BOQ of tender?")
    assert "earnest money deposit" in expand_query("how to pay EMD")
    assert expand_query("what is eligibility?") == "what is eligibility?"
