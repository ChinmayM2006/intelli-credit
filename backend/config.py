import os
from dotenv import load_dotenv

load_dotenv()

def _clean_key(val: str) -> str:
    """Return empty string for placeholder API keys."""
    if not val or val.startswith("your_") or val == "sk-..." or val == "":
        return ""
    return val.strip()

# LLM API Keys
GEMINI_API_KEY = _clean_key(os.getenv("GEMINI_API_KEY", ""))
OPENAI_API_KEY = _clean_key(os.getenv("OPENAI_API_KEY", ""))
SERPER_API_KEY = _clean_key(os.getenv("SERPER_API_KEY", ""))

# LLM provider preference: auto | openai | gemini
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

# Large-document robustness knobs
OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "120"))
OCR_BATCH_SIZE = int(os.getenv("OCR_BATCH_SIZE", "12"))
OCR_VISUAL_MAX_PAGES = int(os.getenv("OCR_VISUAL_MAX_PAGES", "80"))
OCR_VISUAL_MAX_REGIONS_PER_PAGE = int(os.getenv("OCR_VISUAL_MAX_REGIONS_PER_PAGE", "8"))
OCR_VISUAL_MIN_TEXT_CHARS = int(os.getenv("OCR_VISUAL_MIN_TEXT_CHARS", "12"))
OCR_LOW_TEXT_THRESHOLD = int(os.getenv("OCR_LOW_TEXT_THRESHOLD", "120"))
OCR_MAX_LOW_TEXT_PAGES = int(os.getenv("OCR_MAX_LOW_TEXT_PAGES", "40"))
RAG_MAX_TFIDF_CHUNKS = int(os.getenv("RAG_MAX_TFIDF_CHUNKS", "1200"))
RAG_MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "26000"))

# Directories
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(os.path.dirname(__file__), "intelli_credit.db")

for d in [UPLOAD_DIR, OUTPUT_DIR, DATA_DIR]:
    os.makedirs(d, exist_ok=True)
