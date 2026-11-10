"""AI generation endpoints: status, generate, re-verify drafts, material extraction."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from .. import config
from ..database import get_db
from ..models import QUESTION_TYPES, Klass, Subject
from ..schemas import DraftQuestionOut, GenerateIn, GenerateOut
from ..security import require_roles
from ..services import ai as ai_service
from ..services.ai import GenRequest
from ..services.extract import extract_text

router = APIRouter(prefix="/api/ai", tags=["ai"])

writer_dep = require_roles("admin", "exam_controller", "teacher")


@router.get("/status")
def ai_status(db=Depends(get_db), _cu=Depends(require_roles())):
    cfg = ai_service.get_ai_config(db)
    return {
        "configured": cfg.configured,
        "provider": get_provider_name(db, cfg),
        "model": cfg.model,
        "base_url": cfg.base_url,
    }


def get_provider_name(db, cfg) -> str:
    from ..services.common import get_setting

    return get_setting(db, "ai_provider") or ("environment" if cfg.configured else "")


@router.post("/extract")
async def extract_material(file: UploadFile = File(...), cu=Depends(writer_dep)):
    """Pull text out of an uploaded chapter PDF / DOCX / TXT for the generator."""
    raw = await file.read()
    if len(raw) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Files must be smaller than {config.MAX_UPLOAD_MB} MB.")
    try:
        text = extract_text(file.filename or "material", raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"chars": len(text), "text": text}


@router.post("/generate", response_model=GenerateOut)
def generate(payload: GenerateIn, cu=Depends(writer_dep), db=Depends(get_db)):
    """Generate original questions with the configured AI provider, then verify maths with SymPy."""
    klass = db.get(Klass, payload.class_id)
    if klass is None:
        raise HTTPException(status_code=400, detail="The selected class does not exist.")
    subject = db.get(Subject, payload.subject_id) if payload.subject_id else None

    request = GenRequest(
        class_name=klass.name,
        subject=subject.name if subject else "the chosen subject",
        chapters=payload.chapters,
        content_text=payload.content_text,
        types=[t.model_dump() for t in payload.types],
        extra_instructions=payload.extra_instructions,
        avoid_texts=payload.avoid_texts,
    )
    messages = ai_service.build_generation_prompt(request)
    try:
        raw = ai_service.chat_complete(db, messages, temperature=0.7)
        data = ai_service.parse_llm_json(raw)
        raw_questions = data.get("questions")
        if not isinstance(raw_questions, list) or not raw_questions:
            raise ai_service.AIGenerationError("The AI returned no questions. Please try again.")
        drafts = []
        skipped_notes: list[str] = []
        for raw_q in raw_questions:
            try:
                draft = ai_service.normalize_draft(raw_q, QUESTION_TYPES)
            except ai_service.AIGenerationError as exc:
                # one malformed draft must not throw away the whole batch
                skipped_notes.append(str(exc))
                continue
            # honest verification pass — maths only
            if draft["check_expression"] and draft["correct_answer"]:
                result = ai_service.verify_numeric_answer(draft["check_expression"], draft["correct_answer"])
                if result is True:
                    draft["verification"] = "verified"
                    draft["verification_note"] = "Answer checked computationally with SymPy."
                elif result is False:
                    draft["verification"] = "needs_review"
                    draft["verification_note"] = f"SymPy check mismatch: {draft['check_expression']} ≠ {draft['correct_answer']}. Please rework."
            drafts.append(draft)
        if not drafts:
            raise ai_service.AIGenerationError(skipped_notes[0] if skipped_notes else "The AI returned no questions. Please try again.")
    except ai_service.AIConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ai_service.AIGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    cfg = ai_service.get_ai_config(db)
    return GenerateOut(
        questions=[DraftQuestionOut(**d) for d in drafts],
        provider=get_provider_name(db, cfg),
        model=cfg.model,
        skipped=len(skipped_notes),
        skipped_notes=skipped_notes,
    )
