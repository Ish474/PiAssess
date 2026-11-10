"""Student bulk import engine: CSV / Excel parsing, column mapping and validation.

Design rules (from the spec):
- never silently discard invalid records — every problem is reported per row
- duplicates are detected against the database AND within the file
- the caller gets structured results for a preview step before anything is saved
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Klass, Section, Student

FIELD_LABELS: dict[str, str] = {
    "full_name": "Student Name",
    "admission_no": "Admission Number",
    "father_name": "Father's Name",
    "mother_name": "Mother's Name",
    "class_name": "Class",
    "section_name": "Section",
    "roll_no": "Roll Number",
    "dob": "Date of Birth",
    "gender": "Gender",
    "phone": "Contact Number",
    "email": "Email",
    "address": "Address",
    "admission_date": "Admission Date",
    "status": "Status",
}

MAX_IMPORT_ROWS = 2000

_COMMON_HEADER_ALIASES = {
    "full_name": {"name", "student name", "studentname", "full name", "student"},
    "admission_no": {"admission no", "admission number", "admissionno", "admission_no", "adm no", "admn no"},
    "father_name": {"father name", "father's name", "fathers name", "father"},
    "mother_name": {"mother name", "mother's name", "mothers name", "mother"},
    "class_name": {"class", "class name", "grade", "standard"},
    "section_name": {"section", "sec", "div", "division"},
    "roll_no": {"roll", "roll no", "roll number", "rollno", "roll_no"},
    "dob": {"dob", "date of birth", "birth date", "birthday"},
    "gender": {"gender", "sex"},
    "phone": {"phone", "contact", "mobile", "contact number", "phone number", "mobile number"},
    "email": {"email", "e-mail", "email id"},
    "address": {"address", "residence", "home address"},
    "admission_date": {"admission date", "doa", "date of admission"},
    "status": {"status"},
}


def read_tabular(filename: str, raw: bytes) -> tuple[list[str], list[dict]]:
    """Return (header_columns, rows_as_dicts_with_header_keys)."""
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        return _read_xlsx(raw)
    if name.endswith(".xls"):
        raise ValueError("Legacy .xls files are not supported. Please save the file as .xlsx or .csv and try again.")
    return _read_csv(raw)


def _read_csv(raw: bytes) -> tuple[list[str], list[dict]]:
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if not rows:
        return [], []
    header = [(c or "").strip() for c in rows[0]]
    dict_rows = []
    for r in rows[1:]:
        d = {}
        for i, col in enumerate(header):
            if col:
                d[col] = (r[i].strip() if i < len(r) else "")
        dict_rows.append({k: v for k, v in d.items()})
    return header, dict_rows


def _read_xlsx(raw: bytes) -> tuple[list[str], list[dict]]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError("The Excel file appears to be empty.")
    rows_iter = ws.iter_rows(values_only=True)
    header: list[str] = []
    out: list[dict] = []
    for i, row in enumerate(rows_iter):
        cells = ["" if c is None else str(c).strip() for c in row]
        if not any(cells):
            continue
        if i == 0 or not header:
            header = cells
            continue
        d = {}
        for j, col in enumerate(header):
            if col:
                d[col] = cells[j] if j < len(cells) else ""
        out.append(d)
    wb.close()
    return header, out


def guess_mapping(columns: list[str]) -> dict[str, str]:
    """Best-effort automatic column mapping: field -> column header."""
    mapping: dict[str, str] = {}
    lowered = {c: c.strip().lower() for c in columns}
    for field, aliases in _COMMON_HEADER_ALIASES.items():
        for col, low in lowered.items():
            if low in aliases:
                mapping[field] = col
                break
    for field, aliases in _COMMON_HEADER_ALIASES.items():
        if field in mapping:
            continue
        for col, low in lowered.items():
            if any(a in low or low in a for a in aliases) and col not in mapping.values():
                mapping[field] = col
                break
    return mapping


_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%m/%d/%Y", "%Y/%m/%d")


def parse_date_safe(value: str) -> date | None:
    v = (value or "").strip()
    if not v:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    # Excel serial number?
    if re.fullmatch(r"\d{5}", v):
        try:
            return date(1899, 12, 30) + timedelta(days=int(v))
        except (ValueError, OverflowError):
            return None
    return None


def validate_rows(db: Session, mapped_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validate mapped rows. Returns (valid_rows, rejected_rows_with_errors).

    valid_rows contain typed values; rejected rows carry a list of human-readable errors.
    """
    classes = {k.name.strip().lower(): k for k in db.query(Klass).all()}
    sections: dict[int, dict[str, Section]] = {}
    for s in db.query(Section).all():
        sections.setdefault(s.class_id, {})[s.name.strip().lower()] = s

    existing_adm = {a for (a,) in db.execute(select(Student.admission_no).where(Student.admission_no != "")).all()}
    seen_in_file: set[tuple] = set()

    valid: list[dict] = []
    rejected: list[dict] = []

    for idx, row in enumerate(mapped_rows, start=2):  # row 1 is the header
        errors: list[str] = []
        full_name = (row.get("full_name") or "").strip()
        if not full_name:
            errors.append("Student Name is required.")
        if len(full_name) > 160:
            errors.append("Student Name is too long.")

        class_name = (row.get("class_name") or "").strip()
        klass = classes.get(class_name.lower())
        if not class_name:
            errors.append("Class is required.")
        elif klass is None:
            # allow "10" to match "Class 10"
            klass = classes.get(f"class {class_name}")
        if klass is None and class_name:
            errors.append(f"Class \"{class_name}\" does not exist. Add it under Class & Subject Management first.")

        section = None
        section_name = (row.get("section_name") or "").strip()
        if klass is not None and section_name:
            section = sections.get(klass.id, {}).get(section_name.lower())
            if section is None:
                errors.append(f"Section \"{section_name}\" does not exist in {klass.name}.")

        roll_no = None
        roll_raw = (row.get("roll_no") or "").strip()
        if roll_raw:
            try:
                roll_no = int(float(roll_raw))
                if roll_no < 1:
                    raise ValueError
            except ValueError:
                errors.append(f"Roll Number \"{roll_raw}\" is not a valid number.")

        adm = (row.get("admission_no") or "").strip()
        if adm and adm in existing_adm:
            errors.append(f"Admission Number \"{adm}\" already exists in the database.")
        key = (full_name.lower(), klass.id if klass else 0, roll_no or (row.get("roll_no") or "").strip())
        if full_name and key in seen_in_file:
            errors.append("Duplicate of an earlier row in this file (same name, class and roll number).")
        if full_name:
            seen_in_file.add(key)

        dob = parse_date_safe(row.get("dob") or "")
        if (row.get("dob") or "").strip() and dob is None:
            errors.append(f"Date of Birth \"{row.get('dob')}\" is not a recognised date (use DD/MM/YYYY).")

        admission_date = parse_date_safe(row.get("admission_date") or "")
        if (row.get("admission_date") or "").strip() and admission_date is None:
            errors.append(f"Admission Date \"{row.get('admission_date')}\" is not a recognised date (use DD/MM/YYYY).")

        gender = (row.get("gender") or "").strip().lower()
        if gender and gender not in ("male", "female", "other", "m", "f"):
            errors.append(f"Gender \"{gender}\" should be Male, Female or Other.")
        gender = {"m": "male", "f": "female"}.get(gender, gender)

        status = (row.get("status") or "active").strip().lower()
        if status not in ("active", "inactive", "passed", "transferred"):
            status = "active"

        email = (row.get("email") or "").strip()
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors.append(f"Email \"{email}\" does not look valid.")

        record = {
            "full_name": full_name,
            "admission_no": adm,
            "father_name": (row.get("father_name") or "").strip(),
            "mother_name": (row.get("mother_name") or "").strip(),
            "class_id": klass.id if klass else None,
            "section_id": section.id if section else None,
            "roll_no": roll_no,
            "dob": dob,
            "gender": gender,
            "phone": (row.get("phone") or "").strip(),
            "email": email,
            "address": (row.get("address") or "").strip(),
            "admission_date": admission_date,
            "status": status,
        }
        if errors:
            rejected.append({"row_number": idx, "data": row, "errors": errors})
        else:
            valid.append(record)

    return valid, rejected
