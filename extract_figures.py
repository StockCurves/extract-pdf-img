#!/usr/bin/env python3
"""
extract_figures.py
Extract figures and tables with captions from multi-column academic PDFs.

Usage:
    python extract_figures.py <pdf_path> [options]

Options:
    --caption      Render caption text below each exported PNG
    --tables       Also export tables as PNGs
    --dpi N        Output resolution in DPI (default: 300)
    --padding N    Extra padding around crop in points (default: 4)
    --out DIR      Output directory (default: ./<stem>-png/)
"""

import re
import os
import sys
import io
import argparse
import textwrap
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

# ── Constants ────────────────────────────────────────────────────────────────
PAGE_MARGIN_TOP    = 42   # pt  – skip running header band
PAGE_MARGIN_BOTTOM = 36   # pt  – skip footer band
PAGE_MARGIN_SIDE   = 36   # pt  – left/right page margin

# ── Caption detection patterns ────────────────────────────────────────────────
# True figure caption: "Fig. 3." or "Figure 3." — number followed by a period
_FIG_PAT = re.compile(r'^(Fig(?:ure)?\.?\s*\d+\.)', re.IGNORECASE)

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
    return "left" if bx0 < mid else "right"


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

    for b in page.get_text("blocks"):
        x0, y0, x1, y1, text, _bno, btype = b
        if btype != 0:          # skip image-type blocks
            continue
        lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
        if not lines:
            continue
        first = lines[0]

        m = _FIG_PAT.match(first)
        if m:
            results.append({
                "type":      "figure",
                "label":     m.group(1),
                "full_text": " ".join(lines),
                "bbox":      fitz.Rect(x0, y0, x1, y1),
                "col":       _classify_col(x0, x1, pw),
            })
            continue

        if include_tables:
            m = _TBL_PAT.match(first)
            if m:
                results.append({
                    "type":      "table",
                    "label":     m.group(1),
                    "full_text": " ".join(lines),
                    "bbox":      fitz.Rect(x0, y0, x1, y1),
                    "col":       "full",   # tables always span full width in IEEE
                })

    return results


# ── Figure / table region detection ──────────────────────────────────────────

def _text_blocks_on_page(page: fitz.Page) -> list[tuple]:
    return [b for b in page.get_text("blocks") if b[6] == 0]


def find_figure_region(page: fitz.Page,
                       caption: dict,
                       all_captions: list[dict]) -> fitz.Rect | None:
    """
    Find the bounding rectangle of the figure/table for *caption*.

    Figures  → region ABOVE the caption (captions are placed below figures
               in IEEE-style papers).
    Tables   → region BELOW the caption label (caption label sits above the
               table body in IEEE-style papers).
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
        # ── search upward from caption top ────────────────────────────────
        # Use initially-classified column to find the vertical gap_top
        gap_top = PAGE_MARGIN_TOP
        for b in blocks:
            bx0, by0, bx1, by1 = b[0], b[1], b[2], b[3]
            if by1 > cap.y0 - 2:            # must be above caption
                continue
            if by1 < PAGE_MARGIN_TOP + 4:   # skip running header
                continue
            if not overlaps_col(bx0, bx1):  # must share column x-range
                continue
            gap_top = max(gap_top, by1)

        # Also bound by other captions/regions above us
        for c in all_captions:
            if c is caption:
                continue
            cy1 = c.get("region", c["bbox"]).y1
            if cy1 <= cap.y0 + 5:
                # Check if 'c' is full-width. Its caption might be 'left',
                # but its computed region could be full-width.
                c_is_full = c["col"] == "full"
                if "region" in c:
                    c_is_full = c["region"].width > pw * 0.7
                
                # Must share column, or one must be full-width
                if c_is_full or col == "full" or c["col"] == col:
                    gap_top = max(gap_top, cy1)

        # ── auto-detect full-width figures ────────────────────────────────
        # A figure is full-width when its caption is in the left column but
        # NO right-column text blocks exist in the figure's vertical band.
        # This catches figures whose captions are narrow even though the
        # figure graphic spans the entire page width.
        if col != "right":
            mid_x = pw / 2
            right_col_text_in_band = any(
                b[0] >= mid_x - 10    # block starts at/past midpoint
                and b[3] > gap_top + 5  # block bottom below gap_top
                and b[1] < cap.y0 - 5   # block top above caption
                for b in blocks
            )
            right_col_caption_near = any(
                c["bbox"].x0 >= mid_x - 10
                and gap_top < c["bbox"].y0 < cap.y0 + 100
                for c in all_captions if c is not caption
            )
            if not right_col_text_in_band and not right_col_caption_near:
                # No right-column content alongside the figure → full-width
                cx0, cx1 = _col_bounds("full", pw)

        return fitz.Rect(cx0, gap_top, cx1, cap.y1)

    else:
        # ── TABLE: caption label is ABOVE; table body is BELOW ────────────
        # IEEE table captions are centered; the table body spans full width.
        # Find the bottom of the table as the top of the next caption / figure
        # block on this page (searching full page width).
        search_y = cap.y1 + 30   # skip subtitle zone

        # Collect the y0 of any caption on the same page that is below the table
        cap_tops = sorted(
            [c["bbox"].y0 for c in all_captions
             if c["bbox"].y0 > search_y and c is not caption],
        )

        # Also collect body-text block tops (full-width scan) below search_y
        body_tops = sorted(
            [b[1] for b in blocks
             if b[1] >= search_y
             and b[2] > cx0 + 5 and b[0] < cx1 - 5]
        )

        # Use whichever is closer: next caption top or first body text top
        # that is clearly past the table (skip subtitle ~within first 30pt)
        gap_bottom = ph - PAGE_MARGIN_BOTTOM
        if cap_tops:
            gap_bottom = min(gap_bottom, cap_tops[0])
        if body_tops:
            # skip blocks immediately following subtitle (within 60pt)
            far_blocks = [y for y in body_tops if y > cap.y1 + 60]
            if far_blocks:
                gap_bottom = min(gap_bottom, far_blocks[0])

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
            dpi: int = 300,
            padding: float = 4.0,
            out_dir: Path | None = None) -> list[dict]:
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

            # Apply padding
            rect = fitz.Rect(rect.x0 - padding, rect.y0 - padding,
                             rect.x1 + padding, rect.y1 + padding)

            img = render_crop(page, rect, dpi=dpi)

            if add_caption:
                img = add_caption_bar(img, cap["full_text"], dpi=dpi)

            if cap["type"] == "figure":
                fig_n += 1
                fname = f"{stem}-fig{fig_n:03d}.png"
            else:
                tbl_n += 1
                fname = f"{stem}-tbl{tbl_n:03d}.png"

            out_path = out_dir / fname
            img.save(str(out_path), "PNG")
            print(f"  [OK] {fname}  {cap['label']}  p.{pg}")

            results.append({
                "path":    out_path,
                "label":   cap["label"],
                "type":    cap["type"],
                "page":    pg,
                "width":   img.width,
                "height":  img.height,
                "col":     cap["col"],
            })

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
            dpi=args.dpi,
            padding=args.padding,
            out_dir=out_dir)


if __name__ == "__main__":
    main()
