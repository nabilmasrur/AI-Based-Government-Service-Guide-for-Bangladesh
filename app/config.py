"""Central configuration. Everything tunable lives here."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- paths ---
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
EMB_FILE = DATA_DIR / "embeddings.npz"
PENDING_FILE = DATA_DIR / "pending.json"
KB_FILES = {"passport": DATA_DIR / "passport.json", "licence": DATA_DIR / "licence.json"}
ANALYTICS_DB = DATA_DIR / "analytics.db"

# --- credentials & models ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-3.6-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()

# --- CORS: the frontend's origin(s), comma separated. "*" allows all. ---
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

# --- retrieval ---
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.62"))
TOP_K = 5
KEYWORD_BOOST = 0.08          # added to score per matched keyword, capped below
KEYWORD_BOOST_MAX = 0.20

# --- behaviour ---
SESSION_TTL = 60 * 60         # seconds a session survives without activity
HISTORY_TURNS = 6             # turns kept in the prompt
STALE_DAYS = 180              # entries older than this get a "needs re-checking" flag

# --- rate limits (per client IP) ---
RATE_PER_MIN = int(os.getenv("RATE_PER_MIN", "8"))
RATE_PER_DAY = int(os.getenv("RATE_PER_DAY", "300"))
