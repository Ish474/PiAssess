"""Phase 3 tests: AI service, question bank, verification, papers."""
from __future__ import annotations

import pytest

from app.services.ai import (
    content_hash_of,
    normalize_draft,
    parse_llm_json,
    verify_numeric_answer,
)


# ---------------------------------------------------------------- sympy verification
def test_sympy_verifies_correct_maths():
    assert verify_numeric_answer("(15*40 + 2*60)/12", "60") is True
    assert verify_numeric_answer("23*17", "391") is True
    assert verify_numeric_answer("3 + 4 * 2", "11") is True
    assert verify_numeric_answer("1/2 + 1/3", "5/6") is True


def test_sympy_rejects_wrong_maths():
    assert verify_numeric_answer("23*17", "392") is False
    assert verify_numeric_answer("100/3", "33") is False


def test_sympy_handles_garbage_safely():
    assert verify_numeric_answer("solve(x**2)", "5") is None
    assert verify_numeric_answer("", "") is None
    assert verify_numeric_answer("abc !!!", "42") is None
    assert verify_numeric_answer("1,234*2", "2468") is True  # commas stripped


# ---------------------------------------------------------------- LLM answer parsing
def test_parse_llm_json_plain():
    assert parse_llm_json('{"questions": [1, 2]}') == {"questions": [1, 2]}


def test_parse_llm_json_with_fences_and_prose():
    raw = 'Here is your paper:\n```json\n{"questions": [{"text": "x"}]}\n```\nHope this helps!'
    assert parse_llm_json(raw)["questions"][0]["text"] == "x"


def test_parse_llm_json_balanced_braces_fallback():
    raw = 'Sure! {"questions": [{"text": "has } brace inside"}]} done'
    assert parse_llm_json(raw)["questions"][0]["text"] == "has } brace inside"


def test_parse_llm_json_failure():
    from app.services.ai import AIGenerationError

    with pytest.raises(AIGenerationError):
        parse_llm_json("no json at all")


# ---------------------------------------------------------------- draft normalisation
def test_normalize_draft_defaults_and_validation():
    d = normalize_draft({
        "type": "NUMERICAL", "difficulty": "wild", "marks": "3", "text": "Add: 2+2?",
        "options": ["", "  "], "correct_answer": " 4 ", "check_expression": "2+2",
    }, {"numerical": "Numerical Problem"})
    assert d["qtype"] == "numerical"
    assert d["difficulty"] == "moderate"  # invalid -> default
    assert d["marks"] == 3
    assert d["options"] == []
    assert d["correct_answer"] == "4"


def test_normalize_draft_rejects_unknown_type():
    from app.services.ai import AIGenerationError

    with pytest.raises(AIGenerationError):
        normalize_draft({"type": "essay", "text": "x"}, {})


def test_normalize_draft_maps_llm_type_variants():
    """LLM paraphrases like 'application_based' must map to canonical keys."""
    from app.models import QUESTION_TYPES

    for raw, expected in (
        ("application_based", "application"),
        ("Application-Based", "application"),
        ("fill in the blanks", "fill_blank"),
        ("true-or-false", "true_false"),
        ("case study", "case_based"),
        ("Match The Following", "match_following"),
        ("higher_order_thinking", "hots"),
        ("numericals", "numerical"),
    ):
        d = normalize_draft({"type": raw, "text": "x"}, QUESTION_TYPES)
        assert d["qtype"] == expected, f"{raw} -> {d['qtype']} (wanted {expected})"


def test_content_hash_normalisation():
    a = content_hash_of("mcq", "What  is   2+2?", "(A) 4")
    b = content_hash_of("mcq", "what is 2+2?", "(A) 4")
    assert a == b
    assert a != content_hash_of("mcq", "What is 2+3?", "(A) 4")


# ---------------------------------------------------------------- API: question bank
def _meta(client):
    return client.get("/api/questions/meta").json()


def test_question_manual_add_dedup_and_list(client, class_id):
    r = client.post("/api/questions", json={
        "class_id": class_id, "qtype": "short", "marks": 2,
        "text": "Define photosynthesis.", "correct_answer": "Process by which plants make food",
        "chapter": "Life Processes",
    })
    assert r.status_code == 200, r.text
    qid = r.json()["id"]
    assert r.json()["verification"] == "unverified"

    # exact duplicate (same type+text+answer) must be refused
    r = client.post("/api/questions", json={
        "class_id": class_id, "qtype": "short", "marks": 2,
        "text": "Define   photosynthesis.", "correct_answer": "process by which plants make food",
    })
    assert r.status_code == 409

    r = client.get("/api/questions", params={"search": "photosynthesis"})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["id"] == qid


