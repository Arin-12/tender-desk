"""
Evaluation harness for the report.
Usage:  python -m evaluation.eval_qa <doc_id> evaluation/eval_set.json [--k 6]
Each item: {"question": "...", "expected_contains": ["2.90"], "expected_pages": [3]}
Reports answer accuracy (all expected strings present), citation accuracy (a cited
page is in expected_pages) and mean confidence. Run it with different CHUNK_SIZE /
TOP_K values for your ablation table.
"""
import csv
import json
import sys
from pathlib import Path

from rag.pipeline import run_rag_pipeline


def _norm(s):
    return s.lower().replace(",", "")


def main():
    doc_id, path = sys.argv[1], Path(sys.argv[2])
    k = int(sys.argv[sys.argv.index("--k") + 1]) if "--k" in sys.argv else 6
    items = json.loads(path.read_text(encoding="utf-8"))

    rows, correct, cited_ok, with_pages = [], 0, 0, 0
    for item in items:
        res = run_rag_pipeline(item["question"], doc_id, k)
        answer = _norm(res["answer"])
        ok = all(_norm(x) in answer for x in item.get("expected_contains", []))
        pages = {s["page"] for s in res["sources"]}
        exp = set(item.get("relevant_pages") or item.get("expected_pages", []))
        cite = bool(pages & exp) if exp else None
        correct += ok
        if exp:
            with_pages += 1
            cited_ok += bool(cite)
        rows.append({"question": item["question"], "answer_correct": ok, "citation_correct": cite,
                     "confidence": res["confidence"]["score"], "answer": res["answer"][:300]})
        print(f"{'PASS' if ok else 'FAIL'}  {item['question']}")

    n = len(items)
    print(f"\nAnswer accuracy   : {correct}/{n} = {correct / n:.0%}")
    if with_pages:
        print(f"Citation accuracy : {cited_ok}/{with_pages} = {cited_ok / with_pages:.0%}")
    print(f"Mean confidence   : {sum(r['confidence'] for r in rows) / n:.2f}")

    out = Path("evaluation") / f"results_{doc_id}_k{k}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
