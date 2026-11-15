import json

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import CHUNK_OVERLAP, CHUNK_SIZE, PROCESSED_DIR, TABLE_CHUNK_CHARS
from ingestion.table_extractor import to_markdown


def split_table(rows, max_chars=TABLE_CHUNK_CHARS):
    """Split a table into Markdown parts, repeating the header row in each part."""
    header, body = rows[0], rows[1:]
    parts, current = [], []
    for row in body:
        candidate = to_markdown([header] + current + [row])
        if current and len(candidate) > max_chars:
            parts.append(to_markdown([header] + current))
            current = [row]
        else:
            current.append(row)
    if current or not parts:
        parts.append(to_markdown([header] + current))
    return parts


def chunk_processed_document(doc_id, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    """Processed JSON -> LangChain Documents. Prose and tables are chunked separately
    so a table is never cut mid-row and every part keeps its header."""
    path = PROCESSED_DIR / f"{doc_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Processed file not found for '{doc_id}': {path}")
    pages = json.loads(path.read_text(encoding="utf-8"))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    docs = []
    for page in pages:
        number = page.get("page", 0)
        base = {
            "doc_id": doc_id,
            "document": page.get("document", doc_id),
            "page": number,
            "section": page.get("section", "Unknown"),
            "subsection": page.get("subsection", "Unknown"),
            "extraction_method": page.get("extraction_method", "PyMuPDF"),
        }
        text = page.get("text", "")
        if text.strip():
            for i, piece in enumerate(splitter.split_text(text), start=1):
                docs.append(Document(
                    page_content=piece,
                    metadata={**base, "chunk_type": "text", "chunk_id": f"{doc_id}_p{number}_c{i}"},
                ))
        for table in page.get("tables", []):
            for j, part in enumerate(split_table(table["rows"]), start=1):
                docs.append(Document(
                    page_content=part,
                    metadata={**base, "chunk_type": "table",
                              "chunk_id": f"{doc_id}_{table['table_id']}_part{j}"},
                ))
    return docs
