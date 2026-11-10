"""Question Bank: CRUD, search, filters, verification, duplicate prevention."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_

from ..database import get_db
from ..models import DIFFICULTIES, QUESTION_TYPES, Question, VERIFICATION_STATES
from ..schemas import (
    BulkSaveIn,
    BulkSaveOut,
    QuestionIn,
    QuestionListOut,
    QuestionOut,
    QuestionUpdateIn,
    VerificationIn,
)
from ..security import require_roles
from ..services.ai import content_hash_of, verify_numeric_answer
from ..services.common import log_action

router = APIRouter(prefix="/api/questions", tags=["questions"])

reader_dep = Depends(require_roles())
writer_dep = require_roles("admin", "exam_controller", "teacher")


def to_out(q: Question) -> QuestionOut:
    o = QuestionOut.model_validate(q, from_attributes=True)
    o.options = json.loads(q.options_json or "[]")
    o.keywords = json.loads(q.keywords_json or "[]")
    return o


def _hash_for(qtype: str, text: str, answer: str) -> str:
    return content_hash_of(qtype, text, answer)


def _run_verification(draft: dict) -> tuple[str, str]:
    """Honest verification: only SymPy maths proofs count as 'verified'."""
    if draft["check_expression"] and draft["correct_answer"]:
        result = verify_numeric_answer(draft["check_expression"], draft["correct_answer"])
        if result is True:
            return "verified", "Answer checked computationally with SymPy."
        if result is False:
            return "needs_review", (
                f"SymPy check mismatch: {draft['check_expression']} does not equal {draft['correct_answer']}. "
                "Please rework this question."
            )
        return "unverified", "The answer could not be verified computationally. Please review manually."
    return "unverified", "No computational check available. Please review manually before publishing."


@router.get("/meta")
def meta(_cu=reader_dep):
    return {
        "types": [{"key": k, "label": v} for k, v in QUESTION_TYPES.items()],
        "difficulties": list(DIFFICULTIES),
        "verifications": list(VERIFICATION_STATES),
    }


@router.get("", response_model=QuestionListOut)
def list_questions(
    search: str = "",
    class_id: int | None = None,
    subject_id: int | None = None,
    qtype: str = "",
    difficulty: str = "",
    verification: str = "",
    chapter: str = "",
    exam_id: int | None = None,
    in_paper: str = "",  # "yes" | "no" | ""
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db=Depends(get_db),
    _cu=reader_dep,
):
    q = db.query(Question)
    if search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(or_(Question.text.ilike(term), Question.chapter.ilike(term), Question.topic.ilike(term)))
    for field_name, value in (
        ("class_id", class_id), ("subject_id", subject_id), ("qtype", qtype),
        ("difficulty", difficulty), ("verification", verification), ("exam_id", exam_id),
    ):
        if value not in (None, ""):
            q = q.filter(getattr(Question, field_name) == value)
    if chapter.strip():
        q = q.filter(Question.chapter.ilike(f"%{chapter.strip()}%"))
    if in_paper == "yes":
        q = q.filter(Question.exam_id != None)  # noqa: E711
    elif in_paper == "no":
        q = q.filter(Question.exam_id == None)  # noqa: E711
    total = q.count()
    items = q.order_by(Question.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return QuestionListOut(items=[to_out(x) for x in items], total=total, page=page, page_size=page_size)


def _create_question(db, payload: dict, source: str, cu) -> tuple[Question | None, str]:
    """Shared creation with duplicate guard. Returns (question, error_message)."""
    h = _hash_for(payload["qtype"], payload["text"], payload.get("correct_answer", ""))
    dup = db.query(Question).filter(Question.content_hash == h).first()
    if dup is not None:
        return None, f"This question already exists in the bank (#{dup.id}): \"{dup.text[:80]}…\""
    verification, note = _run_verification(payload)
    q = Question(
        class_id=payload["class_id"],
        subject_id=payload.get("subject_id"),
        exam_id=payload.get("exam_id"),
        chapter=payload.get("chapter", ""),
        topic=payload.get("topic", ""),
        qtype=payload["qtype"],
        difficulty=payload["difficulty"],
        marks=payload["marks"],
        text=payload["text"],
        options_json=json.dumps(payload.get("options", []), ensure_ascii=False),
        correct_answer=payload.get("correct_answer", ""),
        explanation=payload.get("explanation", ""),
        keywords_json=json.dumps(payload.get("keywords", []), ensure_ascii=False),
        marking_notes=payload.get("marking_notes", ""),
        check_expression=payload.get("check_expression", ""),
        verification=verification,
        verification_note=note,
        source=source,
        content_hash=h,
    )
    db.add(q)
    db.flush()
    return q, ""


@router.post("", response_model=QuestionOut)
def create_question(payload: QuestionIn, cu=Depends(writer_dep), db=Depends(get_db)):
    q, error = _create_question(db, payload.model_dump(), source="manual", cu=cu)
    if error:
        raise HTTPException(status_code=409, detail=error)
    log_action(db, cu, "create", "question", q.id, f"Added {QUESTION_TYPES[q.qtype]} to the question bank")
    db.commit()
    db.refresh(q)
    return to_out(q)


@router.post("/bulk-save", response_model=BulkSaveOut)
def bulk_save(payload: BulkSaveIn, cu=Depends(writer_dep), db=Depends(get_db)):
    """Save a batch of AI-drafted questions, optionally attaching them to a paper in order."""
    saved_ids: list[int] = []
    duplicates = 0
    saved_drafts: list = []  # aligned with saved_ids
    for draft in payload.questions:
        data = draft.model_dump() | {
            "class_id": payload.class_id,
            "subject_id": payload.subject_id,
            "exam_id": payload.exam_id,
        }
        q, error = _create_question(db, data, source="ai", cu=cu)
        if error:
            duplicates += 1
            continue
        saved_ids.append(q.id)
        saved_drafts.append(draft)

    paper_id = None
    if payload.exam_id and saved_ids:
        from ..models import QuestionPaper, PaperItem

        paper = db.query(QuestionPaper).filter(QuestionPaper.exam_id == payload.exam_id).first()
        if paper is None:
            paper = QuestionPaper(exam_id=payload.exam_id)
            db.add(paper)
            db.flush()
        position = db.query(func.max(PaperItem.position)).filter(PaperItem.paper_id == paper.id).scalar() or 0
        for draft, qid in zip(saved_drafts, saved_ids):
            position += 1
            db.add(PaperItem(paper_id=paper.id, question_id=qid, position=position, marks=draft.marks))
        paper_id = paper.id

    log_action(
        db, cu, "generate", "question", None,
        f"Saved {len(saved_ids)} AI question(s) to the bank ({duplicates} duplicate(s) skipped)",
    )
    db.commit()
    return BulkSaveOut(saved=len(saved_ids), duplicates_skipped=duplicates, ids=saved_ids, paper_id=paper_id)


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(question_id: int, db=Depends(get_db), _cu=reader_dep):
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    return to_out(q)


@router.put("/{question_id}", response_model=QuestionOut)
def update_question(question_id: int, payload: QuestionUpdateIn, cu=Depends(writer_dep), db=Depends(get_db)):
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    changes = payload.model_dump(exclude_none=True)
    for k, v in changes.items():
        if k in ("options", "keywords"):
            setattr(q, "options_json" if k == "options" else "keywords_json", json.dumps(v, ensure_ascii=False))
        else:
            setattr(q, k, v)
    # re-hash and re-verify after edits
    q.content_hash = _hash_for(q.qtype, q.text, q.correct_answer)
    verification, note = _run_verification({
        "check_expression": q.check_expression, "correct_answer": q.correct_answer,
    })
    q.verification, q.verification_note = verification, note
    dup = db.query(Question).filter(Question.content_hash == q.content_hash, Question.id != q.id).first()
    if dup:
        raise HTTPException(status_code=409, detail=f"This edit would make the question identical to #{dup.id} already in the bank.")
    log_action(db, cu, "update", "question", q.id, f"Edited question #{q.id}")
    db.commit()
    db.refresh(q)
    return to_out(q)


@router.post("/{question_id}/verify", response_model=QuestionOut)
def set_verification(question_id: int, payload: VerificationIn, cu=Depends(writer_dep), db=Depends(get_db)):
    """Teacher's manual review decision — always recorded in the audit log."""
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    q.verification = payload.verification
    q.verification_note = payload.note or {
        "verified": "Confirmed correct by teacher review.",
        "needs_review": "Flagged by teacher for another look.",
        "unverified": "",
    }.get(payload.verification, "")
    log_action(db, cu, "verify", "question", q.id, f"Marked question #{q.id} as {payload.verification}")
    db.commit()
    db.refresh(q)
    return to_out(q)


@router.delete("/{question_id}")
def delete_question(question_id: int, cu=Depends(writer_dep), db=Depends(get_db)):
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    log_action(db, cu, "delete", "question", q.id, f"Deleted question #{q.id}")
    db.delete(q)  # paper items cascade
    db.commit()
    return {"ok": True}
