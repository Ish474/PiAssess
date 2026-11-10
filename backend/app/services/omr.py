"""Printable OMR bubble sheets — modelled on the school's reference OMR sheet.

Layout (matching the supplied Single_Clear_OMR_Sheet.pdf reference):
  * corner tags: ``CLASS <name>`` top-left, ``SET <X>`` top-right
  * dark school banner with the logo and school name in white
  * test name, class/session/date line, subjects line
  * Time / Test code on the left, Maximum Marks / question counts on the right
  * candidate block: Name, Roll No. / Section / Date, both signatures
  * bordered ``Instructions for marking the OMR sheet`` box
  * parallel section boxes (dark header, lettered bubbles, integer digit
    bubbles, per-box ``Marks`` line), 20 rows per box, 4 boxes per page
  * registration squares around the grid, QR code, office-use footer

Bubble rows follow the question-paper numbering exactly — question 7 on the OMR
sheet is question 7 on the printed paper. Questions with options get letter
bubbles; integer/numerical questions get 0–9 digit bubbles.
"""
from __future__ import annotations

import io
import re

from ..schemas import PaperOut

MAROON_HEX = "#791D32"
INK_HEX = "#292329"

LETTERS = "ABCDEFGH"
SETS = ("A", "B", "C", "D")
INTEGER_TYPES = {"numerical", "integer", "integer_type"}
ROWS_PER_BOX = 20
BOXES_PER_PAGE = 4

# fixed vertical geometry (millimetres from the top of the page)
TAG_TOP = 8.0             # CLASS / SET corner tags
TAG_H = 6.0
BANNER_TOP = 17.0         # dark school banner
BANNER_H = 11.0
TEST_NAME_DY = 34.0       # test-name baseline below the banner
META_DY = 38.5            # class | session | date line
SUBJECTS_DY = 45.5
TIME_DY = 54.5
CANDIDATE_NAME_DY = 69.0
CANDIDATE_ROW_DY = 6.6
INSTR_BOX_TOP_DY = 92.5
LABEL_ROW_DY = 6.5        # instructions box bottom -> OMR ANSWER SHEET label
GRID_GAP_DY = 6.0         # label row -> top of section boxes

BOX_HEADER_H = 6.0
BOX_COL_H = 3.0
BOX_ROW_H = 6.0
BOX_MARKS_H = 6.0
BOX_H = BOX_HEADER_H + BOX_COL_H + ROWS_PER_BOX * BOX_ROW_H + BOX_MARKS_H


def _class_label(class_name: str | None) -> str:
    """"Class 4" — without doubling the prefix when the stored name already has it."""
    name = (class_name or "").strip()
    return name if name.lower().startswith("class") else f"Class {name}".strip()


def _answer_index(question) -> int | None:
    """0-based bubble index of an MCQ's correct option; None when it can't be mapped."""
    ans = (question.correct_answer or "").strip()
    opts = [str(o).strip() for o in (question.options or [])]
    if not ans:
        return None
    for i, o in enumerate(opts):          # exact option-text match
        if o == ans:
            return i
    # "(B) y", "B.", "B" — the letter must not be just the start of a word
    m = re.match(r"^\(?([A-Ha-h])\)?(?=\W|\d|$)", ans)
    if m:
        idx = ord(m.group(1).upper()) - ord("A")
        if opts and idx < len(opts):
            return idx
    return None


def _integer_digit(question) -> int | None:
    """The single digit (0-9) of an integer answer; None for anything else."""
    ans = (question.correct_answer or "").strip()
    m = re.fullmatch(r"\(?([0-9])\)?[.:]?", ans)
    return int(m.group(1)) if m else None


def _qr_png(payload: str) -> bytes | None:
    """QR code as PNG bytes; None if the QR library is unavailable."""
    try:
        import segno
    except ImportError:
        return None
    try:
        buf = io.BytesIO()
        segno.make(payload, error="m").save(buf, kind="png", scale=4, border=2)
        return buf.getvalue()
    except Exception:
        return None


