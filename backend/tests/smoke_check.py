"""End-to-end smoke test against the running PiAssess server."""
import httpx

BASE = "http://127.0.0.1:8600"
out = {}

c = httpx.Client(base_url=BASE, timeout=30)

# 1. login + CSRF
r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
assert r.status_code == 200, r.text
csrf = r.json()["csrf_token"]
out["cookie_set"] = "piassess_session" in r.headers.get("set-cookie", "")
c.headers.update({"X-CSRF-Token": csrf})

# 2. seeded classes
classes = c.get("/api/academics/classes").json()
class10 = next(k for k in classes if k["name"] == "Class 10")
out["classes"] = {"count": len(classes), "subjects_class1": len(classes[0]["subjects"]),
                  "sections": [s["name"] for s in class10["sections"]]}

# 3. student create (auto ID)
r = c.post("/api/students", json={"full_name": "Smoke Test Student", "class_id": class10["id"],
                                  "section_id": class10["sections"][0]["id"], "roll_no": 42,
                                  "gender": "male", "dob": "2011-05-14"})
assert r.status_code == 200, r.text
s1 = r.json()
code1 = s1["student_code"]
out["create_student"] = {"code": code1, "class": s1["class_name"], "section": s1["section_name"]}

r = c.post("/api/students", json={"full_name": "Second Student", "class_id": class10["id"]})
code2 = r.json()["student_code"]
out["unique_codes"] = code1 != code2 and code2.endswith("0002")

# 4. dashboard
d = c.get("/api/dashboard").json()
out["dashboard"] = {"students": d["total_students"], "exams": d["total_examinations"],
                    "subjects": d["total_subjects"], "activity_items": len(d["activity"])}

# 5. exam create (session + passing marks default from settings)
r = c.post("/api/exams", json={"name": "Smoke Test - Unit Test", "exam_type": "Unit Test",
                               "class_id": class10["id"], "exam_date": "2026-04-20",
                               "max_marks": 40, "passing_marks": 13})
assert r.status_code == 200, r.text
e = r.json()
out["create_exam"] = {"session": e["academic_session"], "status": e["status"]}

# 6. security: CSRF + unauthenticated
r = c.post("/api/students", json={"full_name": "NoCsrf", "class_id": class10["id"]},
           headers={"X-CSRF-Token": ""})
out["csrf_blocked"] = r.status_code
out["unauth_blocked"] = httpx.get(f"{BASE}/api/students").status_code

# 7. SPA + logo
r = httpx.get(f"{BASE}/students")
out["spa_served"] = r.status_code == 200 and '<div id="root">' in r.text
out["logo_ok"] = httpx.get(f"{BASE}/api/settings/logo").status_code == 200

# 8. backup
r = c.post("/api/settings/backup")
out["backup"] = {"status": r.status_code, "file": r.json().get("file")}

# 9. CSV import end-to-end
files = {"file": ("import.csv", "Student Name,Class,Section,Roll Number\nImport Kid A,Class 10,A,51\nImport Kid B,Class 10,B,52\n".encode(), "text/csv")}
preview = c.post("/api/students/import/preview", files=files).json()
out["import_preview"] = {"columns": preview["columns"], "hint_name": preview["mapping_hint"].get("full_name")}
r = c.post("/api/students/import/confirm", json={"rows": [row["data"] for row in preview["rows"]],
                                                 "mapping": preview["mapping_hint"]})
out["import_confirm"] = r.json()

d2 = c.get("/api/dashboard").json()
out["final_student_count"] = d2["total_students"]

# 10. export
r = c.get("/api/students/export", params={"format": "csv"})
out["export_csv"] = {"status": r.status_code, "has_header": "Student ID" in r.text}

for k, v in out.items():
    print(f"{k}: {v}")
