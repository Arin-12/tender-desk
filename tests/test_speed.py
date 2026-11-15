import threading
import time
from types import SimpleNamespace

import pymupdf
import pytest

import ingestion.pdf_loader as loader
import intelligence.extractor as ex
from intelligence.cache import clear_cache


def make_pdf(path):
    doc = pymupdf.open()
    p1 = doc.new_page(); p1.insert_text((72, 72), "Plain text page with plenty of characters to skip OCR.")
    p2 = doc.new_page(); p2.insert_text((72, 60), "Table page text that is long enough to count.")
    for i in range(4):
        p2.draw_line((72, 100 + i * 30), (372, 100 + i * 30))
        p2.draw_line((72 + i * 100, 100), (72 + i * 100, 190))
    scan_src = pymupdf.open(); sp = scan_src.new_page(); sp.insert_text((72, 100), "Scanned words here")
    pix = sp.get_pixmap(dpi=60)
    for _ in range(6):                      # six image-only pages
        pg = doc.new_page(); pg.insert_image(pg.rect, pixmap=pix)
    doc.save(path)


def test_loader_order_methods_and_parallel_ocr(tmp_path, monkeypatch):
    pdf = tmp_path / "t.pdf"; make_pdf(pdf)
    calls = []

    def fake_ocr(image):
        calls.append(threading.get_ident()); time.sleep(0.3); return "OCR TEXT"
    import ingestion.ocr as ocr
    monkeypatch.setattr(ocr, "ocr_image", fake_ocr)
    monkeypatch.setattr(loader, "OCR_WORKERS", 3)
    monkeypatch.setattr(loader, "OCR_ENABLED", True)

    start = time.time()
    pages = list(loader.iter_pdf_pages(pdf))
    elapsed = time.time() - start

    assert [p["page"] for p in pages] == list(range(1, 9))           # order preserved
    assert [p["extraction_method"] for p in pages] == ["PyMuPDF"] * 2 + ["OCR"] * 6
    assert pages[1]["drawings"] >= 6 and pages[0]["drawings"] < 6      # table page detectable
    assert len(set(calls)) > 1                                         # several worker threads
    assert elapsed < 6 * 0.3 * 0.8                                     # faster than sequential (1.8 s)


def test_missing_tesseract_fails_fast(tmp_path, monkeypatch):
    pdf = tmp_path / "t.pdf"; make_pdf(pdf)
    import ingestion.ocr as ocr

    def boom(image):
        raise ocr.OCRUnavailable("no tesseract")
    monkeypatch.setattr(ocr, "ocr_image", boom)
    with pytest.raises(ocr.OCRUnavailable):
        list(loader.iter_pdf_pages(pdf))


@pytest.fixture
def stub_llm(monkeypatch):
    state = SimpleNamespace(calls=0)
    doc = SimpleNamespace(page_content="x", metadata={"chunk_id": "c1", "page": 3, "section": "S", "similarity": 0.8})
    monkeypatch.setattr(ex, "retrieve_multi", lambda *a, **k: [doc])

    def fake_invoke_json(messages, model=None):
        state.calls += 1; time.sleep(0.2)
        import re
        keys = re.findall(r'^- "(\w+)"', messages[0].content, re.M)
        return {k: {"value": "v", "refs": ["S1"], "found": True} for k in keys}
    monkeypatch.setattr(ex, "invoke_json", fake_invoke_json)
    clear_cache("speedtest")
    yield state
    clear_cache("speedtest")


def test_concurrent_requests_call_model_once(stub_llm):
    out = []
    threads = [threading.Thread(target=lambda: out.append(ex.run_group("speedtest", "key_info"))) for _ in range(4)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert stub_llm.calls == 1 and len(out) == 4


def test_warm_fills_cache_in_background(stub_llm, monkeypatch):
    monkeypatch.setattr(ex, "PREFETCH", ["key_info", "eligibility", "risks", "boq"])
    ex.warm("speedtest")
    for _ in range(50):
        if stub_llm.calls >= 4:
            break
        time.sleep(0.1)
    time.sleep(0.2)
    assert stub_llm.calls == 4
    from intelligence.cache import cache_get
    assert all(cache_get("speedtest", k) for k in ("key_info", "eligibility", "risks", "boq"))
