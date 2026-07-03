#!/usr/bin/env python3
"""
extract_figures.py
Extract figures and tables with captions from multi-column academic PDFs.

Usage:
    python extract_figures.py <pdf_path> [options]

Options:
    --caption                    Render caption text below each exported PNG
    --tables                     Also export tables as PNGs
    --exclude-figure-captions    Crop figures without their caption area
    --dpi N                      Output resolution in DPI (default: 300)
    --padding N                  Extra padding around crop in points (default: 4)
    --out DIR                    Output directory (default: ./<stem>-png/)
"""

import re
import os
import sys
import io
import argparse
import textwrap
from pathlib import Path
from typing import Callable

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

# ── Constants ────────────────────────────────────────────────────────────────
PAGE_MARGIN_TOP    = 42   # pt  – skip running header band
PAGE_MARGIN_BOTTOM = 36   # pt  – skip footer band
PAGE_MARGIN_SIDE   = 36   # pt  – left/right page margin

# ── Caption detection patterns ────────────────────────────────────────────────
# True figure caption labels:
#   "Fig. 3. ..." / "Figure 3.5.1: ..."
# Body references such as "Figure 3.5.1 shows ..." must not match.
_FIG_PAT = re.compile(
    r'^(Fig(?:ure)?\.?\s*\d+(?:\.\d+)*(?:\.|:))(?=\s|$)',
    re.IGNORECASE,
)

# True table caption: "TABLE I" or "TABLE 1" as a standalone label line
_TBL_PAT = re.compile(r'^(TABLE\s+[IVXivx\d]+)\s*$', re.IGNORECASE)


# ── Column geometry ───────────────────────────────────────────────────────────

def _col_bounds(col: str, pw: float) -> tuple[float, float]:
    """Return (x0, x1) for a named column on a page of width pw."""
    mid = pw / 2
    m = PAGE_MARGIN_SIDE
    if col == "left":
        return (m, mid - 6)
    elif col == "right":
        return (mid + 6, pw - m)
    else:  # "full"
        return (m, pw - m)


def _classify_col(bx0: float, bx1: float, pw: float) -> str:
    """Classify a bbox as left / right / full column."""
    mid = pw / 2
    # Full-width: starts in left-col territory and ends beyond midpoint
    if bx0 < mid - 20 and bx1 > mid + 8:
        return "full"
    if bx0 > mid - 15:
        return "right"
    if bx1 < mid + 15:
        return "left"
    return "left" if (bx0 + bx1)/2 < mid else "right"


def _rect_to_list(rect: fitz.Rect | None) -> list[float] | None:
    if rect is None:
        return None
    return [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]


def _union_rects(rects: list[fitz.Rect]) -> fitz.Rect | None:
    if not rects:
        return None
    out = fitz.Rect(rects[0])
    for rect in rects[1:]:
        out |= rect
    return out


def _apply_padding(rect: fitz.Rect,
                   page_rect: fitz.Rect,
                   padding: float,
                   *,
                   max_bottom: float | None = None) -> fitz.Rect:
    padded = fitz.Rect(
        rect.x0 - padding,
        rect.y0 - padding,
        rect.x1 + padding,
        rect.y1 + padding,
    )
    padded = padded & page_rect
    if max_bottom is not None:
        padded.y1 = min(padded.y1, max_bottom)
    return padded


def _graphics_bbox_in_rect(page: fitz.Page, crop: fitz.Rect) -> fitz.Rect | None:
    """Return the union of graphic/image bounds intersecting the crop."""
    rects: list[fitz.Rect] = []

    for drawing in page.get_drawings():
        rect = drawing.get("rect", fitz.Rect())
        if rect.is_empty or rect.width < 3 or rect.height < 3:
            continue
        clipped = fitz.Rect(rect) & crop
        if clipped.is_empty:
            continue
        rects.append(clipped)

    for img_info in page.get_images(full=True):
        try:
            image_rects = page.get_image_rects(img_info[0])
        except Exception:
            continue
        for rect in image_rects:
            if rect.width < 10 or rect.height < 10:
                continue
            clipped = fitz.Rect(rect) & crop
            if clipped.is_empty:
                continue
            rects.append(clipped)

    return _union_rects(rects)


# ── Caption finding ───────────────────────────────────────────────────────────

