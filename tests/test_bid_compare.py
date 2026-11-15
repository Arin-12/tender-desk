from types import SimpleNamespace

import intelligence.bid_checker as bc
import intelligence.compare as cmp
from intelligence.cache import clear_cache


def doc(page, text):
    return SimpleNamespace(page_content=text, metadata={"chunk_id": f"c{page}", "page": page, "section": "S",
                                                        "similarity": 0.8, "chunk_type": "text"})


def test_bid_check_statuses_counts_and_rules(monkeypatch):
    docs = [doc(5, "x"), doc(6, "y")]
    monkeypatch.setattr(bc, "retrieve_multi", lambda *a, **k: docs)
    monkeypatch.setattr(bc, "run_group", lambda *a, **k: {"fields": []})
    answers = iter([
        {"criteria": [
            {"category": "registration", "criterion": "Enlistment", "requirement": "valid enlistment", "applies_to": "all bidders", "refs": ["S1"]},
            {"category": "technical", "criterion": "Similar works", "requirement": "amount left blank in the tender", "applies_to": "non-CPWD contractors only", "blank_amount": True, "refs": ["S2"]},
            {"category": "technical", "criterion": "EPC work", "requirement": "one EPC work", "applies_to": "EPC tenders only", "refs": ["S2"]},
            {"category": "bid_document", "criterion": "EMD receipt", "requirement": "receipt", "applies_to": "all bidders", "refs": ["S1"]},
            {"category": "personnel", "criterion": "Site engineer", "requirement": "1 engineer", "applies_to": "all bidders", "refs": ["S1"]}]},
        {"results": [
            {"id": "C1", "status": "met", "evidence": "valid"},
            {"id": "C2", "status": "met", "evidence": "3 works"},          # blank amount: must be downgraded
            {"id": "C3", "status": "not_applicable", "evidence": "not an EPC tender"},
            {"id": "C4", "status": "unclear", "evidence": "No information provided"},  # bid document -> to_prepare
            {"id": "C5", "status": "not_met", "evidence": "none", "action": "hire"}]}])
    monkeypatch.setattr(bc, "invoke_json", lambda *a, **k: next(answers))
    clear_cache("bidtest")
    out = bc.check_eligibility("bidtest", {"company": "X"})
    st = {c["id"]: c["status"] for c in out["criteria"]}
    assert st == {"C1": "met", "C2": "unclear", "C3": "not_applicable", "C4": "to_prepare", "C5": "not_met"}
    s = out["summary"]
    assert (s["met"], s["unclear"], s["not_met"], s["to_prepare"], s["not_applicable"]) == (1, 1, 1, 1, 1)
    assert s["judged"] == 3 and s["readiness"] == 33 and s["verdict"] == "not_eligible_as_stated"
    clear_cache("bidtest")


def test_compare_does_not_treat_missing_as_difference(monkeypatch):
    def fake_group(doc_id, group, refresh=False):
        found_b = doc_id == "a"           # tender B has no value for "completion"
        return {"title": "Key", "fields": [
            {"key": "cost", "label": "Cost", "value": "Rs 1" if doc_id == "a" else "Rs 2", "found": True, "pages": [1]},
            {"key": "completion", "label": "Completion", "value": "3 months" if found_b else "Not specified", "found": found_b, "pages": [2]}]}
    monkeypatch.setattr(cmp, "run_group", fake_group)
    seen = {}

    def fake_invoke(llm, messages, retries=4):
        seen["prompt"] = messages[0].content
        return SimpleNamespace(content="- cost differs")
    monkeypatch.setattr(cmp, "invoke_with_retry", fake_invoke)
    monkeypatch.setattr(cmp, "get_llm", lambda **k: None)
    out = cmp.compare_tenders("a", "b")
    row = next(r for r in out["rows"] if r["label"] == "Completion")
    assert row["comparable"] is False and "Not found" in row["b"]
    assert "Completion: A =" not in seen["prompt"] and "Completion" in seen["prompt"].split("NOT EXTRACTED")[1]
    assert "never convert units" in seen["prompt"]
