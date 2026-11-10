"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import DIFFICULTIES, QUESTION_TYPES, ROLES, EXAM_TYPES

# ---------------------------------------------------------------- auth
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None

    model_config = ConfigDict(from_attributes=True)



class LoginOut(BaseModel):
    user: UserOut
    csrf_token: str


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(min_length=1, max_length=128)  # strength enforced with a friendly message in the router
    full_name: str = Field(max_length=120)
    role: Literal[tuple(ROLES)]  # type: ignore[valid-type]


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    role: Literal[tuple(ROLES)] | None = None  # type: ignore[valid-type]
    is_active: bool | None = None


class UserSetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------- academics
class SectionOut(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)



class SubjectOut(BaseModel):
    id: int
    name: str
    code: str
    max_marks: int
    model_config = ConfigDict(from_attributes=True)



class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(default="", max_length=24)
    max_marks: int = Field(default=100, ge=1, le=1000)


class ClassOut(BaseModel):
    id: int
    name: str
    level: int | None
    sections: list[SectionOut]
    subjects: list[SubjectOut]
    student_count: int = 0
    model_config = ConfigDict(from_attributes=True)



class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    level: int | None = Field(default=None, ge=0, le=14)


class SectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=16)


# ---------------------------------------------------------------- students
class StudentIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    admission_no: str = Field(default="", max_length=32)
    father_name: str = Field(default="", max_length=160)
    mother_name: str = Field(default="", max_length=160)
    class_id: int
    section_id: int | None = None
    roll_no: int | None = Field(default=None, ge=1, le=999)
    dob: date | None = None
    gender: str = Field(default="", max_length=16)
    phone: str = Field(default="", max_length=32)
    email: str = Field(default="", max_length=160)
    address: str = Field(default="", max_length=500)
    admission_date: date | None = None
    status: Literal["active", "inactive", "passed", "transferred"] = "active"

    @field_validator("gender")
    @classmethod
    def norm_gender(cls, v: str) -> str:
        v = v.strip().lower()
        return v if v in ("male", "female", "other") else ""


class StudentOut(StudentIn):
    id: int
    student_code: str
    class_name: str = ""
    section_name: str = ""
    created_at: datetime


class StudentListOut(BaseModel):
    items: list[StudentOut]
    total: int
    page: int
    page_size: int


class ImportPreviewRow(BaseModel):
    row_number: int
    data: dict
    errors: list[str]


class ImportPreviewOut(BaseModel):
    columns: list[str]
    rows: list[ImportPreviewRow]
    valid_count: int
    error_count: int
    duplicate_count: int
    mapping_hint: dict = {}


class ImportConfirmIn(BaseModel):
    rows: list[dict]
    mapping: dict = {}
    send_login_notice: bool = False


class ImportResultOut(BaseModel):
    imported: int
    skipped: int
    first_student_code: str = ""
    codes: list[str] = []


# ---------------------------------------------------------------- exams
class ExamIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    exam_type: str = Field(default=EXAM_TYPES[2], max_length=64)
    academic_session: str = Field(default="", max_length=32)
    class_id: int
    subject_id: int | None = None
    exam_date: date | None = None
    max_marks: int = Field(default=100, ge=1, le=1000)
    passing_marks: int = Field(default=33, ge=0, le=1000)
    negative_marks: float = Field(default=0.0, ge=0, le=100)
    duration_minutes: int = Field(default=60, ge=1, le=600)
    status: Literal["draft", "ready", "published", "archived"] = "draft"
    instructions: str = Field(default="", max_length=4000)


class ExamOut(ExamIn):
    id: int
    class_name: str = ""
    subject_name: str = ""
    student_count: int = 0
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)



class ExamListOut(BaseModel):
    items: list[ExamOut]
    total: int


# ---------------------------------------------------------------- documents
class DocumentOut(BaseModel):
    id: int
    category: str
    title: str
    file_name: str
    mime_type: str
    file_size: int
    uploaded_by: str
    is_archived: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)



class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int


# ---------------------------------------------------------------- question bank (Phase 3)
class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    class_id: int
    subject_id: int | None
    exam_id: int | None
    chapter: str
    topic: str
    qtype: str
    difficulty: str
    marks: int
    text: str
    options: list[str] = []
    correct_answer: str
    explanation: str
    keywords: list[str] = []
    marking_notes: str
    check_expression: str
    verification: str
    verification_note: str
    source: str
    created_at: datetime


class QuestionListOut(BaseModel):
    items: list[QuestionOut]
    total: int
    page: int
    page_size: int


class QuestionIn(BaseModel):
    class_id: int
    subject_id: int | None = None
    exam_id: int | None = None
    chapter: str = Field(default="", max_length=200)
    topic: str = Field(default="", max_length=200)
    qtype: Literal[tuple(QUESTION_TYPES.keys())]  # type: ignore[valid-type]
    difficulty: Literal[tuple(DIFFICULTIES)] = "moderate"  # type: ignore[valid-type]
    marks: int = Field(default=1, ge=1, le=100)
    text: str = Field(min_length=1, max_length=4000)
    options: list[str] = Field(default_factory=list, max_length=10)
    correct_answer: str = Field(default="", max_length=4000)
    explanation: str = Field(default="", max_length=4000)
    keywords: list[str] = Field(default_factory=list, max_length=10)
    marking_notes: str = Field(default="", max_length=2000)
    check_expression: str = Field(default="", max_length=500)


