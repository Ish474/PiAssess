"""Shared pytest fixtures: isolated temp database, cleaned between tests, signed-in client."""
from __future__ import annotations

import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp(prefix="piassess_test_")
os.environ["PIASSESS_DATA_DIR"] = _tmp


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.database import Base, SessionLocal, engine
    from app.main import app as fastapi_app
    from app.security import api_limiter, login_limiter

    Base.metadata.create_all(bind=engine)
    login_limiter._hits.clear()
    api_limiter._hits.clear()

    with TestClient(fastapi_app) as c:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert r.status_code == 200, r.text
        c.headers.update({"X-CSRF-Token": r.json()["csrf_token"]})
        yield c

    # wipe all data between tests (reverse dependency order)
    db = SessionLocal()
    try:
        from app.database import Base as B
        for table in reversed(B.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def class_id(client):
    return client.get("/api/academics/classes").json()[0]["id"]
