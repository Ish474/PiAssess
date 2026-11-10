"""Class, section and subject management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from ..database import get_db
from ..models import Klass, Section, Student, Subject
from ..schemas import ClassIn, ClassOut, SectionIn, SubjectIn
from ..security import require_roles
from ..services.common import log_action

router = APIRouter(prefix="/api/academics", tags=["academics"])

MANAGE = require_roles("admin", "exam_controller")


@router.get("/classes", response_model=list[ClassOut])
def list_classes(db=Depends(get_db), _cu=Depends(require_roles())):
    classes = db.query(Klass).order_by(Klass.level, Klass.name).all()
    counts = dict(db.execute(select(Student.class_id, func.count(Student.id)).group_by(Student.class_id)).all())
    out = []
    for k in classes:
        co = ClassOut.model_validate(k)
        co.student_count = counts.get(k.id, 0)
        out.append(co)
    return out


@router.post("/classes", response_model=ClassOut)
def create_class(payload: ClassIn, cu=Depends(MANAGE), db=Depends(get_db)):
    name = payload.name.strip()
    if db.query(Klass).filter(func.lower(Klass.name) == name.lower()).first():
        raise HTTPException(status_code=409, detail=f"A class named \"{name}\" already exists.")
    k = Klass(name=name, level=payload.level)
    db.add(k)
    db.flush()
    log_action(db, cu, "create", "class", k.id, f"Created class {name}")
    db.commit()
    return ClassOut.model_validate(k)


@router.put("/classes/{class_id}", response_model=ClassOut)
def rename_class(class_id: int, payload: ClassIn, cu=Depends(MANAGE), db=Depends(get_db)):
    k = db.get(Klass, class_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Class not found.")
    name = payload.name.strip()
    dup = db.query(Klass).filter(func.lower(Klass.name) == name.lower(), Klass.id != class_id).first()
    if dup:
        raise HTTPException(status_code=409, detail=f"A class named \"{name}\" already exists.")
    old = k.name
    k.name, k.level = name, payload.level
    log_action(db, cu, "update", "class", k.id, f"Renamed class {old} to {name}")
    db.commit()
    return ClassOut.model_validate(k)


@router.delete("/classes/{class_id}")
def delete_class(class_id: int, cu=Depends(MANAGE), db=Depends(get_db)):
    k = db.get(Klass, class_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Class not found.")
    n_students = db.query(Student).filter(Student.class_id == class_id).count()
    if n_students:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete {k.name}: {n_students} student(s) are still assigned to it. Move them to another class first.",
        )
    log_action(db, cu, "delete", "class", class_id, f"Deleted class {k.name}")
    db.delete(k)
    db.commit()
    return {"ok": True}


@router.post("/classes/{class_id}/sections", response_model=list)
def add_section(class_id: int, payload: SectionIn, cu=Depends(MANAGE), db=Depends(get_db)):
    k = db.get(Klass, class_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Class not found.")
    name = payload.name.strip().upper()
    if db.query(Section).filter(Section.class_id == class_id, func.lower(Section.name) == name.lower()).first():
        raise HTTPException(status_code=409, detail=f"Section {name} already exists in {k.name}.")
    s = Section(class_id=class_id, name=name)
    db.add(s)
    db.flush()
    log_action(db, cu, "create", "section", s.id, f"Added section {name} to {k.name}")
    db.commit()
    return {"ok": True, "id": s.id, "name": name}


@router.delete("/classes/{class_id}/sections/{section_id}")
def delete_section(class_id: int, section_id: int, cu=Depends(MANAGE), db=Depends(get_db)):
    s = db.get(Section, section_id)
    if s is None or s.class_id != class_id:
        raise HTTPException(status_code=404, detail="Section not found.")
    n = db.query(Student).filter(Student.section_id == section_id).count()
    if n:
        raise HTTPException(status_code=409, detail=f"Cannot delete section {s.name}: {n} student(s) are assigned to it.")
    log_action(db, cu, "delete", "section", section_id, f"Deleted section {s.name}")
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.post("/classes/{class_id}/subjects")
def add_subject(class_id: int, payload: SubjectIn, cu=Depends(MANAGE), db=Depends(get_db)):
    k = db.get(Klass, class_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Class not found.")
    name = payload.name.strip()
    if db.query(Subject).filter(Subject.class_id == class_id, func.lower(Subject.name) == name.lower()).first():
        raise HTTPException(status_code=409, detail=f"Subject \"{name}\" already exists in {k.name}.")
    s = Subject(class_id=class_id, name=name, code=payload.code.strip(), max_marks=payload.max_marks)
    db.add(s)
    db.flush()
    log_action(db, cu, "create", "subject", s.id, f"Added subject {name} to {k.name}")
    db.commit()
    return {"ok": True, "id": s.id}


@router.put("/subjects/{subject_id}")
def update_subject(subject_id: int, payload: SubjectIn, cu=Depends(MANAGE), db=Depends(get_db)):
    s = db.get(Subject, subject_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Subject not found.")
    s.name, s.code, s.max_marks = payload.name.strip(), payload.code.strip(), payload.max_marks
    log_action(db, cu, "update", "subject", subject_id, f"Updated subject {s.name}")
    db.commit()
    return {"ok": True}


@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int, cu=Depends(MANAGE), db=Depends(get_db)):
    s = db.get(Subject, subject_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Subject not found.")
    log_action(db, cu, "delete", "subject", subject_id, f"Deleted subject {s.name}")
    db.delete(s)
    db.commit()
    return {"ok": True}