def _test_code(paper: PaperOut, set_letter: str) -> str:
    """Deterministic, human-readable test code, e.g. ``WT-002-MA-6-B``."""
    initials = "".join(w[0] for w in (paper.exam_name or "Test").split()[:2]).upper()
    subj = "".join(w[:2] for w in (paper.subject_name or "GS").split())[:4].upper()
    cls = "".join(ch for ch in (paper.class_name or "") if ch.isdigit()) or "00"
    return f"{initials}-{paper.exam_id:03d}-{subj}-{cls}-{set_letter}"


def _fmt_time(minutes: int) -> str:
    if not minutes:
        return ""
    h, m = divmod(minutes, 60)
    parts = []
    if h:
        parts.append(f"{h} Hour{'s' if h > 1 else ''}")
    if m or not parts:
        parts.append(f"{m} Minutes")
    return " ".join(parts)


def _instructions_block(has_integer: bool, box_w_pt: float) -> float:
    """Height (points) of the instructions box for a given inner-page width.

    Shared by the sheet builder and the scanner so both agree on where the
    bubble grid starts.
    """
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph

    from .printing import _ensure_pdf_fonts

    body_font, _bold = _ensure_pdf_fonts()
    instr_lines = [
        "Use only a black or blue ball-point pen. Darken the circle completely.",
        "An answer once marked cannot be changed. Do not use correction fluid or overwrite.",
    ]
    if has_integer:
        instr_lines.append("For integer-type questions, darken the one digit (0 to 9) that is your answer.")
    instr_lines.append("Hand over this sheet to the invigilator at the end of the examination.")
    style = ParagraphStyle(
        "instr", fontName=body_font, fontSize=8, leading=9.8,
        leftIndent=5.5 * mm, firstLineIndent=-5.5 * mm,
    )
    paras = [Paragraph(f"{i}.&nbsp;&nbsp;{t}", style) for i, t in enumerate(instr_lines, start=1)]
    heights = []
    for p in paras:
        _, ph = p.wrap(box_w_pt - 2 * (3 * mm), 30 * mm)
        heights.append(ph)
    title_h = 4.5 * mm
    return title_h + sum(heights) + (len(paras) - 1) * 1.0 * mm + 4.2 * mm