def test_question_verification_workflow(client, class_id):
    qid = client.post("/api/questions", json={
        "class_id": class_id, "qtype": "true_false", "text": "The sun rises in the east.",
        "correct_answer": "True",
    }).json()["id"]
    r = client.post(f"/api/questions/{qid}/verify", json={"verification": "verified", "note": "Checked by teacher"})
    assert r.json()["verification"] == "verified"
    assert "teacher" in r.json()["verification_note"]
    r = client.get("/api/questions", params={"verification": "verified"})
    assert r.json()["total"] == 1


def test_bulk_save_with_dedup_and_paper(client, class_id):
    exam_id = client.post("/api/exams", json={"name": "Paper Test", "class_id": class_id}).json()["id"]
    drafts = [
        {"qtype": "mcq", "difficulty": "easy", "marks": 1, "text": "Capital of Bihar?",
         "options": ["(A) Patna", "(B) Ranchi", "(C) Kolkata", "(D) Delhi"], "correct_answer": "(A) Patna"},
        {"qtype": "numerical", "difficulty": "moderate", "marks": 3, "text": "Evaluate 17*23.",
         "correct_answer": "391", "check_expression": "17*23"},
        {"qtype": "mcq", "difficulty": "easy", "marks": 1, "text": "Capital of Bihar?",
         "options": ["(A) Patna"], "correct_answer": "(A) Patna"},  # duplicate
    ]
    r = client.post("/api/questions/bulk-save", json={
        "class_id": class_id, "exam_id": exam_id, "questions": drafts,
    })
    body = r.json()
    assert body["saved"] == 2
    assert body["duplicates_skipped"] == 1
    assert body["paper_id"] is not None

    # numerical one is SymPy-verified
    qs = client.get("/api/questions", params={"exam_id": exam_id}).json()["items"]
    numerical = [q for q in qs if q["qtype"] == "numerical"][0]
    assert numerical["verification"] == "verified"


def test_paper_reorder_marks_and_totals(client, class_id):
    exam_id = client.post("/api/exams", json={"name": "Reorder Test", "class_id": class_id}).json()["id"]
    ids = []
    for i in range(3):
        r = client.post("/api/questions/bulk-save", json={
            "class_id": class_id, "exam_id": exam_id,
            "questions": [{"qtype": "short", "marks": 2, "text": f"Question {chr(65 + i)}?", "correct_answer": "x"}],
        }).json()
        ids.append(r["ids"][0])

    paper = client.get(f"/api/papers/{exam_id}").json()
    assert [i["question"]["id"] for i in paper["items"]] == ids
    assert paper["total_marks"] == 6

    # reorder: move third to first, change marks
    new_items = [{"question_id": ids[2], "position": 1, "marks": 5},
                 {"question_id": ids[0], "position": 2, "marks": 2},
                 {"question_id": ids[1], "position": 3, "marks": 2}]
    r = client.put(f"/api/papers/{exam_id}", json={"items": new_items, "instructions": "Attempt all."}).json()
    assert [i["question"]["id"] for i in r["items"]] == [ids[2], ids[0], ids[1]]
    assert r["total_marks"] == 9
    assert r["instructions"] == "Attempt all."


def test_paper_missing_returns_404(client, class_id):
    assert client.get("/api/papers/99999").status_code == 404


def test_paper_autocreate_on_first_save(client, class_id):
    """PUT to an exam with no paper creates the paper (editor can start from scratch)."""
    exam_id = client.post("/api/exams", json={"name": "Autocreate", "class_id": class_id}).json()["id"]
    r = client.put(f"/api/papers/{exam_id}", json={"title": "My Paper", "items": []})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["exam_id"] == exam_id
    assert body["class_id"] == class_id
    assert body["title"] == "My Paper"
    # a second PUT updates the same paper instead of creating another
    r2 = client.put(f"/api/papers/{exam_id}", json={"title": "Renamed"})
    assert r2.json()["id"] == body["id"]


