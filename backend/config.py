import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CAP_BASE_URL = os.getenv("CAP_BASE_URL", "http://localhost:4004")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
APP_SECRET = os.getenv("APP_SECRET", "dev-secret-123")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_INDEX = FRONTEND_DIR / "index.html"