def get_captions(page: fitz.Page, include_tables: bool = True) -> list[dict]:
    """
    Return all true figure/table captions on *page*.

    A "true" figure caption is a text block whose first line matches
    'Fig. N.' (with a period after the number), distinguishing it from
    body-text references like 'Fig. 2 shows…'.
    """
    pw = page.rect.width
    results: list[dict] = []

    text_dict = page.get_text("dict")
    for block in text_dict["blocks"]:
        if "lines" not in block:
            continue

        # Check if the block starts with a caption pattern (if not, it is body text)
        first_line_text = ""
        for line in block["lines"]:
            first_line_text = "".join(span["text"] for span in line["spans"]).strip()
            if first_line_text:
                break
        if not first_line_text:
            continue

        is_caption_block = bool(_FIG_PAT.match(first_line_text) or (_TBL_PAT.match(first_line_text) if include_tables else False))
        if not is_caption_block:
            continue

        current_captions = []

        for line in block["lines"]:
            line_text = "".join(span["text"] for span in line["spans"]).strip()
            if not line_text:
                continue

            fig_match = _FIG_PAT.match(line_text)
            tbl_match = _TBL_PAT.match(line_text) if include_tables else None

            if fig_match:
                current_captions.append({
                    "type": "figure",
                    "label": fig_match.group(1),
                    "lines": [line],
                    "line_texts": [line_text],
                })
            elif tbl_match:
                current_captions.append({
                    "type": "table",
                    "label": tbl_match.group(1),
                    "lines": [line],
                    "line_texts": [line_text],
                })
            else:
                if current_captions:
                    current_captions[-1]["lines"].append(line)
                    current_captions[-1]["line_texts"].append(line_text)

        for cap in current_captions:
            union_bbox = fitz.Rect(cap["lines"][0]["bbox"])
            for line in cap["lines"][1:]:
                union_bbox |= fitz.Rect(line["bbox"])

            results.append({
                "type":      cap["type"],
                "label":     cap["label"],
                "full_text": " ".join(cap["line_texts"]),
                "bbox":      union_bbox,
                "col":       _classify_col(union_bbox.x0, union_bbox.x1, pw),
            })

    return results


# ── Figure / table region detection ──────────────────────────────────────────

def _text_blocks_on_page(page: fitz.Page) -> list[tuple]:
    return [b for b in page.get_text("blocks") if b[6] == 0]


def _is_body_text(block_tuple) -> bool:
    """Return True if a text block looks like real body text (not a short
    in-figure label like '(a)', axis ticks, etc.)."""
    return len(block_tuple[4].strip()) >= 5


def _graphics_span_both_columns(page: fitz.Page,
                                 y_top: float, y_bot: float,
                                 pw: float) -> bool:
    """Check whether graphic content in the vertical band [y_top, y_bot]
    spans both columns — i.e. there are significant drawings/images on
    BOTH sides of the page midpoint.

    This is the reliable way to decide if a figure/table is truly full-width.
    Instead of guessing from absence-of-text, we verify the drawn content
    itself is present in both the left and right halves.
    """
    mid_x = pw / 2
    left_count = 0
    right_count = 0
    THRESHOLD = 5  # need at least this many graphics on each side

    # Check vector drawings
    for d in page.get_drawings():
        r = d.get("rect", fitz.Rect())
        if r.y1 < y_top or r.y0 > y_bot:
            continue
        if r.width < 3 or r.height < 3:
            continue
        if r.x1 < mid_x:
            left_count += 1
        elif r.x0 > mid_x:
            right_count += 1
        else:
            # Straddles midpoint — counts for both
            left_count += 1
            right_count += 1
        if left_count >= THRESHOLD and right_count >= THRESHOLD:
            return True

    # Check embedded images
    for img_info in page.get_images(full=True):
        try:
            for r in page.get_image_rects(img_info[0]):
                if r.y1 < y_top or r.y0 > y_bot:
                    continue
                if r.width < 10 or r.height < 10:
                    continue
                if r.x0 < mid_x - 10 and r.x1 > mid_x + 10:
                    return True  # single image crossing midpoint
                if r.x1 < mid_x:
                    left_count += THRESHOLD
                elif r.x0 > mid_x:
                    right_count += THRESHOLD
        except Exception:
            pass

    return left_count >= THRESHOLD and right_count >= THRESHOLD