def sheet_geometry(paper: PaperOut, set_letter: str = "A", page: int = 0) -> dict:
    """Canonical mm-from-top-left positions for machine reading of the sheet.

    Returns registration-square centres, per-box bubble centres and the row
    layout — exactly the coordinates the builder draws with.
    """
    eligible = [
        (pos, r) for pos, r in enumerate(paper.items, start=1)
        if (r.question.options and len(r.question.options) >= 2)
        or (r.question.qtype in INTEGER_TYPES)
    ]
    boxes = [eligible[i:i + ROWS_PER_BOX] for i in range(0, len(eligible), ROWS_PER_BOX)]
    page_boxes = boxes[page * BOXES_PER_PAGE:(page + 1) * BOXES_PER_PAGE]

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    W, H = A4
    W_mm, H_mm = W / mm, H / mm
    margin_mm = 12.0
    from reportlab.lib.styles import ParagraphStyle  # noqa: F401  (geometry only)

    has_integer = any(r.question.qtype in INTEGER_TYPES for _, r in eligible)
    box_w_pt = W - 2 * margin_mm * mm
    box_h_pt = _instructions_block(has_integer, box_w_pt) if eligible else 0.0

    label_from_top = INSTR_BOX_TOP_DY + box_h_pt / mm + LABEL_ROW_DY
    grid_top = label_from_top + GRID_GAP_DY       # mm from the top of the page
    grid_bottom = grid_top + BOX_H                # mm from the top of the page
    sq = 3.2
    squares = {  # centre coordinates, mm from top-left — mirrors the builder's draws
        "TL": (margin_mm - 4.6 + sq / 2, grid_top - 0.8 - sq / 2),
        "TR": (W_mm - margin_mm + 1.4 + sq / 2, grid_top - 0.8 - sq / 2),
        "BL": (margin_mm - 4.6 + sq / 2, grid_bottom + 1.4 + sq / 2),
        "BR": (W_mm - margin_mm + 1.4 + sq / 2, grid_bottom + 1.4 + sq / 2),
    }

    n_boxes = max(len(page_boxes), 1)
    gap = 4.0
    box_w = (W_mm - 2 * margin_mm - (n_boxes - 1) * gap) / n_boxes
    gutter, pad_b = 6.5, 2.0
    rows = []  # {"position": paper question number, "integer": bool, "n_opts": int,
    #           "y": mm, "xs": [mm per option], "marks": float}
    for bi, chunk in enumerate(page_boxes):
        x0 = margin_mm + bi * (box_w + gap)
        area_x = x0 + gutter + pad_b
        area_w = box_w - gutter - 2 * pad_b
        y_row0 = grid_top + BOX_HEADER_H + BOX_COL_H
        for j, (num, r) in enumerate(chunk):
            integer = r.question.qtype in INTEGER_TYPES
            n_opts = 10 if integer else min(len(r.question.options), len(LETTERS))
            rows.append({
                "position": num,
                "integer": integer,
                "n_opts": n_opts,
                "y": y_row0 + BOX_ROW_H * (j + 0.5),
                "xs": [area_x + (area_w / n_opts) * (k + 0.5) for k in range(n_opts)],
                "marks": float(r.marks),
            })
    return {
        "page_mm": (W_mm, H_mm),
        "squares": squares,
        "square_size_mm": sq,
        "rows": rows,
        "eligible_count": len(eligible),
        "pages": (len(boxes) + BOXES_PER_PAGE - 1) // BOXES_PER_PAGE,
    }


