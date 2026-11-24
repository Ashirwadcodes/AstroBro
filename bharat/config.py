"""Central configuration. Everything is local; no network except localhost Ollama."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("BHARAT_DB", ROOT / "database" / "bharat.db"))
KEY_PATH = ROOT / "database" / "field.key"
CORPUS_DIR = ROOT / "corpus"
LOG_DIR = ROOT / "logs"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("BHARAT_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
LLM_TIMEOUT_S = 300

# Security limits
MAX_INPUT_CHARS = 1500
SESSION_TTL_S = 8 * 3600
LOGIN_MAX_FAILS = 5
LOGIN_LOCK_S = 15 * 60
CHAT_RATE = (10, 60)        # 10 requests / 60 s per user
LOGIN_RATE = (10, 300)      # 10 attempts / 5 min per username
MIN_PASSWORD_LEN = 12
MAX_NOTES = 200
MAX_NOTE_CHARS = 2000
HISTORY_TURNS = 3

# Only text under these licences may be indexed.
ALLOWED_LICENSES = {"public-domain", "cc0", "cc-by", "cc-by-sa", "own-work"}

AYANAMSA = "lahiri"
HOUSE_SYSTEM = "whole-sign"

DEFAULT_LANG = os.environ.get("BHARAT_LANG", "english")  # english | hinglish | hindi
EMBED_MODEL = os.environ.get("BHARAT_EMBED_MODEL", "nomic-embed-text")
USE_EMBEDDINGS = os.environ.get("BHARAT_EMBED", "1") != "0"  # 0 = keyword search only
