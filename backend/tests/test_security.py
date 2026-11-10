"""Security: auth, CSRF, permissions, ranking/math utility correctness."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.security import hash_password, verify_password


def test_password_hash_roundtrip():
    h = hash_password("S3cure-pass!")
    assert h != "S3cure-pass!"
    assert verify_password("S3cure-pass!", h)
    assert not verify_password("wrong", h)


def test_unauthenticated_requests_blocked(client):
    # fresh client without the login cookie
    fresh = TestClient(client.app)
    r = fresh.get("/api/students")
    assert r.status_code == 401


def test_csrf_required_for_writes(client, class_id):
    import httpx

    cookie = client.cookies.get("piassess_session")
    fresh = TestClient(client.app)
    fresh.cookies.set("piassess_session", cookie)
    r = fresh.post("/api/students", json={"full_name": "No CSRF", "class_id": class_id})
    assert r.status_code == 403


def test_viewer_cannot_create_students(client):
    # create a viewer, then try a write with their session
    r = client.post("/api/settings/users", json={
        "username": "viewy", "password": "ViewerPass1", "full_name": "View Only", "role": "viewer",
    })
    assert r.status_code == 200, r.text
    fresh = TestClient(client.app)
    r = fresh.post("/api/auth/login", json={"username": "viewy", "password": "ViewerPass1"})
    token = r.json()["csrf_token"]
    fresh.headers.update({"X-CSRF-Token": token})
    r = fresh.post("/api/students", json={"full_name": "Sneaky", "class_id": 1})
    assert r.status_code == 403


def test_weak_password_rejected(client):
    r = client.post("/api/settings/users", json={
        "username": "shorty", "password": "abc", "full_name": "X", "role": "viewer",
    })
    assert r.status_code == 400


def test_competition_ranking():
    from app.services.common import competition_rank

    totals = [300, 280, 280, 250, 220]
    assert competition_rank(totals) == [1, 2, 2, 4, 5]
    assert competition_rank([100, 100, 100]) == [1, 1, 1]


def test_wrong_login_rate_limited(client):
    fresh = TestClient(client.app)
    responses = [
        fresh.post("/api/auth/login", json={"username": "admin", "password": "nope"})
        for _ in range(12)
    ]
    assert any(r.status_code == 429 for r in responses)
