"""PiAssess configuration.

Everything sensitive comes from environment variables first.
Nothing secret is ever hard-coded here.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent   # backend/
DATA_DIR = Path(os.getenv("PIASSESS_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
BACKUP_DIR = DATA_DIR / "backups"
DOC_UPLOAD_DIR = UPLOAD_DIR / "documents"
LOGO_UPLOAD_DIR = UPLOAD_DIR / "logos"
OMR_SCAN_DIR = UPLOAD_DIR / "omr_scans"

DATABASE_URL = os.getenv("PIASSESS_DATABASE_URL", f"sqlite:///{(DATA_DIR / 'piassess.db').as_posix()}")

# For a localhost-only school deployment the cookie is sent over http.
SESSION_COOKIE_NAME = "piassess_session"
SESSION_TTL_HOURS = int(os.getenv("PIASSESS_SESSION_HOURS", "12"))
SECRET_PLACEHOLDER = "set-in-env"  # session tokens are random per login; no app secret needed

# Optional AI provider configuration (Phase 3). Read from environment when present.
AI_BASE_URL = os.getenv("PIASSESS_AI_BASE_URL", "")
AI_API_KEY = os.getenv("PIASSESS_AI_API_KEY", "")
AI_MODEL = os.getenv("PIASSESS_AI_MODEL", "")

MAX_UPLOAD_MB = int(os.getenv("PIASSESS_MAX_UPLOAD_MB", "100"))

ALLOWED_DOCUMENT_TYPES = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".png", ".jpg", ".jpeg"}
ALLOWED_IMAGE_TYPES = {".png", ".jpg", ".jpeg"}

for _d in (DATA_DIR, UPLOAD_DIR, BACKUP_DIR, DOC_UPLOAD_DIR, LOGO_UPLOAD_DIR, OMR_SCAN_DIR):
    _d.mkdir(parents=True, exist_ok=True)
