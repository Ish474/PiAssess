"""OMR processing — upload scanned answer sheets, read bubbles, score them.

Sheets are the PiAssess-generated OMR bubble sheets: the scanner uses the
printed registration squares to straighten each scan and reads every bubble at
its known canonical coordinate. No AI is involved in reading bubbles.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import Examination, OMRScan, Student, User
from ..schemas import PaperOut
from ..security import require_roles
from ..services.common import log_action
from ..services.omr_scan import ScanError, pdf_pages_to_images, recognize_scan
from .papers import build_paper_out, get_paper_or_404

router = APIRouter(prefix="/api/papers", tags=["omr-scans"])

reader_dep = Depends(require_roles())
writer_dep = require_roles("admin", "exam_controller", "teacher")

ALLOWED_SCAN_TYPES = {".png", ".jpg", ".jpeg", ".pdf"}


def _scan_out(scan: OMRScan, student_name: str | None = None) -> dict:
    return {
        "id": scan.id,
        "exam_id": scan.exam_id,
        "set_letter": scan.set_letter,
        "student_id": scan.student_id,
        "student_name": student_name,
        "original_name": scan.original_name,
        "status": scan.status,
        "confidence_band": scan.confidence_band,
        "score": scan.score,
        "max_score": scan.max_score,
        "error_message": scan.error_message,
        "processed_at": scan.processed_at.isoformat() if scan.processed_at else None,
        "created_at": scan.created_at.isoformat(),
    }


def _scan_with_student(db: Session, scan: OMRScan) -> dict:
    name = None
    if scan.student_id:
        st = db.get(Student, scan.student_id)
        name = st.full_name if st else None
    return _scan_out(scan, name)


@router.get("/{exam_id}/omr-scans")
def list_scans(exam_id: int, db=Depends(get_db), _cu=reader_dep):
    get_paper_or_404(db, exam_id)
    scans = (db.query(OMRScan).filter(OMRScan.exam_id == exam_id)
             .order_by(OMRScan.created_at.desc()).all())
    items = [_scan_with_student(db, s) for s in scans]
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "processed": sum(1 for i in items if i["status"] == "processed"),
            "needs_review": sum(1 for i in items if i["confidence_band"] == "YELLOW"),
            "failed": sum(1 for i in items if i["status"] == "failed"),
            "pending": sum(1 for i in items if i["status"] == "pending"),
        },
    }


@router.get("/{exam_id}/omr-scans/{scan_id}")
def scan_detail(exam_id: int, scan_id: int, db=Depends(get_db), _cu=reader_dep):
    scan = _scan_or_404(db, exam_id, scan_id)
    out = _scan_with_student(db, scan)
    out["responses"] = json.loads(scan.responses or "[]")
    return out


def _scan_or_404(db: Session, exam_id: int, scan_id: int) -> OMRScan:
    scan = db.query(OMRScan).filter(OMRScan.id == scan_id, OMRScan.exam_id == exam_id).first()
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return scan


@router.post("/{exam_id}/omr-scans")
async def upload_scans(
    exam_id: int,
    set: str = Form("A"),
    files: list[UploadFile] = File(...),
    cu: User = Depends(writer_dep),
    db=Depends(get_db),
):
    """Upload one or more scanned sheets (JPG/PNG) or a scanned PDF for an examination's paper.

    Each page of a PDF is treated as one student's sheet — a whole stack
    scanned on the photocopier lands as one PDF and is split automatically.
    """
    set_letter = (set or "A").strip().upper()
    if set_letter not in ("A", "B", "C", "D"):
        raise HTTPException(status_code=400, detail="Set must be one of A, B, C or D.")
    paper = get_paper_or_404(db, exam_id)

    out_dir = config.OMR_SCAN_DIR / str(exam_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    created = []
    for file in files:
        raw = await file.read()
        if len(raw) > config.MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(status_code=413,
                                detail=f"{file.filename}: files must be smaller than {config.MAX_UPLOAD_MB} MB.")
        original_name = Path(file.filename or "scan").name
        ext = Path(original_name).suffix.lower()
        if ext not in ALLOWED_SCAN_TYPES:
            raise HTTPException(status_code=400,
                                detail=f"{original_name}: scans must be JPG, PNG or PDF images.")
        if ext == ".pdf":
            # a scanned stack: every page of the PDF is one student's sheet
            try:
                page_images = pdf_pages_to_images(raw)
            except ScanError as exc:
                raise HTTPException(status_code=400, detail=f"{original_name}: {exc}")
            for i, page_jpeg in enumerate(page_images, start=1):
                stored_name = f"{uuid.uuid4().hex}.jpg"
                (out_dir / stored_name).write_bytes(page_jpeg)
                scan = OMRScan(
                    exam_id=exam_id, set_letter=set_letter, stored_name=stored_name,
                    original_name=f"{original_name} — page {i}", status="pending",
                    uploaded_by=cu.username,
                )
                db.add(scan)
                db.flush()
                created.append(_scan_out(scan))
        else:
            stored_name = f"{uuid.uuid4().hex}{ext}"
            (out_dir / stored_name).write_bytes(raw)
            scan = OMRScan(
                exam_id=exam_id, set_letter=set_letter, stored_name=stored_name,
                original_name=original_name, status="pending", uploaded_by=cu.username,
            )
            db.add(scan)
            db.flush()
            created.append(_scan_out(scan))
    log_action(db, cu, "upload", "omr_scan", str(exam_id), f"Uploaded {len(created)} scanned sheet(s) (Set {set_letter})")
    db.commit()
    return {"items": created, "uploaded": len(created)}


@router.patch("/{exam_id}/omr-scans/{scan_id}/responses")
def correct_scan(exam_id: int, scan_id: int, position: int, chosen: int | None = None,
                 db=Depends(get_db), cu: User = Depends(writer_dep)):
    """Manual correction: set or clear a question's marked option, then rescore.

    ``chosen`` is the 0-based option index, or null to clear the answer.
    Corrections are recorded in the audit log.
    """
    scan = _scan_or_404(db, exam_id, scan_id)
    if not scan.responses:
        raise HTTPException(status_code=400, detail="Process this scan before correcting answers.")

    rows = json.loads(scan.responses)
    row = next((r for r in rows if r["position"] == position), None)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Question {position} is not on this sheet.")

    n_opts = row.get("n_opts", 4)  # stored per row by the recognition step
    if chosen is not None and not (0 <= chosen < n_opts):
        raise HTTPException(status_code=400, detail="That option number does not exist on this row.")

    row["chosen"] = chosen
    row["verdict"] = "answered" if chosen is not None else "unanswered"
    row["correct"] = chosen is not None and row["key"] is not None and chosen == row["key"]
    row["overridden"] = True
    if chosen is not None:
        row["fill"] = 1.0

    scan.score = round(sum(r["marks"] for r in rows if r["correct"]), 2)
    # re-apply negative marking on the corrected sheet, same rule as the scanner:
    # wrong answers deduct, but only when the key is known for that row
    exam = db.get(Examination, exam_id)
    penalty = float(exam.negative_marks or 0.0) if exam else 0.0
    penalised = sum(1 for r in rows if r["verdict"] == "answered" and not r["correct"] and r["key"] is not None)
    scan.score = round(scan.score - penalty * penalised, 2)
    review_left = any(r["verdict"] in ("multi", "review") for r in rows)
    scan.status = "review" if review_left else "processed"
    if not review_left:
        scan.confidence_band = "GREEN"
    scan.responses = json.dumps(rows)
    log_action(db, cu, "correct", "omr_scan", str(scan.id),
               f"Manual correction: question {position} -> {chosen if chosen is not None else 'cleared'} "
               f"(score now {scan.score}/{scan.max_score})")
    db.commit()
    return _scan_with_student(db, scan)


@router.post("/{exam_id}/omr-scans/{scan_id}/assign")
def assign_student(exam_id: int, scan_id: int, payload: dict, db=Depends(get_db),
                   cu: User = Depends(writer_dep)):
    """Attach (or clear) the student this answer sheet belongs to.

    The printed sheet has a handwritten roll number, which the scanner cannot
    read honestly — so the teacher assigns each sheet once and results are
    ranked per student.
    """
    scan = _scan_or_404(db, exam_id, scan_id)
    student_id = payload.get("student_id")
    if student_id is not None:
        student = db.get(Student, int(student_id))
        if student is None:
            raise HTTPException(status_code=404, detail="That student does not exist.")
        exam = db.get(Examination, exam_id)
        if exam is None or student.class_id != exam.class_id:
            raise HTTPException(status_code=400,
                                detail=f"{student.full_name} is not in this examination's class.")
        scan.student_id = student.id
        log_action(db, cu, "assign", "omr_scan", str(scan.id),
                   f"Assigned sheet to {student.full_name} (roll {student.roll_no})")
    else:
        scan.student_id = None
        log_action(db, cu, "assign", "omr_scan", str(scan.id), "Cleared the student assignment on a sheet")
    db.commit()
    return _scan_with_student(db, scan)


@router.delete("/{exam_id}/omr-scans/{scan_id}")
def delete_scan(exam_id: int, scan_id: int, db=Depends(get_db), cu: User = Depends(writer_dep)):
    """Remove a scanned sheet and its result."""
    scan = _scan_or_404(db, exam_id, scan_id)
    path = config.OMR_SCAN_DIR / str(exam_id) / scan.stored_name
    path.unlink(missing_ok=True)
    db.delete(scan)
    log_action(db, cu, "delete", "omr_scan", str(scan_id), f"Deleted scan {scan.original_name}")
    db.commit()
    return {"deleted": True}


@router.post("/{exam_id}/omr-scans/{scan_id}/process")
def process_scan(exam_id: int, scan_id: int, db=Depends(get_db), cu: User = Depends(writer_dep)):
    """Read one uploaded sheet: straighten, detect bubbles, score against the key."""
    scan = _scan_or_404(db, exam_id, scan_id)
    if scan.status == "processing":
        raise HTTPException(status_code=409, detail="This scan is already being processed.")

    paper = get_paper_or_404(db, exam_id)
    out = build_paper_out(db, paper)
    path = config.OMR_SCAN_DIR / str(exam_id) / scan.stored_name
    if not path.exists():
        scan.status = "failed"
        scan.error_message = "The uploaded file is missing from storage."
        db.commit()
        raise HTTPException(status_code=410, detail="The uploaded file is missing from storage.")

    scan.status = "processing"
    db.commit()
    try:
        result = recognize_scan(path.read_bytes(), out, scan.set_letter)
    except ScanError as exc:
        scan.status = "failed"
        scan.confidence_band = "RED"
        scan.error_message = str(exc)
        db.commit()
        return _scan_out(scan)
    except Exception:  # never leave the queue stuck on an unexpected crash
        scan.status = "failed"
        scan.confidence_band = "RED"
        scan.error_message = "Something went wrong while reading this scan. Try processing it again."
        db.commit()
        raise

    needs_review = result["low_confidence"] > 0 or result["multi_marks"] > 0
    scan.status = "review" if needs_review else "processed"
    scan.confidence_band = result["confidence_band"]
    scan.score = result["score"]
    scan.max_score = result["max_score"]
    scan.responses = json.dumps(result["rows"])
    scan.error_message = ""
    scan.processed_at = datetime.now(timezone.utc)
    log_action(db, cu, "process", "omr_scan", str(scan.id),
               f"Processed scan (Set {scan.set_letter}): {result['score']}/{result['max_score']}, {result['confidence_band']}")
    db.commit()
    return _scan_with_student(db, scan)
