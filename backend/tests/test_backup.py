"""Backup & restore tests: zip snapshot -> mutate -> restore -> mutation undone."""
from __future__ import annotations

import io
import json


def test_backup_create_restore_roundtrip(client, class_id, monkeypatch, tmp_path):
    from app import config as cfg
    from app.services.backup import create_backup, list_backups

    # keep every backup-related path inside the test sandbox
    backup_dir = tmp_path / "backups"
    uploads = tmp_path / "uploads"
    monkeypatch.setattr(cfg, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(cfg, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(cfg, "LOGO_UPLOAD_DIR", uploads / "logos")
    monkeypatch.setattr(cfg, "DOC_UPLOAD_DIR", uploads / "documents")
    monkeypatch.setattr(cfg, "OMR_SCAN_DIR", uploads / "omr_scans")
    backup_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("logos", "documents", "omr_scans"):
        (uploads / sub).mkdir(parents=True, exist_ok=True)

    # seed some real data: a student and the school logo
    st = client.post("/api/students", json={"full_name": "Keep Me", "class_id": class_id, "roll_no": 3}).json()["id"]
    client.post("/api/settings/logo", files={"file": ("logo.png", bytes(range(64)), "image/png")})

    # -- create the backup
    created = client.post("/api/backups", data={"upload_to_drive": "false"})
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["drive_note"] is None
    assert body["name"].startswith("piassess_backup_")
    assert body["manifest"]["students"] >= 1
    zip_bytes = client.get(f"/api/backups/{body['name']}/download").content
    assert zip_bytes[:2] == b"PK"

    # -- mutate: a second student that must disappear after restore
    gone = client.post("/api/students", json={"full_name": "Delete Me", "class_id": class_id, "roll_no": 4}).json()["id"]
    names = {s["full_name"] for s in client.get(f"/api/students?class_id={class_id}&page_size=100").json()["items"]}
    assert "Delete Me" in names

    # -- restore from the uploaded zip
    restored = client.post("/api/backups/restore",
                           files={"file": (body["name"], io.BytesIO(zip_bytes), "application/zip")})
    assert restored.status_code == 200, restored.text
    assert restored.json()["manifest"]["students"] >= 1

    names = {s["full_name"] for s in client.get(f"/api/students?class_id={class_id}&page_size=100").json()["items"]}
    assert "Keep Me" in names
    assert "Delete Me" not in names

    # the logo came back from the backup too
    logo = client.get("/api/settings/logo")
    assert logo.status_code == 200

    # -- overview lists the backup with honest status
    overview = client.get("/api/backups").json()
    assert overview["status"]["drive_connected"] is False
    assert overview["status"]["auto_enabled"] is False
    assert any(b["name"] == body["name"] for b in overview["backups"])

    # -- delete works
    deleted = client.delete(f"/api/backups/{body['name']}")
    assert deleted.status_code == 200
    assert client.get(f"/api/backups/{body['name']}/download").status_code == 404


def test_backup_restore_rejects_foreign_zip(client, monkeypatch, tmp_path):
    """A zip without a PiAssess manifest is refused with a clear message."""
    import zipfile
    from app import config as cfg

    monkeypatch.setattr(cfg, "BACKUP_DIR", tmp_path / "backups")
    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("some_other_app_data.txt", "hello")
    bad = client.post("/api/backups/restore",
                      files={"file": ("not_ours.zip", io.BytesIO(buf.getvalue()), "application/zip")})
    assert bad.status_code == 400
    assert "not a PiAssess backup" in bad.json()["detail"]


def test_backup_settings_save_and_drive_not_configured(client):
    """Settings persist; Drive endpoints explain what is missing instead of crashing."""
    saved = client.post("/api/backups/settings", data={
        "auto_enabled": "true", "interval_hours": "12", "folder_id": "",
    })
    assert saved.status_code == 200
    assert saved.json()["status"]["auto_enabled"] is True

    no_key = client.post("/api/backups/drive/test")
    assert no_key.status_code == 400
    assert "service-account" in no_key.json()["detail"]

    no_key_list = client.get("/api/backups/drive/files")
    assert no_key_list.status_code == 400

    # a broken key JSON is rejected at save time
    bad_key = client.post("/api/backups/settings", data={"folder_id": "abc"},
                          files={"sa_file": ("key.json", b"not json", "application/json")})
    assert bad_key.status_code == 400
    assert "service-account" in bad_key.json()["detail"]
