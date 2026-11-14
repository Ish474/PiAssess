# PiAssess — Academic Evaluation Suite

**Pi World School, Forbesganj, Bihar · Academic Session 2026–27**

PiAssess manages the complete examination lifecycle: students → classes & subjects →
AI question papers with verified answer keys → printable OMR sheets → scanned-sheet
evaluation (OpenCV) → results, rankings, report cards and analytics.

Built as a **local, offline-friendly Windows application**: one server, one browser tab,
no cloud dependency. All features (Phases 1–10) are available.

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

## 4. What PiAssess can do

- **Students** — full student database with admission numbers, import wizard (CSV),
  profile dialogs, exports.
- **Academics** — classes, sections, subjects, teachers, academic year management.
- **Examinations** — create exams, manage question papers, export PDF/DOCX, OMR sheets.
- **AI question generator** — generate questions with an AI provider, edit drafts,
  store in the question bank with SymPy-verified answer keys.
- **OMR designer** — design printable OMR sheets; print-ready templates.
- **OMR scanning & evaluation** — upload scanned sheets, OpenCV-based bubble
  detection, manual response correction, assign to students, process results.
- **Results & rankings** — automatic scoring, competition ranking (1, 2, 2, 4),
  report cards.
- **Documents** — generate and export printable documents.
- **Analytics** — dashboard with charts and summaries.
- **Settings** — users & roles, school profile & logo, backup & data, AI provider config.

## 5. Project layout

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
│   │   │                     questions · papers · OMR scans · documents
│   │   │                     settings · AI
│   │   └── services/         audit trail, student codes, import engine
│   ├── tests/                pytest suite (62 tests) + live smoke test
│   └── data/                 piassess.db · uploads · backups   ← all school data
└── frontend/                 React 18 + TypeScript + Vite + Tailwind
    └── src/
        ├── components/       design system, layout, dialogs
        └── pages/            dashboard · students (+ import wizard) · academics
                              exams · question bank · AI generator · OMR designer
                              OMR processing · results · documents · settings
```

## 6. Security

- Passwords hashed with **bcrypt**; sessions are HttpOnly cookies with CSRF double-checks.
- Role-based access: **Administrator / Exam Controller / Teacher / Viewer**.
- Rate limiting on sign-in and API traffic; audit log of every mutation.
- API keys may be provided via environment variables
  (`PIASSESS_AI_API_KEY`, `PIASSESS_AI_BASE_URL`, `PIASSESS_AI_MODEL`) — never in source code.
- Student data is never exposed without sign-in.

## 7. Tests

```
cd backend
..\ .venv\Scripts\python.exe -m pytest
```
62 automated tests cover: student ID generation & uniqueness, CRUD, duplicate admission
numbers, CSV import mapping/validation, exports, authentication, CSRF, role permissions,
password policy, rate limiting, competition ranking (1, 2, 2, 4), question bank,
OMR scanning, results and more.

Synthetic demo data (no real students): `cd backend` then
`..\.venv\Scripts\python.exe -m app.seed --demo`.

## 8. Development phases

| Phase | Scope | Status |
|---|---|---|
| 1 | Architecture, database, UI shell, security | ✅ Done |
| 2 | Student database, examination manager | ✅ Done |
| 3 | AI question generator, question bank, answer keys (SymPy verification) | ✅ Done |
| 4 | Question paper designer, templates, PDF/DOCX export | ✅ Done |
| 5 | OMR sheet designer | ✅ Done |
| 6 | OMR scanning & evaluation (OpenCV + NumPy) | ✅ Done |
| 7 | Results, rankings, report cards | ✅ Done |
| 8 | Analytics | ✅ Done |
| 9 | Security hardening & extended testing | ✅ Done |
| 10 | Packaging & deployment | ✅ Done |

All features are available. Modules that are still being polished may show a "Phase N"
badge in the app — there are no fake buttons.

## 9. School logo

The interface ships with a branded π placeholder. Upload the official
Pi World School logo in **Settings → School → Upload Official Logo** — it then appears
throughout the app and on printed documents. The file itself is stored in
`backend/data/uploads/logos/`.

## 10. Support

- User manual: `docs/USER_MANUAL.md`
- All school data lives in `backend/data/` — back up that folder regularly.