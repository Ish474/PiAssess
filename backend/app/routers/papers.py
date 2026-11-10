"""Question paper assembly: order, marks, instructions, live preview data."""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from .. import config
from ..database import get_db
from ..models import Examination, OMRScan, PaperItem, Question, QuestionPaper, Student
from ..schemas import PaperItemIn, PaperItemOut, PaperOut, PaperUpdateIn, QuestionOut
from ..security import require_roles
from ..services.common import get_setting, log_action
from ..services.omr import build_omr_pdf
from ..services.printing import build_paper_docx, build_paper_pdf
from .questions import to_out

router = APIRouter(prefix="/api/papers", tags=["papers"])

reader_dep = Depends(require_roles())
writer_dep = require_roles("admin", "exam_controller", "teacher")


def get_paper_or_404(db, exam_id: int) -> QuestionPaper:
    paper = db.query(QuestionPaper).filter(QuestionPaper.exam_id == exam_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="No question paper has been created for this examination yet. Generate or add questions first.")
    return paper


def build_paper_out(db, paper: QuestionPaper) -> PaperOut:
    exam = db.get(Examination, paper.exam_id)
    items = (
        db.query(PaperItem)
        .filter(PaperItem.paper_id == paper.id)
        .order_by(PaperItem.position)
        .all()
    )
    return PaperOut(
        id=paper.id,
        exam_id=paper.exam_id,
        class_id=exam.class_id if exam else 0,
        title=paper.title or (exam.name if exam else ""),
        instructions=paper.instructions if paper.instructions else (exam.instructions if exam else ""),
        total_marks=sum(i.marks for i in items),
        exam_name=exam.name if exam else "",
        class_name=exam.klass.name if exam and exam.klass else "",
        subject_name=exam.subject.name if exam and exam.subject else "",
        exam_date=exam.exam_date if exam else None,
        duration_minutes=exam.duration_minutes if exam else 0,
        academic_session=exam.academic_session if exam else "",
        exam_max_marks=exam.max_marks if exam else 0,
        negative_marks=float(exam.negative_marks) if exam else 0.0,
        items=[PaperItemOut(question_id=i.question_id, position=i.position, marks=i.marks, question=to_out(i.question)) for i in items],
    )


@router.get("/{exam_id}", response_model=PaperOut)
def get_paper(exam_id: int, db=Depends(get_db), _cu=reader_dep):
    paper = get_paper_or_404(db, exam_id)
    return build_paper_out(db, paper)


