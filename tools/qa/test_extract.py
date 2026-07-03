#!/usr/bin/env python3
"""
test_extract.py
Automated verification of extract_figures.py output.

Usage:
    python test_extract.py <pdf_path> [--tables] [--contact-sheet]

Checks performed per exported PNG:
    1. File exists and size > 0
    2. Image can be opened (not corrupt)
    3. Width and height are within sane bounds (not a sliver, not larger than page)
    4. Image is not blank (std-dev of pixel values > threshold)
    5. Aggregate: expected figure count matches a known reference (if provided)

Produces:
    - Console pass/fail summary with per-item detail
    - Optional contact-sheet PNG showing all crops side-by-side
"""

import sys
import argparse
import statistics
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extract_png_from_pdf.extract_figures import extract
from extract_png_from_pdf.verify_crops import (
    save_metadata,
    verify_results,
    write_overlays,
    write_reports,
)

# ── Config ────────────────────────────────────────────────────────────────────
MIN_WIDTH_PX  = 100    # smallest plausible figure width at 300 dpi
MIN_HEIGHT_PX = 60     # smallest plausible figure height at 300 dpi
MAX_WIDTH_PX  = 5000   # sanity upper bound
MAX_HEIGHT_PX = 6000
BLANK_STDDEV_THRESHOLD = 8.0   # pixel stddev below this - likely blank/white


# ── Individual image checks ───────────────────────────────────────────────────

def check_image(result: dict) -> list[str]:
    """
    Run all checks on a single result entry.
    Returns a list of failure strings (empty = all pass).
    """
    failures = []
    p = result["path"]

    # 1. File exists and non-empty
    if not p.exists():
        failures.append("file does not exist")
        return failures          # can't continue without the file
    if p.stat().st_size == 0:
        failures.append("file is empty (0 bytes)")
        return failures

    # 2. Opens without error
    try:
        img = Image.open(p).convert("RGB")
        img.load()
    except Exception as e:
        failures.append(f"cannot open image: {e}")
        return failures

    w, h = img.size

    # 3. Dimension bounds
    if w < MIN_WIDTH_PX:
        failures.append(f"width {w}px too small (min {MIN_WIDTH_PX})")
    if h < MIN_HEIGHT_PX:
        failures.append(f"height {h}px too small (min {MIN_HEIGHT_PX})")
    if w > MAX_WIDTH_PX:
        failures.append(f"width {w}px suspiciously large (max {MAX_WIDTH_PX})")
    if h > MAX_HEIGHT_PX:
        failures.append(f"height {h}px suspiciously large (max {MAX_HEIGHT_PX})")

    # 4. Not blank / all-white
    arr   = np.array(img, dtype=np.float32)
    stddev = float(arr.std())
    if stddev < BLANK_STDDEV_THRESHOLD:
        failures.append(f"image appears blank (pixel stddev={stddev:.1f})")

    # 5. Aspect ratio sanity (width should generally be >= height for figures)
    aspect = w / max(h, 1)
    if aspect < 0.15:
        failures.append(f"extreme aspect ratio (w/h={aspect:.2f}) - crop may be wrong")

    return failures


# ── Contact sheet ─────────────────────────────────────────────────────────────

