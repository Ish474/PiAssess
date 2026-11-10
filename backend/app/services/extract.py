"""Text extraction from uploaded learning material (PDF / DOCX / TXT)."""
from __future__ import annotations

import io

MAX_EXTRACT_CHARS = 200_000


def extract_text(filename: str, raw: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return _from_pdf(raw)
    if name.endswith((".docx",)):
        return _from_docx(raw)
    if name.endswith(".doc"):
        raise ValueError("Legacy .doc files are not supported. Please save as .docx or PDF.")
    return raw.decode("utf-8-sig", errors="replace")


def _from_pdf(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ValueError("PDF support is not installed.") from exc
    try:
        reader = PdfReader(io.BytesIO(raw))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:  # malformed pdf
        raise ValueError("The PDF could not be read. It may be damaged or password-protected.") from exc
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError("No selectable text was found in this PDF (it may be a scanned image). Paste the chapter text instead.")
    return text[:MAX_EXTRACT_CHARS]


def _from_docx(raw: bytes) -> str:
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover
        raise ValueError("DOCX support is not installed.") from exc
    try:
        document = docx.Document(io.BytesIO(raw))
        parts = [p.text for p in document.paragraphs]
        # tables often carry syllabus data
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        text = "\n".join(parts).strip()
    except Exception as exc:
        raise ValueError("The DOCX file could not be read.") from exc
    if not text:
        raise ValueError("The DOCX file appears to be empty.")
    return text[:MAX_EXTRACT_CHARS]
