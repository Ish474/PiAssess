"""Backup & restore: local zip snapshots, Google Drive upload/download, auto-backup settings."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from .. import config
from ..database import get_db
from ..models import User
from ..security import require_roles
from ..services.backup import (
    BackupError, create_backup, drive_download, drive_file_name, drive_list,
    drive_test, drive_upload, list_backups, restore_backup,
)
from ..services.common import get_setting, log_action, set_setting

router = APIRouter(prefix="/api/backups", tags=["backups"])

admin_dep = require_roles("admin")
SYSTEM_USER = SimpleNamespace(username="system", full_name="System")


def _backup_status(db) -> dict:
    sa_set = bool((get_setting(db, "gdrive_service_account") or "").strip())
    folder_id = (get_setting(db, "gdrive_folder_id") or "").strip()
    last_upload = get_setting(db, "gdrive_last_upload") or None
    return {
        "auto_enabled": (get_setting(db, "backup_auto") or "0") == "1",
        "interval_hours": int(get_setting(db, "backup_interval_hours") or "24"),
        "drive_connected": sa_set and bool(folder_id),
        "drive_folder_id": folder_id,
        "drive_last_upload": last_upload,
    }


@router.get("")
def backup_overview(_cu=Depends(admin_dep), db=Depends(get_db)):
    return {"backups": list_backups(), "status": _backup_status(db)}


@router.post("/settings")
def save_backup_settings(
    auto_enabled: bool = Form(False),
    interval_hours: int = Form(24),
    folder_id: str = Form(""),
    sa_file: UploadFile | None = File(None),
    cu: User = Depends(admin_dep),
    db=Depends(get_db),
):
    """Save the auto-backup schedule and Google Drive configuration.

    The service-account JSON is optional here — it is only replaced when a new
    file is uploaded (it is never sent back to the browser afterwards).
    """
    if not (1 <= interval_hours <= 168):
        raise HTTPException(status_code=400, detail="The backup interval must be between 1 and 168 hours.")
    set_setting(db, "backup_auto", "1" if auto_enabled else "0")
    set_setting(db, "backup_interval_hours", str(interval_hours))
    set_setting(db, "gdrive_folder_id", folder_id.strip())
    if sa_file is not None:
        raw = sa_file.file.read()
        if len(raw) > 1024 * 512:
            raise HTTPException(status_code=400, detail="That service-account file is too large to be a key JSON.")
        try:
            info = json.loads(raw.decode("utf-8"))
            if info.get("type") != "service_account":
                raise ValueError()
        except Exception:
            raise HTTPException(status_code=400, detail="That file is not a Google service-account JSON key.")
        set_setting(db, "gdrive_service_account", raw.decode("utf-8"))
    log_action(db, cu, "settings", "backup", None,
               f"Backup settings saved (auto {'on' if auto_enabled else 'off'}, interval {interval_hours}h)")
    db.commit()
    return {"saved": True, "status": _backup_status(db)}


@router.post("/drive/test")
def test_drive(_cu=Depends(admin_dep), db=Depends(get_db)):
    """Verify the saved Google Drive key + folder actually work."""
    sa_json = get_setting(db, "gdrive_service_account") or ""
    if not sa_json.strip():
        raise HTTPException(status_code=400, detail="Upload the service-account JSON key first.")
    try:
        info = drive_test(sa_json, get_setting(db, "gdrive_folder_id") or "")
    except BackupError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return info


@router.post("")
def create_backup_now(upload_to_drive: bool = Form(True), cu: User = Depends(admin_dep), db=Depends(get_db)):
    """Create a backup zip now; upload it to Google Drive when configured."""
    result = create_backup(db)
    note = f"Manual backup created: {result['name']} ({result['size'] // 1024} KB)"
    drive_note = None
    sa_json = get_setting(db, "gdrive_service_account") or ""
    folder_id = (get_setting(db, "gdrive_folder_id") or "").strip()
    if upload_to_drive and sa_json.strip() and folder_id:
        try:
            drive_upload(sa_json, folder_id, Path(result["path"]))
            set_setting(db, "gdrive_last_upload", datetime.now(timezone.utc).isoformat())
            drive_note = "Uploaded to Google Drive."
            note += " and uploaded to Google Drive"
        except BackupError as exc:
            drive_note = f"The local backup is safe, but Google Drive refused it: {exc}"
    log_action(db, cu, "backup", "database", result["name"], note)
    db.commit()
    return {**{k: v for k, v in result.items() if k != "path"}, "drive_note": drive_note}


@router.delete("/{name}")
def delete_backup(name: str, cu: User = Depends(admin_dep), db=Depends(get_db)):
    if not name.startswith("piassess_backup_") or ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="That is not a PiAssess backup file.")
    path = config.BACKUP_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="That backup no longer exists on disk.")
    path.unlink()
    log_action(db, cu, "delete", "backup", name, f"Deleted local backup {name}")
    db.commit()
    return {"deleted": True}


@router.get("/{name}/download")
def download_backup(name: str, _cu=Depends(admin_dep), db=Depends(get_db)):
    if not name.startswith("piassess_backup_") or ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="That is not a PiAssess backup file.")
    path = config.BACKUP_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="That backup no longer exists on disk.")
    return FileResponse(path, media_type="application/zip", filename=name)


@router.post("/restore")
async def restore_from_upload(file: UploadFile = File(...), cu: User = Depends(admin_dep), db=Depends(get_db)):
    """Restore the database + uploaded files from a backup zip (local or Drive)."""
    raw = await file.read()
    if len(raw) > 800 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Backups larger than 800 MB cannot be restored here.")
    tmp = config.BACKUP_DIR / f"_restore_{cu.username}.zip"
    tmp.write_bytes(raw)
    db.close()  # release this request's own connection so the DB files can be swapped
    try:
        result = restore_backup(tmp)
    except BackupError as exc:
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc))
    tmp.unlink(missing_ok=True)
    log_action(db, cu, "restore", "backup", file.filename,
               f"Restored from backup {file.filename or 'uploaded zip'}")
    db.commit()
    return result


@router.get("/drive/files")
def list_drive_backups(_cu=Depends(admin_dep), db=Depends(get_db)):
    sa_json = get_setting(db, "gdrive_service_account") or ""
    folder_id = (get_setting(db, "gdrive_folder_id") or "").strip()
    if not sa_json.strip() or not folder_id:
        raise HTTPException(status_code=400, detail="Connect Google Drive in Settings first.")
    try:
        return {"files": drive_list(sa_json, folder_id)}
    except BackupError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/drive/files/{file_id}/restore")
def restore_from_drive(file_id: str, cu: User = Depends(admin_dep), db=Depends(get_db)):
    """Download a backup from Google Drive and restore it."""
    sa_json = get_setting(db, "gdrive_service_account") or ""
    if not sa_json.strip():
        raise HTTPException(status_code=400, detail="Connect Google Drive in Settings first.")
    tmp = config.BACKUP_DIR / f"_restore_drive_{file_id}.zip"
    try:
        drive_download(sa_json, file_id, tmp)
        db.close()  # release this request's own connection so the DB files can be swapped
        result = restore_backup(tmp)
    except BackupError as exc:
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc))
    tmp.unlink(missing_ok=True)
    log_action(db, cu, "restore", "backup", file_id, f"Restored from a Google Drive backup ({file_id})")
    db.commit()
    return result


@router.get("/drive/files/{file_id}/download")
def download_drive_backup(file_id: str, _cu=Depends(admin_dep), db=Depends(get_db)):
    """Download a backup stored on Google Drive as a local zip file."""
    sa_json = get_setting(db, "gdrive_service_account") or ""
    if not sa_json.strip():
        raise HTTPException(status_code=400, detail="Connect Google Drive in Settings first.")
    tmp = config.BACKUP_DIR / f"_download_drive_{file_id}.zip"
    try:
        name = drive_file_name(sa_json, file_id)
        drive_download(sa_json, file_id, tmp)
    except BackupError as exc:
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc))
    filename = name if name.endswith(".zip") else f"{name}.zip"
    # the temp copy is removed after the response has been streamed
    return FileResponse(tmp, media_type="application/zip", filename=filename,
                        background=BackgroundTask(tmp.unlink, missing_ok=True))
