"""Table extraction with pdfplumber. The PDF is opened ONCE by the caller."""

# Tune these for your PDFs. Larger tolerances merge nearby lines (good for
# sloppy scans, bad for dense BOQ grids).
LINE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 6,
    "join_tolerance": 6,
    "intersection_tolerance": 8,
    "edge_min_length": 10,
}


def _clean(cell) -> str:
    if not cell:
        return ""
    return " ".join(str(cell).split()).replace("|", "/")


def to_markdown(rows) -> str:
    """2-D list -> Markdown table. First row is the header."""
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [list(r) + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "|".join(["---"] * width) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def extract_tables(plumber_page, page_number):
    """Return ruled tables on a page. Prose is never mistaken for a table:
    a table needs >= 2 rows and >= 2 columns."""
    try:
        raw = plumber_page.extract_tables(LINE_SETTINGS)
    except Exception as error:
        print(f"[Tables] page {page_number} failed: {error}")
        return []

    tables = []
    for index, table in enumerate(raw, start=1):
        rows = [[_clean(c) for c in row] for row in (table or []) if row]
        rows = [r for r in rows if any(r)]
        if len(rows) < 2 or max(len(r) for r in rows) < 2:
            continue
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        tables.append({
            "table_id": f"p{page_number}_t{index}",
            "rows": rows,
            "markdown": to_markdown(rows),
        })
    return tables
