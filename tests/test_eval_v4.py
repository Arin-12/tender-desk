import json

import pytest

import evaluation.eval_qa_v3 as ev
from config.settings import PROCESSED_DIR


def test_answer_check_ignores_formatting():
    ans = "**Security deposit:** 2.5 % of the gross amount; released after defect\u2011liability period + 2 months. Rs. 32,96,951/-"
    assert ev.check_answer({"expected_contains": ["2.5%", "defect liability", "32,96,951"]}, ans) is True
    assert ev.check_answer({"expected_contains": ["5%"]}, "about 25 percent") is False
    assert ev.check_answer({"expected_contains": []}, "anything") is None


def test_citation_metrics():
    assert ev.citation_metrics({3, 4, 7}, {7}) == {"hit": True, "precision": 1.0, "strict": True, "coverage": 1 / 3}
    m = ev.citation_metrics({3, 4}, {28})
    assert m["hit"] is False and m["precision"] == 0.0
    assert ev.citation_metrics({3}, set())["hit"] is False
    assert ev.citation_metrics(set(), {1}) is None
    assert ev.citation_metrics({7, 33}, {33, 36})["strict"] is False


def test_pages_containing_uses_text_and_tables():
    pages = [{"page": 1, "text": "Estimated Cost: Rs. 32,96,951/-", "tables": []},
             {"page": 2, "text": "nothing", "tables": [{"rows": [["Earnest money", "Rs. 65,939/-"]]}]},
             {"page": 3, "text": "Rs. 65,939/- and 32,96,951", "tables": []}]
    (PROCESSED_DIR / "evtest.json").write_text(json.dumps(pages))
    try:
        assert ev.pages_containing("evtest", ["65,939"]) == {2, 3}
        assert ev.pages_containing("evtest", ["65,939", "32,96,951"]) == {3}
        assert ev.pages_containing("evtest", []) == set()
    finally:
        (PROCESSED_DIR / "evtest.json").unlink()


def test_run_all_with_stub_pipeline(tmp_path, monkeypatch, capsys):
    data = [{"id": "a1", "tender_id": "t1", "question": "q1", "expected_contains": ["2.5%"], "expected_pages": [3]},
            {"id": "b1", "tender_id": "t2", "question": "q2", "expected_contains": ["x"], "expected_pages": [5]}]
    p = tmp_path / "d.json"; p.write_text(json.dumps(data))
    import rag.pipeline as pl
    monkeypatch.setattr(pl, "run_rag_pipeline", lambda q, d, k: {
        "answer": "It is 2.5 % [1]" if d == "t1" else "I cannot find this", "sources": [{"page": 3}] if d == "t1" else [],
        "confidence": {"score": 0.8 if d == "t1" else 0.4}})
    monkeypatch.chdir(tmp_path); (tmp_path / "evaluation").mkdir()
    ev.main(["all", str(p), "--k", "6"])
    out = capsys.readouterr().out
    assert "COMBINED" in out and "answer accuracy           : 1/2" in out and "declined (cannot find)    : 1" in out


def test_generic_search_string_is_ignored(tmp_path, monkeypatch, capsys):
    pages = [{"page": i, "text": "CPWD contractors", "tables": []} for i in range(1, 9)]
    (PROCESSED_DIR / "gen1.json").write_text(json.dumps(pages))
    try:
        data = [{"id": "g1", "tender_id": "gen1", "question": "q", "expected_contains": ["CPWD"], "expected_pages": [3]}]
        p = tmp_path / "d.json"; p.write_text(json.dumps(data))
        import rag.pipeline as pl
        monkeypatch.setattr(pl, "run_rag_pipeline", lambda q, d, k: {"answer": "CPWD", "sources": [{"page": 3}], "confidence": {"score": 0.8}})
        monkeypatch.chdir(tmp_path); (tmp_path / "evaluation").mkdir()
        ev.main(["gen1", str(p), "--auto-pages"])
        out = capsys.readouterr().out
        assert "too generic" in out and "relevant: [3]" in out
    finally:
        (PROCESSED_DIR / "gen1.json").unlink()


