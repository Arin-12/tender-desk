import re
from pathlib import Path

from chunking.chunker import chunk_processed_document
from embeddings.embedder import get_bge_embeddings
from ingestion.document_processor import process_document
from intelligence.cache import clear_cache
from vectorstore.faiss_store import build_and_save_faiss


def make_doc_id(filename: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", Path(filename).stem).strip("_").lower()
    return stem[:60] or "tender"


def ingest_pdf(pdf_path, doc_id, original_name=None, progress=None):
    """
    Full pipeline for ONE tender: process -> chunk -> embed -> index, then warm the analysis cache
    in the background so the Analysis tabs open instantly.
    progress(percent:int, message:str) is called throughout.
    """
    report = progress or (lambda pct, msg: None)

    report(2, "Reading pages")
    stats = process_document(
        pdf_path, doc_id,
        progress=lambda f: report(2 + int(f * 48), "Reading pages and tables"),
    )

    report(52, "Splitting into passages")
    chunks = chunk_processed_document(doc_id)

    report(55, "Embedding passages")
    meta = {
        "name": original_name or Path(pdf_path).name,
        "pages": stats["pages"],
        "tables": stats["tables"],
        "ocr_pages": stats["ocr_pages"],
    }
    build_and_save_faiss(
        chunks, get_bge_embeddings(), doc_id, meta=meta,
        progress=lambda f: report(55 + int(f * 44), "Embedding passages"),
    )
    clear_cache(doc_id)  # stale analyses must not outlive a re-upload
    report(100, "Ready")

    try:
        from intelligence.extractor import warm
        warm(doc_id)
    except Exception as error:  # never let warm-up break an upload
        print(f"[Warm-up] skipped: {error}")
    return doc_id
