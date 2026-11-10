"""Backup & restore — local zip snapshots with optional Google Drive upload.

A backup is a zip containing:
  * ``piassess.db``     — a consistent snapshot of the SQLite database
  * ``manifest.json``   — when/what/counts, used to validate restores
  * ``uploads/...``     — logos, uploaded documents and scanned OMR sheets

Google Drive uses a **service account**: the school admin creates one in the
Google Cloud Console, shares the target Drive folder with its email address,
and pastes the key JSON into Settings. The app then talks to Drive directly
(JWT -> access token -> REST) with no interactive sign-in and no extra SDK.
"""
from __future__ import annotations

import base64
import io
import json
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .. import config

DRIVE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
MAX_RESTORE_MB = 800


class BackupError(Exception):
    """Raised with a teacher-readable message when a backup/restore cannot proceed."""


# ---------------------------------------------------------------- local backups
def _snapshot_db(dest_db_path: Path) -> None:
    """Copy the live SQLite database safely (includes committed WAL content)."""
    from ..database import engine

    raw = engine.raw_connection()
    try:
        src: sqlite3.Connection = raw.driver_connection  # type: ignore[assignment]
        with sqlite3.connect(dest_db_path) as dst:
            src.backup(dst)
    finally:
        raw.close()


def _count(db, model) -> int:
    try:
        return db.query(model).count()
    except Exception:
        return 0


def create_backup(db) -> dict:
    """Zip the database + uploaded files into BACKUP_DIR. Returns backup info."""
    from ..models import Examination, OMRScan, QuestionPaper, Student

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"piassess_backup_{stamp}.zip"
    out_path = config.BACKUP_DIR / name
    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        db_copy = tmp_dir / "piassess.db"
        _snapshot_db(db_copy)

        manifest = {
            "app": "PiAssess",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "students": _count(db, Student),
            "examinations": _count(db, Examination),
            "question_papers": _count(db, QuestionPaper),
            "omr_scans": _count(db, OMRScan),
        }
        (tmp_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        uploads_src = config.UPLOAD_DIR
        uploads_dst = tmp_dir / "uploads"
        if uploads_src.exists():
            shutil.copytree(uploads_src, uploads_dst,
                            ignore=shutil.ignore_patterns("*.tmp", "Thumbs.db"))

        import zipfile
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_copy, "piassess.db")
            zf.write(tmp_dir / "manifest.json", "manifest.json")
            for p in uploads_dst.rglob("*"):
                if p.is_file():
                    zf.write(p, f"uploads/{p.relative_to(uploads_dst).as_posix()}")

    return {
        "name": name,
        "size": out_path.stat().st_size,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest": manifest,
        "path": str(out_path),
    }