def find_figure_region(page: fitz.Page,
                       caption: dict,
                       all_captions: list[dict]) -> fitz.Rect | None:
    """
    Find the bounding rectangle of the figure/table for *caption*.

    Figures  → region ABOVE the caption (captions are placed below figures
               in IEEE-style papers).
    Tables   → region BELOW the caption label (caption label sits above the
               table body in IEEE-style papers).

    Full-width expansion is only applied when actual drawn graphic content
    is verified to cross the page midpoint (using page.get_drawings()).
    """
    pw, ph = page.rect.width, page.rect.height
    cap   = caption["bbox"]
    col   = caption["col"]
    cx0, cx1 = _col_bounds(col, pw)

    blocks = _text_blocks_on_page(page)

    # x-overlap check: does a block share horizontal territory with this column?
    def overlaps_col(bx0, bx1):
        return bx1 > cx0 + 5 and bx0 < cx1 - 5

    if caption["type"] == "figure":
        def calc_gap_top(bound_x0, bound_x1):
            g_top = PAGE_MARGIN_TOP
            for b in blocks:
                if b[3] > cap.y0 - 2: continue
                if b[3] < PAGE_MARGIN_TOP + 4: continue
                if not (b[2] > bound_x0 + 5 and b[0] < bound_x1 - 5): continue
                if not _is_body_text(b): continue
                g_top = max(g_top, b[3] + 6)

            for c in all_captions:
                if c is caption: continue
                cy1 = c.get("region", c["bbox"]).y1
                if cy1 <= cap.y0 + 5:
                    c_is_full = c["col"] == "full"
                    if "region" in c:
                        c_is_full = c["region"].width > pw * 0.7
                    is_full_check = (bound_x1 - bound_x0) > pw * 0.7
                    if c_is_full or is_full_check or c["col"] == col:
                        g_top = max(g_top, cy1 + 6)
            return g_top

        gap_top_single = calc_gap_top(cx0, cx1)

        # ── auto-detect full-width ──────────────────────────────────────
        cx0_full, cx1_full = _col_bounds("full", pw)
        if col != "full":
            gap_top_full = calc_gap_top(cx0_full, cx1_full)
            mid_x = pw / 2
            
            # If full-width gap is lower, check if we'd lose graphics in our own column
            lost_graphics = False
            if gap_top_full > gap_top_single + 10:
                for d in page.get_drawings():
                    r = d.get("rect", fitz.Rect())
                    if r.y1 > gap_top_single and r.y0 < gap_top_full and r.width > 3 and r.height > 3:
                        if (col == "left" and r.x0 < mid_x) or (col == "right" and r.x1 > mid_x):
                            lost_graphics = True
                            break

            if not lost_graphics:
                if col == "left":
                    opp_cap = any(c["bbox"].x0 >= mid_x - 10 and gap_top_full < c["bbox"].y0 < cap.y0 + 100 for c in all_captions if c is not caption)
                    # Check if right column drawings cross our caption line
                    crosses_cap = any(d.get("rect", fitz.Rect()).y0 < cap.y0 and d.get("rect", fitz.Rect()).y1 > cap.y0 and d.get("rect", fitz.Rect()).x1 > mid_x for d in page.get_drawings() if d.get("rect", fitz.Rect()).width > 3)
                else:
                    opp_cap = any(c["bbox"].x1 <= mid_x + 10 and gap_top_full < c["bbox"].y0 < cap.y0 + 100 for c in all_captions if c is not caption)
                    # Check if left column drawings cross our caption line
                    crosses_cap = any(d.get("rect", fitz.Rect()).y0 < cap.y0 and d.get("rect", fitz.Rect()).y1 > cap.y0 and d.get("rect", fitz.Rect()).x0 < mid_x for d in page.get_drawings() if d.get("rect", fitz.Rect()).width > 3)

                if not opp_cap and not crosses_cap and _graphics_span_both_columns(page, gap_top_full, cap.y0, pw):
                    col = "full"
                    cx0, cx1 = cx0_full, cx1_full

        gap_top = calc_gap_top(cx0, cx1)
        return fitz.Rect(cx0, gap_top, cx1, cap.y1)

    else:
        # ── TABLE: caption label is ABOVE; table body is BELOW ────────────
        search_y = cap.y1 + 30   # skip subtitle zone

        def calc_gap_bottom(bound_x0, bound_x1):
            c_tops = sorted([c["bbox"].y0 for c in all_captions if c["bbox"].y0 > search_y and c is not caption])
            b_tops = sorted([b[1] for b in blocks if b[1] >= search_y and b[2] > bound_x0 + 5 and b[0] < bound_x1 - 5 and _is_body_text(b)])
            
            g_bot = ph - PAGE_MARGIN_BOTTOM
            if c_tops:
                g_bot = min(g_bot, c_tops[0] - 6)
            if b_tops:
                far_blocks = [y for y in b_tops if y > cap.y1 + 60]
                if far_blocks:
                    g_bot = min(g_bot, far_blocks[0] - 6)
            return g_bot

        gap_bottom_single = calc_gap_bottom(cx0, cx1)

        # ── auto-detect full-width ──────────────────────────────────────
        cx0_full, cx1_full = _col_bounds("full", pw)
        if col != "full":
            gap_bottom_full = calc_gap_bottom(cx0_full, cx1_full)
            mid_x = pw / 2
            if col == "left":
                opp_cap = any(c["bbox"].x0 >= mid_x - 10 and cap.y0 < c["bbox"].y0 < gap_bottom_full + 100 for c in all_captions if c is not caption)
                crosses_cap = any(d.get("rect", fitz.Rect()).y0 < cap.y0 and d.get("rect", fitz.Rect()).y1 > cap.y0 and d.get("rect", fitz.Rect()).x1 > mid_x for d in page.get_drawings() if d.get("rect", fitz.Rect()).width > 3)
            else:
                opp_cap = any(c["bbox"].x1 <= mid_x + 10 and cap.y0 < c["bbox"].y0 < gap_bottom_full + 100 for c in all_captions if c is not caption)
                crosses_cap = any(d.get("rect", fitz.Rect()).y0 < cap.y0 and d.get("rect", fitz.Rect()).y1 > cap.y0 and d.get("rect", fitz.Rect()).x0 < mid_x for d in page.get_drawings() if d.get("rect", fitz.Rect()).width > 3)

            if not opp_cap and not crosses_cap and _graphics_span_both_columns(page, cap.y0, gap_bottom_full, pw):
                col = "full"
                cx0, cx1 = cx0_full, cx1_full

        gap_bottom = calc_gap_bottom(cx0, cx1)
        return fitz.Rect(cx0, cap.y0, cx1, gap_bottom)


