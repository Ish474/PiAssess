"""Authentication endpoints: login, logout, me, change password."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select

from .. import config
from ..database import get_db, utcnow
from ..models import AuthSession, User
from ..schemas import ChangePasswordIn, LoginIn, LoginOut, UserOut
from ..security import (
    get_current_user,
    hash_password,
    hash_token,
    login_limiter,
    new_session_token,
    password_problem,
    require_csrf,
    session_expiry,
    verify_password,
)
from ..services.common import log_action

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, request: Request, response: Response, db=Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not login_limiter.check(f"login:{client_ip}", limit=10, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Please wait a minute and try again.")

    user = db.execute(select(User).where(User.username == payload.username.strip().lower())).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        log_action(db, None, "login_failed", "user", payload.username, "Invalid username or password")
        db.commit()
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated. Contact the administrator.")

    raw, token_hash, csrf = new_session_token()
    sess = AuthSession(
        token_hash=token_hash,
        user_id=user.id,
        csrf_token=csrf,
        ip_address=client_ip,
        expires_at=session_expiry(),
    )
    db.add(sess)
    user.last_login_at = utcnow()
    log_action(db, user, "login", "user", user.id, "Signed in")
    db.commit()

    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=raw,
        httponly=True,
        samesite="strict",
        max_age=config.SESSION_TTL_HOURS * 3600,
        path="/",
    )
    return LoginOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/logout")
def logout(request: Request, response: Response, db=Depends(get_db)):
    raw = request.cookies.get(config.SESSION_COOKIE_NAME)
    if raw:
        db.execute(
            AuthSession.__table__.delete().where(AuthSession.token_hash == hash_token(raw))
        )
        db.commit()
    response.delete_cookie(config.SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(cu=Depends(get_current_user)):
    return cu.user


@router.post("/change-password")
def change_password(payload: ChangePasswordIn, cu=Depends(require_csrf), db=Depends(get_db)):
    if not verify_password(payload.current_password, cu.user.password_hash):
        raise HTTPException(status_code=400, detail="Your current password is not correct.")
    if problem := password_problem(payload.new_password):
        raise HTTPException(status_code=400, detail=problem)
    cu.user.password_hash = hash_password(payload.new_password)
    cu.user.must_change_password = False
    log_action(db, cu, "password_changed", "user", cu.id, "Changed own password")
    db.commit()
    return {"ok": True}
