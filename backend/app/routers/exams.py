"""Examination Manager: create, edit and track examinations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import joinedload

from ..database import get_db
from ..models import Examination, EXAM_TYPES, Klass, Student
from ..schemas import ExamIn, ExamListOut, ExamOut
from ..security import require_roles
from ..services.common import get_setting, log_action

router = APIRouter(prefix="/api/exams", tags=["exams"])

reader_dep = Depends(require_roles())
writer_dep = require_roles("admin", "exam_controller", "teacher")
manage_dep = require_roles("admin", "exam_controller")


def _to_out(db, e: Examination) -> ExamOut:
    o = ExamOut(
        id=e.id, name=e.name, exam_type=e.exam_type, academic_session=e.academic_session,
        class_id=e.class_id, subject_id=e.subject_id, exam_date=e.exam_date,
        max_marks=e.max_marks, passing_marks=e.passing_marks, duration_minutes=e.duration_minutes,
        negative_marks=e.negative_marks,
        status=e.status, instructions=e.instructions, created_at=e.created_at,
        class_name=e.klass.name if e.klass else "",
        subject_name=e.subject.name if e.subject else "",
        student_count=db.query(Student).filter(Student.class_id == e.class_id).count(),
    )
    return o


@router.get("/meta")
def exam_meta(_cu=reader_dep, db=Depends(get_db)):
    return {"exam_types": list(EXAM_TYPES), "default_session": get_setting(db, "academic_session")}


@router.get("", response_model=ExamListOut)
def list_exams(
    search: str = "",
    class_id: int | None = None,
    status: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db=Depends(get_db),
    _cu=reader_dep,
):
    q = db.query(Examination).options(joinedload(Examination.klass), joinedload(Examination.subject))
    if search.strip():
        q = q.filter(Examination.name.ilike(f"%{search.strip()}%"))
    if class_id:
        q = q.filter(Examination.class_id == class_id)
    if status:
        q = q.filter(Examination.status == status)
    total = q.count()
    items = q.order_by(Examination.exam_date.desc().nullslast(), Examination.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ExamListOut(items=[_to_out(db, e) for e in items], total=total)


@router.post("", response_model=ExamOut)
def create_exam(payload: ExamIn, cu=Depends(writer_dep), db=Depends(get_db)):
    if db.get(Klass, payload.class_id) is None:
        raise HTTPException(status_code=400, detail="The selected class does not exist.")
    if not payload.academic_session:
        payload.academic_session = get_setting(db, "academic_session")
    e = Examination(**payload.model_dump(), created_by=cu.username)
    db.add(e)
    db.flush()
    log_action(db, cu, "create", "exam", e.id, f"Created examination \"{e.name}\"")
    db.commit()
    db.refresh(e)
    return _to_out(db, e)


@router.get("/{exam_id}", response_model=ExamOut)
def get_exam(exam_id: int, db=Depends(get_db), _cu=reader_dep):
    e = db.query(Examination).filter(Examination.id == exam_id).first()
    if e is None:
        raise HTTPException(status_code=404, detail="Examination not found.")
    return _to_out(db, e)


@router.put("/{exam_id}", response_model=ExamOut)
def update_exam(exam_id: int, payload: ExamIn, cu=Depends(writer_dep), db=Depends(get_db)):
    e = db.get(Examination, exam_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Examination not found.")
    if db.get(Klass, payload.class_id) is None:
        raise HTTPException(status_code=400, detail="The selected class does not exist.")
    for k, v in payload.model_dump().items():
        setattr(e, k, v)
    log_action(db, cu, "update", "exam", e.id, f"Updated examination \"{e.name}\"")
    db.commit()
    db.refresh(e)
    return _to_out(db, e)


@router.delete("/{exam_id}")
def delete_exam(exam_id: int, cu=Depends(manage_dep), db=Depends(get_db)):
    e = db.get(Examination, exam_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Examination not found.")
    log_action(db, cu, "delete", "exam", exam_id, f"Deleted examination \"{e.name}\"")
    db.delete(e)
    db.commit()
    return {"ok": True}
