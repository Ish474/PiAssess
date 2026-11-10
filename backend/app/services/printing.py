"""Professional PDF and DOCX question papers, answer keys and marking schemes.

The PDF path is typeset with LaTeX for true print-shop alignment. The project
ships the self-contained ``tectonic`` XeTeX engine (no installation, no admin
rights) under ``tools/tectonic``. If tectonic is unavailable or a compile ever
fails, the renderer transparently falls back to the pure-Python ReportLab
builder — exports must never break.
DOCX is built with python-docx. Both formats carry the school identity: logo,
name, address, session, and the school's maroon accent colour. MCQ options are
laid out in one horizontal line per question in every format.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

from ..schemas import PaperOut

MAROON = "#791D32"
INK = "#292329"
CREAM = "#FFF9F0"

_LATEX_TIMEOUT = 300  # seconds; the first run also downloads the TeX bundle


def _fmt_date(d: date | None) -> str:
    if not d:
        return ""
    return d.strftime("%d %B %Y").lstrip("0")


def _paper_meta_lines(paper: PaperOut) -> list[str]:
    parts = [
        f"Class: {paper.class_name}" if paper.class_name else "",
        f"Subject: {paper.subject_name}" if paper.subject_name else "",
        f"Date: {_fmt_date(paper.exam_date)}" if paper.exam_date else "",
        f"Time: {paper.duration_minutes} minutes" if paper.duration_minutes else "",
        f"Maximum Marks: {paper.exam_max_marks or paper.total_marks}",
    ]
    return [p for p in parts if p]


def _option_label(index: int, text: str) -> str:
    """Prefix options with (A) (B) (C)… unless the text already carries a label."""
    text = text.strip()
    if re.match(r"^\(?[A-Ja-j][).:]", text):
        return text
    return f"({chr(65 + index)}) {text}"


# ------------------------------------------------------------------ LaTeX path
_TEX_SPECIALS = [
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
]


def _tex_escape(text: str, escape_dollars: bool = False) -> str:
    """Escape LaTeX specials. By default ``$...$`` runs are kept as raw math
    (the AI writes questions in LaTeX notation); a fallback pass escapes them."""
    if escape_dollars:
        for a, b in _TEX_SPECIALS + [("$", r"\$")]:
            text = text.replace(a, b)
        return text
    parts = text.split("$")
    out: list[str] = []
    for i, part in enumerate(parts):
        if i % 2:  # inside $...$ — keep the math verbatim so it renders
            out.append(f"${part}$")
        else:
            for a, b in _TEX_SPECIALS:
                part = part.replace(a, b)
            out.append(part)
    return "$".join(out)


_tectonic_cache: str | None = None


def _tectonic_binary() -> str | None:
    """Find tectonic: PIASSESS_TEX_BINARY env var → project tools dir → PATH."""
    global _tectonic_cache
    if _tectonic_cache is not None:
        return _tectonic_cache or None
    candidates: list[Path] = []
    env = os.environ.get("PIASSESS_TEX_BINARY")
    if env:
        candidates.append(Path(env))
    candidates.append(Path(__file__).resolve().parents[3] / "tools" / "tectonic" / "tectonic.exe")
    found = next((str(c) for c in candidates if c.is_file()), None) or shutil.which("tectonic")
    _tectonic_cache = found or ""
    return found


def _build_tex_source(paper: PaperOut, school: dict, include_key: bool, escape_math: bool = False) -> str:
    esc = lambda s: _tex_escape(s or "", escape_dollars=escape_math)

    school_name = esc(school.get("school_name") or "Pi World School")
    addr = (school.get("school_address") or "").strip()
    sub = addr + (f"  ·  Session {paper.academic_session}" if paper.academic_session else "")
    meta = "  ·  ".join(_paper_meta_lines(paper))
    title = esc(paper.title or paper.exam_name)

    L: list[str] = [
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[a4paper,margin=18mm]{geometry}",
        r"\usepackage{fontspec}",
        r"\usepackage{xcolor}",
        r"\usepackage{graphicx}",
        r"\usepackage{multicol}",
        r"\usepackage{tabularx}",
        r"\usepackage{longtable}",
        r"\usepackage{booktabs}",
        r"\usepackage{fancyhdr}",
        r"\usepackage{lastpage}",
        r"\definecolor{maroon}{HTML}{791D32}",
        r"\definecolor{ink}{HTML}{292329}",
        r"\definecolor{cream}{HTML}{FFF9F0}",
        r"\definecolor{grey}{HTML}{6B6666}",
        r"\IfFontExistsTF{Arial}{\setmainfont{Arial}}{}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\columnsep}{7mm}",
        r"\setlength{\multicolsep}{4mm}",
        r"\raggedbottom",
        r"\pagestyle{fancy}",
        r"\fancyhf{}",
        r"\renewcommand{\headrulewidth}{0pt}",
        r"\fancyfoot[C]{\footnotesize\color{grey}Page \thepage\ of \pageref{LastPage}}",
        r"\begin{document}",
        # ---- masthead: centered logo, school name, address, maroon rule
        r"\begin{center}",
        r"\IfFileExists{logo.png}{\includegraphics[height=13mm]{logo.png}}{}\\[2mm]",
        r"{\color{maroon}\bfseries\fontsize{17}{21}\selectfont " + school_name + r"}\\[1.5mm]",
        r"{\small " + esc(sub) + r"}",
        r"\end{center}",
        r"\vspace{1mm}",
        r"{\color{maroon}\hrule height 1.4pt}",
        r"\vspace{5mm}",
    ]

    if include_key:
        L += [
            r"\begin{center}{\color{maroon}\bfseries\small ANSWER KEY --- FOR EXAMINER USE ONLY}\end{center}",
            r"\vspace{2mm}",
        ]

    L += [
        r"\begin{center}{\color{ink}\bfseries\large " + title + r"}\end{center}",
        r"\vspace{1mm}",
        r"\begin{center}{\small " + esc(meta) + r"}\end{center}",
        r"\vspace{3mm}",
    ]

    if paper.instructions and not include_key:
        L += [
            r"\fcolorbox{maroon}{cream}{\begin{minipage}{\dimexpr\linewidth-2\fboxsep-2\fboxrule\relax}"
            r"\small\textbf{General Instructions:} " + esc(paper.instructions) + r"\end{minipage}}",
            r"\vspace{4mm}",
        ]

    if include_key:
        L += [
            r"\begin{longtable}{@{}>{\bfseries}p{12mm}p{\dimexpr\linewidth-40mm\relax}"
            r">{\bfseries\raggedleft\arraybackslash}p{14mm}@{}}",
            r"\toprule",
            r"\textbf{Q.No} & \textbf{Correct Answer / Marking Scheme} & \textbf{Marks} \\",
            r"\midrule",
            r"\endhead",
        ]
        for i, r in enumerate(paper.items):
            ans = esc(r.question.correct_answer) if r.question.correct_answer else "—"
            if r.question.marking_notes:
                ans += r"\newline{\small\color{grey}Marking: " + esc(r.question.marking_notes) + "}"
            L.append(f"{i + 1}. & " + ans + r" & " + str(r.marks) + r" \\")
        L += [r"\bottomrule", r"\end{longtable}"]
    else:
        # two-column body: every question is an UNBREAKABLE block (minipage), so
        # a question and its options can never split across columns or pages —
        # if it does not fit, the whole block moves to the next column/page.
        L += [r"\begin{multicols}{2}", r"\setlength{\parskip}{0pt}"]
        for i, r in enumerate(paper.items):
            q = esc(r.question.text)
            q = q.replace("\r\n", "\n").replace("\n", r"\newline ")
            block = [
                r"\par\noindent\begin{minipage}{\linewidth}%",
                r"\begin{tabularx}{\linewidth}{@{}p{6mm}@{}X@{}r@{}}",
                r"\textbf{" + str(i + 1) + r".} & " + q + r" & \textbf{" + str(r.marks) + r"} \\",
                r"\end{tabularx}",
            ]
            opts = [str(o) for o in (r.question.options or [])]
            if opts:
                row = " & ".join(esc(_option_label(j, o)) for j, o in enumerate(opts))
                block += [
                    r"\par\vspace{1mm}",
                    # one horizontal line: a single row with one column per option
                    r"\noindent\begin{tabularx}{\linewidth}{*{" + str(len(opts)) + "}{X}}",
                    row + r" \\",
                    r"\end{tabularx}",
                ]
            block += [r"\end{minipage}", r"\par\vspace{2.4mm}"]
            L += block
        L.append(r"\end{multicols}")

    L += [
        r"\vspace{4mm}",
        r"{\color{maroon}\hrule height 0.6pt}",
        r"\vspace{3mm}",
        r"\noindent{\bfseries Total: " + str(len(paper.items)) + r" question(s)}\hfill"
        r"{\bfseries Total Marks: " + str(paper.total_marks) + "}",
        r"\vspace{8mm}",
        r"\noindent Verified by: \rule[-1mm]{45mm}{0.4pt}",
        r"\vspace{6mm}",
        r"\begin{center}{\footnotesize\color{grey}Generated with PiAssess · " + school_name + r"}\end{center}",
        r"\end{document}",
    ]
    return "\n".join(L) + "\n"


def _compile_latex(tex_src: str, logo_bytes: bytes | None) -> bytes | None:
    binary = _tectonic_binary()
    if not binary:
        return None
    import tempfile

    with tempfile.TemporaryDirectory(prefix="piassess_tex_") as tmp_name:
        tmp = Path(tmp_name)
        (tmp / "paper.tex").write_text(tex_src, encoding="utf-8")
        if logo_bytes:
            (tmp / "logo.png").write_bytes(logo_bytes)
        pdf_path = tmp / "paper.pdf"
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # legacy V1 interface first, then the V2 (-X compile) interface
        for args in ([binary, "paper.tex"], [binary, "-X", "compile", "paper.tex"]):
            try:
                subprocess.run(
                    args, cwd=tmp, capture_output=True, text=True,
                    timeout=_LATEX_TIMEOUT, creationflags=no_window,
                )
            except (OSError, subprocess.TimeoutExpired):
                return None
            if pdf_path.exists() and pdf_path.read_bytes()[:5] == b"%PDF-":
                return pdf_path.read_bytes()
    return None


# --------------------------------------------------------- ReportLab fallback
_pdf_fonts_ready = False


def _ensure_pdf_fonts() -> tuple[str, str]:
    """Register Unicode-capable fonts (Windows ships Arial). Falls back to Helvetica."""
    global _pdf_fonts_ready
    body, bold = "Helvetica", "Helvetica-Bold"
    if not _pdf_fonts_ready:
        from reportlab import pdfbase
        from reportlab.pdfbase.ttfonts import TTFont

        for path, name in ((r"C:\Windows\Fonts\arial.ttf", "PiBody"), (r"C:\Windows\Fonts\arialbd.ttf", "PiBold")):
            try:
                pdfbase.pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass
        names = pdfbase.pdfmetrics.getRegisteredFontNames()
        if "PiBody" in names:
            body = "PiBody"
            bold = "PiBold" if "PiBold" in names else body
        _pdf_fonts_ready = True
    return body, bold


def _build_pdf_reportlab(paper: PaperOut, school: dict, logo_bytes: bytes | None, include_key: bool) -> bytes:
    """Fallback renderer — pure Python, no external engine required."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    body_font, bold_font = _ensure_pdf_fonts()
    maroon = colors.HexColor(MAROON)
    ink = colors.HexColor(INK)
    cream = colors.HexColor(CREAM)

    body = ParagraphStyle("body", fontName=body_font, fontSize=10.5, leading=15, textColor=ink)
    qtext = ParagraphStyle("qtext", parent=body, leftIndent=18, firstLineIndent=-18, spaceBefore=4)
    option = ParagraphStyle("option", parent=body, fontSize=10, leading=13.5)
    center = ParagraphStyle("center", parent=body, alignment=TA_CENTER)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, textColor=colors.HexColor("#6B6666"), alignment=TA_CENTER)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
        title=paper.title or paper.exam_name,
        author=school.get("school_name", "Pi World School"),
    )

    story: list = []

    logo = None
    if logo_bytes:
        try:
            logo = Image(io.BytesIO(logo_bytes), width=30 * mm, height=13 * mm)
            logo.hAlign = "LEFT"
        except Exception:
            logo = None
    masthead_style = ParagraphStyle("school", parent=center, fontName=bold_font, fontSize=16, leading=20, textColor=maroon)
    addr_style = ParagraphStyle("addr", parent=center, fontSize=9.5, leading=12.5, textColor=ink)
    school_cell = [
        Paragraph(school.get("school_name", "Pi World School"), masthead_style),
        Paragraph(
            f"{school.get('school_address', '')}"
            + (f" &nbsp;·&nbsp; Session {paper.academic_session}" if paper.academic_session else ""),
            addr_style,
        ),
    ]
    masthead = Table([[logo or "", school_cell]], colWidths=[36 * mm, None])
    masthead.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
    ]))
    story.append(masthead)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.6, color=maroon))
    story.append(Spacer(1, 10))

    if include_key:
        story.append(Paragraph("ANSWER KEY — FOR EXAMINER USE ONLY",
                               ParagraphStyle("key", parent=center, fontName=bold_font, fontSize=11, textColor=maroon)))
        story.append(Spacer(1, 6))

    story.append(Paragraph(paper.title or paper.exam_name,
                           ParagraphStyle("title", parent=center, fontName=bold_font, fontSize=13, leading=17, textColor=ink)))
    meta = Table([_paper_meta_lines(paper)], colWidths=[None])
    meta.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(meta)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#D8CFCF")))
    story.append(Spacer(1, 8))

    if paper.instructions and not include_key:
        instr = Table([[Paragraph(f"<b>General Instructions:</b> {paper.instructions}",
                                  ParagraphStyle("instr", parent=body, fontSize=9.5, leading=13))]],
                      colWidths=[None])
        instr.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), cream),
            ("BOX", (0, 0), (-1, -1), 0.75, maroon),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(instr)
        story.append(Spacer(1, 8))

    if include_key:
        key_rows = [[Paragraph(f"<b>Ans {i + 1}.</b>", body),
                     Paragraph(f"{r.question.correct_answer or '—'}"
                               + (f"<br/><font size=8 color=#6B6666>Marking: {r.question.marking_notes}</font>"
                                  if r.question.marking_notes else ""), body),
                     Paragraph(str(r.marks), body)] for i, r in enumerate(paper.items)]
        key_table = Table([[Paragraph("<b>Q.No</b>", body), Paragraph("<b>Correct Answer / Marking Scheme</b>", body),
                            Paragraph("<b>Marks</b>", body)]] + key_rows,
                          colWidths=[16 * mm, None, 14 * mm])
        key_table.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#E4DBDB")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(key_table)
    else:
        blocks: list = []
        for i, r in enumerate(paper.items):
            block: list = []
            marks_cell = Table([[Paragraph(str(r.marks), ParagraphStyle("m", parent=body, alignment=2))]],
                               colWidths=[12 * mm])
            q = Table([[Paragraph(f"<b>{i + 1}.</b> {r.question.text}", qtext), marks_cell]],
                      colWidths=[None, 14 * mm])
            q.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
            ]))
            block.append(q)
            opts = [str(o) for o in (r.question.options or [])]
            if opts:  # one horizontal line: a single row with one column per option
                cells = [Paragraph(_option_label(j, o), option) for j, o in enumerate(opts)]
                opt_table = Table([cells], colWidths=[None] * len(opts))
                opt_table.setStyle(TableStyle([
                    ("LEFTPADDING", (0, 0), (0, 0), 26),
                    ("LEFTPADDING", (1, 0), (-1, 0), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]))
                block.append(opt_table)
            block.append(Spacer(1, 6))
            # KeepTogether: a question and its options never split across pages
            blocks.append(KeepTogether(block))
        try:  # two-column flow; plain single column if this reportlab lacks it
            from reportlab.platypus.flowables import BalancedColumns
            story.append(BalancedColumns(blocks, nCols=2))
        except ImportError:
            story.extend(blocks)

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#D8CFCF")))
    totals = Paragraph(
        f"<b>Total: {len(paper.items)} question(s)</b> &nbsp;&nbsp;·&nbsp;&nbsp; <b>Total Marks: {paper.total_marks}</b>",
        ParagraphStyle("totals", parent=body, fontSize=10),
    )
    footer = Table([[totals, Paragraph("Verified by: ______________", ParagraphStyle("sig", parent=body, fontSize=10, alignment=2))]],
                   colWidths=[None, 60 * mm])
    footer.setStyle(TableStyle([("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (-1, 0), (-1, 0), 0)]))
    story.append(footer)
    story.append(Spacer(1, 8))
    story.append(Paragraph("Generated with PiAssess · " + school.get("school_name", "Pi World School"), small))

    doc.build(story)
    return buf.getvalue()


def build_paper_pdf(paper: PaperOut, school: dict, logo_bytes: bytes | None, include_key: bool) -> bytes:
    """Render the question paper (or answer key) as a print-ready PDF.

    LaTeX (tectonic) does the typesetting; if that fails — engine missing,
    network hiccup, pathological question text — fall back to ReportLab.
    """
    for escape_math in (False, True):
        try:
            pdf = _compile_latex(_build_tex_source(paper, school, include_key, escape_math=escape_math), logo_bytes)
        except Exception:
            pdf = None
        if pdf:
            return pdf
    return _build_pdf_reportlab(paper, school, logo_bytes, include_key)


# ----------------------------------------------------------------------- DOCX
def build_paper_docx(paper: PaperOut, school: dict, logo_bytes: bytes | None, include_key: bool) -> bytes:
    """Render the question paper (or answer key) as an editable Word document."""
    import docx
    from docx import shared
    from docx.enum.section import WD_SECTION_START
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    maroon_rgb = shared.RGBColor(0x79, 0x1D, 0x32)

    document = docx.Document()
    for section in document.sections:
        section.top_margin = shared.Mm(14)
        section.bottom_margin = shared.Mm(14)
        section.left_margin = shared.Mm(18)
        section.right_margin = shared.Mm(18)

    def para(text="", *, bold=False, center=False, color=None, size=None, space_after=4):
        p = document.add_paragraph()
        p.paragraph_format.space_after = shared.Pt(space_after)
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = bold
        if color is not None:
            run.font.color.rgb = color
        if size is not None:
            run.font.size = shared.Pt(size)
        return p

    # masthead: centered logo above the school name (add_paragraph — a fresh
    # Document has no paragraphs[0], so indexing used to crash and skip the logo)
    if logo_bytes:
        try:
            head = document.add_paragraph()
            head.alignment = WD_ALIGN_PARAGRAPH.CENTER
            head.paragraph_format.space_after = shared.Pt(2)
            head.add_run().add_picture(io.BytesIO(logo_bytes), height=shared.Mm(13))
        except Exception:
            pass  # a damaged logo must never block the export
    para(school.get("school_name", "Pi World School"), bold=True, center=True, color=maroon_rgb, size=17, space_after=1)
    sub = f"{school.get('school_address', '')}"
    if paper.academic_session:
        sub += f"  ·  Session {paper.academic_session}"
    para(sub, center=True, size=9.5, space_after=6)
    rule = document.add_paragraph()
    rule.paragraph_format.space_after = shared.Pt(8)
    pPr = rule._p.get_or_add_pPr()
    bottom = OxmlElement("w:pBdr")
    line = OxmlElement("w:bottom")
    line.set(qn("w:val"), "single")
    line.set(qn("w:sz"), "18")
    line.set(qn("w:color"), MAROON.lstrip("#"))
    bottom.append(line)
    pPr.append(bottom)

    if include_key:
        para("ANSWER KEY — FOR EXAMINER USE ONLY", bold=True, center=True, color=maroon_rgb, size=11, space_after=8)

    para(paper.title or paper.exam_name, bold=True, center=True, size=13, space_after=4)
    para("  ·  ".join(_paper_meta_lines(paper)), center=True, size=9.5, space_after=10)

    if paper.instructions and not include_key:
        para("General Instructions:", bold=True, size=10, space_after=2)
        para(paper.instructions, size=10, space_after=10)

    if include_key:
        table = document.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        for cell, text in zip(hdr, ("Q.No", "Correct Answer / Marking Scheme", "Marks")):
            cell.text = text
            cell.paragraphs[0].runs[0].bold = True
        for i, r in enumerate(paper.items):
            row = table.add_row().cells
            row[0].text = str(i + 1)
            answer = r.question.correct_answer or "—"
            if r.question.marking_notes:
                answer += f"\nMarking: {r.question.marking_notes}"
            row[1].text = answer
            row[2].text = str(r.marks)
    else:
        # two-column question body via a continuous section break (masthead and
        # footer stay full width)
        body_sec = document.add_section(WD_SECTION_START.CONTINUOUS)
        cols_el = body_sec._sectPr.xpath("./w:cols")
        if cols_el:
            cols_el[0].set(qn("w:num"), "2")
            cols_el[0].set(qn("w:space"), "340")
        for i, r in enumerate(paper.items):
            q = document.add_paragraph()
            q.paragraph_format.space_after = shared.Pt(2)
            # keep the whole question on one page/column
            q.paragraph_format.keep_together = True
            q.paragraph_format.keep_with_next = True
            run = q.add_run(f"{i + 1}. ")
            run.bold = True
            q.add_run(r.question.text)
            marks_run = q.add_run(f"  [{r.marks}]")
            marks_run.font.color.rgb = maroon_rgb
            opts = [str(o) for o in (r.question.options or [])]
            if opts:  # one horizontal line: a borderless single-row table
                opt_table = document.add_table(rows=1, cols=len(opts))
                opt_table.autofit = True
                tr_pr = opt_table.rows[0]._tr.get_or_add_trPr()
                tr_pr.append(OxmlElement("w:cantSplit"))  # options row never splits across pages
                for j, (cell, opt) in enumerate(zip(opt_table.rows[0].cells, opts)):
                    cell_padding = cell.paragraphs[0]
                    cell_padding.paragraph_format.space_after = shared.Pt(1)
                    opt_run = cell_padding.add_run(_option_label(j, opt))
                    opt_run.font.size = shared.Pt(10)
                document.add_paragraph().paragraph_format.space_after = shared.Pt(0)
        # back to one full-width column for the footer
        end_sec = document.add_section(WD_SECTION_START.CONTINUOUS)
        end_cols = end_sec._sectPr.xpath("./w:cols")
        if end_cols:
            end_cols[0].set(qn("w:num"), "1")

    para("", space_after=2)
    para(f"Total: {len(paper.items)} question(s)   ·   Total Marks: {paper.total_marks}", bold=True, size=10, space_after=14)
    para("Verified by: ______________", size=10, space_after=2)

    out = io.BytesIO()
    document.save(out)
    return out.getvalue()
