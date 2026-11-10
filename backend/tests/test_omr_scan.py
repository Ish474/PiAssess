"""OMR scanning tests: synthetic marked sheets run through the real pipeline.

The synthetic scan is drawn at the exact canonical coordinates from
``omr.sheet_geometry`` — the same source the printer uses — then rotated and
re-encoded as a JPEG like a real scanner would produce.
"""
from __future__ import annotations

import base64
import io

import cv2
import numpy as np

from app.services.omr import sheet_geometry

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _make_mcq_paper(client, class_id: int, n_questions: int = 4) -> int:
    """Paper with n_questions MCQs whose keys march A, B, C, D..."""
    client.post("/api/settings/logo", files={"file": ("logo.png", TINY_PNG, "image/png")})
    exam_id = client.post("/api/exams", json={
        "name": "Scan Test Exam", "class_id": class_id, "max_marks": n_questions * 2,
    }).json()["id"]
    keys = ["(A) alpha", "(B) beta", "(C) gamma", "(D) delta"]
    questions = []
    for n in range(1, n_questions + 1):
        correct = keys[(n - 1) % 4]
        questions.append({
            "qtype": "mcq", "difficulty": "easy", "marks": 2,
            "text": f"Question {n}?", "options": ["(A) alpha", "(B) beta", "(C) gamma", "(D) delta"],
            "correct_answer": correct,
        })
    client.post("/api/questions/bulk-save", json={"class_id": class_id, "exam_id": exam_id, "questions": questions})
    return exam_id


