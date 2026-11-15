"""
QA evaluation, v3. Same dataset format as v2.

    python -m evaluation.eval_qa_v3 final_nit_fmtti evaluation/eval_set_2tenders_30q.json --k 6
    python -m evaluation.eval_qa_v3 all evaluation/eval_set_2tenders_30q.json --k 6 --auto-pages

What changed compared with v2
  * Answer check ignores formatting: "2.5 %" matches "2.5%", "defect-liability" (any Unicode hyphen) matches
    "defect liability", markdown and commas are ignored. v2 marked answers wrong on such differences.
  * Citation HIT: at least one cited page is a relevant page. This is the right question when a fact is repeated
    on several pages. Citation precision and strict citation are kept; the old "citation recall" is renamed
    "evidence coverage" because answering needs one good page, not all of them.
  * --auto-pages: relevant pages = listed pages + every page whose text contains ALL expected_contains strings,
    so the labels are built by exhaustive text search. The added pages are printed: check them in the PDF.
  * "all" runs every tender in the dataset and prints a combined summary.
  * manual_grade column: fill in Correct / Partly / Wrong yourself after reading each answer.
  * Extra pages from --auto-pages are ignored for a question when more than 5 match (string too generic).
  * Retrieval metrics on the passages the retriever returns: Hit@1, Hit@3, Hit@k and MRR@k, at page level
    (a retrieved passage lies on a relevant page) and text level (it contains all expected_contains strings;
    not evaluable when no passage in the document contains them). In the CSV, rank 0 = no relevant passage in the top k.
  * answer-in-context: do ALL expected strings appear somewhere in the retrieved passages? (answers spread over
    several passages are not misses). expected_any: [[alt1, alt2], ...] accepts alternative wordings.
  * Mean confidence is shown separately for answers marked correct and incorrect.
Answer correctness is still text matching. Read the failures and a sample of passes yourself.
"""
import argparse
import csv
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from config.settings import PROCESSED_DIR


MAX_AUTO_PAGES = 5  # more extra pages than this means the search string is too generic to trust


def compact(value):
    """Lower-case, Unicode-normalised, only letters, digits, '.' and '%': formatting differences vanish."""
    text = unicodedata.normalize("NFKC", str(value)).lower()
    return re.sub(r"[^a-z0-9.%]", "", text)


def has_all(item, text):
    """text must be compact(...). Needs every expected_contains string and, for each group in
    expected_any, at least one alternative (e.g. [["03 (three) month", "three months"]]). None = nothing to check."""
    keys = [compact(v) for v in item.get("expected_contains", []) if compact(v)]
    groups = [[compact(a) for a in g if compact(a)] for g in item.get("expected_any", [])]
    groups = [g for g in groups if g]
    if not keys and not groups:
        return None
    return all(k in text for k in keys) and all(any(a in text for a in g) for g in groups)


def check_answer(item, answer):
    return has_all(item, compact(answer))


def to_pages(values):
    out = set()
    for v in values or []:
        try:
            out.add(int(v))
        except (TypeError, ValueError):
            pass
    return out


def citation_metrics(relevant, cited):
    if not relevant:
        return None
    if not cited:
        return {"hit": False, "precision": 0.0, "strict": False, "coverage": 0.0}
    both = relevant & cited
    return {"hit": bool(both), "precision": len(both) / len(cited),
            "strict": cited <= relevant, "coverage": len(both) / len(relevant)}


def pages_containing(doc_id, needles):
    """Pages (text and tables) that contain every needle. Empty if there is nothing to search for."""
    keys = [compact(n) for n in needles if compact(n)]
    path = PROCESSED_DIR / f"{doc_id}.json"
    if not keys or not path.exists():
        return set()
    found = set()
    for page in json.loads(path.read_text(encoding="utf-8")):
        table_text = " ".join(" ".join(row) for t in page.get("tables", []) for row in t.get("rows", []))
        haystack = compact(page.get("text", "") + " " + table_text)
        if all(k in haystack for k in keys):
            found.add(page["page"])
    return found


