import io
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from intelligence.cache import cache_get
from vectorstore.faiss_store import list_documents

ORDER = ["key_info", "summary", "eligibility", "risks", "boq"]
DISCLAIMER = "AI-generated decision support. Verify against the original tender before relying on it."


def _plain(md: str) -> str:
    md = re.sub(r"\*\*|__|`", "", md or "")
    md = re.sub(r"^\s*[-*]\s+", "• ", md, flags=re.M)
    return md


def _para(text, style):
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def build_pdf(doc_id: str) -> bytes:
    sections = [d for d in (cache_get(doc_id, n) for n in ORDER) if d]
    if not sections:
        raise ValueError("Run at least one analysis (Key details, Summary, ...) before exporting.")
    name = next((d["name"] for d in list_documents() if d["doc_id"] == doc_id), doc_id)

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9, leading=12)
    cell = ParagraphStyle("cell", parent=body, fontSize=8.5, leading=11)
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=18, alignment=0)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=12)

    story = [Paragraph("Tender summary", h1), _para(name, body), Spacer(1, 6)]
    for sec in sections:
        story.append(Paragraph(escape(sec["title"]), h2))
        if sec["type"] == "text":
            story.append(_para(_plain(sec["content"]), body))
            continue
        srcmap = {s["ref_id"]: s for s in sec["sources"]}
        rows = [[_para("Item", cell), _para("Details", cell), _para("Page", cell)]]
        for f in sec["fields"]:
            label = f["label"] + (f"\nRisk: {f['risk']}" if f.get("risk") else "")
            pages = ", ".join(str(srcmap[r]["page"]) for r in f["refs"] if r in srcmap)
            rows.append([_para(label, cell), _para(_plain(f["value"]), cell), _para(pages, cell)])
        table = Table(rows, colWidths=[45 * mm, 112 * mm, 15 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9CDC4")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9EBE5")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(18 * mm, 10 * mm, DISCLAIMER)
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=16 * mm, bottomMargin=18 * mm).build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