def make_contact_sheet(results: list[dict], out_path: Path,
                       thumb_w: int = 400) -> None:
    """Tile all extracted PNGs into a single contact-sheet PNG."""
    cols   = 4
    pad    = 10
    label_h = 28
    thumbs = []

    for r in results:
        try:
            img = Image.open(r["path"]).convert("RGB")
            ratio = thumb_w / img.width
            th    = max(1, int(img.height * ratio))
            thumb = img.resize((thumb_w, th), Image.LANCZOS)
        except Exception:
            thumb = Image.new("RGB", (thumb_w, thumb_w // 2), (220, 220, 220))
        thumbs.append((thumb, r["label"], r.get("page", "?")))

    rows    = (len(thumbs) + cols - 1) // cols
    max_th  = max((t[0].height for t in thumbs), default=200) + label_h
    sheet_w = cols * (thumb_w + pad) + pad
    sheet_h = rows * (max_th + pad) + pad

    sheet = Image.new("RGB", (sheet_w, sheet_h), (245, 245, 245))
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(sheet)

    for idx, (thumb, label, pg) in enumerate(thumbs):
        row, col = divmod(idx, cols)
        x = pad + col * (thumb_w + pad)
        y = pad + row * (max_th + pad)
        sheet.paste(thumb, (x, y))
        draw.text((x, y + thumb.height + 2),
                  f"{label}  p.{pg}", fill=(60, 60, 60), font=font)

    sheet.save(str(out_path), "PNG")
    print(f"  Contact sheet -> {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Test and verify extract_figures.py output.")
    ap.add_argument("pdf_path")
    ap.add_argument("--tables",        action="store_true")
    ap.add_argument("--image-only",    action="store_true",
                    help="Exclude figure caption areas from exported crops")
    ap.add_argument("--dpi",           type=int, default=300)
    ap.add_argument("--contact-sheet", action="store_true",
                    help="Save a contact-sheet PNG of all crops")
    ap.add_argument("--qa",            action="store_true",
                    help="Write crop QA metadata and reports")
    ap.add_argument("--qa-overlay",    action="store_true",
                    help="With --qa, write page overlays for suspicious crops")
    ap.add_argument("--expected-figs", type=int, default=None,
                    help="Expected number of figure PNGs (for count assertion)")
    args = ap.parse_args()

    pdf_path = Path(args.pdf_path)
    out_dir  = pdf_path.parent / f"{pdf_path.stem}-png"

    # Clean previous output so we test a fresh run
    if out_dir.exists():
        shutil.rmtree(out_dir)
        print(f"Cleared previous output: {out_dir}")

    print(f"\n{'='*60}")
    print(f"Running extractor on: {pdf_path.name}")
    print(f"{'='*60}")

    results = extract(
        pdf_path,
        add_caption=False,     # test pure crop first
        include_tables=args.tables,
        exclude_figure_captions=args.image_only,
        dpi=args.dpi,
        padding=4.0,
        out_dir=out_dir,
    )

    print(f"\n{'='*60}")
    print(f"Verifying {len(results)} exported files...")
    print(f"{'='*60}")

    passed = 0
    failed = 0
    fail_details = []

    for r in results:
        issues = check_image(r)
        tag    = r["label"]
        pg     = r["page"]
        fname  = r["path"].name
        if issues:
            failed += 1
            fail_msg = f"  [FAIL] {fname}  ({tag} p.{pg})"
            for iss in issues:
                fail_msg += f"\n         X {iss}"
            print(fail_msg)
            fail_details.append(fail_msg)
        else:
            passed += 1
            w, h = r["width"], r["height"]
            print(f"  [PASS] {fname}  ({tag} p.{pg})  {w}x{h}px")

    # Count assertion
    fig_count = sum(1 for r in results if r["type"] == "figure")
    tbl_count = sum(1 for r in results if r["type"] == "table")

    print("-" * 60)
    print(f"Figures: {fig_count}   Tables: {tbl_count}")

    if args.expected_figs is not None:
        if fig_count == args.expected_figs:
            print(f"  [PASS] Figure count matches expected ({args.expected_figs})")
            passed += 1
        else:
            msg = (f"  [FAIL] Figure count {fig_count} != expected "
                   f"{args.expected_figs}")
            print(msg)
            fail_details.append(msg)
            failed += 1

    # Contact sheet
    if args.contact_sheet and results:
        cs_path = out_dir / f"{pdf_path.stem}-contact-sheet.png"
        make_contact_sheet(results, cs_path)

    if args.qa and results:
        metadata_path = out_dir / "extract_metadata.json"
        save_metadata(results, metadata_path)
        report = verify_results(pdf_path, results)
        json_path, txt_path = write_reports(report, out_dir)
        print(f"  QA metadata -> {metadata_path}")
        print(f"  QA JSON -> {json_path}")
        print(f"  QA text -> {txt_path}")
        print(
            "  QA summary -> "
            f"pass={report['summary']['pass']} "
            f"warn={report['summary']['warn']} "
            f"fail={report['summary']['fail']}"
        )
        if args.qa_overlay:
            overlay_paths = write_overlays(pdf_path, report, out_dir)
            print(f"  QA overlays -> {len(overlay_paths)} files")
        if report["summary"]["fail"]:
            failed += report["summary"]["fail"]

    # Final summary
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"Result: {passed}/{total} checks passed", end="")
    if failed:
        print(f"  <- {failed} FAILED")
        sys.exit(1)
    else:
        print("  ALL PASS")


if __name__ == "__main__":
    main()