def first_rank(flags):
    """1-based rank of the first True, or 0 when there is none."""
    return next((i + 1 for i, f in enumerate(flags) if f), 0)


def rank_summary(ranks, k):
    """ranks: 1.. = rank of first relevant passage, 0 = none in the top k, None = not evaluable."""
    ev = [r for r in ranks if r is not None]
    if not ev:
        return None
    return {"n": len(ev), "hit1": mean([int(0 < r <= 1) for r in ev]), "hit3": mean([int(0 < r <= 3) for r in ev]),
            "hitk": mean([int(r > 0) for r in ev]), "mrr": mean([1 / r if r > 0 else 0 for r in ev]), "k": k}


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def fmt(x, pct=False):
    if x is None:
        return "n/a"
    return f"{x:.0%}" if pct else f"{x:.2f}"


def run_tender(doc_id, items, k, auto_pages, run_pipeline, retrieve_fn=None):
    rows = []
    for index, item in enumerate(items, start=1):
        question = item["question"]
        print(f"\n[{doc_id} {index}/{len(items)}] {question}")
        try:
            result = run_pipeline(question, doc_id, k)
            answer = result.get("answer", "")
            correct = check_answer(item, answer)
            cited = to_pages(s.get("page") for s in result.get("sources", []))
            listed = to_pages(item.get("relevant_pages") or item.get("expected_pages"))
            added = pages_containing(doc_id, item.get("expected_contains", [])) - listed if auto_pages else set()
            if len(added) > MAX_AUTO_PAGES:
                print(f"  WARNING: text search matched {len(added)} extra pages {sorted(added)}: expected_contains is too "
                      f"generic for this question, so the extra pages are ignored. List relevant_pages by hand.")
                added = set()
            relevant = listed | added
            cm = citation_metrics(relevant, cited)
            rank_page = rank_text = context_has = None
            if retrieve_fn is not None:
                retrieved = retrieve_fn(question, doc_id, k)
                context_has = has_all(item, compact(" ".join(d.page_content for d in retrieved)))
                if relevant:
                    rank_page = first_rank([d.metadata.get("page") in relevant for d in retrieved])
                keys = [compact(v) for v in item.get("expected_contains", []) if compact(v)]
                if keys and pages_containing(doc_id, item.get("expected_contains", [])):
                    rank_text = first_rank([all(x in compact(d.page_content) for x in keys) for d in retrieved])
            conf = result.get("confidence", {})
            conf = conf.get("score") if isinstance(conf, dict) else conf
            declined = "cannot find" in answer.lower()
            rows.append({
                "id": item.get("id", ""), "tender_id": doc_id, "question": question,
                "question_type": item.get("question_type", ""), "answer_correct": correct, "declined": declined,
                "citation_hit": cm and cm["hit"], "citation_precision": cm and cm["precision"],
                "strict_citation": cm and cm["strict"], "evidence_coverage": cm and cm["coverage"],
                "relevant_pages": ",".join(map(str, sorted(relevant))), "pages_added_by_search": ",".join(map(str, sorted(added))),
                "cited_pages": ",".join(map(str, sorted(cited))), "retrieval_rank_page": rank_page, "retrieval_rank_text": rank_text, "context_has_answer": context_has, "confidence": conf, "manual_grade": "", "answer": answer[:600]})
            print(f"  answer correct : {correct}{'   (declined to answer)' if declined else ''}")
            print(f"  cited / relevant: {sorted(cited)} / {sorted(relevant)}" + (f"   (+{sorted(added)} from text search)" if added else ""))
            if retrieve_fn is not None:
                print(f"  answer text present in the retrieved passages: {context_has}")
                print(f"  retrieval: first relevant passage at rank {rank_page if rank_page else 'none'} (page level), "
                      f"{rank_text if rank_text else ('none' if rank_text == 0 else 'not evaluable')} (text level)")
            if cm:
                print(f"  citation hit {cm['hit']}, precision {cm['precision']:.2f}, strict {cm['strict']}")
        except Exception as error:
            print(f"  ERROR: {error}")
            rows.append({"tender_id": doc_id, "question": question, "error": str(error)})
    return rows


