"""Student database management: CRUD, search, bulk import/export."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from .. import config
from ..database import get_db
from ..models import Klass, Section, Student
from ..schemas import (
    ImportConfirmIn,
    ImportPreviewOut,
    ImportResultOut,
    StudentIn,
    StudentListOut,
    StudentOut,
)
from ..security import require_roles
from ..services.common import generate_student_codes, log_action
from ..services.imports import (
    FIELD_LABELS,
    MAX_IMPORT_ROWS,
    guess_mapping,
    read_tabular,
    validate_rows,
)

router = APIRouter(prefix="/api/students", tags=["students"])

reader_dep = Depends(require_roles())          # any signed-in role may read (viewer is read-only by CSRF+role gates)
writer_dep = require_roles("admin", "exam_controller", "teacher")


def _to_out(s: Student) -> StudentOut:
    o = StudentOut(
        id=s.id,
        student_code=s.student_code,
        admission_no=s.admission_no,
        full_name=s.full_name,
        father_name=s.father_name,
        mother_name=s.mother_name,
        class_id=s.class_id,
        section_id=s.section_id,
        roll_no=s.roll_no,
        dob=s.dob,
        gender=s.gender,
        phone=s.phone,
        email=s.email,
        address=s.address,
        admission_date=s.admission_date,
        status=s.status,
        created_at=s.created_at,
        class_name=s.klass.name if s.klass else "",
        section_name=s.section.name if s.section else "",
    )
    return o


def _validate_links(db, payload: StudentIn) -> None:
    klass = db.get(Klass, payload.class_id)
    if klass is None:
        raise HTTPException(status_code=400, detail="The selected class does not exist.")
    if payload.section_id is not None:
        sec = db.get(Section, payload.section_id)
        if sec is None or sec.class_id != payload.class_id:
            raise HTTPException(status_code=400, detail="The selected section does not belong to that class.")
    if payload.email and ("@" not in payload.email):
        raise HTTPException(status_code=400, detail="The email address does not look valid.")


@router.get("", response_model=StudentListOut)
def list_students(
    search: str = "",
    class_id: int | None = None,
    section_id: int | None = None,
    status: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db=Depends(get_db),
    _cu=reader_dep,
):
    q = db.query(Student).options(joinedload(Student.klass), joinedload(Student.section))
    if search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                Student.full_name.ilike(term),
                Student.student_code.ilike(term),
                Student.admission_no.ilike(term),
            )
        )
    if class_id:
        q = q.filter(Student.class_id == class_id)
    if section_id:
        q = q.filter(Student.section_id == section_id)
    if status:
        q = q.filter(Student.status == status)
    total = q.count()
    items = (
        q.order_by(Student.class_id, Student.section_id, Student.roll_no, Student.full_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return StudentListOut(items=[_to_out(s) for s in items], total=total, page=page, page_size=page_size)


@router.get("/fields")
def import_field_labels(_cu=reader_dep):
    return {"fields": [{"key": k, "label": v} for k, v in FIELD_LABELS.items()]}


@router.get("/export")
def export_students(format: str = "csv", class_id: int | None = None, cu=Depends(require_roles()), db=Depends(get_db)):
    q = db.query(Student).options(joinedload(Student.klass), joinedload(Student.section))
    if class_id:
        q = q.filter(Student.class_id == class_id)
    students = q.order_by(Student.class_id, Student.section_id, Student.roll_no, Student.full_name).all()

    headers = ["Student ID", "Admission Number", "Student Name", "Father's Name", "Mother's Name",
               "Class", "Section", "Roll Number", "Date of Birth", "Gender", "Contact Number",
               "Email", "Address", "Admission Date", "Status"]
    rows = [[
        s.student_code, s.admission_no, s.full_name, s.father_name, s.mother_name,
        s.klass.name if s.klass else "", s.section.name if s.section else "",
        s.roll_no or "", s.dob.strftime("%d/%m/%Y") if s.dob else "", s.gender.title() if s.gender else "",
        s.phone, s.email, s.address, s.admission_date.strftime("%d/%m/%Y") if s.admission_date else "", s.status,
    ] for s in students]

    if format == "xlsx":
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Students"
        ws.append(headers)
        for r in rows:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="piassess_students.xlsx"'},
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="piassess_students.csv"'},
    )


@router.post("", response_model=StudentOut)
def create_student(payload: StudentIn, cu=Depends(writer_dep), db=Depends(get_db)):
    _validate_links(db, payload)
    if payload.admission_no:
        dup = db.query(Student).filter(Student.admission_no == payload.admission_no).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Admission number {payload.admission_no} is already used by {dup.full_name} ({dup.student_code}).")

    (code,) = generate_student_codes(db, 1)
    s = Student(student_code=code, **payload.model_dump())
    db.add(s)
    db.flush()
    log_action(db, cu, "create", "student", s.id, f"Added student {s.full_name} ({s.student_code})")
    db.commit()
    db.refresh(s)
    return _to_out(s)


@router.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db=Depends(get_db), _cu=reader_dep):
    s = (
        db.query(Student)
        .options(joinedload(Student.klass), joinedload(Student.section))
        .filter(Student.id == student_id)
        .first()
    )
    if s is None:
        raise HTTPException(status_code=404, detail="Student not found.")
    return _to_out(s)


@router.put("/{student_id}", response_model=StudentOut)
def update_student(student_id: int, payload: StudentIn, cu=Depends(writer_dep), db=Depends(get_db)):
    s = db.get(Student, student_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Student not found.")
    _validate_links(db, payload)
    if payload.admission_no:
        dup = db.query(Student).filter(Student.admission_no == payload.admission_no, Student.id != student_id).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Admission number {payload.admission_no} is already used by {dup.full_name} ({dup.student_code}).")
    for k, v in payload.model_dump().items():
        setattr(s, k, v)
    log_action(db, cu, "update", "student", s.id, f"Updated student {s.full_name} ({s.student_code})")
    db.commit()
    db.refresh(s)
    return _to_out(s)


@router.delete("/{student_id}")
def delete_student(student_id: int, cu=Depends(require_roles("admin", "exam_controller")), db=Depends(get_db)):
    s = db.get(Student, student_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Student not found.")
    log_action(db, cu, "delete", "student", s.id, f"Deleted student {s.full_name} ({s.student_code})")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- bulk import
@router.post("/import/preview", response_model=ImportPreviewOut)
def import_preview(file: UploadFile = File(...), cu=Depends(writer_dep), db=Depends(get_db)):
    raw = file.file.read()
    if len(raw) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"The file is larger than {config.MAX_UPLOAD_MB} MB.")
    filename = file.filename or "upload.csv"
    try:
        columns, rows = read_tabular(filename, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=400, detail="The file could not be read. Please check it is a valid CSV or Excel file.")

    if not rows:
        raise HTTPException(status_code=400, detail="No data rows were found in the file. The first row should contain column headings.")
    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(status_code=400, detail=f"The file contains {len(rows)} rows. Please split it into files of at most {MAX_IMPORT_ROWS} rows.")

    # Displayed preview rows keep the original (string) values.
    preview_rows = []
    for i, row in enumerate(rows[:MAX_IMPORT_ROWS], start=2):
        preview_rows.append({"row_number": i, "data": row, "errors": []})
    return ImportPreviewOut(
        columns=columns,
        rows=preview_rows,
        valid_count=0,
        error_count=0,
        duplicate_count=0,
        mapping_hint=guess_mapping(columns),
    )


@router.post("/import/confirm", response_model=ImportResultOut)
def import_confirm(payload: ImportConfirmIn, cu=Depends(writer_dep), db=Depends(get_db)):
    mapping: dict[str, str] = payload.mapping or {}
    mapped_rows: list[dict] = []
    for raw_row in payload.rows[:MAX_IMPORT_ROWS]:
        mapped_rows.append({field: raw_row.get(col, "") for field, col in mapping.items() if col})
    valid, rejected = validate_rows(db, mapped_rows)
    if not valid:
        return ImportResultOut(imported=0, skipped=len(rejected))
    codes = generate_student_codes(db, len(valid))
    students = [Student(student_code=code, **rec) for code, rec in zip(codes, valid)]
    db.add_all(students)
    log_action(
        db, cu, "import", "student", None,
        f"Imported {len(students)} student(s) from file; {len(rejected)} row(s) skipped",
    )
    db.commit()
    return ImportResultOut(
        imported=len(students),
        skipped=len(rejected),
        first_student_code=codes[0] if codes else "",
        codes=codes[:50],
    )