# ── Rendering helpers ─────────────────────────────────────────────────────────

def render_crop(page: fitz.Page, rect: fitz.Rect, dpi: int = 300) -> Image.Image:
    """Render a rectangular region of *page* at *dpi* and return a PIL Image."""
    mat  = fitz.Matrix(dpi / 72, dpi / 72)
    clip = fitz.Rect(rect) & page.rect          # clamp to page bounds
    pix  = page.get_pixmap(matrix=mat, clip=clip, colorspace=fitz.csRGB)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def add_caption_bar(img: Image.Image,
                    caption_text: str,
                    dpi: int = 300) -> Image.Image:
    """Append a white caption bar with rendered text below *img*."""
    pt_to_px = dpi / 72
    font_px   = max(10, int(8 * pt_to_px))   # 8 pt caption font
    pad_px    = max(4,  int(4 * pt_to_px))

    try:
        font = ImageFont.truetype("arial.ttf", font_px)
    except OSError:
        font = ImageFont.load_default()

    avg_char_w = font_px * 0.55
    max_chars  = max(40, int(img.width / avg_char_w))
    wrapped    = textwrap.fill(caption_text, width=max_chars)

    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    tb = dummy_draw.multiline_textbbox((0, 0), wrapped, font=font)
    text_h = tb[3] - tb[1]
    bar_h  = text_h + pad_px * 2

    out = Image.new("RGB", (img.width, img.height + bar_h), "white")
    out.paste(img, (0, 0))
    draw = ImageDraw.Draw(out)
    draw.multiline_text((pad_px, img.height + pad_px),
                        wrapped, fill="black", font=font)
    return out


# ── Main ──────────────────────────────────────────────────────────────────────

