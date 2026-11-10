"""Security primitives: password hashing, sessions, CSRF, role checks, rate limiting."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from datetime import timedelta

import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, delete

from . import config
from .database import get_db, utcnow
from .models import AuthSession, ROLE_ADMIN, ROLES, User

SESSION_COOKIE = config.SESSION_COOKIE_NAME


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


PASSWORD_MIN_LENGTH = 8


def password_problem(password: str) -> str | None:
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
    return None


# ---------------------------------------------------------------- tokens
def new_session_token() -> tuple[str, str, str]:
    """Returns (raw_token, token_hash, csrf_token)."""
    raw = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest(), csrf


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# ---------------------------------------------------------------- session dependency
class CurrentUser:
    def __init__(self, user: User, session: AuthSession):
        self.user = user
        self.session = session

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def role(self) -> str:
        return self.user.role

    @property
    def username(self) -> str:
        return self.user.username


def _get_session_from_cookie(request: Request, db) -> CurrentUser | None:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    token_hash = hash_token(raw)
    sess = db.execute(select(AuthSession).where(AuthSession.token_hash == token_hash)).scalar_one_or_none()
    if sess is None or sess.expires_at < utcnow():
        return None
    user = db.get(User, sess.user_id)
    if user is None or not user.is_active:
        return None
    return CurrentUser(user, sess)


def get_current_user(request: Request, db=Depends(get_db)) -> CurrentUser:
    cu = _get_session_from_cookie(request, db)
    if cu is None:
        raise HTTPException(status_code=401, detail="You are signed out. Please sign in again.")
    return cu


def require_csrf(request: Request, cu: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        header = request.headers.get("X-CSRF-Token", "")
        if not header or not constant_time_equals(header, cu.session.csrf_token):
            raise HTTPException(status_code=403, detail="Security check failed. Please refresh the page and try again.")
    return cu


def require_roles(*roles: str):
    def dep(cu: CurrentUser = Depends(require_csrf)) -> CurrentUser:
        if roles and cu.role not in roles:
            raise HTTPException(status_code=403, detail="Your account does not have permission to do that.")
        return cu
    return dep


def admin_required(cu: CurrentUser = Depends(require_csrf)) -> CurrentUser:
    return require_roles(ROLE_ADMIN)(cu)


# mutators need CSRF; readers only need a session
WriteUser = Depends  # readability alias (unused)
login_required = get_current_user


# ---------------------------------------------------------------- rate limiting (in-memory)
class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: float) -> bool:
        """True if allowed, False if over the limit."""
        now = time.monotonic()
        with self._lock:
            bucket = [t for t in self._hits.get(key, []) if now - t < window_seconds]
            if len(bucket) >= limit:
                self._hits[key] = bucket
                return False
            bucket.append(now)
            self._hits[key] = bucket
            return True


login_limiter = SlidingWindowLimiter()
api_limiter = SlidingWindowLimiter()


def purge_expired_sessions(db) -> None:
    db.execute(delete(AuthSession).where(AuthSession.expires_at < utcnow()))
    db.commit()


def session_expiry() -> datetime:
    return utcnow() + timedelta(hours=config.SESSION_TTL_HOURS)