def _synthetic_scan(paper_json: dict, answers: dict[int, int | None],
                    rotate_deg: float = 1.8) -> bytes:
    """Draw a filled OMR sheet at canonical coordinates, mark answers, rotate, JPEG."""
    from app.schemas import PaperOut

    paper = PaperOut.model_validate(paper_json)
    geo = sheet_geometry(paper, "A", page=0)
    assert geo["pages"] == 1

    px = 8.0  # canonical pixels per mm
    W = int(geo["page_mm"][0] * px)
    H = int(geo["page_mm"][1] * px)
    img = np.full((H, W), 255, dtype=np.uint8)

    def mm(pt: tuple[float, float]) -> tuple[int, int]:
        return int(pt[0] * px), int(pt[1] * px)

    # registration squares — solid black, like the print
    sq = int(geo["square_size_mm"] * px)
    for corner, (sx, sy) in geo["squares"].items():
        cx, cy = mm((sx, sy))
        cv2.rectangle(img, (cx - sq // 2, cy - sq // 2), (cx + sq // 2, cy + sq // 2), 0, -1)

    # bubble outlines (thin dark circles) and the student's marks
    r = int(1.55 * px)
    for row in geo["rows"]:
        for x in row["xs"]:
            cx, cy = mm((x, row["y"]))
            cv2.circle(img, (cx, cy), r, 60, max(1, int(0.28 * px)))
        chosen = answers.get(row["position"])
        if chosen is not None:
            cx, cy = mm((row["xs"][chosen], row["y"]))
            cv2.circle(img, (cx, cy), r, 0, -1)

    # simulate a slightly careless scanner: small rotation + noise + JPEG
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rotate_deg, 1.0)
    img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)
    noise = np.random.default_rng(7).normal(0, 6, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    assert ok
    return enc.tobytes()


def test_scan_read_and_scored(client, class_id):
    """A marked, slightly rotated scan reads back the right answers and score."""
    exam_id = _make_mcq_paper(client, class_id)

    paper_json = client.get(f"/api/papers/{exam_id}").json()
    # student answers q1=A, q2=B, q3=C, q4=blank — keys march A,B,C,D
    scan_bytes = _synthetic_scan(paper_json, {1: 0, 2: 1, 3: 2, 4: None})
    result = client.post(
        f"/api/papers/{exam_id}/omr-scans", data={"set": "A"},
        files=[("files", ("student1.jpg", scan_bytes, "image/jpeg"))],
    )
    assert result.status_code == 200, result.text
    scan = result.json()["items"][0]
    assert scan["status"] == "pending"

    processed = client.post(f"/api/papers/{exam_id}/omr-scans/{scan['id']}/process")
    assert processed.status_code == 200, processed.text
    body = processed.json()
    assert body["status"] in ("processed", "review"), body
    assert body["score"] == 6.0, body          # q1..q3 correct (2 marks each), q4 blank
    assert body["max_score"] == 8.0
    assert body["confidence_band"] in ("GREEN", "YELLOW")

    detail = client.get(f"/api/papers/{exam_id}/omr-scans/{scan['id']}").json()
    rows = {r["position"]: r for r in detail["responses"]}
    assert rows[1]["correct"] is True and rows[1]["chosen"] == 0
    assert rows[2]["correct"] is True and rows[2]["chosen"] == 1
    assert rows[3]["correct"] is True and rows[3]["chosen"] == 2
    assert rows[4]["verdict"] == "unanswered" and rows[4]["correct"] is False

    listing = client.get(f"/api/papers/{exam_id}/omr-scans").json()
    assert listing["summary"]["processed"] + listing["summary"]["needs_review"] >= 1


def test_scan_flags_multi_mark(client, class_id):
    """Two darkened bubbles on one row must be flagged, never scored."""
    exam_id = _make_mcq_paper(client, class_id, n_questions=2)
    paper_json = client.get(f"/api/papers/{exam_id}").json()
    scan_bytes = _synthetic_scan(paper_json, {1: 0, 2: 1})
    # add a second mark on question 1 (option B as well)
    from app.schemas import PaperOut
    geo = sheet_geometry(PaperOut.model_validate(paper_json), "A", 0)
    px, r = 8.0, int(1.55 * 8.0)
    ok, enc = cv2.imencode(".jpg", _draw_extra_mark(scan_bytes, geo, px, r, position=1, option=1),
                           [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok

    result = client.post(
        f"/api/papers/{exam_id}/omr-scans", data={"set": "A"},
        files=[("files", ("double.jpg", enc.tobytes(), "image/jpeg"))],
    )
    scan = result.json()["items"][0]
    processed = client.post(f"/api/papers/{exam_id}/omr-scans/{scan['id']}/process").json()
    assert processed["status"] == "review"
    assert processed["confidence_band"] == "YELLOW"
    detail = client.get(f"/api/papers/{exam_id}/omr-scans/{scan['id']}").json()
    row1 = next(r for r in detail["responses"] if r["position"] == 1)
    assert row1["verdict"] == "multi"
    assert processed["score"] == 2.0  # only question 2's correct answer counts


def _draw_extra_mark(jpeg_bytes: bytes, geo, px: float, r: int, position: int, option: int) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    row = next(r_ for r_ in geo["rows"] if r_["position"] == position)
    cx, cy = int(row["xs"][option] * px), int(row["y"] * px)
    cv2.circle(img, (cx, cy), r, 0, -1)
    return img


def test_scan_negative_marking(client, class_id):
    """Wrong answers deduct the exam's negative marks; blanks never do."""
    client.post("/api/settings/logo", files={"file": ("logo.png", TINY_PNG, "image/png")})
    exam_id = client.post("/api/exams", json={
        "name": "Negative Marking Exam", "class_id": class_id, "max_marks": 6,
        "negative_marks": 0.5,
    }).json()["id"]
    keys = ["(A) alpha", "(B) beta", "(C) gamma"]
    questions = []
    for n in range(1, 4):
        questions.append({
            "qtype": "mcq", "difficulty": "easy", "marks": 2,
            "text": f"Question {n}?", "options": keys, "correct_answer": keys[n - 1],
        })
    client.post("/api/questions/bulk-save", json={"class_id": class_id, "exam_id": exam_id, "questions": questions})

    # paper confirms the exam's rule travels with it
    paper_json = client.get(f"/api/papers/{exam_id}").json()
    assert paper_json["negative_marks"] == 0.5

    # student: q1 correct, q2 wrong (marked C instead of B), q3 blank
    scan_bytes = _synthetic_scan(paper_json, {1: 0, 2: 2, 3: None})
    result = client.post(
        f"/api/papers/{exam_id}/omr-scans", data={"set": "A"},
        files=[("files", ("neg.jpg", scan_bytes, "image/jpeg"))],
    )
    scan = result.json()["items"][0]
    processed = client.post(f"/api/papers/{exam_id}/omr-scans/{scan['id']}/process").json()
    # 2 marks for q1, -0.5 for the wrong q2, 0 for the blank q3
    assert processed["score"] == 1.5, processed
    assert processed["max_score"] == 6.0

    # clearing the wrong answer by hand removes its penalty too
    detail = client.get(f"/api/papers/{exam_id}/omr-scans/{scan['id']}").json()
    corrected = client.patch(
        f"/api/papers/{exam_id}/omr-scans/{scan['id']}/responses?position=2&chosen=1"
    ).json()
    assert corrected["score"] == 4.0, corrected  # q1 and q2 both correct now

    # a plain exam keeps the old behaviour (no deduction)
    plain_exam = client.post("/api/exams", json={
        "name": "Plain Exam", "class_id": class_id, "max_marks": 6,
    }).json()
    assert plain_exam["negative_marks"] == 0.0


def _jpeg_to_pdf(*pages_jpeg: bytes) -> bytes:
    """Wrap scan images into a PDF exactly like a scanner/photocopier would."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for jpg in pages_jpeg:
        c.drawImage(ImageReader(io.BytesIO(jpg)), 0, 0, width=A4[0], height=A4[1])
        c.showPage()
    c.save()
    return buf.getvalue()


def test_scan_pdf_upload(client, class_id):
    """A scanned PDF sheet goes through rasterisation and scores the same."""
    exam_id = _make_mcq_paper(client, class_id)
    paper_json = client.get(f"/api/papers/{exam_id}").json()
    jpeg = _synthetic_scan(paper_json, {1: 0, 2: 1, 3: 2, 4: None})
    pdf_bytes = _jpeg_to_pdf(jpeg)

    result = client.post(
        f"/api/papers/{exam_id}/omr-scans", data={"set": "A"},
        files=[("files", ("sheet.pdf", pdf_bytes, "application/pdf"))],
    )
    assert result.status_code == 200, result.text
    items = result.json()["items"]
    assert len(items) == 1
    assert "sheet.pdf" in items[0]["original_name"] and "page 1" in items[0]["original_name"]

    processed = client.post(f"/api/papers/{exam_id}/omr-scans/{items[0]['id']}/process").json()
    assert processed["status"] in ("processed", "review"), processed
    assert processed["score"] == 6.0, processed
    assert processed["max_score"] == 8.0


def test_scan_multipage_pdf_splits_into_sheets(client, class_id):
    """A stack of two students scanned into one PDF becomes two sheets."""
    exam_id = _make_mcq_paper(client, class_id, n_questions=2)
    paper_json = client.get(f"/api/papers/{exam_id}").json()
    jpeg1 = _synthetic_scan(paper_json, {1: 0, 2: 1})   # both correct
    jpeg2 = _synthetic_scan(paper_json, {1: 1, 2: 2}, )  # both wrong
    pdf_bytes = _jpeg_to_pdf(jpeg1, jpeg2)

    result = client.post(
        f"/api/papers/{exam_id}/omr-scans", data={"set": "A"},
        files=[("files", ("class_stack.pdf", pdf_bytes, "application/pdf"))],
    )
    assert result.status_code == 200, result.text
    items = result.json()["items"]
    assert len(items) == 2
    assert "page 1" in items[0]["original_name"]
    assert "page 2" in items[1]["original_name"]

    scores = []
    for scan in items:
        processed = client.post(f"/api/papers/{exam_id}/omr-scans/{scan['id']}/process").json()
        scores.append(processed["score"])
    assert scores == [4.0, 0.0], scores

    listing = client.get(f"/api/papers/{exam_id}/omr-scans").json()
    assert listing["summary"]["total"] == 2


def test_results_assign_rank_and_stats(client, class_id):
    """Assigned sheets get names, ranks and honest class statistics."""
    exam_id = _make_mcq_paper(client, class_id, n_questions=2)
    # make passing realistic for a 4-mark test
    client.put(f"/api/exams/{exam_id}", json={
        "name": "Scan Test Exam", "exam_type": "Unit Test", "academic_session": "",
        "class_id": class_id, "subject_id": None, "exam_date": None,
        "max_marks": 4, "passing_marks": 2, "negative_marks": 0,
        "duration_minutes": 60, "status": "published", "instructions": "",
    })

    st1 = client.post("/api/students", json={"full_name": "Aarav Kumar", "class_id": class_id, "roll_no": 1}).json()["id"]
    st2 = client.post("/api/students", json={"full_name": "Ishita Devi", "class_id": class_id, "roll_no": 2}).json()["id"]

    paper_json = client.get(f"/api/papers/{exam_id}").json()
    j1 = _synthetic_scan(paper_json, {1: 0, 2: 1})   # both correct -> 4
    j2 = _synthetic_scan(paper_json, {1: 1, 2: 0})   # both wrong -> 0
    result = client.post(
        f"/api/papers/{exam_id}/omr-scans", data={"set": "A"},
        files=[("files", ("a.jpg", j1, "image/jpeg")), ("files", ("b.jpg", j2, "image/jpeg"))],
    )
    items = result.json()["items"]
    for scan in items:
        client.post(f"/api/papers/{exam_id}/omr-scans/{scan['id']}/process")
    client.post(f"/api/papers/{exam_id}/omr-scans/{items[0]['id']}/assign", json={"student_id": st1})
    client.post(f"/api/papers/{exam_id}/omr-scans/{items[1]['id']}/assign", json={"student_id": st2})

    results = client.get(f"/api/papers/{exam_id}/results").json()
    rows = results["rows"]
    assert len(rows) == 2
    assert rows[0]["student_name"] == "Aarav Kumar" and rows[0]["rank"] == 1
    assert rows[0]["score"] == 4.0 and rows[0]["passed"] is True
    assert rows[1]["student_name"] == "Ishita Devi" and rows[1]["rank"] == 2
    assert rows[1]["passed"] is False  # 0 < passing 2
    stats = results["stats"]
    assert stats["sheets_scored"] == 2 and stats["students_ranked"] == 2
    assert stats["highest"] == 4.0 and stats["average_percent"] == 50.0
    assert stats["pass_count"] == 1 and stats["unassigned"] == 0

    # a student from another class cannot be assigned
    classes = client.get("/api/academics/classes").json()
    other_class = next(c["id"] for c in (classes["items"] if isinstance(classes, dict) else classes) if c["id"] != class_id)
    other = client.post("/api/students", json={"full_name": "Other Kid", "class_id": other_class, "roll_no": 5}).json()
    refused = client.post(f"/api/papers/{exam_id}/omr-scans/{items[0]['id']}/assign",
                          json={"student_id": other["id"]})
    assert refused.status_code == 400

    # clearing the assignment drops the name and rank
    client.post(f"/api/papers/{exam_id}/omr-scans/{items[0]['id']}/assign", json={"student_id": None})
    results2 = client.get(f"/api/papers/{exam_id}/results").json()
    row0 = next(r for r in results2["rows"] if r["scan_id"] == items[0]["id"])
    assert row0["student_name"] is None and row0["rank"] is None
    assert results2["stats"]["unassigned"] == 1


def test_scan_rejects_bad_pdf(client, class_id):
    """A corrupt PDF is refused at upload with a helpful message, not a crash."""
    exam_id = _make_mcq_paper(client, class_id, n_questions=2)
    result = client.post(
        f"/api/papers/{exam_id}/omr-scans", data={"set": "A"},
        files=[("files", ("broken.pdf", b"%PDF-1.4 this is not really a pdf", "application/pdf"))],
    )
    assert result.status_code == 400
    assert "could not be opened" in result.json()["detail"]


def test_scan_rejects_garbage(client, class_id):
    """Non-image uploads are refused with a helpful message, not a crash."""
    exam_id = _make_mcq_paper(client, class_id, n_questions=2)
    result = client.post(
        f"/api/papers/{exam_id}/omr-scans", data={"set": "A"},
        files=[("files", ("notes.txt", b"not an image", "text/plain"))],
    )
    assert result.status_code == 400
    assert "JPG, PNG or PDF" in result.json()["detail"]

    unreadable = client.post(
        f"/api/papers/{exam_id}/omr-scans", data={"set": "A"},
        files=[("files", ("fake.jpg", b"\xff\xd8\xffnot really", "image/jpeg"))],
    )
    assert unreadable.status_code == 200  # stored, will fail at processing time
    scan = unreadable.json()["items"][0]
    processed = client.post(f"/api/papers/{exam_id}/omr-scans/{scan['id']}/process").json()
    assert processed["status"] == "failed"
    assert "not a readable image" in processed["error_message"]
