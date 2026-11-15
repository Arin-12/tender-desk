import collections
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

from config.settings import OCR_ENABLED, OCR_TEXT_THRESHOLD

OCR_WORKERS = int(os.getenv("OCR_WORKERS", str(max(1, min(4, (os.cpu_count() or 2) - 1)))))


def _drawing_count(page):
    """Number of vector lines/rectangles on the page. A ruled table needs several."""
    try:
        return len(page.get_drawings())
    except Exception:
        return 10 ** 6  # unknown: let the table extractor decide


def iter_pdf_pages(pdf_path):
    """
    Yield one dict per page, in order.
    Native text first. Pages with (almost) no text layer are OCR'd in a small thread pool
    (Tesseract runs as a separate process, so threads give real parallelism). Rendering
    stays on the main thread and at most 2 x workers pages are in flight, so memory stays bounded.
    """
    from ingestion.ocr import OCRUnavailable, ocr_image, render_page

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = pymupdf.open(pdf_path)
    pool = ThreadPoolExecutor(max_workers=OCR_WORKERS) if OCR_ENABLED else None
    window = OCR_WORKERS * 2
    pending = collections.deque()

    def finish(info, future):
        if future is not None:
            try:
                text = future.result()
                if len(text) > len(info["text"]):
                    info["text"], info["extraction_method"] = text, "OCR"
            except OCRUnavailable:
                raise
            except Exception as error:
                print(f"[OCR] page {info['page']} failed: {error}")
        return info

    try:
        total = len(doc)
        for number, page in enumerate(doc, start=1):
            try:
                text = page.get_text("text").strip()
            except Exception:
                text = ""
            info = {"text": text, "page": number, "total": total, "document": pdf_path.name,
                    "extraction_method": "PyMuPDF", "drawings": _drawing_count(page)}
            future = None
            if pool is not None and len(text) < OCR_TEXT_THRESHOLD:
                try:
                    future = pool.submit(ocr_image, render_page(page))
                except Exception as error:
                    print(f"[OCR] page {number} could not be rendered: {error}")
            pending.append((info, future))
            while len(pending) >= window:
                yield finish(*pending.popleft())
        while pending:
            yield finish(*pending.popleft())
    finally:
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
        doc.close()
