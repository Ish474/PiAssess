"""First-run seeding: default admin, classes 1–12, sections, subjects.

Optional demo data (synthetic students + exams) via:  python -m app.seed --demo
"""
from __future__ import annotations

import random
from datetime import date

from .database import SessionLocal, utcnow
from .models import Examination, Klass, Section, Student, Subject, User
from .security import hash_password
from .services.common import generate_student_codes

FIRST_NAMES = ["Aarav", "Ananya", "Rohit", "Priya", "Imran", "Sneha", "Vikash", "Pooja", "Arman", "Kavya",
               "Rahul", "Nisha", "Sameer", "Anjali", "Deepak", "Ritu", "Sahil", "Megha", "Ravi", "Shreya"]
LAST_NAMES = ["Kumar", "Sharma", "Yadav", "Singh", "Das", "Gupta", "Jha", "Mishra", "Paswan", "Verma"]


def seed_defaults(db) -> None:
    if db.query(User).count() == 0:
        db.add(User(
            username="admin",
            password_hash=hash_password("admin123"),
            full_name="School Administrator",
            role="admin",
            must_change_password=True,
        ))
        print("  Created default administrator - username: admin  password: admin123")
        print("  Please change this password after first sign-in (Settings -> Users).")

    if db.query(Klass).count() == 0:
        junior = ["English", "Hindi", "Mathematics", "Science", "Social Science", "Computer"]
        senior = ["English", "Physics", "Chemistry", "Mathematics", "Biology", "Computer Science"]
        for level in range(1, 13):
            k = Klass(name=f"Class {level}", level=level)
            db.add(k)
            db.flush()
            for s in ("A", "B", "C"):
                db.add(Section(class_id=k.id, name=s))
            names = junior if level <= 10 else senior
            for i, subj in enumerate(names):
                db.add(Subject(class_id=k.id, name=subj, code=f"SUB{level}{i + 1:02d}", max_marks=100))
        print("  Created Classes 1-12 with sections A/B/C and default subjects.")
    db.commit()


def seed_demo(db) -> None:
    """Synthetic students and examinations for testing — never real personal data."""
    random.seed(42)
    if db.query(Student).count() > 0:
        print("  Demo data skipped: students already exist.")
        return

    classes = db.query(Klass).order_by(Klass.level).all()
    made = 0
    for k in classes:
        if k.level not in (9, 10):
            continue
        sections = db.query(Section).filter(Section.class_id == k.id).all()
        for sec in sections:
            for roll in range(1, 7):  # 6 synthetic students per section
                name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
                (code,) = generate_student_codes(db, 1)
                db.add(Student(
                    student_code=code,
                    admission_no=f"ADM{made + 1:05d}",
                    full_name=name,
                    father_name=f"{random.choice(FIRST_NAMES)} {LAST_NAMES[made % len(LAST_NAMES)]}",
                    mother_name=f"{random.choice(FIRST_NAMES)} {LAST_NAMES[(made + 3) % len(LAST_NAMES)]}",
                    class_id=k.id,
                    section_id=sec.id,
                    roll_no=roll,
                    dob=date(2010 + (k.level % 4), random.randint(1, 12), random.randint(1, 28)),
                    gender=random.choice(["male", "female"]),
                    phone=f"9{random.randint(100000000, 999999999)}",
                    admission_date=date(2024, 4, 1),
                    status="active",
                ))
                made += 1

    maths = None
    for k in classes:
        if k.level == 10:
            maths = db.query(Subject).filter(Subject.class_id == k.id, Subject.name == "Mathematics").first()
            if maths:
                db.add(Examination(
                    name="Unit Test 1 — Mathematics", exam_type="Unit Test", academic_session="2026-27",
                    class_id=k.id, subject_id=maths.id, exam_date=date(2026, 4, 18),
                    max_marks=40, passing_marks=13, duration_minutes=60, status="ready",
                    instructions="All questions are compulsory. Marks are indicated against each question.",
                    created_by="admin",
                ))
                db.add(Examination(
                    name="Weekly Test — Mathematics (Ch 1–3)", exam_type="Weekly Test", academic_session="2026-27",
                    class_id=k.id, subject_id=maths.id, exam_date=date(2026, 4, 6),
                    max_marks=20, passing_marks=7, duration_minutes=30, status="published",
                    created_by="admin",
                ))
    db.commit()
    print(f"  Created {made} synthetic students and sample examinations.")


def _migrate_sqlite(engine) -> None:
    """Add columns that were introduced after a table already exists.

    ``create_all`` only creates missing *tables*, so new columns on existing
    tables are added here. Idempotent — safe to run on every startup.
    """
    from sqlalchemy import text
    wanted = {
        "examinations": {"negative_marks": "REAL NOT NULL DEFAULT 0"},
        "omr_scans": {"student_id": "INTEGER"},
    }
    with engine.begin() as conn:
        for table, columns in wanted.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for col, ddl in columns.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


def run(demo: bool = False) -> None:
    from .database import Base, engine
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite(engine)
    db = SessionLocal()
    try:
        seed_defaults(db)
        if demo:
            seed_demo(db)
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialise the PiAssess database")
    parser.add_argument("--demo", action="store_true", help="also create synthetic sample data")
    args = parser.parse_args()
    run(demo=args.demo)
    print("Database ready.")
