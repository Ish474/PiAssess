"""Services: audit trail and student ID generation."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..database import utcnow
from ..models import AuditLog, Setting, Student


def log_action(db: Session, user, action: str, entity: str = "", entity_id=None, details: str = "") -> None:
    db.add(AuditLog(
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", "system"),
        action=action,
        entity=entity,
        entity_id=str(entity_id or ""),
        details=details,
    ))


# ---------------------------------------------------------------- settings helpers
DEFAULTS: dict[str, str] = {
    "school_name": "Pi World School",
    "school_address": "Forbesganj, Bihar, India",
    "school_tagline": "Academic Evaluation Suite",
    "academic_session": "2026-27",
    "student_id_prefix": "APWS",
    "passing_marks_default": "33",
    "exam_types": "Weekly Test|Monthly Test|Unit Test|Half-Yearly Examination|Annual Examination|Practice Test|Custom Examination",
    "default_question_template": "Pi-Edge Academic",
    "ai_provider": "",
    "ai_base_url": "",
    "ai_model": "",
    "ai_api_key": "",
    "logo_path": "",
}


def get_setting(db: Session, key: str) -> str:
    row = db.get(Setting, key)
    if row is not None:
        return row.value
    return DEFAULTS.get(key, "")


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value, updated_at=utcnow()))
    else:
        row.value = value
        row.updated_at = utcnow()


# ---------------------------------------------------------------- student codes
def generate_student_codes(db: Session, count: int) -> list[str]:
    """Generate `count` unique student codes atomically enough for a single-school app.

    Format: PREFIX-YYYY-NNNN where YYYY comes from the academic session start year.
    """
    prefix = get_setting(db, "student_id_prefix") or "APWS"
    session_str = get_setting(db, "academic_session") or "2026-27"
    year = session_str.split("-")[0].strip() or "2026"

    base = f"{prefix}-{year}-"
    last = (
        db.query(Student)
        .filter(Student.student_code.like(f"{base}%"))
        .order_by(Student.student_code.desc())
        .first()
    )
    seq = int(last.student_code.rsplit("-", 1)[1]) if last else 0
    codes = [f"{base}{seq + i + 1:04d}" for i in range(count)]
    # defensive: guarantee uniqueness against any stray codes
    existing = {c[0] for c in db.query(Student.student_code).filter(Student.student_code.in_(codes)).all()}
    while {c for c in codes if c in existing}:
        seq = seq + len(codes)
        codes = [f"{base}{seq + i + 1:04d}" for i in range(len(codes))]
        existing = {c[0] for c in db.query(Student.student_code).filter(Student.student_code.in_(codes)).all()}
    return codes


def competition_rank(totals: list[float]) -> list[int]:
    """Competition ranking ("1, 2, 2, 4" style): equal totals share a rank, next rank skips.

    >>> competition_rank([300, 280, 280, 250, 220])
    [1, 2, 2, 4, 5]
    """
    sorted_desc = sorted(totals, reverse=True)
    first_position: dict[float, int] = {}
    for position, total in enumerate(sorted_desc, start=1):
        first_position.setdefault(total, position)
    return [first_position[t] for t in totals]