@pytest.fixture(autouse=True)
def stub_retriever(monkeypatch):
    import vectorstore.retriever as r
    from types import SimpleNamespace
    monkeypatch.setattr(r, "retrieve", lambda q, d, k: [SimpleNamespace(page_content="x", metadata={"page": 3})])


def test_rank_summary_hit_and_mrr():
    rs = ev.rank_summary([1, 2, 0, 4, None], k=6)
    assert rs["n"] == 4 and rs["hit1"] == 0.25 and rs["hit3"] == 0.5 and rs["hitk"] == 0.75
    assert abs(rs["mrr"] - (1 + 0.5 + 0 + 0.25) / 4) < 1e-9
    assert ev.rank_summary([None, None], 6) is None
    assert ev.first_rank([False, False, True]) == 3 and ev.first_rank([False]) == 0


def test_retrieval_ranks_page_and_text_level(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace
    pages = [{"page": 3, "text": "Earnest money Rs. 65,939/-", "tables": []}, {"page": 9, "text": "other", "tables": []}]
    (PROCESSED_DIR / "rk1.json").write_text(json.dumps(pages))
    try:
        def D(page, text):
            return SimpleNamespace(page_content=text, metadata={"page": page})
        retrieved = {"q1": [D(9, "other"), D(3, "Earnest money Rs. 65,939/-")],     # relevant at rank 2
                     "q2": [D(9, "other")],                                        # miss
                     "q3": [D(3, "x")]}                                            # page hit, string not evaluable
        items = [{"question": "q1", "expected_contains": ["65,939"], "expected_pages": [3]},
                 {"question": "q2", "expected_contains": ["65,939"], "expected_pages": [3]},
                 {"question": "q3", "expected_contains": ["not in the document"], "expected_pages": [3]}]
        pipeline = lambda q, d, k: {"answer": "a", "sources": [], "confidence": {"score": 0.5}}
        rows = ev.run_tender("rk1", items, 6, False, pipeline, lambda q, d, k: retrieved[q])
        assert [r["retrieval_rank_page"] for r in rows] == [2, 0, 1]
        assert [r["retrieval_rank_text"] for r in rows] == [2, 0, None]
        ev.summarise("T", rows, 6)
        out = capsys.readouterr().out
        assert "retrieval page level (n=3): Hit@1 0.33  Hit@3 0.67  Hit@6 0.67  MRR@6 0.50" in out
        assert "retrieval text level (n=2): Hit@1 0.00  Hit@3 0.50  Hit@6 0.50  MRR@6 0.25" in out
    finally:
        (PROCESSED_DIR / "rk1.json").unlink()


def test_expected_any_and_context_metric(tmp_path, monkeypatch, capsys):
    item = {"expected_contains": ["65,939"], "expected_any": [["03 (three) month", "three months", "3 months"]]}
    assert ev.check_answer(item, "EMD Rs. 65,939 and the work takes 3 months") is True
    assert ev.check_answer(item, "EMD Rs. 65,939 only") is False
    assert ev.check_answer({"expected_any": []}, "x") is None
    from types import SimpleNamespace
    D = lambda text: SimpleNamespace(page_content=text, metadata={"page": 3})
    pages = [{"page": 3, "text": "Rs. 65,939 and 3 months", "tables": []}]
    (PROCESSED_DIR / "cx1.json").write_text(json.dumps(pages))
    try:
        items = [{"question": "q1", "expected_contains": ["65,939", "pune"], "expected_pages": [3]}]
        spread = [D("Earnest money Rs. 65,939"), D("Arbitration venue: Pune")]   # answer spread over two passages
        rows = ev.run_tender("cx1", items, 6, False, lambda q, d, k: {"answer": "a", "sources": [], "confidence": {"score": 0.5}},
                             lambda q, d, k: spread)
        assert rows[0]["context_has_answer"] is True and rows[0]["retrieval_rank_text"] is None  # no single passage holds both
        ev.summarise("T", rows, 6)
        assert "answer text in retrieved context: 1/1 = 100%" in capsys.readouterr().out
    finally:
        (PROCESSED_DIR / "cx1.json").unlink()
