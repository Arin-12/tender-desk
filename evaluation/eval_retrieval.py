"""
Retrieval evaluation for the report: Hit@k, Precision@k, Recall@k and MRR.

    python -m evaluation.eval_retrieval <doc_id> evaluation/eval_set.json
    python -m evaluation.eval_retrieval <doc_id> evaluation/eval_set.json --ks 1,3,5,8 --level page
    python -m evaluation.eval_retrieval <doc_id> evaluation/eval_set.json --chunk-sizes 500,800,1200

Eval set item (all keys except "question" are optional, pick what you need):
  {"question": "...",
   "relevant_pages": [3, 28],          # PDF page numbers (same as the p.N chips) that contain the answer
   "relevant_contains": ["65,939"]}    # text that a relevant passage must contain (for --level chunk)
(`expected_pages` from eval_qa.py is accepted as a synonym for `relevant_pages`.)

Relevance levels
  page   a retrieved passage is relevant if it is on one of the relevant pages.
         Recall@k = share of the relevant pages that appear in the top k.
  chunk  a retrieved passage is relevant if it contains one of `relevant_contains`.
         Recall@k = relevant passages retrieved / all relevant passages in the document.

Metrics at cutoff k (averaged over questions)
  Hit@k        1 if at least one relevant passage is in the top k
  Precision@k  relevant passages in the top k / k
  Recall@k     see above
  MRR@k        1 / rank of the first relevant passage (0 if none in the top k)

Modes: dense (BGE only), bm25 (keywords only), hybrid (the RRF fusion), production
(the app's real retrieve() function, default chunk size only).
"""
import argparse
import csv
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

import vectorstore.retriever as R
from chunking.chunker import chunk_processed_document
from config.settings import CHUNK_OVERLAP, CHUNK_SIZE
from embeddings.embedder import BGE_QUERY_PREFIX, get_bge_embeddings

QUERY_TOK = getattr(R, "_qtok", R._tok)  # picks up the stop-word tokenizer if you added it


def norm(text):
    return re.sub(r"\s+", " ", text.lower().replace(",", "")).strip()


class Index:
    """In-memory passages + embeddings + BM25, so chunk sizes can be compared without touching disk."""

    def __init__(self, docs, matrix):
        self.docs = docs
        m = np.array(matrix, dtype="float32")
        self.matrix = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)
        self.bm25 = BM25Okapi([R._tok(d.page_content) or ["_"] for d in docs])

    @classmethod
    def from_disk(cls, doc_id):
        disk = R._get_index(doc_id)
        obj = cls.__new__(cls)
        obj.docs, obj.matrix, obj.bm25 = disk.docs, disk.matrix, disk.bm25
        return obj

    @classmethod
    def build(cls, doc_id, size, overlap):
        docs = chunk_processed_document(doc_id, size, overlap)
        print(f"  embedding {len(docs)} passages at chunk size {size} ...")
        vecs = get_bge_embeddings().embed_documents([d.page_content for d in docs])
        return cls(docs, vecs)


_qcache = {}


def qvec(query):
    if query not in _qcache:
        v = np.array(get_bge_embeddings().embed_query(BGE_QUERY_PREFIX + query), dtype="float32")
        _qcache[query] = v / (np.linalg.norm(v) + 1e-9)
    return _qcache[query]


def rank(index, mode, query, kmax, doc_id):
    if mode == "production":
        return R.retrieve(query, doc_id, kmax)
    sims = index.matrix @ qvec(query)
    if mode == "dense":
        return [index.docs[i] for i in np.argsort(-sims)[:kmax]]
    bm = index.bm25.get_scores(QUERY_TOK(query))
    if mode == "bm25":
        return [index.docs[i] for i in np.argsort(-bm)[:kmax] if bm[i] > 0]
    fused = {}
    for r, i in enumerate(np.argsort(-sims)[:R.POOL]):
        fused[int(i)] = fused.get(int(i), 0) + 1 / (R.RRF_K + r + 1)
    for r, i in enumerate(np.argsort(-bm)[:R.POOL]):
        if bm[i] > 0:
            fused[int(i)] = fused.get(int(i), 0) + 1 / (R.RRF_K + r + 1)
    return [index.docs[i] for i in sorted(fused, key=fused.get, reverse=True)[:kmax]]


def relevance_fn(item, level):
    pages = set(item.get("relevant_pages") or item.get("expected_pages") or [])
    needles = [norm(x) for x in item.get("relevant_contains", [])]
    if level == "page":
        return (lambda d: d.metadata.get("page") in pages), pages
    return (lambda d: any(n in norm(d.page_content) for n in needles)), pages


def score(ranked, rel, k, level, pages, total_rel):
    top = ranked[:k]
    flags = [bool(rel(d)) for d in top]
    precision = sum(flags) / k
    if level == "page":
        hit_pages = {d.metadata.get("page") for d, f in zip(top, flags) if f}
        recall = len(hit_pages) / len(pages)
    else:
        recall = sum(flags) / total_rel
    rr = next((1 / (i + 1) for i, f in enumerate(flags) if f), 0.0)
    return {"hit": float(any(flags)), "precision": precision, "recall": recall, "mrr": rr}


