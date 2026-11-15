# Tender Desk — AI Tender Intelligence and Decision Support (RAG)

Upload construction tender PDFs, ask questions with page citations, extract key terms, check a contractor's
eligibility, compare tenders, and export a summary PDF.

**Backend:** Flask · PyMuPDF / pdfplumber / Tesseract · BGE embeddings · FAISS + BM25 hybrid retrieval · Groq (Llama 3.3 70B)
**Frontend:** React (Vite)

## Setup

### 1. Backend (Python 3.10+)
```bash
python -m venv venv
venv\Scripts\activate            # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # then put your GROQ_API_KEY in .env
python app.py                    # http://127.0.0.1:5000
```
Scanned tenders need Tesseract OCR. Windows: set `TESSERACT_CMD` in `.env`.

### 2. Frontend (Node 18+)
```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173  (proxies /api to Flask)
```
For a single-server deployment run `npm run build` in `frontend/`; Flask then serves `frontend/dist` at port 5000.

### 3. Migrating from the old version
Delete the old `data/vectorstore/index.faiss`, `index.pkl` and the `new_db` folder (each tender now gets its own
folder `data/vectorstore/<doc_id>/`). Delete `app.py`/`app_upload.py`/`templates/` from the old project; this app replaces them.
Re-upload your tenders in the UI.

## Features
| Feature | Where |
|---|---|
| Multiple tenders, each with its own index | sidebar |
| Q&A with clickable page citations and a confidence score | Ask |
| Exact word / clause search (BM25, no AI) | Ask → Find words |
| Key details: EMD, fee, security, completion period, dates, bid validity | Analysis |
| Eligibility criteria, risk clauses (LD, termination, escalation, payment, retention), BOQ and pricing | Analysis |
| Executive summary, PDF export | Analysis |
| Bid eligibility checker (Met / Not met / Unclear with evidence and actions) | Bid check |
| Tender comparison (also works for two revisions) | Compare |

Not implemented (future scope): deadline reminders, e-tender portal integration, Hindi/Marathi, bid/no-bid recommendation.

## How it works
1. **Ingest** (`ingestion/`): PyMuPDF text, OCR only for pages without a text layer, pdfplumber tables (PDF opened once),
   running headers/footers removed, section detection. Saved to `data/processed/<doc_id>.json`.
2. **Chunk** (`chunking/`): prose split with overlap; each table is its own chunk (header repeated if split).
3. **Index** (`vectorstore/`): BGE embeddings → FAISS, one folder per tender.
4. **Retrieve**: dense cosine + BM25, merged by reciprocal-rank fusion. Structured analyses use one sub-query per field.
5. **Answer** (`rag/`): chunks are labelled S1, S2… in the prompt; the model cites those labels; the validator maps them to
   page numbers and drops invented citations.
6. **Structured extraction** (`intelligence/`): fixed JSON schemas (`catalog.py`), one LLM call per group, cached on disk.

### Confidence score
`0.6 × mean similarity of cited passages + 0.4 × share of valid citations` → High ≥ 0.70, Medium ≥ 0.50, else Low.
It is a transparent heuristic, not a probability. Report how it correlates with correctness on your evaluation set.

### Bid check is not a probability
The checker returns per-criterion status with evidence. An LLM cannot give a calibrated "probability of qualifying",
so the app does not claim one. Numeric comparisons are done by the LLM: always verify them.

## Evaluation (for the report)
```bash
copy evaluation\eval_set.example.json evaluation\eval_set.json    # write 20–30 questions with known answers/pages
python -m evaluation.eval_qa <doc_id> evaluation/eval_set.json --k 6
```
Repeat with different `CHUNK_SIZE` and `--k` values for an ablation table. Unit tests: `python -m pytest tests`.

## API
`GET /api/documents` · `POST /api/upload` · `DELETE /api/documents/<id>` · `POST /api/chat` · `POST /api/search` ·
`POST /api/analyze {doc_id,type}` (`key_info|summary|eligibility|risks|boq`) · `POST /api/eligibility/check` ·
`POST /api/compare` · `GET /api/export/<id>`

## Security notes
Server binds to `127.0.0.1` with debug off. Document ids are validated (`^[a-z0-9_]+$`). Model output is rendered with
`react-markdown` (no raw HTML), so PDF content cannot inject scripts. Keep `.env` out of git.

## Limitations
Tables without ruling lines are not detected. Tender PDFs with many scanned pages are slow (OCR). Free-tier Groq limits
tokens per minute; the first comparison of two tenders makes several calls. All outputs need human verification.