def summarise(label, rows, k=6):
    ok = [r for r in rows if "error" not in r]
    ans = [r for r in ok if r["answer_correct"] is not None]
    cit = [r for r in ok if r.get("citation_hit") is not None]
    good = [r["confidence"] for r in ans if r["answer_correct"]]
    bad = [r["confidence"] for r in ans if not r["answer_correct"]]
    print(f"\n{label}")
    print(f"  questions answered        : {len(ok)} of {len(rows)}")
    print(f"  answer accuracy           : {sum(r['answer_correct'] for r in ans)}/{len(ans)} = {fmt(mean([int(r['answer_correct']) for r in ans]), True)}")
    print(f"  declined (cannot find)    : {sum(r['declined'] for r in ok)}")
    print(f"  citation hit              : {sum(bool(r['citation_hit']) for r in cit)}/{len(cit)} = {fmt(mean([int(bool(r['citation_hit'])) for r in cit]), True)}")
    print(f"  citation precision        : {fmt(mean([r['citation_precision'] for r in cit]))}")
    print(f"  strict citation           : {fmt(mean([int(bool(r['strict_citation'])) for r in cit]), True)}")
    print(f"  evidence coverage         : {fmt(mean([r['evidence_coverage'] for r in cit]))}")
    ctx = [r["context_has_answer"] for r in ok if r.get("context_has_answer") is not None]
    if ctx:
        print(f"  answer text in retrieved context: {sum(ctx)}/{len(ctx)} = {sum(ctx) / len(ctx):.0%}"
              f"   (retrieval could answer; misses here are retrieval failures)")
    for name, key in (("page level", "retrieval_rank_page"), ("text level", "retrieval_rank_text")):
        rs = rank_summary([r.get(key) for r in ok], k)
        if rs:
            print(f"  retrieval {name} (n={rs['n']}): Hit@1 {rs['hit1']:.2f}  Hit@3 {rs['hit3']:.2f}  "
                  f"Hit@{k} {rs['hitk']:.2f}  MRR@{k} {rs['mrr']:.2f}")
    print(f"  mean confidence           : {fmt(mean([r['confidence'] for r in ok]))}"
          f"   (correct answers {fmt(mean(good))}, incorrect {fmt(mean(bad))})")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("doc_id", help="document id, or 'all' for every tender_id in the dataset")
    ap.add_argument("dataset")
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--auto-pages", action="store_true", help="add pages found by text search to the relevant pages")
    args = ap.parse_args(argv)

    from rag.pipeline import run_rag_pipeline
    from rag.query_expansion import expand_query
    from vectorstore.retriever import retrieve
    retrieve_fn = lambda q, d, kk: retrieve(expand_query(q), d, kk)  # exactly what the pipeline retrieves
    items = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    by_tender = {}
    for item in items:
        by_tender.setdefault(item.get("tender_id", args.doc_id), []).append(item)
    targets = list(by_tender) if args.doc_id == "all" else [args.doc_id]
    if any(t not in by_tender for t in targets):
        raise SystemExit(f"No questions for: {[t for t in targets if t not in by_tender]}. Dataset has: {list(by_tender)}")

    all_rows = []
    for doc_id in targets:
        rows = run_tender(doc_id, by_tender[doc_id], args.k, args.auto_pages, run_rag_pipeline, retrieve_fn)
        all_rows += rows
        print("\n" + "=" * 60)
        summarise(f"SUMMARY  {doc_id}", rows, args.k)
    if len(targets) > 1:
        print("\n" + "=" * 60)
        summarise("COMBINED", all_rows, args.k)

    out = Path("evaluation") / f"results_v3_{'all' if len(targets) > 1 else targets[0]}_k{args.k}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    fields = list(dict.fromkeys(key for r in all_rows for key in r))
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
