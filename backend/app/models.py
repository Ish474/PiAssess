"""PiAssess relational schema.

SQLite now, PostgreSQL later: every column type used here is portable.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base, utcnow

# ---------------------------------------------------------------- roles
ROLE_ADMIN = "admin"
ROLE_EXAM_CONTROLLER = "exam_controller"
ROLE_TEACHER = "teacher"
ROLE_VIEWER = "viewer"
ROLES = (ROLE_ADMIN, ROLE_EXAM_CONTROLLER, ROLE_TEACHER, ROLE_VIEWER)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(32), default=ROLE_TEACHER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    csrf_token: Mapped[str] = mapped_column(String(64))
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


# ---------------------------------------------------------------- academics
class Klass(Base):
    __tablename__ = "classes"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..12 where sensible
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    sections: Mapped[list["Section"]] = relationship(back_populates="klass", cascade="all, delete-orphan")
    subjects: Mapped[list["Subject"]] = relationship(back_populates="klass", cascade="all, delete-orphan")


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("class_id", "name", name="uq_section_per_class"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(16))
    klass: Mapped[Klass] = relationship(back_populates="sections")


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("class_id", "name", name="uq_subject_per_class"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(24), default="")
    max_marks: Mapped[int] = mapped_column(Integer, default=100)
    klass: Mapped["Klass"] = relationship(back_populates="subjects")


# ---------------------------------------------------------------- students
class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # APWS-2026-0001
    admission_no: Mapped[str] = mapped_column(String(32), default="", index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    father_name: Mapped[str] = mapped_column(String(160), default="")
    mother_name: Mapped[str] = mapped_column(String(160), default="")
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id"), nullable=True)
    roll_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str] = mapped_column(String(16), default="")  # male/female/other/"" 
    phone: Mapped[str] = mapped_column(String(32), default="")
    email: Mapped[str] = mapped_column(String(160), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    admission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/inactive/passed/transferred
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    klass: Mapped[Klass] = relationship()
    section: Mapped[Section | None] = relationship()


Index("ix_students_class_section", Student.class_id, Student.section_id)


# ---------------------------------------------------------------- examinations
EXAM_STATUS = ("draft", "ready", "published", "archived")
EXAM_TYPES = (
    "Weekly Test",
    "Monthly Test",
    "Unit Test",
    "Half-Yearly Examination",
    "Annual Examination",
    "Practice Test",
    "Custom Examination",
)


class Examination(Base):
    __tablename__ = "examinations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    exam_type: Mapped[str] = mapped_column(String(64), default="Unit Test")
    academic_session: Mapped[str] = mapped_column(String(32), default="")
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    max_marks: Mapped[int] = mapped_column(Integer, default=100)
    passing_marks: Mapped[int] = mapped_column(Integer, default=33)
    negative_marks: Mapped[float] = mapped_column(Float, default=0.0)  # deducted per wrong answer (0 = none)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    instructions: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    klass: Mapped[Klass] = relationship()
    subject: Mapped[Subject | None] = relationship()


# ---------------------------------------------------------------- question bank (Phase 3)
QUESTION_TYPES: dict[str, str] = {
    "mcq": "Multiple Choice Question",
    "fill_blank": "Fill in the Blank",
    "true_false": "True or False",
    "match_following": "Match the Following",
    "very_short": "Very Short Answer",
    "short": "Short Answer",
    "long": "Long Answer",
    "numerical": "Numerical Problem",
    "case_based": "Case-Based Question",
    "assertion_reason": "Assertion and Reason",
    "logical_reasoning": "Logical Reasoning",
    "application": "Application-Based Question",
    "hots": "HOTS (Higher Order Thinking)",
}
DIFFICULTIES = ("easy", "moderate", "challenging", "advanced")
VERIFICATION_STATES = ("unverified", "needs_review", "verified")


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    exam_id: Mapped[int | None] = mapped_column(ForeignKey("examinations.id", ondelete="SET NULL"), nullable=True)
    chapter: Mapped[str] = mapped_column(String(200), default="", index=True)
    topic: Mapped[str] = mapped_column(String(200), default="")
    qtype: Mapped[str] = mapped_column(String(32), index=True)          # key of QUESTION_TYPES
    difficulty: Mapped[str] = mapped_column(String(16), default="moderate")
    marks: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text)
    options_json: Mapped[str] = mapped_column(Text, default="[]")       # JSON list (MCQ / match columns)
    correct_answer: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    keywords_json: Mapped[str] = mapped_column(Text, default="[]")      # JSON list
    marking_notes: Mapped[str] = mapped_column(Text, default="")
    check_expression: Mapped[str] = mapped_column(Text, default="")     # SymPy- verifiable arithmetic
    verification: Mapped[str] = mapped_column(String(16), default="unverified", index=True)
    verification_note: Mapped[str] = mapped_column(String(300), default="")
    source: Mapped[str] = mapped_column(String(16), default="manual")   # ai / manual / import
    content_hash: Mapped[str] = mapped_column(String(64), index=True)   # duplicate detection
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    klass: Mapped[Klass] = relationship()
    subject: Mapped[Subject | None] = relationship()
    exam: Mapped[Examination | None] = relationship()


class QuestionPaper(Base):
    __tablename__ = "question_papers"
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("examinations.id", ondelete="CASCADE"), unique=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    items: Mapped[list["PaperItem"]] = relationship(back_populates="paper", cascade="all, delete-orphan", order_by="PaperItem.position")


class PaperItem(Base):
    __tablename__ = "paper_items"
    __table_args__ = (UniqueConstraint("paper_id", "question_id", name="uq_question_once_per_paper"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("question_papers.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    marks: Mapped[int] = mapped_column(Integer, default=1)

    paper: Mapped[QuestionPaper] = relationship(back_populates="items")
    question: Mapped[Question] = relationship()


# ---------------------------------------------------------------- documents
DOC_CATEGORIES = (
    "Question Papers",
    "Answer Keys",
    "OMR Sheets",
    "Scanned Answer Sheets",
    "Results",
    "Report Cards",
    "Examination Reports",
)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(255))       # original name
    stored_name: Mapped[str] = mapped_column(String(255))     # uuid name on disk
    mime_type: Mapped[str] = mapped_column(String(128), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[str] = mapped_column(String(64), default="")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


# ------------------------------------------------------------- OMR scanning
class OMRScan(Base):
    """One scanned answer sheet and its evaluation result."""
    __tablename__ = "omr_scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("examinations.id"), index=True)
    set_letter: Mapped[str] = mapped_column(String(1), default="A")
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    stored_name: Mapped[str] = mapped_column(String(255))      # uuid name on disk
    original_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending | processing | processed | failed | review
    confidence_band: Mapped[str] = mapped_column(String(8), default="")   # GREEN | YELLOW | RED | ""
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    responses: Mapped[str] = mapped_column(Text, default="[]")   # JSON per-question detail
    error_message: Mapped[str] = mapped_column(Text, default="")
    uploaded_by: Mapped[str] = mapped_column(String(64), default="")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
