import os

# Tesseract can start several threads per process. With parallel OCR that oversubscribes the CPU.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

import pymupdf
import pytesseract
from PIL import Image
from pytesseract import TesseractNotFoundError

from config.settings import OCR_LANGUAGE, TESSERACT_CMD

OCR_DPI = int(os.getenv("OCR_DPI", "300"))  # 200 is about twice as fast, slightly less accurate on small print

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


class OCRUnavailable(RuntimeError):
    """Tesseract is not installed / not found."""


def render_page(page):
    """Render a PyMuPDF page to a greyscale image (3x less memory than RGB; Tesseract uses grey anyway)."""
    pix = page.get_pixmap(dpi=OCR_DPI, colorspace=pymupdf.csGRAY, alpha=False)
    return Image.frombytes("L", [pix.width, pix.height], pix.samples)


def ocr_image(image) -> str:
    try:
        return pytesseract.image_to_string(image, lang=OCR_LANGUAGE, config="--psm 6").strip()
    except TesseractNotFoundError as error:
        raise OCRUnavailable(
            "This PDF has scanned pages and needs Tesseract OCR, which was not found. "
            "Install it and set TESSERACT_CMD in .env."
        ) from error


def ocr_page(page) -> str:  # kept for backward compatibility
    return ocr_image(render_page(page))
