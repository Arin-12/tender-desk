import json, sys
import vectorstore.retriever as R
from config.settings import PROCESSED_DIR
from evaluation.eval_retrieval import Index, rank

doc_id, q = sys.argv[1], sys.argv[2]
pages = {int(p) for p in sys.argv[3].split(",")}
idx = Index.from_disk(doc_id)

ev = [d.metadata["chunk_id"] for d in rank(idx, "hybrid", q, 8, doc_id)]
pr = [d.metadata["chunk_id"] for d in R.retrieve(q, doc_id, 8)]
print("eval hybrid:", ev)
print("production :", pr)
print("same order :", ev == pr)

print("\nBM25 top 5:")
for d in rank(idx, "bm25", q, 5, doc_id):
    print(" p.%s  %s" % (d.metadata["page"], d.page_content[:110].replace("\n", " ")))

print("\nRelevant pages as indexed:")
data = json.loads((PROCESSED_DIR / f"{doc_id}.json").read_text(encoding="utf-8"))
for p in data:
    if p["page"] in pages:
        print(" p.%s  method=%s  chars=%s" % (p["page"], p["extraction_method"], len(p["text"])))
        print("   ", p["text"][:300].replace("\n", " "))