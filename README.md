# PiAssess — Academic Evaluation Suite

**Pi World School, Forbesganj, Bihar · Academic Session 2026–27**

PiAssess manages the complete examination lifecycle: students → classes & subjects →
AI question papers with verified answer keys → printable OMR sheets → scanned-sheet
evaluation (OpenCV) → results, rankings, report cards and analytics.

Built as a **local, offline-friendly Windows application**: one server, one browser tab,
no cloud dependency.

---

## 1. Quick start (Windows)

1. Install **Python 3.12** (https://www.python.org/downloads — tick *Add Python to PATH*).
   For building the interface the first time you also need **Node.js** (https://nodejs.org).
2. Double-click **`start_piassess.bat`**.
   - First run: it creates the environment, installs dependencies and builds the interface
     (needs internet once). Later runs start instantly and work fully offline.
3. Your browser opens **http://localhost:8600**.
4. Sign in the first time with:
   - Username: `admin`
   - Password: `admin123`
   - **Change this password immediately** in *Settings → Users*.

All data (database, uploads, backups) lives in `backend/data/` — copy that folder to move
or back up the whole system.

## 2. Daily use

- Keep the black console window open while using PiAssess; closing it stops the app.
- Follow the **Getting Started** checklist on the Dashboard.
- Create a backup at the end of each working day: *Settings → Backup & Data*.

## 3. Backup and restore

**Backup** (administrator): *Settings → Backup & Data → Create Backup Now.*
A snapshot is written to `backend/data/backups/` and a copy is downloaded.
Automate it by running this daily:

```
.venv\Scripts\python.exe -c "from app.database import SessionLocal; from app.routers.settings import create_backup; from app.models import User; db=SessionLocal(); create_backup(db.get(User,1), db)"
```
(run from the `backend` folder, or simply use the button).

**Restore:**
1. Close PiAssess (the black window).
2. Replace the file `backend/data/piassess.db` with your backup copy (rename it to `piassess.db`).
3. Start PiAssess again. Everything is back exactly as it was.

## 4. Project layout

```
PiAssess/
├── start_piassess.bat        one-click launcher
├── backend/                  FastAPI server (port 8600)
│   ├── app/
│   │   ├── main.py           app entry, security headers, serves the UI
│   │   ├── config.py         configuration (env-var driven)
│   │   ├── database.py       SQLite WAL via SQLAlchemy 2.0 (PostgreSQL-ready)
│   │   ├── models.py         full relational schema
│   │   ├── security.py       bcrypt, sessions, CSRF, roles, rate limiting
│   │   ├── seed.py           first-run defaults + `--demo` synthetic data
│   │   ├── routers/          auth · dashboard · students · academics · exams
│   │   │                     documents · settings
│   │   └── services/         audit trail, student codes, import engine
│   ├── tests/                pytest suite + live smoke test
│   └── data/                 piassess.db · uploads · backups   ← all school data
└── frontend/                 React 18 + TypeScript + Vite + Tailwind
    └── src/
        ├── components/       design system, layout, dialogs
        └── pages/            dashboard · students (+ import wizard) · academics
                              exams · documents · settings · phase placeholders
```

## 5. Security

- Passwords hashed with **bcrypt**; sessions are HttpOnly cookies with CSRF double-checks.
- Role-based access: **Administrator / Exam Controller / Teacher / Viewer**.
- Rate limiting on sign-in and API traffic; audit log of every mutation.
- API keys may be provided via environment variables
  (`PIASSESS_AI_API_KEY`, `PIASSESS_AI_BASE_URL`, `PIASSESS_AI_MODEL`) — never in source code.
- Student data is never exposed without sign-in.

## 6. Tests

```
cd backend
..\ .venv\Scripts\python.exe -m pytest
```
16 automated tests cover: student ID generation & uniqueness, CRUD, duplicate admission
numbers, CSV import mapping/validation, exports, authentication, CSRF, role permissions,
password policy, rate limiting and competition ranking (1, 2, 2, 4).

Synthetic demo data (no real students): `cd backend` then
`..\.venv\Scripts\python.exe -m app.seed --demo`.

## 7. Development phases

| Phase | Scope | Status |
|---|---|---|
| 1 | Architecture, database, UI shell, security | ✅ Done |
| 2 | Student database, examination manager | ✅ Done |
| 3 | AI question generator, question bank, answer keys (SymPy verification) | Next |
| 4 | Question paper designer, templates, PDF/DOCX export | |
| 5 | OMR sheet designer | |
| 6 | OMR scanning & evaluation (OpenCV + NumPy) | |
| 7 | Results, rankings, report cards | |
| 8 | Analytics | |
| 9 | Security hardening & extended testing | |
| 10 | Packaging & deployment | |

Modules arriving in a later phase are shown honestly in the app with a "Phase N" badge —
there are no fake buttons.

## 8. School logo

The interface ships with a branded π placeholder. Upload the official
Pi World School logo in **Settings → School → Upload Official Logo** — it then appears
throughout the app and on printed documents. The file itself is stored in
`backend/data/uploads/logos/`.
