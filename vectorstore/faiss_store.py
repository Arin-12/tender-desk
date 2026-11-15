import json
import shutil
import threading
from datetime import datetime

from langchain_community.vectorstores import FAISS

from config.settings import CACHE_DIR, PROCESSED_DIR, UPLOAD_DIR, VECTORSTORE_DIR

BATCH = 64
_cache = {}
_lock = threading.Lock()


def doc_dir(doc_id):
    return VECTORSTORE_DIR / doc_id


def document_exists(doc_id) -> bool:
    return (doc_dir(doc_id) / "index.faiss").exists()


def build_and_save_faiss(chunks, embeddings, doc_id, meta=None, progress=None):
    """Embed in batches (so progress can be reported), then swap the index in
    only once it is complete."""
    vs, total = None, len(chunks)
    for i in range(0, total, BATCH):
        batch = chunks[i:i + BATCH]
        if vs is None:
            vs = FAISS.from_documents(batch, embeddings)
        else:
            vs.add_documents(batch)
        if progress:
            progress(min(1.0, (i + len(batch)) / total))
    if vs is None:
        raise ValueError("No text could be extracted from this PDF.")

    target = doc_dir(doc_id)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    vs.save_local(str(target))
    info = {"doc_id": doc_id, "chunks": total,
            "ingested_at": datetime.now().isoformat(timespec="seconds"), **(meta or {})}
    (target / "meta.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return vs


def load_faiss_index(doc_id, embeddings):
    """Load one tender's index (cached until the index file changes)."""
    f = doc_dir(doc_id) / "index.faiss"
    if not f.exists():
        raise FileNotFoundError(f"Document '{doc_id}' is not indexed.")
    key = (doc_id, f.stat().st_mtime)
    with _lock:
        if key not in _cache:
            for old in [k for k in _cache if k[0] == doc_id]:
                del _cache[old]
            _cache[key] = FAISS.load_local(
                str(doc_dir(doc_id)), embeddings,
                allow_dangerous_deserialization=True,  # index is produced locally by this app
            )
        return _cache[key]


def list_documents():
    docs = []
    for p in VECTORSTORE_DIR.iterdir():
        if p.is_dir() and (p / "index.faiss").exists():
            meta_file = p / "meta.json"
            meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
            docs.append({"doc_id": p.name, "name": p.name, **meta})
    return sorted(docs, key=lambda d: d.get("ingested_at", ""), reverse=True)


def delete_document(doc_id):
    shutil.rmtree(doc_dir(doc_id), ignore_errors=True)
    shutil.rmtree(CACHE_DIR / doc_id, ignore_errors=True)
    (PROCESSED_DIR / f"{doc_id}.json").unlink(missing_ok=True)
    (UPLOAD_DIR / f"{doc_id}.pdf").unlink(missing_ok=True)
    with _lock:
        for old in [k for k in _cache if k[0] == doc_id]:
            del _cache[old]