def extract(pdf_path: Path,
            add_caption: bool = False,
            include_tables: bool = False,
            exclude_figure_captions: bool = False,
            dpi: int = 300,
            padding: float = 4.0,
            out_dir: Path | None = None,
            on_result: Callable[[dict], None] | None = None) -> list[dict]:
    """
    Core extraction routine.  Returns a list of result dicts for callers
    (useful for testing).
    """
    stem    = pdf_path.stem
    out_dir = out_dir or pdf_path.parent / f"{stem}-png"
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf     = fitz.open(str(pdf_path))
    results = []
    fig_n   = 0
    tbl_n   = 0

    for page in pdf:
        pg  = page.number + 1
        caps = get_captions(page, include_tables=include_tables)

        # Pass 1: compute table regions
        for cap in caps:
            if cap["type"] == "table":
                cap["region"] = find_figure_region(page, cap, caps)

        # Pass 2: compute figure regions
        for cap in caps:
            if cap["type"] == "figure":
                cap["region"] = find_figure_region(page, cap, caps)

        for cap in caps:
            rect = cap.get("region")
            if rect is None or rect.is_empty or rect.width < 10 or rect.height < 10:
                print(f"  [SKIP] {cap['label']} p.{pg} — empty region")
                continue

            max_bottom = None
            if exclude_figure_captions and cap["type"] == "figure":
                max_bottom = cap["bbox"].y0

            rect = _apply_padding(rect, page.rect, padding, max_bottom=max_bottom)
            if rect.is_empty or rect.width < 10 or rect.height < 10:
                print(f"  [SKIP] {cap['label']} p.{pg} - empty region after padding")
                continue
            graphics_bbox = _graphics_bbox_in_rect(page, rect)

            img = render_crop(page, rect, dpi=dpi)

            if add_caption:
                img = add_caption_bar(img, cap["full_text"], dpi=dpi)

            # Use a truncated, filesystem‑safe stem for filenames (max 50 chars)
            safe_stem = stem[:50].replace(' ', '_')
            if cap["type"] == "figure":
                fig_n += 1
                fname = f"{safe_stem}-fig{fig_n:03d}.png"
            else:
                tbl_n += 1
                fname = f"{safe_stem}-tbl{tbl_n:03d}.png"


            out_path = out_dir / fname
            # Guarantee the directory exists (handles edge‑cases with long or missing paths)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(str(out_path), "PNG")
            print(f"  [OK] {fname}  {cap['label']}  p.{pg}")

            results.append({
                "path":         out_path,
                "path_str":     str(out_path),
                "label":        cap["label"],
                "type":         cap["type"],
                "page":         pg,
                "width":        img.width,
                "height":       img.height,
                "col":          cap["col"],
                "col_detected": cap["col"],
                "rect_pt":      _rect_to_list(rect),
                "caption_bbox": _rect_to_list(cap["bbox"]),
                "graphics_bbox": _rect_to_list(graphics_bbox),
                "full_text":    cap["full_text"],
            })
            if on_result is not None:
                on_result(results[-1])

    pdf.close()
    print(f"\nDone -- {fig_n} figures, {tbl_n} tables -> {out_dir}")
    return results


def main():
    ap = argparse.ArgumentParser(
        description="Extract figures/tables from academic PDFs as PNGs.")
    ap.add_argument("pdf_path")
    ap.add_argument("--caption", action="store_true",
                    help="Render caption text below the PNG")
    ap.add_argument("--tables",  action="store_true",
                    help="Also export tables as PNGs")
    ap.add_argument("--exclude-figure-captions", action="store_true",
                    help="Crop figure images without the figure caption area")
    ap.add_argument("--dpi",     type=int,   default=300)
    ap.add_argument("--padding", type=float, default=4.0,
                    help="Padding in points (default 4)")
    ap.add_argument("--out",     default=None,
                    help="Output directory")
    args = ap.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        sys.exit(f"Error: {pdf_path} not found")

    out_dir = Path(args.out) if args.out else None
    extract(pdf_path,
            add_caption=args.caption,
            include_tables=args.tables,
            exclude_figure_captions=args.exclude_figure_captions,
            dpi=args.dpi,
            padding=args.padding,
            out_dir=out_dir)


if __name__ == "__main__":
    main()
