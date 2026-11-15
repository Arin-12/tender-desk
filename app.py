import io
import os
import re
import threading
import traceback
from functools import wraps

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS

from config.settings import BASE_DIR, MAX_UPLOAD_MB, TOP_K, UPLOAD_DIR
from ingestion.ingest import ingest_pdf, make_doc_id
from intelligence import check_eligibility, compare_tenders, get_criteria, run_analysis
from intelligence.export_pdf import build_pdf
from rag.pipeline import run_rag_pipeline
from vectorstore.faiss_store import delete_document, document_exists, list_documents
from vectorstore.retriever import keyword_search

DIST = BASE_DIR / "frontend" / "dist"
DOC_ID_RE = re.compile(r"^[a-z0-9_]{1,80}$")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
CORS(app, resources={r"/api/*": {"origins": os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")}})

jobs = {}                      # doc_id -> {state, percent, message, name}
ingest_lock = threading.Lock()  # one ingestion at a time (CPU / RAM heavy)


class ApiError(Exception):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.message, self.code = message, code


def _friendly(error):
    text = str(error)
    if "429" in text or "rate limit" in text.lower():
        return "The AI service is rate-limited right now. Wait a minute and try again."
    return text[:300]


def api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ApiError as e:
            return jsonify(status="error", message=e.message), e.code
        except FileNotFoundError as e:
            return jsonify(status="error", message=str(e)), 404
        except ValueError as e:
            return jsonify(status="error", message=str(e)), 400
        except Exception as e:
            traceback.print_exc()
            return jsonify(status="error", message=_friendly(e)), 500
    return wrapper


def need_doc(doc_id):
    """Validate the id (blocks path traversal) and make sure the tender is indexed."""
    if not isinstance(doc_id, str) or not DOC_ID_RE.match(doc_id):
        raise ApiError("Invalid document id.")
    if not document_exists(doc_id):
        raise ApiError("This tender is not indexed (yet).", 404)
    return doc_id


def body():
    return request.get_json(silent=True) or {}


# ----------------------------------------------------------------- documents
def _run_ingest(doc_id, pdf_path, original):
    with ingest_lock:
        job = jobs[doc_id]
        job.update(state="processing", message="Starting")
        try:
            ingest_pdf(pdf_path, doc_id, original,
                       progress=lambda pct, msg: job.update(percent=pct, message=msg))
            job.update(state="done", percent=100, message="Ready")
        except Exception as e:
            traceback.print_exc()
            job.update(state="error", message=_friendly(e))


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/documents")
@api
def documents():
    out = {d["doc_id"]: {**d, "state": "done", "percent": 100} for d in list_documents()}
    for doc_id, job in jobs.items():
        if job["state"] != "done" or doc_id not in out:
            out[doc_id] = {**out.get(doc_id, {"doc_id": doc_id}), **job}
    return jsonify(status="success", documents=list(out.values()))


@app.post("/api/upload")
@api
def upload():
    file = request.files.get("file")
    if not file or not file.filename:
        raise ApiError("No file uploaded.")
    if not file.filename.lower().endswith(".pdf"):
        raise ApiError("Only PDF files are allowed.")

    doc_id = make_doc_id(file.filename)
    if jobs.get(doc_id, {}).get("state") in ("queued", "processing"):
        raise ApiError("This tender is already being processed.", 409)

    pdf_path = UPLOAD_DIR / f"{doc_id}.pdf"
    file.save(pdf_path)
    jobs[doc_id] = {"state": "queued", "percent": 0, "message": "Queued", "name": file.filename}
    threading.Thread(target=_run_ingest, args=(doc_id, pdf_path, file.filename), daemon=True).start()
    return jsonify(status="success", doc_id=doc_id)


@app.delete("/api/documents/<doc_id>")
@api
def remove(doc_id):
    need_doc(doc_id)
    if jobs.get(doc_id, {}).get("state") in ("queued", "processing"):
        raise ApiError("Wait for processing to finish before deleting.", 409)
    delete_document(doc_id)
    jobs.pop(doc_id, None)
    return jsonify(status="success")


# --------------------------------------------------------------------- Q&A
@app.post("/api/chat")
@api
def chat():
    data = body()
    doc_id = need_doc(data.get("doc_id"))
    query = str(data.get("query", "")).strip()
    if not query:
        raise ApiError("A question is required.")
    k = max(1, min(int(data.get("k", TOP_K)), 20))
    return jsonify(status="success", **run_rag_pipeline(query, doc_id, k))


@app.post("/api/search")
@api
def search():
    data = body()
    doc_id = need_doc(data.get("doc_id"))
    query = str(data.get("query", "")).strip()
    if not query:
        raise ApiError("Enter a word or phrase to search for.")
    k = max(1, min(int(data.get("k", 10)), 30))
    hits = [{"page": d.metadata.get("page"), "section": d.metadata.get("section"),
             "chunk_type": d.metadata.get("chunk_type"), "text": d.page_content[:1200],
             "score": d.metadata.get("keyword_score")}
            for d in keyword_search(query, doc_id, k)]
    return jsonify(status="success", hits=hits)


# ------------------------------------------------------------ intelligence
@app.post("/api/analyze")
@api
def analyze():
    data = body()
    doc_id = need_doc(data.get("doc_id"))
    result = run_analysis(doc_id, str(data.get("type", "")), bool(data.get("refresh", False)))
    return jsonify(status="success", **result)


@app.get("/api/eligibility/criteria/<doc_id>")
@api
def criteria(doc_id):
    return jsonify(status="success", **get_criteria(need_doc(doc_id)))


@app.post("/api/eligibility/check")
@api
def eligibility_check():
    data = body()
    doc_id = need_doc(data.get("doc_id"))
    profile = data.get("profile")
    if not isinstance(profile, dict):
        raise ApiError("A contractor profile is required.")
    return jsonify(status="success", **check_eligibility(doc_id, profile))


@app.post("/api/compare")
@api
def compare():
    data = body()
    a, b = need_doc(data.get("doc_a")), need_doc(data.get("doc_b"))
    if a == b:
        raise ApiError("Pick two different tenders to compare.")
    return jsonify(status="success", **compare_tenders(a, b))


@app.get("/api/export/<doc_id>")
@api
def export(doc_id):
    pdf = build_pdf(need_doc(doc_id))
    return send_file(io.BytesIO(pdf), mimetype="application/pdf",
                     as_attachment=True, download_name=f"{doc_id}_summary.pdf")


# ------------------------------------------- serve the built React app (optional)
@app.get("/", defaults={"path": ""})
@app.get("/<path:path>")
def frontend(path):
    if path.startswith("api/"):
        return jsonify(status="error", message="Not found."), 404
    if DIST.exists():
        target = DIST / path
        return send_from_directory(DIST, path if path and target.is_file() else "index.html")
    return jsonify(status="ok", message="API running. Start the frontend with `npm run dev` in /frontend.")


if __name__ == "__main__":
    def _warm():
        try:
            from embeddings.embedder import get_bge_embeddings
            get_bge_embeddings()
            print("[Startup] Embedding model ready.")
        except Exception as e:
            print(f"[Startup] Embedding model failed to load: {e}")

    threading.Thread(target=_warm, daemon=True).start()
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")),
            debug=False, threaded=True)
