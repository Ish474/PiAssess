"""Student registration, ID generation, import validation tests."""
from __future__ import annotations

import io

from app.services.imports import guess_mapping, parse_date_safe, validate_rows


def test_student_id_format_and_uniqueness(client):
    class_ = client.get("/api/academics/classes").json()[0]
    codes = set()
    for i in range(3):
        r = client.post("/api/students", json={
            "full_name": f"Test Student {i}", "class_id": class_["id"], "roll_no": i + 1,
        })
        assert r.status_code == 200, r.text
        code = r.json()["student_code"]
        assert code.startswith("APWS-2026-")
        assert code.endswith(f"{i + 1:04d}")
        codes.add(code)
    assert len(codes) == 3


def test_duplicate_admission_number_rejected(client, class_id):
    r = client.post("/api/students", json={"full_name": "A Kumar", "class_id": class_id, "admission_no": "ADM-001"})
    assert r.status_code == 200
    r = client.post("/api/students", json={"full_name": "B Kumar", "class_id": class_id, "admission_no": "ADM-001"})
    assert r.status_code == 409


def test_search_and_filters(client, class_id):
    client.post("/api/students", json={"full_name": "Ananya Sharma", "class_id": class_id})
    client.post("/api/students", json={"full_name": "Rohit Yadav", "class_id": class_id})
    r = client.get("/api/students", params={"search": "ananya"})
    assert r.json()["total"] == 1
    r = client.get("/api/students", params={"class_id": class_id})
    assert r.json()["total"] >= 2


def test_delete_student(client, class_id):
    r = client.post("/api/students", json={"full_name": "Delete Me", "class_id": class_id})
    sid = r.json()["id"]
    r = client.delete(f"/api/students/{sid}")
    assert r.json()["ok"] is True
    r = client.get(f"/api/students/{sid}")
    assert r.status_code == 404


def test_date_parsing_formats():
    assert parse_date_safe("15/03/2012").isoformat() == "2012-03-15"
    assert parse_date_safe("2012-03-15").isoformat() == "2012-03-15"
    assert parse_date_safe("15-03-2012").isoformat() == "2012-03-15"
    assert parse_date_safe("not a date") is None
    assert parse_date_safe("") is None


def test_import_column_mapping_guess():
    columns = ["Sr", "Student Name", "Father's Name", "Class", "Sec", "Roll No", "DOB", "Mobile"]
    m = guess_mapping(columns)
    assert m["full_name"] == "Student Name"
    assert m["class_name"] == "Class"
    assert m["roll_no"] == "Roll No"
    assert m["dob"] == "DOB"


def test_import_validation_reports_all_errors(client):
    rows = [
        {"full_name": "", "class_name": "Class 1"},                      # missing name
        {"full_name": "X Y", "class_name": "Class 99"},                  # missing class
        {"full_name": "Good One", "class_name": "Class 1", "dob": "01/02/2013"},
    ]
    # bind the db session properly
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        valid, rejected = validate_rows(db, rows)
    finally:
        db.close()
    assert len(valid) == 1
    assert len(rejected) == 2
    assert "Student Name is required." in rejected[0]["errors"][0]
    assert valid[0]["dob"].isoformat() == "2013-02-01"


def test_import_end_to_end_csv(client, class_id):
    csv_data = "Student Name,Class,Section,Roll Number,Gender\nTest Kid A,Class 1,A,1,male\nTest Kid B,Class 1,B,2,Female\n"
    files = {"file": ("students.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    r = client.post("/api/students/import/preview", files=files)
    assert r.status_code == 200, r.text
    preview = r.json()
    assert preview["mapping_hint"]["full_name"] == "Student Name"
    r = client.post("/api/students/import/confirm", json={
        "rows": preview["rows"][0]["data"] and [
            {"Student Name": "Test Kid A", "Class": "Class 1", "Section": "A", "Roll Number": "1", "Gender": "male"},
            {"Student Name": "Test Kid B", "Class": "Class 1", "Section": "B", "Roll Number": "2", "Gender": "Female"},
        ],
        "mapping": {"full_name": "Student Name", "class_name": "Class", "section_name": "Section",
                    "roll_no": "Roll Number", "gender": "Gender"},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 2
    assert body["skipped"] == 0


def test_student_export_csv(client, class_id):
    client.post("/api/students", json={"full_name": "Export Kid", "class_id": class_id})
    r = client.get("/api/students/export", params={"format": "csv"})
    assert r.status_code == 200
    assert "Export Kid" in r.text
    assert "Student ID" in r.text