def list_backups() -> list[dict]:
    items = []
    for p in sorted(config.BACKUP_DIR.glob("piassess_backup_*.zip"), reverse=True):
        items.append({
            "name": p.name,
            "size": p.stat().st_size,
            "created_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
    return items


def _validate_backup_zip(zf) -> dict:
    names = zf.namelist()
    if "manifest.json" not in names or "piassess.db" not in names:
        raise BackupError(
            "This file is not a PiAssess backup (it has no PiAssess database or manifest inside). "
            "Choose a zip that was created by the Backups page."
        )
    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    if manifest.get("app") != "PiAssess":
        raise BackupError("This backup was not created by PiAssess.")
    return manifest


def _swap_in_restored_db(staged_db: Path) -> None:
    """Replace the live database file with the staged snapshot.

    On Windows an open connection keeps the ``-wal`` file locked, so every
    pooled connection is closed first and the swap is retried briefly before
    giving up with an honest message.
    """
    import time as _time

    from ..database import engine

    engine.dispose()  # release open file handles so the swap can happen
    live_db = Path(config.DATABASE_URL.replace("sqlite:///", ""))

    last_error: PermissionError | None = None
    for attempt in range(5):
        try:
            for suffix in ("-wal", "-shm"):
                Path(str(live_db) + suffix).unlink(missing_ok=True)
            shutil.copyfile(staged_db, live_db)
            return
        except PermissionError as exc:
            last_error = exc
            _time.sleep(0.4 * (attempt + 1))
    raise BackupError(
        "The database is busy right now — close any other open PiAssess windows and try the restore again."
    )


def restore_backup(zip_path: Path) -> dict:
    """Replace the database and uploaded files with the contents of a backup zip.

    The uploaded database is checked for integrity before anything is touched.
    Existing connections are closed and reopen automatically on the restored data.
    """
    import zipfile

    if not zip_path.exists():
        raise BackupError("The backup file could not be found.")
    if zip_path.stat().st_size > MAX_RESTORE_MB * 1024 * 1024:
        raise BackupError(f"Backups larger than {MAX_RESTORE_MB} MB cannot be restored here.")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                manifest = _validate_backup_zip(zf)
                zf.extractall(tmp_dir)
        except zipfile.BadZipFile:
            raise BackupError("This file is not a valid zip archive.")

        staged_db = tmp_dir / "piassess.db"
        if not staged_db.exists():
            raise BackupError("The backup does not contain the PiAssess database.")

        # integrity check before touching anything real (close the connection
        # explicitly — a leaked handle keeps the file locked on Windows)
        try:
            check = sqlite3.connect(staged_db)
            try:
                row = check.execute("PRAGMA integrity_check").fetchone()
            finally:
                check.close()
            if row is None or row[0] != "ok":
                raise BackupError("The database inside this backup is damaged — not restoring it.")
        except sqlite3.DatabaseError:
            raise BackupError("The database inside this backup could not be opened — not restoring it.")

        _swap_in_restored_db(staged_db)

        uploads_zip = tmp_dir / "uploads"
        if uploads_zip.exists():
            if config.UPLOAD_DIR.exists():
                shutil.rmtree(config.UPLOAD_DIR)
            shutil.copytree(uploads_zip, config.UPLOAD_DIR)

    return {
        "restored": True,
        "manifest": manifest,
        "note": "Restored. If anything looks out of date, close and reopen the app.",
    }


# ---------------------------------------------------------------- Google Drive
def _load_service_account(sa_json: str) -> dict:
    try:
        info = json.loads(sa_json)
        if info.get("type") != "service_account" or not info.get("client_email"):
            raise ValueError("not a service account key")
        return info
    except Exception:
        raise BackupError(
            "The Google Drive key is not a valid service-account JSON. "
            "In Google Cloud Console create a service account, make a JSON key, and paste its full contents here."
        )


def _drive_access_token(sa_info: dict) -> str:
    """Exchange the service account's signed JWT for an OAuth access token."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    private_pem = sa_info["private_key"].replace("\\n", "\n")
    try:
        key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    except Exception:
        raise BackupError("The service-account private key could not be read — re-download the JSON key.")

    now = int(time.time())
    header = base64.urlsafe_b64encode(json.dumps(
        {"alg": "RS256", "typ": "JWT"}).encode()).rstrip(b"=")
    claim = base64.urlsafe_b64encode(json.dumps({
        "iss": sa_info["client_email"],
        "scope": DRIVE_SCOPE,
        "aud": DRIVE_TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=")
    signing_input = header + b"." + claim
    signature = base64.urlsafe_b64encode(key.sign(
        signing_input, padding.PKCS1v15(), hashes.SHA256())).rstrip(b"=")
    assertion = (signing_input + b"." + signature).decode()

    try:
        resp = httpx.post(DRIVE_TOKEN_URL, timeout=30, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        })
        resp.raise_for_status()
        return resp.json()["access_token"]
    except httpx.HTTPStatusError:
        raise BackupError("Google refused the sign-in. Check that the Google Cloud project has the Drive API enabled.")
    except httpx.HTTPError:
        raise BackupError("Could not reach Google Drive — check the school's internet connection.")


def _drive_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def drive_test(sa_json: str, folder_id: str) -> dict:
    """Verify the key and folder work; returns the folder name on success."""
    if not folder_id.strip():
        raise BackupError("Paste the Google Drive folder ID first (the long code at the end of the folder's web address).")
    sa = _load_service_account(sa_json)
    token = _drive_access_token(sa)
    try:
        resp = httpx.get(f"{DRIVE_FILES_URL}/{folder_id.strip()}",
                         params={"supportsAllDrives": True, "fields": "name,webViewLink"},
                         headers=_drive_headers(token), timeout=30)
        if resp.status_code == 404:
            raise BackupError(
                "Google could not find that folder. Check the folder ID — and that the folder is "
                f"shared with the service-account email ({sa['client_email']}) as Editor."
            )
        resp.raise_for_status()
        info = resp.json()
    except httpx.HTTPStatusError:
        raise BackupError("Google Drive rejected the request — check the folder ID and sharing settings.")
    except httpx.HTTPError:
        raise BackupError("Could not reach Google Drive — check the school's internet connection.")
    return {"folder_name": info.get("name", ""), "service_account": sa["client_email"]}


def drive_upload(sa_json: str, folder_id: str, path: Path) -> dict:
    """Upload one backup zip into the configured folder."""
    sa = _load_service_account(sa_json)
    token = _drive_access_token(sa)
    metadata = {"name": path.name, "parents": [folder_id.strip()]}
    try:
        resp = httpx.post(
            DRIVE_UPLOAD_URL,
            params={"uploadType": "multipart", "supportsAllDrives": True},
            headers={**_drive_headers(token), "Content-Type": "multipart/related; boundary=piassess"},
            timeout=600,
            content=(
                "--piassess\r\n"
                "Content-Type: application/json; charset=UTF-8\r\n\r\n"
                + json.dumps(metadata) + "\r\n"
                + "--piassess\r\n"
                + "Content-Type: application/zip\r\n"
                + "Content-Transfer-Encoding: binary\r\n\r\n"
            ).encode() + path.read_bytes() + b"\r\n--piassess--",
        )
        if resp.status_code in (403, 404):
            raise BackupError(
                "Google refused the upload. Make sure the Drive folder is shared with the "
                f"service-account email ({sa['client_email']}) as Editor."
            )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        raise BackupError("The upload to Google Drive failed — check the internet connection and try again.")


def drive_list(sa_json: str, folder_id: str) -> list[dict]:
    """Backups currently stored in the Drive folder (newest first)."""
    sa = _load_service_account(sa_json)
    token = _drive_access_token(sa)
    try:
        resp = httpx.get(
            DRIVE_FILES_URL,
            params={
                "q": f"'{folder_id.strip()}' in parents and trashed = false and mimeType != 'application/vnd.google-apps.folder'",
                "orderBy": "createdTime desc",
                "pageSize": 50,
                "fields": "files(id, name, size, createdTime)",
                "supportsAllDrives": True,
            },
            headers=_drive_headers(token), timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("files", [])
    except httpx.HTTPStatusError:
        raise BackupError("Google refused to list the folder — check the folder ID and sharing settings.")
    except httpx.HTTPError:
        raise BackupError("Could not reach Google Drive — check the school's internet connection.")


def drive_download(sa_json: str, file_id: str, dest: Path) -> Path:
    sa = _load_service_account(sa_json)
    token = _drive_access_token(sa)
    try:
        with httpx.stream("GET", f"{DRIVE_FILES_URL}/{file_id}",
                          params={"alt": "media", "supportsAllDrives": True},
                          headers=_drive_headers(token), timeout=600, follow_redirects=True) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
    except httpx.HTTPStatusError:
        raise BackupError("Google refused the download — the file may have been deleted from Drive.")
    except httpx.HTTPError:
        raise BackupError("Could not reach Google Drive — check the school's internet connection.")
    return dest


def drive_file_name(sa_json: str, file_id: str) -> str:
    """Look up a Drive file's name (used to give downloads their real filename)."""
    sa = _load_service_account(sa_json)
    token = _drive_access_token(sa)
    try:
        resp = httpx.get(
            f"{DRIVE_FILES_URL}/{file_id}",
            params={"fields": "name", "supportsAllDrives": True},
            headers=_drive_headers(token), timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("name") or f"piassess_drive_{file_id}.zip"
    except httpx.HTTPStatusError:
        raise BackupError("Google refused the download — the file may have been deleted from Drive.")
    except httpx.HTTPError:
        raise BackupError("Could not reach Google Drive — check the school's internet connection.")


# ---------------------------------------------------------------- auto-backup
def last_backup_time() -> datetime | None:
    files = list(config.BACKUP_DIR.glob("piassess_backup_*.zip"))
    if not files:
        return None
    return datetime.fromtimestamp(max(f.stat().st_mtime for f in files), tz=timezone.utc)


def maybe_run_auto_backup() -> str | None:
    """Run a backup (and Drive upload when configured) if the schedule says it is due.

    Called hourly from the background thread started at app startup.
    Returns a description of what happened, or None when nothing was due.
    """
    from ..database import SessionLocal
    from ..services.common import get_setting

    db = SessionLocal()
    try:
        if (get_setting(db, "backup_auto") or "0") != "1":
            return None
        try:
            interval_hours = int(get_setting(db, "backup_interval_hours") or "24")
        except ValueError:
            interval_hours = 24

        last = last_backup_time()
        if last is not None:
            age_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
            if age_hours < interval_hours:
                return None

        result = create_backup(db)
        note = f"Automatic backup created: {result['name']}"

        sa_json = get_setting(db, "gdrive_service_account") or ""
        folder_id = get_setting(db, "gdrive_folder_id") or ""
        if sa_json.strip() and folder_id.strip():
            try:
                drive_upload(sa_json, folder_id, Path(result["path"]))
                set_setting(db, "gdrive_last_upload", datetime.now(timezone.utc).isoformat())
                note += " and uploaded to Google Drive"
            except BackupError as exc:
                note += f" (Google Drive upload failed: {exc})"
        return note
    finally:
        db.close()


def auto_backup_worker() -> None:
    """Background loop: first check shortly after startup, then once an hour, forever."""
    import time as _time
    _time.sleep(120)  # let the app finish starting up
    while True:
        try:
            maybe_run_auto_backup()
        except Exception:
            pass  # the next hourly check retries; never crash the app on a backup hiccup
        _time.sleep(3600)