def load_items(path, level, index):
    items, skipped = [], []
    for it in __import__("json").loads(Path(path).read_text(encoding="utf-8")):
        rel, pages = relevance_fn(it, level)
        if level == "page" and not pages:
            skipped.append((it["question"], "no relevant_pages"))
            continue
        if level == "chunk" and not it.get("relevant_contains"):
            skipped.append((it["question"], "no relevant_contains"))
            continue
        total = sum(1 for d in index.docs if rel(d))
        if total == 0:
            skipped.append((it["question"], "ground truth not found in the indexed text (wrong page/string, or OCR misread it)"))
            continue
        items.append({"q": it["question"], "rel": rel, "pages": pages, "total": total})
    return items, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("doc_id")
    ap.add_argument("eval_set")
    ap.add_argument("--ks", default="1,3,5,8")
    ap.add_argument("--level", choices=["page", "chunk"], default="page")
    ap.add_argument("--modes", default="dense,bm25,hybrid,production")
    ap.add_argument("--chunk-sizes", default="", help="comma list, e.g. 500,800,1200 (default: your CHUNK_SIZE)")
    ap.add_argument("--overlap", type=int, default=CHUNK_OVERLAP)
    args = ap.parse_args()

    ks = sorted({int(x) for x in args.ks.split(",")})
    kmax = max(ks)
    modes = [m.strip() for m in args.modes.split(",")]
    sizes = [int(x) for x in args.chunk_sizes.split(",") if x.strip()] or [CHUNK_SIZE]

    summary_rows, question_rows, md = [], [], []
    for size in sizes:
        default_cfg = size == CHUNK_SIZE and args.overlap == CHUNK_OVERLAP
        print(f"\n=== chunk size {size}, overlap {args.overlap} {'(index on disk)' if default_cfg else ''}")
        index = Index.from_disk(args.doc_id) if default_cfg else Index.build(args.doc_id, size, args.overlap)
        items, skipped = load_items(args.eval_set, args.level, index)
        for q, why in skipped:
            print(f"  SKIPPED: {q[:70]}  ({why})")
        if not items:
            print("  No usable questions.")
            continue

        title = f"Chunk size {size}, overlap {args.overlap}, relevance level '{args.level}', n = {len(items)} questions"
        md += [f"### {title}", "", "| Mode | k | Hit@k | Precision@k | Recall@k | MRR@k |", "|---|---|---|---|---|---|"]
        print(f"  {title}\n")
        print(f"  {'mode':<11}{'k':>3}{'Hit@k':>8}{'Prec@k':>9}{'Recall@k':>10}{'MRR@k':>8}")

        for mode in modes:
            if mode == "production" and not default_cfg:
                continue
            results = {k: [] for k in ks}
            for it in items:
                ranked = rank(index, mode, it["q"], kmax, args.doc_id)
                for k in ks:
                    results[k].append(score(ranked, it["rel"], k, args.level, it["pages"], it["total"]))
                first = next((i + 1 for i, d in enumerate(ranked) if it["rel"](d)), "")
                question_rows.append({"chunk_size": size, "mode": mode, "question": it["q"], "first_relevant_rank": first})
            for k in ks:
                avg = {m: float(np.mean([r[m] for r in results[k]])) for m in ("hit", "precision", "recall", "mrr")}
                summary_rows.append({"chunk_size": size, "overlap": args.overlap, "level": args.level, "mode": mode,
                                     "k": k, "n": len(items), **{m: round(v, 4) for m, v in avg.items()}})
                print(f"  {mode:<11}{k:>3}{avg['hit']:>8.2f}{avg['precision']:>9.2f}{avg['recall']:>10.2f}{avg['mrr']:>8.2f}")
                md.append(f"| {mode} | {k} | {avg['hit']:.2f} | {avg['precision']:.2f} | {avg['recall']:.2f} | {avg['mrr']:.2f} |")
            print()
        md.append("")

        # Questions that retrieval missed entirely (best place to look for improvements)
        best = "hybrid" if "hybrid" in modes else modes[0]
        missed = [r["question"] for r in question_rows
                  if r["chunk_size"] == size and r["mode"] == best and r["first_relevant_rank"] == ""]
        if missed:
            print(f"  Missed by '{best}' within top {kmax}:")
            for q in missed:
                print(f"    - {q}")

    if not summary_rows:
        return
    out = Path("evaluation")
    stem = f"retrieval_{args.doc_id}_{args.level}"
    with open(out / f"{stem}_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        w.writeheader()
        w.writerows(summary_rows)
    with open(out / f"{stem}_per_question.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=question_rows[0].keys())
        w.writeheader()
        w.writerows(question_rows)
    (out / f"{stem}_tables.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nSaved to evaluation/: {stem}_summary.csv, {stem}_per_question.csv, {stem}_tables.md")


if __name__ == "__main__":
    main()
