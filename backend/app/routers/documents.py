"""Document Library: upload, list, download, archive school documents."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from .. import config
from ..database import get_db
from ..models import DOC_CATEGORIES, Document
from ..schemas import DocumentListOut, DocumentOut
from ..security import require_roles
from ..services.common import log_action

router = APIRouter(prefix="/api/documents", tags=["documents"])

reader_dep = Depends(require_roles())
writer_dep = require_roles("admin", "exam_controller", "teacher")


@router.get("/categories")
def categories(_cu=reader_dep):
    return {"categories": list(DOC_CATEGORIES)}


@router.get("", response_model=DocumentListOut)
def list_documents(
    category: str = "",
    search: str = "",
    include_archived: bool = True,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    db=Depends(get_db),
    _cu=reader_dep,
):
    q = db.query(Document)
    if category:
        q = q.filter(Document.category == category)
    if search.strip():
        q = q.filter(Document.title.ilike(f"%{search.strip()}%"))
    if not include_archived:
        q = q.filter(Document.is_archived == False)  # noqa: E712
    total = q.count()
    items = q.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return DocumentListOut(items=[DocumentOut.model_validate(d) for d in items], total=total)


@router.post("", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(...),
    title: str = Form(""),
    cu=Depends(writer_dep),
    db=Depends(get_db),
):
    if category not in DOC_CATEGORIES:
        raise HTTPException(status_code=400, detail="Please choose a valid category for the document.")
    raw = await file.read()
    if len(raw) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Files must be smaller than {config.MAX_UPLOAD_MB} MB.")
    original_name = Path(file.filename or "document").name
    ext = Path(original_name).suffix.lower()
    if ext not in config.ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail="Allowed file types: PDF, DOCX, XLSX, CSV, PNG, JPG.")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    (config.DOC_UPLOAD_DIR / stored_name).write_bytes(raw)

    d = Document(
        category=category,
        title=(title.strip() or Path(original_name).stem),
        file_name=original_name,
        stored_name=stored_name,
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(raw),
        uploaded_by=cu.username,
    )
    db.add(d)
    db.flush()
    log_action(db, cu, "upload", "document", d.id, f"Uploaded \"{d.title}\" to {category}")
    db.commit()
    db.refresh(d)
    return DocumentOut.model_validate(d)


@router.get("/{document_id}/download")
def download_document(document_id: int, db=Depends(get_db), _cu=reader_dep):
    d = db.get(Document, document_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    path = config.DOC_UPLOAD_DIR / d.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="The file is missing from storage. It may have been removed during maintenance.")
    return FileResponse(path, filename=d.file_name, media_type=d.mime_type)


@router.post("/{document_id}/archive", response_model=DocumentOut)
def set_archive(document_id: int, archived: bool = True, cu=Depends(writer_dep), db=Depends(get_db)):
    d = db.get(Document, document_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    d.is_archived = archived
    log_action(db, cu, "archive" if archived else "unarchive", "document", d.id, f"{'Archived' if archived else 'Restored'} \"{d.title}\"")
    db.commit()
    db.refresh(d)
    return DocumentOut.model_validate(d)


@router.delete("/{document_id}")
def delete_document(document_id: int, cu=Depends(require_roles("admin", "exam_controller")), db=Depends(get_db)):
    d = db.get(Document, document_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    path = config.DOC_UPLOAD_DIR / d.stored_name
    if path.exists():
        path.unlink(missing_ok=True)
    log_action(db, cu, "delete", "document", d.id, f"Deleted \"{d.title}\"")
    db.delete(d)
    db.commit()
    return {"ok": True}