# ---------------------------------------------------------------- API: generation with mocked LLM
@pytest.fixture()
def fake_llm(monkeypatch):
    def _fake(db, messages, **kwargs):
        return '''
        {"questions": [
          {"type": "mcq", "difficulty": "easy", "marks": 1, "text": "Mock MCQ about Pi?",
           "options": ["(A) 3.14", "(B) 2.17", "(C) 9.81", "(D) 1.61"], "correct_answer": "(A) 3.14",
           "explanation": "Pi is 3.14...", "keywords": ["pi"], "marking_notes": "1 mark", "check_expression": ""},
          {"type": "numerical", "difficulty": "moderate", "marks": 3, "text": "Compute 45 x 12.",
           "options": [], "correct_answer": "540", "explanation": "Multiply.", "keywords": [],
           "marking_notes": "1 mark per step", "check_expression": "45*12"},
          {"type": "numerical", "difficulty": "moderate", "marks": 2, "text": "Compute 99 x 2.",
           "options": [], "correct_answer": "123", "explanation": "Multiply.", "keywords": [],
           "marking_notes": "", "check_expression": "99*2"}
        ]}
        '''

    from app.services import ai

    monkeypatch.setattr(ai, "chat_complete", _fake)
    return _fake


def test_generate_endpoint_with_mocked_llm(client, class_id, fake_llm):
    r = client.post("/api/ai/generate", json={
        "class_id": class_id, "chapters": "Integers",
        "types": [{"type": "mcq", "count": 1, "difficulty": "easy", "marks": 1},
                  {"type": "numerical", "count": 2, "difficulty": "moderate", "marks": 3}],
    })
    assert r.status_code == 200, r.text
    drafts = r.json()["questions"]
    assert len(drafts) == 3
    assert drafts[0]["verification"] == "unverified"          # MCQ: AI alone is never "verified"
    assert drafts[1]["verification"] == "verified"            # 45*12 == 540 — SymPy proof
    assert drafts[2]["verification"] == "needs_review"        # 99*2 != 123 — flagged honestly
    assert r.json()["skipped"] == 0


def test_generate_skips_bad_drafts_without_losing_good_ones(client, class_id, monkeypatch):
    """One malformed draft (unknown type) must not throw away the whole batch."""
    import json as _json

    from app.services import ai

    def _fake(db, messages, **kwargs):
        return _json.dumps({"questions": [
            {"type": "mcq", "difficulty": "easy", "marks": 1, "text": "Good MCQ?",
             "options": ["(A) 1", "(B) 2", "(C) 3", "(D) 4"], "correct_answer": "(B) 2"},
            {"type": "application_based", "difficulty": "moderate", "marks": 2,
             "text": "Apply your knowledge.", "correct_answer": "x"},  # paraphrased type -> maps to "application"
        ]})

    monkeypatch.setattr(ai, "chat_complete", _fake)
    r = client.post("/api/ai/generate", json={
        "class_id": class_id, "types": [{"type": "mcq", "count": 1}, {"type": "application", "count": 1}],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["questions"]) == 2
    assert [q["qtype"] for q in body["questions"]] == ["mcq", "application"]


def test_generate_skips_truly_unknown_type_and_reports(client, class_id, monkeypatch):
    import json as _json

    from app.services import ai

    def _fake(db, messages, **kwargs):
        return _json.dumps({"questions": [
            {"type": "mcq", "difficulty": "easy", "marks": 1, "text": "Good MCQ?",
             "options": ["(A) 1", "(B) 2"], "correct_answer": "(A) 1"},
            {"type": "viva_viva_s special", "text": "???"},
        ]})

    monkeypatch.setattr(ai, "chat_complete", _fake)
    r = client.post("/api/ai/generate", json={
        "class_id": class_id, "types": [{"type": "mcq", "count": 1}],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["questions"]) == 1
    assert body["skipped"] == 1
    assert "unknown question type" in body["skipped_notes"][0]


def test_generate_requires_configured_provider(client, class_id, monkeypatch):
    from app.services import ai

    def _no_config(db):
        return ai.AIConfig(base_url="", api_key="", model="")

    monkeypatch.setattr(ai, "get_ai_config", _no_config)
    r = client.post("/api/ai/generate", json={
        "class_id": class_id, "types": [{"type": "short", "count": 1}],
    })
    assert r.status_code == 400
    assert "AI provider" in r.json()["detail"]


def test_ai_status_endpoint(client):
    r = client.get("/api/ai/status").json()
    assert set(r.keys()) == {"configured", "provider", "model", "base_url"}
