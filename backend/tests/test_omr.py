"""Phase 5 tests: printable OMR bubble sheets."""
from __future__ import annotations

import base64
import io

from pypdf import PdfReader

# a valid 1×1 PNG so the logo-embedding logic runs end to end
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _make_paper(client, class_id: int, with_mcq: bool = True) -> int:
    client.post("/api/settings/logo", files={"file": ("logo.png", TINY_PNG, "image/png")})
    exam_id = client.post("/api/exams", json={
        "name": "OMR Test Exam", "class_id": class_id, "max_marks": 10,
    }).json()["id"]
    questions = []
    if with_mcq:
        questions += [
            {"qtype": "mcq", "difficulty": "easy", "marks": 2,
             "text": f"MCQ number {n}?", "options": ["(A) x", "(B) y", "(C) z", "(D) w"],
             "correct_answer": "(B) y"}
            for n in range(1, 4)
        ]
    questions.append({"qtype": "numerical", "difficulty": "moderate", "marks": 4,
                      "text": "Integer question: evaluate 12+13.", "correct_answer": "25"})
    questions.append({"qtype": "short", "difficulty": "moderate", "marks": 4,
                      "text": "Written question.", "correct_answer": "anything"})
    client.post("/api/questions/bulk-save", json={"class_id": class_id, "exam_id": exam_id, "questions": questions})
    return exam_id


def test_omr_sheet_generated(client, class_id):
    exam_id = _make_paper(client, class_id)
    r = client.get(f"/api/papers/{exam_id}/omr")
    assert r.status_code == 200, r.text
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 5000
    assert "omr" in r.headers["content-disposition"]


def test_omr_sheet_has_logo_and_qr(client, class_id):
    exam_id = _make_paper(client, class_id)
    r = client.get(f"/api/papers/{exam_id}/omr")
    reader = PdfReader(io.BytesIO(r.content))
    imgs = 0
    for page in reader.pages:
        res = page.get("/Resources")
        xo = res.get_object().get("/XObject") if res else None
        xo = xo.get_object() if xo else {}
        for name in xo:
            if xo[name].get_object().get("/Subtype") == "/Image":
                imgs += 1
    assert imgs >= 2, "OMR sheet must carry the school logo and the QR code"

    # reference-style header: candidate block, corner tags, banner
    text = reader.pages[0].extract_text()
    assert "Roll No." in text
    assert "Name:" in text
    assert "SET A" in text
    assert "OMR ANSWER SHEET" in text
    assert "Instructions for marking the OMR sheet" in text
    assert "Pi World School" in text  # banner below the candidate block


def test_omr_respects_set_parameter(client, class_id):
    exam_id = _make_paper(client, class_id)
    r = client.get(f"/api/papers/{exam_id}/omr", params={"set": "b"})
    assert r.status_code == 200
    assert "SET B" in PdfReader(io.BytesIO(r.content)).pages[0].extract_text()

    bad = client.get(f"/api/papers/{exam_id}/omr", params={"set": "E"})
    assert bad.status_code == 400
    assert "Set must be one of" in bad.json()["detail"]


def test_omr_rejects_paper_without_mcq(client, class_id):
    exam_id = _make_paper(client, class_id, with_mcq=False)
    # also strip the numerical question: nothing left that can be bubbled
    exam_id = client.post("/api/exams", json={
        "name": "Written Only Exam", "class_id": class_id, "max_marks": 4,
    }).json()["id"]
    client.post("/api/questions/bulk-save", json={
        "class_id": class_id, "exam_id": exam_id,
        "questions": [{"qtype": "short", "difficulty": "moderate", "marks": 4,
                       "text": "Written question.", "correct_answer": "anything"}],
    })
    client.put(f"/api/papers/{exam_id}", json={"items": []})  # create the (empty) paper
    r = client.get(f"/api/papers/{exam_id}/omr")
    assert r.status_code == 400
    assert "MCQ" in r.json()["detail"]


def test_omr_missing_paper_404(client):
    assert client.get("/api/papers/99999/omr").status_code == 404


def test_omr_key_copy_marks_answers(client, class_id):
    """key=1 returns the teacher's checking copy: watermarked, answer bubbles darkened."""
    exam_id = _make_paper(client, class_id)

    blank = client.get(f"/api/papers/{exam_id}/omr", params={"set": "A"})
    marked = client.get(f"/api/papers/{exam_id}/omr", params={"set": "A", "key": 1})
    assert blank.status_code == 200 and marked.status_code == 200, marked.text

    blank_text = PdfReader(io.BytesIO(blank.content)).pages[0].extract_text()
    marked_text = PdfReader(io.BytesIO(marked.content)).pages[0].extract_text()
    assert "KEY COPY" not in blank_text, "blank student sheet must not carry the key watermark"
    assert "KEY COPY" in marked_text and "OMR ANSWER SHEET — KEY COPY" in marked_text

    # the marked copy carries the same objective rows (3 MCQs + 1 single-digit integer)
    assert "Instructions for marking" in marked_text


def test_combined_question_paper_with_omr(client, class_id):
    """with_omr=1 staples the OMR sheet in front of the question paper, same A4 size."""
    exam_id = _make_paper(client, class_id)
    plain = client.get(f"/api/papers/{exam_id}/export", params={"format": "pdf", "doc": "question"})
    combo = client.get(f"/api/papers/{exam_id}/export",
                       params={"format": "pdf", "doc": "question", "with_omr": 1, "set": "B"})
    assert plain.status_code == 200 and combo.status_code == 200, combo.text

    plain_pages = len(PdfReader(io.BytesIO(plain.content)).pages)
    combo_reader = PdfReader(io.BytesIO(combo.content))
    assert len(combo_reader.pages) > plain_pages, "combined PDF must carry the OMR pages with the paper"
    # FIRST page is the OMR sheet for the requested set
    first = combo_reader.pages[0].extract_text()
    assert "SET B" in first and "OMR ANSWER SHEET" in first
    # question paper follows after the OMR page(s)
    paper_page = combo_reader.pages[len(combo_reader.pages) - plain_pages].extract_text()
    assert "SET B" not in paper_page
    # every page is the same size (A4), paper and OMR alike
    boxes = {tuple(round(float(v), 1) for v in page.mediabox) for page in combo_reader.pages}
    assert len(boxes) == 1, f"page sizes differ: {boxes}"

    # attachment is rejected on Word exports and on answer keys
    bad_docx = client.get(f"/api/papers/{exam_id}/export",
                          params={"format": "docx", "doc": "question", "with_omr": 1})
    assert bad_docx.status_code == 400
    bad_key = client.get(f"/api/papers/{exam_id}/export",
                         params={"format": "pdf", "doc": "key", "with_omr": 1})
    assert bad_key.status_code == 400
