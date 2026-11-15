import json
import os
from pathlib import Path

import pdfplumber

from config.settings import PROCESSED_DIR
from ingestion.pdf_loader import iter_pdf_pages
from ingestion.table_extractor import extract_tables
from preprocessing.section_detector import detect_section
from preprocessing.text_cleaner import clean_text, find_repeated_lines, remove_repeated_lines

# A ruled table needs several lines or rectangles. Pages with fewer drawn elements are skipped,
# which avoids the slow pdfplumber pass on plain-text and scanned pages. Set to 0 to scan every page.
MIN_DRAWINGS = int(os.getenv("TABLE_MIN_DRAWINGS", "6"))


def process_document(pdf_path, doc_id, progress=None):
    """
    PDF -> cleaned pages with tables and section labels -> data/processed/<doc_id>.json
    `progress(fraction)` is called after every page.
    """
    pdf_path = Path(pdf_path)
    pages = []

    with pdfplumber.open(pdf_path) as plumber:
        for page in iter_pdf_pages(pdf_path):
            number = page["page"]
            tables = []
            if page["extraction_method"] == "PyMuPDF" and page["drawings"] >= MIN_DRAWINGS:
                plumber_page = plumber.pages[number - 1]
                tables = extract_tables(plumber_page, number)
                plumber_page.flush_cache()
            pages.append({**page, "tables": tables})
            if progress:
                progress(number / page["total"])

    repeated = find_repeated_lines([p["text"] for p in pages])

    section, subsection = "Unknown", "Unknown"
    for page in pages:
        text = clean_text(remove_repeated_lines(page["text"], repeated))
        found_section, found_sub = detect_section(text)
        if found_section:
            section = found_section
            subsection = "Unknown"
        if found_sub:
            subsection = found_sub
        page["text"] = text
        page["section"] = section
        page["subsection"] = subsection
        page["doc_id"] = doc_id
        page.pop("total", None)
        page.pop("drawings", None)

    out_path = PROCESSED_DIR / f"{doc_id}.json"
    out_path.write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")

    return {
        "path": out_path,
        "pages": len(pages),
        "tables": sum(len(p["tables"]) for p in pages),
        "ocr_pages": sum(1 for p in pages if p["extraction_method"] == "OCR"),
    }