def build_omr_pdf(paper: PaperOut, school: dict, logo_bytes: bytes | None, set_letter: str = "A",
                  fill_key: bool = False) -> bytes:
    """Render the OMR bubble sheet for the paper's objective questions.

    ``fill_key=True`` produces the teacher's checking copy: correct bubbles
    darkened, a KEY COPY watermark, starred rows where no answer is set.
    Raises ValueError when the paper has nothing to bubble.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import Paragraph

    from .printing import _ensure_pdf_fonts, _fmt_date

    body_font, bold_font = _ensure_pdf_fonts()
    maroon = colors.HexColor(MAROON_HEX)
    ink = colors.HexColor(INK_HEX)
    grey = colors.HexColor("#8A8080")
    line_grey = colors.HexColor("#9A9090")
    white = colors.white

    # eligible rows, numbered exactly as on the printed paper
    eligible = [
        (pos, r) for pos, r in enumerate(paper.items, start=1)
        if (r.question.options and len(r.question.options) >= 2)
        or (r.question.qtype in INTEGER_TYPES)
    ]
    if not eligible:
        raise ValueError(
            "This paper has no MCQ or integer-type questions, so there is nothing to bubble. "
            "Add objective questions to the paper first."
        )
    has_integer = any(r.question.qtype in INTEGER_TYPES for _, r in eligible)
    boxes = [eligible[i:i + ROWS_PER_BOX] for i in range(0, len(eligible), ROWS_PER_BOX)]
    pages = (len(boxes) + BOXES_PER_PAGE - 1) // BOXES_PER_PAGE

    school_name = school.get("school_name") or "Pi World School"
    code = _test_code(paper, set_letter)
    subject_line = paper.subject_name or "General"
    total = paper.exam_max_marks or paper.total_marks
    marks_values = {r.marks for _, r in eligible}
    bonus = f"  |  +{marks_values.pop()}" if len(marks_values) == 1 else ""
    qr = _qr_png(f"PIASSESS-OMR|exam={paper.id}|set={set_letter}|pages={pages}")

    W, H = A4
    margin = 12 * mm
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4, pageCompression=1)
    c.setTitle("OMR Answer Sheet")

    def dotted(x1: float, x2: float, y: float, w: float = 0.6) -> None:
        c.setStrokeColor(line_grey)
        c.setLineWidth(w)
        c.setDash(1.2, 2.2)
        c.line(x1, y, x2, y)
        c.setDash()

    def rule(y: float, width: float = 0.7, color=ink) -> None:
        c.setStrokeColor(color)
        c.setLineWidth(width)
        c.line(margin, y, W - margin, y)

    instr_style = ParagraphStyle(
        "instr", fontName=body_font, fontSize=8, leading=9.8, textColor=ink,
        leftIndent=5.5 * mm, firstLineIndent=-5.5 * mm,  # hanging indent: wrapped lines align
    )

    for page in range(pages):
        page_boxes = boxes[page * BOXES_PER_PAGE:(page + 1) * BOXES_PER_PAGE]
        n_boxes = len(page_boxes)

        # ---- corner tags: CLASS (left) and SET (right)
        tag_h = TAG_H * mm
        tag_w = 30 * mm
        tag_bottom = H - TAG_TOP * mm - tag_h
        c.setFillColor(maroon)
        c.rect(margin, tag_bottom, tag_w, tag_h, stroke=0, fill=1)
        c.rect(W - margin - tag_w, tag_bottom, tag_w, tag_h, stroke=0, fill=1)
        c.setFillColor(white)
        c.setFont(bold_font, 8)
        class_tag = _class_label(paper.class_name).upper()
        c.drawCentredString(margin + tag_w / 2, tag_bottom + 1.8 * mm, class_tag)
        c.drawCentredString(W - margin - tag_w / 2, tag_bottom + 1.8 * mm, f"SET {set_letter}")

        # ---- school banner with logo on a white chip
        banner_top = H - BANNER_TOP * mm
        c.setFillColor(maroon)
        c.rect(margin, banner_top - BANNER_H * mm, W - 2 * margin, BANNER_H * mm, stroke=0, fill=1)
        if logo_bytes:
            try:
                img = ImageReader(io.BytesIO(logo_bytes))
                iw, ih = img.getSize()
                lh = 7 * mm
                lw = lh * iw / ih
                chip_w = lw + 3 * mm
                c.setFillColor(white)
                c.rect(margin + 2.5 * mm, banner_top - BANNER_H * mm + 1.5 * mm, chip_w, 7 * mm, stroke=0, fill=1)
                c.drawImage(img, margin + 4 * mm, banner_top - BANNER_H * mm + 2 * mm, width=lw, height=lh, mask="auto")
            except Exception:
                pass  # a damaged logo must never block the OMR sheet
        c.setFillColor(white)
        c.setFont(bold_font, 13.5)
        c.drawCentredString(W / 2, banner_top - BANNER_H * mm / 2 - 1.6 * mm, school_name)

        # ---- test name + meta line
        c.setFillColor(ink)
        c.setFont(bold_font, 11)
        c.drawCentredString(W / 2, H - TEST_NAME_DY * mm, (paper.exam_name or "Examination").upper())
        meta = "   |   ".join(
            p for p in (
                _class_label(paper.class_name),
                f"Session {paper.academic_session}" if paper.academic_session else "",
                _fmt_date(paper.exam_date),
            ) if p
        )
        c.setFont(body_font, 8)
        c.drawCentredString(W / 2, H - META_DY * mm, meta)

        # ---- subjects line + rules
        c.setFont(bold_font, 13)
        c.drawString(margin, H - SUBJECTS_DY * mm, subject_line)
        rule(H - (SUBJECTS_DY + 3.5) * mm)

        # ---- time / test code (left) — maximum marks / counts (right)
        time_y = H - TIME_DY * mm
        c.setFont(bold_font, 8.5)
        c.drawString(margin, time_y, "Time:")
        c.setFont(body_font, 8.5)
        c.drawString(margin + 10 * mm, time_y, _fmt_time(paper.duration_minutes))
        c.setFont(bold_font, 8.5)
        c.drawString(margin, time_y - 4.6 * mm, "Test code:")
        c.setFont(body_font, 8.5)
        c.drawString(margin + 17 * mm, time_y - 4.6 * mm, code)

        c.setFont(bold_font, 8.5)
        c.drawRightString(W - margin, time_y, f"Maximum Marks: {total}{bonus}")
        c.setFont(body_font, 8.5)
        c.drawRightString(W - margin, time_y - 4.6 * mm,
                          f"{len(eligible)} questions in {len(boxes)} section box(es)")
        rule(time_y - 8.2 * mm)

        # ---- candidate block
        name_y = H - CANDIDATE_NAME_DY * mm
        c.setFont(bold_font, 9.5)
        c.drawString(margin, name_y, "Name:")
        dotted(margin + 11 * mm, W - margin, name_y - 0.7 * mm)

        row2 = name_y - CANDIDATE_ROW_DY * mm
        c.setFont(bold_font, 9.5)
        c.drawString(margin, row2, "Roll No.:")
        dotted(margin + 15 * mm, margin + 62 * mm, row2 - 0.7 * mm)
        c.drawString(margin + 70 * mm, row2, "Section:")
        dotted(margin + 88 * mm, margin + 118 * mm, row2 - 0.7 * mm)
        c.drawString(W - margin - 48 * mm, row2, "Date:")
        dotted(W - margin - 36 * mm, W - margin, row2 - 0.7 * mm)

        row3 = row2 - CANDIDATE_ROW_DY * mm
        c.setFont(bold_font, 9.5)
        c.drawString(margin, row3, "Student's signature:")
        dotted(margin + 33 * mm, margin + 95 * mm, row3 - 0.7 * mm)
        c.drawString(margin + 105 * mm, row3, "Invigilator's signature:")
        dotted(margin + 145 * mm, W - margin, row3 - 0.7 * mm)
        rule(row3 - 4.6 * mm)

        # ---- instructions box (height measured from wrapped paragraphs)
        instr_lines = [
            "Use only a black or blue ball-point pen. Darken the circle completely.",
            "An answer once marked cannot be changed. Do not use correction fluid or overwrite.",
        ]
        if has_integer:
            instr_lines.append("For integer-type questions, darken the one digit (0 to 9) that is your answer.")
        instr_lines.append("Hand over this sheet to the invigilator at the end of the examination.")
        box_w = W - 2 * margin
        pad = 3 * mm
        title_h = 4.5 * mm
        # height comes from the shared helper — the scanner derives the same
        # bubble coordinates from it, so the two can never drift apart
        box_h = _instructions_block(has_integer, box_w)
        paras = [Paragraph(f"{i}.&nbsp;&nbsp;{t}", instr_style) for i, t in enumerate(instr_lines, start=1)]
        heights = []
        for p in paras:
            _, ph = p.wrap(box_w - 2 * pad, 30 * mm)
            heights.append(ph)
        box_top = H - INSTR_BOX_TOP_DY * mm
        c.setStrokeColor(ink)
        c.setLineWidth(0.9)
        c.rect(margin, box_top - box_h, box_w, box_h, stroke=1, fill=0)
        c.setFont(bold_font, 8.5)
        c.drawString(margin + pad, box_top - title_h, "Instructions for marking the OMR sheet")
        ty = box_top - title_h
        for p, ph in zip(paras, heights):
            p.drawOn(c, margin + pad, ty - ph)
            ty -= ph + 1.0 * mm

        # ---- OMR ANSWER SHEET label + set/code line
        label_y = box_top - box_h - LABEL_ROW_DY * mm
        c.setFont(bold_font, 10)
        c.setFillColor(ink)
        c.drawString(margin, label_y, "OMR ANSWER SHEET — KEY COPY" if fill_key else "OMR ANSWER SHEET")
        c.setFont(body_font, 8)
        c.drawRightString(W - margin, label_y, f"Set {set_letter}  |  {code}")

        # ---- section boxes (all equal height, Marks line at the bottom)
        grid_top = label_y - GRID_GAP_DY * mm
        if fill_key:  # light diagonal watermark behind the grid
            c.saveState()
            c.translate(W / 2, grid_top - BOX_H * mm / 2)
            c.rotate(28)
            c.setFont(bold_font, 40)
            c.setFillColor(colors.Color(0.52, 0.47, 0.47, alpha=0.13))
            c.drawCentredString(0, 0, "KEY COPY")
            c.restoreState()
        gap = 4 * mm
        box_w = (W - 2 * margin - (max(n_boxes, 1) - 1) * gap) / max(n_boxes, 1)
        gutter = 6.5 * mm
        pad_b = 2 * mm
        sec_letters = [LETTERS[bi] for bi in range(len(boxes))]  # per-box section letters
        unmapped = 0  # key-copy rows whose correct answer is not set

        for bi, chunk in enumerate(page_boxes):
            box_index = page * BOXES_PER_PAGE + bi
            x = margin + bi * (box_w + gap)
            y_top = grid_top
            h = BOX_H * mm

            c.setStrokeColor(ink)
            c.setLineWidth(1)
            c.rect(x, y_top - h, box_w, h, stroke=1, fill=0)
            c.setFillColor(maroon)
            c.rect(x, y_top - BOX_HEADER_H * mm, box_w, BOX_HEADER_H * mm, stroke=0, fill=1)
            label = f"{sec_letters[box_index]} | {subject_line.upper()}" if box_index == 0 \
                else f"{subject_line.upper()}  ·  {chunk[0][0]}-{chunk[-1][0]}"
            c.setFillColor(white)
            c.setFont(bold_font, 7.6)
            c.drawCentredString(x + box_w / 2, y_top - BOX_HEADER_H * mm + 1.7 * mm, label)

            area_x = x + gutter + pad_b
            area_w = box_w - gutter - 2 * pad_b

            # tiny column letters above the first bubble row
            first_row = chunk[0][1]
            is_int_first = first_row.question.qtype in INTEGER_TYPES
            n_first = 10 if is_int_first else min(len(first_row.question.options), len(LETTERS))
            if not is_int_first:
                c.setFont(bold_font, 5)
                c.setFillColor(grey)
                pitch0 = area_w / n_first
                for k in range(n_first):
                    c.drawCentredString(area_x + pitch0 * (k + 0.5),
                                        y_top - BOX_HEADER_H * mm - BOX_COL_H * mm + 0.8 * mm, LETTERS[k])

            y_row0 = y_top - BOX_HEADER_H * mm - BOX_COL_H * mm
            for j, (num, r) in enumerate(chunk):
                row_c = y_row0 - BOX_ROW_H * mm * (j + 0.5)
                integer = r.question.qtype in INTEGER_TYPES
                n_opts = 10 if integer else min(len(r.question.options), len(LETTERS))
                # which bubble carries the correct answer on the key copy?
                fill_k = None
                if fill_key:
                    fill_k = _integer_digit(r.question) if integer else _answer_index(r.question)
                    if fill_k is not None and not (0 <= fill_k < n_opts):
                        fill_k = None
                    if fill_k is None:
                        unmapped += 1
                c.setFont(bold_font, 8)
                c.setFillColor(ink)
                c.drawRightString(x + gutter, row_c - 1.1 * mm, f"{num}{'*' if fill_key and fill_k is None else ''}.")
                pitch = area_w / n_opts
                rr = 2.1 * mm if not integer else min(1.45 * mm, pitch / 2 - 0.15 * mm)
                # centre the letter/digit vertically inside the bubble: caps and
                # digits have no descender, so drop the baseline by half a
                # cap-height (~0.35 x font size) below the circle's centre
                fs = 5.2 if not integer else 4.6
                baseline_dy = fs * 0.35
                for k in range(n_opts):
                    bx = area_x + pitch * (k + 0.5)
                    if fill_k == k:                     # darkened correct bubble
                        c.setStrokeColor(ink)
                        c.setLineWidth(0.8)
                        c.setFillColor(ink)
                        c.circle(bx, row_c, rr, stroke=1, fill=1)
                        c.setFont(body_font, fs)
                        c.setFillColor(white)
                    else:
                        c.setStrokeColor(ink)
                        c.setLineWidth(0.8)
                        c.circle(bx, row_c, rr, stroke=1, fill=0)
                        c.setFont(body_font, fs)
                        c.setFillColor(grey)
                    c.drawCentredString(bx, row_c - baseline_dy,
                                        LETTERS[k] if not integer else str(k))

            c.setFont(body_font, 7)
            c.setFillColor(ink)
            c.drawString(x + pad_b, y_top - h + 1.8 * mm, "Marks")
            dotted(x + pad_b + 9 * mm, x + box_w - pad_b, y_top - h + 2.2 * mm)

        # registration squares just outside the grid corners
        grid_bottom = grid_top - BOX_H * mm
        if fill_key and unmapped:
            c.setFont(body_font, 6.5)
            c.setFillColor(grey)
            c.drawCentredString(W / 2, grid_bottom - 3.6 * mm,
                                "* Correct answer not set for starred questions — mark them by hand.")
        sq = 3.2 * mm
        c.setFillColor(colors.black)
        for sx, sy in (
            (margin - 4.6 * mm, grid_top + 0.8 * mm),
            (W - margin + 1.4 * mm, grid_top + 0.8 * mm),
            (margin - 4.6 * mm, grid_bottom - 1.4 * mm - sq),
            (W - margin + 1.4 * mm, grid_bottom - 1.4 * mm - sq),
        ):
            c.rect(sx, sy, sq, sq, stroke=0, fill=1)

        # ---- QR + office-use footer
        if qr:
            try:
                c.drawImage(ImageReader(io.BytesIO(qr)), margin, 8 * mm, width=13 * mm, height=13 * mm, mask="auto")
            except Exception:
                pass
        c.setFillColor(ink)
        c.setFont(bold_font, 8.5)
        c.drawString(margin + 17 * mm, 12.5 * mm, "For office use:")
        c.setFont(body_font, 8.5)
        ox = margin + 44 * mm
        page_letters = [LETTERS[page * BOXES_PER_PAGE + bi] for bi in range(n_boxes)]
        for letter in page_letters:
            c.drawString(ox, 12.5 * mm, f"{letter}:")
            dotted(ox + 4.5 * mm, ox + 10.5 * mm, 12 * mm)
            ox += 15 * mm
        # right-anchored "Checked by", Total tucked in front of it without overlap
        from reportlab.pdfbase.pdfmetrics import stringWidth
        checked = "Checked by: ____________"
        total_str = f"Total: ______ / {total}"
        cw = stringWidth(checked, bold_font, 8.5)
        tw = stringWidth(total_str, body_font, 8.5)
        c.drawString(W - margin - cw, 12.5 * mm, checked)
        if W - margin - cw - 6 * mm - tw > ox:
            c.setFont(body_font, 8.5)
            c.drawString(W - margin - cw - 6 * mm - tw, 12.5 * mm, total_str)

        c.setFont(body_font, 7)
        c.setFillColor(grey)
        c.drawCentredString(W / 2, 7 * mm,
                            f"Page {page + 1} of {pages}  ·  {len(eligible)} question(s)  ·  Generated with PiAssess  ·  {school_name}")
        c.showPage()

    c.save()
    return buf.getvalue()
