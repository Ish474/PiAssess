"""PiAssess — FastAPI application entry point."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .database import SessionLocal
from .routers import academics, auth, backups, dashboard, documents, exams, questions, ai as ai_router, omr_scans, papers, settings as settings_router, students
from .security import api_limiter, login_limiter
from .seed import run as seed_run

app = FastAPI(title="PiAssess — Academic Evaluation Suite", version="0.3.0", docs_url=None, redoc_url=None)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(students.router)
app.include_router(academics.router)
app.include_router(exams.router)
app.include_router(documents.router)
app.include_router(settings_router.router)
app.include_router(questions.router)
app.include_router(ai_router.router)
app.include_router(papers.router)
app.include_router(omr_scans.router)
app.include_router(backups.router)


@app.on_event("startup")
def on_startup() -> None:
    seed_run(demo=False)
    import threading
    from .services.backup import auto_backup_worker
    threading.Thread(target=auto_backup_worker, daemon=True, name="auto-backup").start()
    print("PiAssess database ready -> http://localhost:8600")


@app.middleware("http")
async def rate_limit_and_security(request: Request, call_next):
    path = request.url.path
    client_ip = request.client.host if request.client else "unknown"
    if path.startswith("/api/"):
        if path == "/api/auth/login":
            allowed = login_limiter.check(f"login:{client_ip}", limit=10, window_seconds=60)
        else:
            allowed = api_limiter.check(f"api:{client_ip}", limit=600, window_seconds=60)
        if not allowed:
            return JSONResponse({"detail": "Too many requests. Please slow down."}, status_code=429)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


# The static SPA (built frontend) is served for every non-API route.
DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if (DIST_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        candidate = DIST_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