@router.put("/{exam_id}")
def update_paper(exam_id: int, payload: PaperUpdateIn, cu=Depends(writer_dep), db=Depends(get_db)):
    """Save title/instructions and/or the full ordered item list (positions + marks).

    Creates the paper automatically on first save, so the editor can start from scratch.
    """
    exam = db.get(Examination, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found.")
    paper = db.query(QuestionPaper).filter(QuestionPaper.exam_id == exam_id).first()
    if paper is None:
        paper = QuestionPaper(exam_id=exam_id)
        db.add(paper)
        db.flush()
    if payload.title is not None:
        paper.title = payload.title.strip()
    if payload.instructions is not None:
        paper.instructions = payload.instructions

    if payload.items is not None:
        existing = {i.question_id: i for i in paper.items}
        seen = set()
        for entry in payload.items:
            if entry.question_id in seen:
                raise HTTPException(status_code=400, detail="The same question appears twice in the list.")
            seen.add(entry.question_id)
            item = existing.get(entry.question_id)
            if item is None:
                q = db.get(Question, entry.question_id)
                if q is None:
                    raise HTTPException(status_code=400, detail=f"Question #{entry.question_id} no longer exists.")
                item = PaperItem(paper_id=paper.id, question_id=entry.question_id)
                db.add(item)
            item.position = entry.position
            item.marks = entry.marks
        for qid, item in existing.items():
            if qid not in seen:
                db.delete(item)

    log_action(db, cu, "update", "paper", paper.id, f"Updated question paper for examination #{exam_id}")
    db.commit()
    db.refresh(paper)
    return build_paper_out(db, paper)


def _safe_filename(paper: PaperOut, suffix: str) -> str:
    base = (paper.title or paper.exam_name or "question-paper").strip()
    cleaned = "".join(c if c.isascii() and (c.isalnum() or c in " -_") else "-" for c in base)
    cleaned = "-".join(part for part in cleaned.split("-") if part)[:80] or "question-paper"
    return f"{cleaned}{suffix}"


def _school_and_logo(db) -> tuple[dict, bytes | None]:
    school = {k: get_setting(db, k) for k in ("school_name", "school_address")}
    logo_path = get_setting(db, "logo_path")
    logo_bytes = None
    if logo_path:
        try:
            logo_bytes = (config.LOGO_UPLOAD_DIR / logo_path).read_bytes()
        except OSError:
            logo_bytes = None
    return school, logo_bytes


def _merge_pdfs(*parts: bytes) -> bytes:
    """Concatenate PDFs — used to staple the OMR sheet behind the question paper."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for part in parts:
        for page in PdfReader(io.BytesIO(part)).pages:
            writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@router.get("/{exam_id}/export")
def export_paper(
    exam_id: int,
    format: str = "pdf",       # pdf | docx
    doc: str = "question",     # question | key
    with_omr: int = 0,         # 1 = staple the OMR bubble sheet behind the PDF question paper
    set: str = "A",
    db=Depends(get_db),
    _cu=reader_dep,
):
    """Download the styled question paper or answer key as PDF or Word.

    ``with_omr=1`` (PDF, question paper only) appends the printable OMR bubble
    sheet after the question pages so one printout carries both.
    """
    paper = get_paper_or_404(db, exam_id)
    out = build_paper_out(db, paper)
    if not out.items:
        raise HTTPException(status_code=400, detail="This paper has no questions to export yet.")

    school, logo_bytes = _school_and_logo(db)

    include_key = doc == "key"
    if with_omr and (format != "pdf" or include_key):
        raise HTTPException(
            status_code=400,
            detail="The OMR sheet can be attached to the PDF question paper only (format=pdf&doc=question).",
        )
    set_letter = (set or "A").strip().upper()
    if with_omr and set_letter not in ("A", "B", "C", "D"):
        raise HTTPException(status_code=400, detail="Set must be one of A, B, C or D.")

    if format == "docx":
        payload = build_paper_docx(out, school, logo_bytes, include_key)
        media, suffix = "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"
    elif format == "pdf":
        payload = build_paper_pdf(out, school, logo_bytes, include_key)
        media, suffix = "application/pdf", ".pdf"
        if with_omr:
            try:
                omr_pdf = build_omr_pdf(out, school, logo_bytes, set_letter)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            # OMR sheet first — the invigilator hands out the bubble sheet on top
            payload = _merge_pdfs(omr_pdf, payload)
    else:
        raise HTTPException(status_code=400, detail="Format must be pdf or docx.")

    label = "answer-key" if include_key else "question-paper"
    if with_omr:
        label += f"-with-omr-set-{set_letter.lower()}"
    filename = _safe_filename(out, f"-{label}{suffix}")
    log_action(db, _cu, "export", "paper", out.id, f"Exported {label} as {format.upper()}")
    db.commit()
    return Response(
        content=payload,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{exam_id}/omr")
def export_omr(exam_id: int, set: str = "A", key: int = 0, db=Depends(get_db), _cu=reader_dep):
    """Download a printable OMR bubble sheet covering the paper's objective questions.

    ``key=1`` returns the teacher's checking copy with the correct bubbles darkened.
    """
    set_letter = (set or "A").strip().upper()
    if set_letter not in ("A", "B", "C", "D"):
        raise HTTPException(status_code=400, detail="Set must be one of A, B, C or D.")
    paper = get_paper_or_404(db, exam_id)
    out = build_paper_out(db, paper)
    school, logo_bytes = _school_and_logo(db)
    try:
        payload = build_omr_pdf(out, school, logo_bytes, set_letter, fill_key=bool(key))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    kind = "omr-key" if key else "omr-sheet"
    filename = _safe_filename(out, f"-{kind}-set-{set_letter.lower()}.pdf")
    log_action(db, _cu, "export", "paper", out.id,
               f"Exported OMR bubble sheet ({'key copy' if key else 'blank'}, Set {set_letter})")
    db.commit()
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{exam_id}/results")
def exam_results(exam_id: int, db=Depends(get_db), _cu=Depends(require_roles())):
    """Exam results assembled from the evaluated OMR sheets.

    Sheets the teacher has assigned to a student are ranked; unassigned sheets
    still show with their score so nothing is hidden.
    """
    exam = db.get(Examination, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found.")

    scans = (
        db.query(OMRScan)
        .filter(OMRScan.exam_id == exam_id, OMRScan.score.isnot(None))
        .order_by(OMRScan.created_at)
        .all()
    )
    students = {s.id: s for s in db.query(Student).filter(Student.class_id == exam.class_id).all()}

    # rank assigned sheets by score (dense ranking: ties share a rank)
    scored_assigned = sorted(
        (s for s in scans if s.student_id and s.student_id in students),
        key=lambda s: (-s.score, s.id),
    )
    ranks: dict[int, int] = {}
    last_score, last_rank = None, 0
    for i, s in enumerate(scored_assigned, start=1):
        if last_score is not None and s.score == last_score:
            ranks[s.id] = last_rank
        else:
            ranks[s.id] = i
            last_score, last_rank = s.score, i

    passing = float(exam.passing_marks)
    rows = []
    pcts = []
    passes = 0
    for s in scans:
        student = students.get(s.student_id) if s.student_id else None
        max_score = float(s.max_score) if s.max_score else float(exam.max_marks)
        pct = round(float(s.score) / max_score * 100, 1) if max_score else 0.0
        passed = float(s.score) >= passing
        if passed:
            passes += 1
        pcts.append(pct)
        rows.append({
            "scan_id": s.id,
            "student_id": s.student_id,
            "student_name": student.full_name if student else None,
            "roll_no": student.roll_no if student else None,
            "sheet": s.original_name,
            "set": s.set_letter,
            "score": float(s.score),
            "max_score": max_score,
            "percent": pct,
            "passed": passed,
            "band": s.confidence_band,
            "rank": ranks.get(s.id),
        })

    # ranked rows first (by rank), then unassigned by score, then failures of data
    rows.sort(key=lambda r: (r["rank"] is None, r["rank"] if r["rank"] else 0,
                             -(r["score"] or 0)))

    stats = {
        "sheets_scored": len(rows),
        "students_ranked": len(scored_assigned),
        "unassigned": sum(1 for r in rows if r["student_id"] is None),
        "highest": max((r["score"] for r in rows), default=None),
        "average_percent": round(sum(pcts) / len(pcts), 1) if pcts else None,
        "pass_count": passes,
        "pass_percent": round(passes / len(rows) * 100, 1) if rows else None,
    }
    return {
        "exam": {
            "id": exam.id, "name": exam.name, "class_name": exam.klass.name if exam.klass else "",
            "subject_name": exam.subject.name if exam.subject else "",
            "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
            "max_marks": exam.max_marks, "passing_marks": exam.passing_marks,
            "negative_marks": float(exam.negative_marks or 0.0),
            "status": exam.status,
        },
        "rows": rows,
        "stats": stats,
    }
