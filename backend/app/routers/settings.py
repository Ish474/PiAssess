"""Settings, school branding, users administration, backup/restore."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .. import config
from ..database import get_db
from ..models import ROLES, User
from ..schemas import SettingsIn, SettingsOut, UserCreateIn, UserOut, UserSetPasswordIn, UserUpdateIn
from ..security import (
    admin_required,
    hash_password,
    password_problem,
    require_csrf,
    require_roles,
    verify_password,
)
from ..services.common import get_setting, log_action, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])

SENSITIVE_KEYS = {"ai_api_key"}


def _mask(key: str) -> str:
    if not key:
        return ""
    return key[:3] + "…" + key[-2:] if len(key) > 8 else "••••"


@router.get("", response_model=SettingsOut)
def get_settings(cu=Depends(require_roles()), db=Depends(get_db)):
    logo_path = get_setting(db, "logo_path")
    out = SettingsOut(
        school_name=get_setting(db, "school_name"),
        school_address=get_setting(db, "school_address"),
        school_tagline=get_setting(db, "school_tagline"),
        academic_session=get_setting(db, "academic_session"),
        student_id_prefix=get_setting(db, "student_id_prefix"),
        passing_marks_default=int(get_setting(db, "passing_marks_default") or 33),
        exam_types=[t for t in get_setting(db, "exam_types").split("|") if t],
        default_question_template=get_setting(db, "default_question_template"),
        ai_provider=get_setting(db, "ai_provider"),
        ai_base_url=get_setting(db, "ai_base_url") or config.AI_BASE_URL,
        ai_model=get_setting(db, "ai_model"),
        ai_api_key_set=bool(get_setting(db, "ai_api_key") or config.AI_API_KEY),
        ai_api_key_masked=_mask(get_setting(db, "ai_api_key") or config.AI_API_KEY),
        logo_url=f"/api/settings/logo?{uuid.uuid4().hex[:6]}" if logo_path else "",
    )
    return out


@router.put("")
def update_settings(payload: SettingsIn, cu=Depends(admin_required), db=Depends(get_db)):
    for key, value in payload.model_dump(exclude_none=True, exclude={"ai_api_key"}).items():
        if key == "exam_types":
            value = "|".join(t.strip() for t in value if t.strip())
        elif isinstance(value, (int, bool)):
            value = str(value)
        set_setting(db, key, value)
    if payload.ai_api_key is not None:
        set_setting(db, "ai_api_key", payload.ai_api_key.strip())
    log_action(db, cu, "update", "settings", None, "Updated school settings")
    db.commit()
    return get_settings(cu, db)


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), cu=Depends(admin_required), db=Depends(get_db)):
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Logo images must be smaller than 5 MB.")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in config.ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Logo must be a PNG or JPG image.")
    stored = f"logo_{uuid.uuid4().hex}{ext}"
    (config.LOGO_UPLOAD_DIR / stored).write_bytes(raw)
    set_setting(db, "logo_path", stored)
    log_action(db, cu, "update", "settings", None, "Updated school logo")
    db.commit()
    return {"ok": True, "logo_url": f"/api/settings/logo?{uuid.uuid4().hex[:6]}"}


@router.get("/logo")
def get_logo(db=Depends(get_db)):
    logo_path = get_setting(db, "logo_path")
    if logo_path and (config.LOGO_UPLOAD_DIR / logo_path).exists():
        return FileResponse(config.LOGO_UPLOAD_DIR / logo_path)
    # branded placeholder so the UI always has the school mark
    placeholder = Path(__file__).resolve().parent.parent / "static" / "placeholder_logo.svg"
    if placeholder.exists():
        return FileResponse(placeholder, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="No logo configured.")


# ---------------------------------------------------------------- users (admin)
@router.get("/users", response_model=list[UserOut])
def list_users(_cu=Depends(admin_required), db=Depends(get_db)):
    return [UserOut.model_validate(u) for u in db.query(User).order_by(User.username).all()]


@router.post("/users", response_model=UserOut)
def create_user(payload: UserCreateIn, cu=Depends(admin_required), db=Depends(get_db)):
    username = payload.username.strip().lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail=f"The username \"{username}\" is already taken.")
    if problem := password_problem(payload.password):
        raise HTTPException(status_code=400, detail=problem)
    u = User(username=username, password_hash=hash_password(payload.password),
             full_name=payload.full_name.strip(), role=payload.role, must_change_password=True)
    db.add(u)
    db.flush()
    log_action(db, cu, "create", "user", u.id, f"Created user \"{username}\" with role {payload.role}")
    db.commit()
    db.refresh(u)
    return UserOut.model_validate(u)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdateIn, cu=Depends(admin_required), db=Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if payload.full_name is not None:
        u.full_name = payload.full_name.strip()
    if payload.role is not None:
        u.role = payload.role
    if payload.is_active is not None:
        if u.id == cu.id and payload.is_active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
        if u.role == "admin" and payload.is_active is False:
            admins = [x for x in db.query(User).filter(User.role == "admin", User.is_active == True).all() if x.id != u.id]  # noqa: E712
            if not admins:
                raise HTTPException(status_code=400, detail="At least one active administrator must remain.")
        u.is_active = payload.is_active
    log_action(db, cu, "update", "user", u.id, f"Updated user \"{u.username}\"")
    db.commit()
    db.refresh(u)
    return UserOut.model_validate(u)


@router.post("/users/{user_id}/set-password")
def set_user_password(user_id: int, payload: UserSetPasswordIn, cu=Depends(admin_required), db=Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if problem := password_problem(payload.new_password):
        raise HTTPException(status_code=400, detail=problem)
    u.password_hash = hash_password(payload.new_password)
    u.must_change_password = True
    log_action(db, cu, "update", "user", u.id, f"Reset password for \"{u.username}\"")
    db.commit()
    return {"ok": True}
