import OS
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---- OCR ------------------------------------------------------------------
# Leave empty when tesseract is on PATH (Linux/macOS). Set in .env on Windows.
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "eng")
OCR_TEXT_THRESHOLD = int(os.getenv("OCR_TEXT_THRESHOLD", "20"))

# ---- LLM (Groq) -----------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "3000"))

# ---- Embeddings / chunking / retrieval -------------------------------------
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
TABLE_CHUNK_CHARS = int(os.getenv("TABLE_CHUNK_CHARS", "1500"))
TOP_K = int(os.getenv("TOP_K", "6"))

# ---- Server ---------------------------------------------------------------
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))

# ---- Directories ----------------------------------------------------------
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"
CACHE_DIR = DATA_DIR / "cache"

for _d in (UPLOAD_DIR, PROCESSED_DIR, VECTORSTORE_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)
