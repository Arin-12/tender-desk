"""
Hybrid retrieval over ONE tender: dense (BGE cosine) + keyword (BM25), merged
with reciprocal-rank fusion. Every returned chunk carries its cosine
`similarity`, which feeds the confidence score.
"""
import re
import threading

import numpy as np
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from embeddings.embedder import BGE_QUERY_PREFIX, get_bge_embeddings
from vectorstore.faiss_store import doc_dir, load_faiss_index

POOL = 30      # candidates taken from each ranker
RRF_K = 60

_indexes = {}
_lock = threading.Lock()


TABLE_TRIGGERS = {"boq", "quantities", "quantity", "schedule", "bill"}
STOP = set("a an the of to in on for and or is are was be by with what which who how when where does do did "
           "this that these those it its as at from any all must should shall may can will required "
           "requirement exact specific stipulated mentioned".split())

def _qtok(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


def _tok(text):
    return re.findall(r"[a-z0-9]+", text.lower())

def _numbers(text):
    return set(re.findall(r"\d+(?:\.\d+)?", text))


class DocIndex:
    def __init__(self, vs):
        n = vs.index.ntotal
        self.docs = [vs.docstore.search(vs.index_to_docstore_id[i]) for i in range(n)]
        matrix = np.array(vs.index.reconstruct_n(0, n), dtype="float32")
        self.matrix = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
        self.bm25 = BM25Okapi([_qtok(d.page_content) or ["_"] for d in self.docs])

    def _with_sim(self, i, sims):
        d = self.docs[i]
        return Document(page_content=d.page_content,
                        metadata={**d.metadata, "similarity": round(float(sims[i]), 4)})

    def hybrid(self, query, k):
        qv = np.array(
            get_bge_embeddings().embed_query(BGE_QUERY_PREFIX + query),
            dtype="float32"
        )
        qv /= (np.linalg.norm(qv) + 1e-9)

        sims = self.matrix @ qv
        bm = self.bm25.get_scores(_qtok(query))

        fused = {}

        # Dense ranking
        dense_ranks = np.argsort(-sims)[:POOL]

        for rank, i in enumerate(dense_ranks):
            i = int(i)
            fused[i] = fused.get(i, 0) + 1 / (RRF_K + rank + 1)

        # BM25 ranking
        bm25_ranks = np.argsort(-bm)[:POOL]

        for rank, i in enumerate(bm25_ranks):
            i = int(i)

            if bm[i] > 0:
                fused[i] = fused.get(i, 0) + 1 / (RRF_K + rank + 1)

        # # Exact-number boost
        # query_numbers = _numbers(query)

        # if query_numbers:
        #     for i in fused:
        #         doc_numbers = _numbers(self.docs[i].page_content)
        #         matched = query_numbers.intersection(doc_numbers)

        #         if matched:
        #             fused[i] += 0.005 * len(matched)

        # Final ranking
        top = sorted(
            fused,
            key=fused.get,
            reverse=True
        )[:k]

        results = []

        for i in top:
            d = self.docs[i]

            results.append(
                Document(
                    page_content=d.page_content,
                    metadata={
                        **d.metadata,
                        "similarity": round(float(sims[i]), 4),
                        "bm25_score": round(float(bm[i]), 2),
                        "rrf_score": round(float(fused[i]), 6),
                    }
                )
            )

        return results

    def keyword(self, query, k):
        bm = self.bm25.get_scores(_qtok(query))
        sims = np.zeros(len(self.docs))
        out = []
        for i in np.argsort(-bm)[:k]:
            if bm[i] <= 0:
                break
            doc = self._with_sim(int(i), sims)
            doc.metadata["keyword_score"] = round(float(bm[i]), 2)
            out.append(doc)
        return out


def _get_index(doc_id) -> DocIndex:
    f = doc_dir(doc_id) / "index.faiss"
    if not f.exists():
        raise FileNotFoundError(f"Document '{doc_id}' is not indexed.")
    key = (doc_id, f.stat().st_mtime)
    with _lock:
        if key not in _indexes:
            for old in [k for k in _indexes if k[0] == doc_id]:
                del _indexes[old]
            _indexes[key] = DocIndex(load_faiss_index(doc_id, get_bge_embeddings()))
        return _indexes[key]


def retrieve(query, doc_id, k=6):
    return _get_index(doc_id).hybrid(query, k)


def keyword_search(query, doc_id, k=10):
    return _get_index(doc_id).keyword(query, k)


def retrieve_multi(queries, doc_id, k_each=2, max_total=16):
    """One sub-query per field, merged round-robin and de-duplicated.
    Beats a single blurry multi-topic query."""
    index = _get_index(doc_id)
    lists = [index.hybrid(q, k_each) for q in queries]
    seen, out = set(), []
    for rank in range(k_each):
        for results in lists:
            if rank < len(results):
                doc = results[rank]
                cid = doc.metadata["chunk_id"]
                if cid not in seen:
                    seen.add(cid)
                    out.append(doc)
                    if len(out) >= max_total:
                        return out
    return out
