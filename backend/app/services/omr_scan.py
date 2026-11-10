"""OMR scan recognition — deterministic computer-vision bubble reading.

Pipeline (no AI involved — bubble detection is pure image processing):
  1. decode the scanned image (JPEG/PNG) with OpenCV
  2. locate the four black registration squares printed around the bubble grid
  3. warp the scan onto the canonical A4 page (perspective + rotation fix)
  4. sample every bubble's darkness at its known canonical coordinate
  5. classify each row: single mark / blank / multiple / low-confidence
  6. score against the answer key derived from the questions themselves

The bubble coordinates come from ``omr.sheet_geometry`` — the same numbers the
printer draws with, so template and sheet can never drift apart.
"""
from __future__ import annotations

import cv2
import numpy as np

from ..schemas import PaperOut
from .omr import sheet_geometry

# canonical reading resolution (pixels per millimetre of the A4 page)
PX_PER_MM = 8.0

# darkness ratio (0..1) above which a bubble counts as marked
MARK_THRESHOLD = 0.34
# above this the mark is unmistakable
CONFIDENT_THRESHOLD = 0.58


class ScanError(Exception):
    """Raised when the scan cannot be read at all (no sheet found, wrong page...)."""


MAX_PDF_PAGES = 100


def pdf_pages_to_images(pdf_bytes: bytes, dpi: int = 220) -> list[bytes]:
    """Render each page of a scanned PDF to a grayscale JPEG (one per sheet).

    Teachers usually scan a whole stack of answer sheets into one PDF on the
    school photocopier — every page is one student's sheet. Raises ScanError
    with a teacher-readable message when the PDF is unreadable or too big.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:  # pragma: no cover
        raise ScanError("PDF scanning is not available on this installation.")

    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
    except Exception:
        raise ScanError("This PDF could not be opened. Re-scan the sheets and try again.")

    try:
        n_pages = len(pdf)
        if n_pages == 0:
            raise ScanError("This PDF has no pages in it.")
        if n_pages > MAX_PDF_PAGES:
            raise ScanError(
                f"This PDF has {n_pages} pages — the limit is {MAX_PDF_PAGES}. "
                "Please split the scan into smaller files and upload them separately."
            )
        pages: list[bytes] = []
        for i in range(n_pages):
            bitmap = pdf[i].render(scale=dpi / 72, grayscale=True)
            pil = bitmap.to_pil()
            ok, enc = cv2.imencode(".jpg", np.asarray(pil), [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                raise ScanError("A page of this PDF could not be converted for reading.")
            pages.append(enc.tobytes())
        return pages
    finally:
        pdf.close()


def _find_squares(gray: np.ndarray, expected_mm: dict[str, tuple[float, float]],
                  page_mm: tuple[float, float]) -> np.ndarray:
    """Find the four registration squares; return their centres, ordered TL,TR,BL,BR."""
    H_px, W_px = gray.shape
    mm_x = W_px / page_mm[0]
    mm_y = H_px / page_mm[1]
    # registration squares are ~3.2 mm; accept a generous size window
    s_px = 3.2 * mm_x
    lo, hi = s_px * 0.35, s_px * 2.6

    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 25, 15)
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    cands: list[tuple[float, float, float]] = []  # (cx, cy, area)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (lo * lo < area < hi * hi):
            continue
        (cx, cy), (w, h), _angle = cv2.minAreaRect(cnt)
        if not (lo < w < hi and lo < h < hi):
            continue
        if abs(w - h) / max(w, h) > 0.35:  # squareness
            continue
        fill = area / (w * h)
        if fill < 0.75:  # solid black squares
            continue
        cands.append((cx, cy, area))

    if len(cands) < 4:
        raise ScanError(
            "Could not find the four black registration squares on this scan. "
            "Make sure the whole sheet is visible, right side up, and well lit."
        )

    # keep the candidates nearest to each expected corner region
    W_mm, H_mm = page_mm
    chosen: list[tuple[float, float]] = []
    for corner, (ex_mm, ey_mm) in expected_mm.items():
        ex, ey = ex_mm * mm_x, ey_mm * mm_y
        cx, cy, _a = min(cands, key=lambda c: (c[0] - ex) ** 2 + (c[1] - ey) ** 2)
        # sanity: the nearest candidate must sit in the right quadrant
        near_x = abs(cx - ex) < 25 * mm_x
        near_y = abs(cy - ey) < 25 * mm_y
        if not (near_x and near_y):
            raise ScanError(
                "The registration squares are not where this sheet's layout expects them. "
                "Is this scan the printout of the same OMR design?"
            )
        chosen.append((cx, cy))

    # order: TL, TR, BL, BR — chosen[] already follows expected_mm's order
    return np.array(chosen, dtype=np.float32)


def _sample_fill(warp: np.ndarray, cx: float, cy: float, r: float) -> float:
    """How dark a bubble is compared with the paper around it (0..1)."""
    H, W = warp.shape
    x0, x1 = max(int(cx - r - 2), 0), min(int(cx + r + 3), W)
    y0, y1 = max(int(cy - r - 2), 0), min(int(cy + r + 3), H)
    patch = warp[y0:y1, x0:x1]
    if patch.size == 0:
        return 0.0
    yy, xx = np.ogrid[:patch.shape[0], :patch.shape[1]]
    ccx, ccy = cx - x0, cy - y0
    disc = (xx - ccx) ** 2 + (yy - ccy) ** 2 <= r * r
    ring = ((xx - ccx) ** 2 + (yy - ccy) ** 2 > (r * 1.6) ** 2) & \
           ((xx - ccx) ** 2 + (yy - ccy) ** 2 <= (r * 2.6) ** 2)
    if not disc.any() or not ring.any():
        return 0.0
    bg = float(np.mean(patch[ring]))
    inside = float(np.mean(patch[disc]))
    if bg < 30:  # dark scanner background — treat whole area as unreadable
        return 0.0
    return max(0.0, min(1.0, (bg - inside) / bg))


def recognize_scan(image_bytes: bytes, paper: PaperOut, set_letter: str) -> dict:
    """Read one scanned sheet. Returns per-question responses plus the score.

    Raises ScanError with a teacher-readable message when the sheet cannot
    be aligned or has nothing to read.
    """
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ScanError("This file is not a readable image. Save the scan as JPG or PNG and try again.")

    geo = sheet_geometry(paper, set_letter, page=0)
    if geo["pages"] > 1:
        raise ScanError(
            f"This paper's OMR sheet runs to {geo['pages']} pages; "
            "single-image scanning handles one-page (up to 80 question) sheets for now."
        )
    if not geo["rows"]:
        raise ScanError("This paper has no objective questions to read on an OMR sheet.")

    page_mm = geo["page_mm"]
    # upscale small scans to a workable resolution before finding the squares
    scale = max(1.0, (PX_PER_MM * page_mm[0]) / img.shape[1])
    if scale > 1.01:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    squares = _find_squares(img, geo["squares"], page_mm)

    canon_w, canon_h = int(page_mm[0] * PX_PER_MM), int(page_mm[1] * PX_PER_MM)
    src = np.array([[(c[0], c[1])] for c in squares], dtype=np.float32)
    dst = np.array([[(geo["squares"][k][0] * PX_PER_MM, geo["squares"][k][1] * PX_PER_MM)]
                    for k in ("TL", "TR", "BL", "BR")], dtype=np.float32)
    hom, _ = cv2.findHomography(src, dst)
    if hom is None:
        raise ScanError("The scanned sheet is too skewed to straighten. Please rescan it flat.")
    warp = cv2.warpPerspective(img, hom, (canon_w, canon_h),
                               flags=cv2.INTER_AREA, borderValue=255)

    rows_out = []
    score = 0.0
    max_score = 0.0
    from .omr import _answer_index, _integer_digit  # local import: key mapping
    low_conf = 0
    multi = 0
    penalty = float(getattr(paper, "negative_marks", 0.0) or 0.0)

    for row in geo["rows"]:
        q = paper.items[row["position"] - 1].question
        integer = row["integer"]
        # a digit bubble is small; the disc radius follows the drawn circle
        rr_mm = 1.35 if integer else 1.55
        r_px = rr_mm * PX_PER_MM
        fills = [_sample_fill(warp, x * PX_PER_MM, row["y"] * PX_PER_MM, r_px)
                 for x in row["xs"]]
        marked = [i for i, f in enumerate(fills) if f >= MARK_THRESHOLD]
        confident = [i for i, f in enumerate(fills) if f >= CONFIDENT_THRESHOLD]

        # key
        key_idx = _integer_digit(q) if integer else _answer_index(q)
        key_ok = key_idx is not None and 0 <= key_idx < row["n_opts"]

        if len(marked) == 0:
            chosen, verdict, conf = None, "unanswered", 1.0
        elif len(marked) > 1:
            chosen, verdict, conf = None, "multi", 0.0
            multi += 1
        else:
            chosen = marked[0]
            conf = fills[chosen]
            if conf < CONFIDENT_THRESHOLD:
                verdict, _ = "review", None
                low_conf += 1
            else:
                verdict = "answered"

        correct = chosen is not None and verdict == "answered" and key_ok and chosen == key_idx
        if verdict == "answered":
            if correct:
                score += row["marks"]
            elif key_ok:
                # negative marking: wrong answers deduct, when the exam says so
                # (never penalised when the key itself is missing)
                score -= penalty
        max_score += row["marks"]
        rows_out.append({
            "position": row["position"],
            "marks": row["marks"],
            "integer": row["integer"],
            "n_opts": row["n_opts"],
            "chosen": chosen,
            "key": key_idx if key_ok else None,
            "fill": round(max(fills), 3),
            "verdict": verdict,          # answered | unanswered | multi | review
            "correct": bool(correct),
        })

    if multi or low_conf:
        band = "YELLOW"
    elif all(r["verdict"] == "unanswered" for r in rows_out):
        band = "RED"  # nothing read at all — probably the wrong sheet or upside-down
    else:
        band = "GREEN"

    return {
        "rows": rows_out,
        "score": round(score, 2),
        "max_score": round(max_score, 2),
        "negative_marks": penalty,
        "confidence_band": band,
        "low_confidence": low_conf,
        "multi_marks": multi,
    }
