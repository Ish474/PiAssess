"""Phase 4 tests: styled PDF / DOCX export of question papers and answer keys."""
from __future__ import annotations

import base64
import io
import zipfile

# a valid 1×1 PNG so the logo-embedding logic runs end to end
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _make_paper(client, class_id: int) -> int:
    """Create an exam and a paper with three questions (one of each family)."""
    up = client.post("/api/settings/logo", files={"file": ("logo.png", TINY_PNG, "image/png")})
    assert up.status_code == 200, up.text
    exam_id = client.post("/api/exams", json={
        "name": "Export Test Examination", "class_id": class_id,
        "subject_id": None, "max_marks": 8,
    }).json()["id"]
    client.post("/api/questions/bulk-save", json={
        "class_id": class_id, "exam_id": exam_id,
        "questions": [
            {"qtype": "mcq", "difficulty": "easy", "marks": 2, "text": "Which is an integer? — PiAssess",
             "options": ["(A) 2.5", "(B) 3", "(C) ½", "(D) 0.1"], "correct_answer": "(B) 3",
             "explanation": "Integers are whole numbers.", "marking_notes": "No partial marks."},
            {"qtype": "numerical", "difficulty": "moderate", "marks": 3, "text": "Evaluate 17*23 — PiAssess.",
             "correct_answer": "391", "check_expression": "17*23"},
            {"qtype": "short", "difficulty": "moderate", "marks": 3, "text": "Define integer — PiAssess.",
             "correct_answer": "A whole number", "marking_notes": "1 mark per valid point"},
        ],
    })
    return exam_id


def _pdf_image_count(pdf_bytes: bytes) -> int:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    imgs = 0
    for page in reader.pages:
        res = page.get("/Resources")
        xo = res.get_object().get("/XObject") if res else None
        xo = xo.get_object() if xo else {}
        for name in xo:
            if xo[name].get_object().get("/Subtype") == "/Image":
                imgs += 1
    return imgs


def test_pdf_question_paper_export(client, class_id):
    exam_id = _make_paper(client, class_id)
    r = client.get(f"/api/papers/{exam_id}/export", params={"format": "pdf"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    body = r.content
    assert body[:5] == b"%PDF-"                                    # real PDF magic
    assert len(body) > 3000                                        # non-trivial document
    assert "question-paper" in r.headers["content-disposition"]
    assert _pdf_image_count(body) >= 1, "the school logo must be embedded in the PDF"


def test_pdf_answer_key_export(client, class_id):
    exam_id = _make_paper(client, class_id)
    r = client.get(f"/api/papers/{exam_id}/export", params={"format": "pdf", "doc": "key"})
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"
    assert _pdf_image_count(r.content) >= 1
    assert "answer-key" in r.headers["content-disposition"]


def test_docx_exports(client, class_id):
    exam_id = _make_paper(client, class_id)
    for doc, label in (("question", "question-paper"), ("key", "answer-key")):
        r = client.get(f"/api/papers/{exam_id}/export", params={"format": "docx", "doc": doc})
        assert r.status_code == 200, r.text
        assert r.content[:2] == b"PK"                              # DOCX is a zip
        assert label in r.headers["content-disposition"]
        # the logo must be embedded, not silently skipped
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            assert any(n.startswith("word/media/") for n in z.namelist()), \
                "the school logo must be embedded in the Word file"

    # and it opens as a valid Word document with our content
    r = client.get(f"/api/papers/{exam_id}/export", params={"format": "docx", "doc": "question"})
    document = __import__("docx").Document(io.BytesIO(r.content))
    all_text = "\n".join(p.text for p in document.paragraphs)
    assert "Export Test Examination" in all_text
    assert "Which is an integer?" in all_text
    assert "Pi World School" in all_text

    # MCQ options must sit in ONE horizontal row: a 1×4 table, borderless
    option_rows = [t for t in document.tables
                   if len(t.rows) == 1 and len(t.rows[0].cells) == 4
                   and all("2.5" in c.text or "0.1" in c.text or "½" in c.text or c.text.strip() == "(B) 3"
                           for c in t.rows[0].cells)]
    assert option_rows, "MCQ options must be laid out as a single horizontal row"

    # the question body flows in two columns (continuous section break)
    from docx.oxml.ns import qn
    assert len(document.sections) >= 2, "question body must be its own section"
    body_cols = document.sections[1]._sectPr.xpath("./w:cols")
    assert body_cols and body_cols[0].get(qn("w:num")) == "2", "question body must be two-column"


def test_export_rejects_unknown_format(client, class_id):
    exam_id = _make_paper(client, class_id)
    r = client.get(f"/api/papers/{exam_id}/export", params={"format": "html"})
    assert r.status_code == 400


def test_export_missing_paper_404(client):
    assert client.get("/api/papers/99999/export", params={"format": "pdf"}).status_code == 404


def test_export_empty_paper_rejected(client, class_id):
    exam_id = client.post("/api/exams", json={"name": "Empty Export", "class_id": class_id}).json()["id"]
    client.put(f"/api/papers/{exam_id}", json={"items": []})       # create empty paper
    r = client.get(f"/api/papers/{exam_id}/export", params={"format": "pdf"})
    assert r.status_code == 400
    assert "no questions" in r.json()["detail"]