class QuestionUpdateIn(BaseModel):
    chapter: str | None = Field(default=None, max_length=200)
    topic: str | None = Field(default=None, max_length=200)
    qtype: Literal[tuple(QUESTION_TYPES.keys())] | None = None  # type: ignore[valid-type]
    difficulty: Literal[tuple(DIFFICULTIES)] | None = None  # type: ignore[valid-type]
    marks: int | None = Field(default=None, ge=1, le=100)
    text: str | None = Field(default=None, min_length=1, max_length=4000)
    options: list[str] | None = None
    correct_answer: str | None = Field(default=None, max_length=4000)
    explanation: str | None = Field(default=None, max_length=4000)
    keywords: list[str] | None = None
    marking_notes: str | None = Field(default=None, max_length=2000)
    check_expression: str | None = Field(default=None, max_length=500)


class VerificationIn(BaseModel):
    verification: Literal["verified", "needs_review", "unverified"]
    note: str = Field(default="", max_length=300)


class GenerateTypeIn(BaseModel):
    type: Literal[tuple(QUESTION_TYPES.keys())]  # type: ignore[valid-type]
    count: int = Field(ge=1, le=50)
    difficulty: Literal[tuple(DIFFICULTIES) + ("mixed",)] = "mixed"  # type: ignore[valid-type]
    marks: int = Field(default=1, ge=1, le=100)


class GenerateIn(BaseModel):
    class_id: int
    subject_id: int | None = None
    chapters: str = Field(default="", max_length=1000)
    content_text: str = Field(default="", max_length=200_000)
    types: list[GenerateTypeIn] = Field(min_length=1, max_length=13)
    extra_instructions: str = Field(default="", max_length=2000)
    avoid_texts: list[str] = Field(default_factory=list, max_length=40)


class DraftQuestionOut(BaseModel):
    qtype: str = "short"
    difficulty: str = "moderate"
    marks: int = 1
    text: str = ""
    options: list[str] = []
    correct_answer: str = ""
    explanation: str = ""
    keywords: list[str] = []
    marking_notes: str = ""
    check_expression: str = ""
    verification: str = "unverified"
    verification_note: str = ""


class GenerateOut(BaseModel):
    questions: list[DraftQuestionOut]
    provider: str
    model: str
    skipped: int = 0
    skipped_notes: list[str] = []


class BulkSaveIn(BaseModel):
    class_id: int
    subject_id: int | None = None
    exam_id: int | None = None
    questions: list[DraftQuestionOut] = Field(min_length=1, max_length=100)


class BulkSaveOut(BaseModel):
    saved: int
    duplicates_skipped: int
    ids: list[int]
    paper_id: int | None = None


# ---------------------------------------------------------------- question papers
class PaperItemIn(BaseModel):
    question_id: int
    position: int = Field(ge=0, le=500)
    marks: int = Field(ge=1, le=100)


class PaperUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    instructions: str | None = Field(default=None, max_length=4000)
    items: list[PaperItemIn] | None = None


class PaperItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    question_id: int
    position: int
    marks: int
    question: QuestionOut


class PaperOut(BaseModel):
    id: int
    exam_id: int
    class_id: int = 0
    title: str
    instructions: str
    total_marks: int
    exam_name: str = ""
    class_name: str = ""
    subject_name: str = ""
    exam_date: date | None = None
    duration_minutes: int = 0
    academic_session: str = ""
    exam_max_marks: int = 0
    negative_marks: float = 0.0
    items: list[PaperItemOut] = []


# ---------------------------------------------------------------- settings / dashboard
class SettingsOut(BaseModel):
    school_name: str = "Pi World School"
    school_address: str = "Forbesganj, Bihar, India"
    school_tagline: str = "Academic Evaluation Suite"
    academic_session: str = "2026-27"
    student_id_prefix: str = "APWS"
    passing_marks_default: int = 33
    exam_types: list[str] = list(EXAM_TYPES)
    default_question_template: str = "Pi-Edge Academic"
    ai_provider: str = ""
    ai_base_url: str = ""
    ai_model: str = ""
    ai_api_key_set: bool = False
    ai_api_key_masked: str = ""
    logo_url: str = ""


class SettingsIn(BaseModel):
    school_name: str | None = Field(default=None, max_length=120)
    school_address: str | None = Field(default=None, max_length=300)
    school_tagline: str | None = Field(default=None, max_length=120)
    academic_session: str | None = Field(default=None, max_length=32)
    student_id_prefix: str | None = Field(default=None, max_length=10)
    passing_marks_default: int | None = Field(default=None, ge=0, le=1000)
    exam_types: list[str] | None = None
    default_question_template: str | None = Field(default=None, max_length=64)
    ai_provider: str | None = Field(default=None, max_length=64)
    ai_base_url: str | None = Field(default=None, max_length=300)
    ai_model: str | None = Field(default=None, max_length=120)
    ai_api_key: str | None = Field(default=None, max_length=300)


class ActivityOut(BaseModel):
    id: int
    username: str
    action: str
    entity: str
    entity_id: str
    details: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)



class RecentExamOut(BaseModel):
    id: int
    name: str
    class_name: str
    exam_date: date | None
    student_count: int
    status: str
    results_available: bool


class DashboardOut(BaseModel):
    total_students: int
    total_examinations: int
    total_subjects: int
    average_performance: float | None  # None until results exist (Phase 7)
    recent_exams: list[RecentExamOut]
    activity: list[ActivityOut]
    checklist: dict[str, bool]
