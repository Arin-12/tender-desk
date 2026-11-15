import json, re, sys
from config.settings import PROCESSED_DIR

doc_id, needles = sys.argv[1], sys.argv[2:]
norm = lambda s: re.sub(r"\s+", " ", s.lower().replace(",", ""))
pages = json.loads((PROCESSED_DIR / f"{doc_id}.json").read_text(encoding="utf-8"))
for n in needles:
    hits = [p["page"] for p in pages if norm(n) in norm(p["text"])]
    print(f"{n!r}: pages {hits}")