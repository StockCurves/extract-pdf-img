#!/usr/bin/env python3
"""
verify_crops.py
Report-only QA for PDF figure/table crops.

The verifier reads a PDF plus crop metadata produced by extract_figures.extract().
It does not change crops. It writes qa_report.json / qa_report.txt and can render
debug overlays for suspicious pages.
"""

import argparse
import io
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import fitz
import numpy as np
from PIL import Image, ImageDraw


WARN = "warn"
FAIL = "fail"

_FIG_CAPTION_PAT = re.compile(
    r'^(Fig(?:ure)?\.?\s*\d+(?:\.\d+)*(?:\.|:))(?=\s|$)',
    re.IGNORECASE,
)
_TBL_CAPTION_PAT = re.compile(
    r'^(TABLE\s+[IVXivx\d]+)\b',
    re.IGNORECASE,
)


def _rect(values: list[float] | tuple[float, ...] | None) -> fitz.Rect | None:
    if not values or len(values) != 4:
        return None
    return fitz.Rect(float(values[0]), float(values[1]),
                     float(values[2]), float(values[3]))


def _rect_to_list(rect: fitz.Rect | None) -> list[float] | None:
    if rect is None:
        return None
    return [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]


def _path_from_result(result: dict[str, Any]) -> Path:
    raw = result.get("path") or result.get("path_str")
    if raw is None:
        return Path("")
    return Path(raw)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    return value


def load_metadata(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("results", [])
    if not isinstance(data, list):
        raise ValueError(f"metadata must be a list or object with results: {path}")
    return data


def save_metadata(results: list[dict[str, Any]], path: Path) -> None:
    payload = {"results": _jsonable(results)}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _graphic_rects(page: fitz.Page) -> list[fitz.Rect]:
    rects: list[fitz.Rect] = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect", fitz.Rect())
        if rect.is_empty or rect.width < 3 or rect.height < 3:
            continue
        rects.append(fitz.Rect(rect))

    for img_info in page.get_images(full=True):
        try:
            image_rects = page.get_image_rects(img_info[0])
        except Exception:
            continue
        for rect in image_rects:
            if rect.width < 10 or rect.height < 10:
                continue
            rects.append(fitz.Rect(rect))
    return rects


def _distribution(rects: list[fitz.Rect], band: fitz.Rect, mid_x: float) -> dict[str, int]:
    left = 0
    right = 0
    for rect in rects:
        if (rect & band).is_empty:
            continue
        if rect.x0 < mid_x - 8:
            left += 1
        if rect.x1 > mid_x + 8:
            right += 1
    return {"left": left, "right": right}


def _has_both_sides(dist: dict[str, int], threshold: int = 3) -> bool:
    return dist["left"] >= threshold and dist["right"] >= threshold


def _looks_like_caption(text: str) -> bool:
    s = " ".join(text.strip().split())
    return bool(_FIG_CAPTION_PAT.match(s) or _TBL_CAPTION_PAT.match(s))


def _starts_with_complete_label(text: str, label: str) -> bool:
    s = " ".join(text.strip().split())
    normalized_label = " ".join(label.strip().split())
    if not normalized_label:
        return False
    if not s.lower().startswith(normalized_label.lower()):
        return False
    if len(s) == len(normalized_label):
        return True
    return s[len(normalized_label)].isspace()


def _looks_like_allowed_short_label(text: str) -> bool:
    s = " ".join(text.strip().split())
    if len(s) <= 12 and len(s.split()) <= 3:
        return True
    if len(s) <= 24 and any(ch.isdigit() for ch in s) and len(s.split()) <= 4:
        return True
    return False


def _text_issues(page: fitz.Page, item: dict[str, Any],
                 all_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    crop = _rect(item.get("rect_pt"))
    cap = _rect(item.get("caption_bbox"))
    if crop is None:
        return []

    label = str(item.get("label", ""))
    issues: list[dict[str, Any]] = []
    page_h = page.rect.height

    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text, _bno, btype = block
        if btype != 0:
            continue
        block_rect = fitz.Rect(x0, y0, x1, y1)
        overlap = block_rect & crop
        if overlap.is_empty or overlap.get_area() < 4:
            continue

        normalized = " ".join(text.strip().split())
        if not normalized:
            continue
        if _starts_with_complete_label(normalized, label):
            continue
        if cap is not None and not (block_rect & cap).is_empty:
            continue
        if _looks_like_allowed_short_label(normalized):
            continue

        other_caption = None
        if _looks_like_caption(normalized):
            for other in all_items:
                if other is item:
                    continue
                other_label = str(other.get("label", ""))
                if other_label and normalized.startswith(other_label):
                    other_caption = other_label
                    break
            if other_caption:
                issues.append({
                    "code": "extra_text_inside_crop",
                    "severity": WARN,
                    "message": f"crop includes caption for {other_caption}",
                    "bbox": _rect_to_list(block_rect),
                    "text": normalized[:120],
                })
                continue

        word_count = len(normalized.split())
        likely_running_text = y0 < 48 or y1 > page_h - 30
        likely_body_text = word_count >= 7 and len(normalized) >= 38
        if item.get("type") == "table":
            likely_body_text = False

        if likely_running_text or likely_body_text:
            reason = "running header/footer" if likely_running_text else "body text"
            issues.append({
                "code": "extra_text_inside_crop",
                "severity": WARN,
                "message": f"crop includes likely {reason}",
                "bbox": _rect_to_list(block_rect),
                "text": normalized[:120],
            })

    return issues


def _overlap_issues(item: dict[str, Any],
                    peers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    crop = _rect(item.get("rect_pt"))
    if crop is None:
        return []

    issues: list[dict[str, Any]] = []
    for peer in peers:
        if peer is item or peer.get("page") != item.get("page"):
            continue
        peer_crop = _rect(peer.get("rect_pt"))
        if peer_crop is None:
            continue
        inter = crop & peer_crop
        if inter.is_empty:
            continue
        vertical_overlap = inter.height
        horizontal_overlap = inter.width
        if vertical_overlap >= 6 and horizontal_overlap >= 10:
            issues.append({
                "code": "crop_overlap",
                "severity": WARN,
                "message": f"overlaps {peer.get('label')} by {vertical_overlap:.1f} pt vertically",
                "peer_label": peer.get("label"),
                "bbox": _rect_to_list(inter),
            })
    return issues


def _has_peer_in_opposite_column(item: dict[str, Any],
                                 peers: list[dict[str, Any]],
                                 mid_x: float) -> bool:
    crop = _rect(item.get("rect_pt"))
    if crop is None:
        return False
    item_center = (crop.x0 + crop.x1) / 2
    for peer in peers:
        if peer is item or peer.get("page") != item.get("page"):
            continue
        peer_crop = _rect(peer.get("rect_pt"))
        if peer_crop is None:
            continue
        peer_center = (peer_crop.x0 + peer_crop.x1) / 2
        if (item_center < mid_x and peer_center < mid_x) or (item_center > mid_x and peer_center > mid_x):
            continue
        overlap_y = min(crop.y1, peer_crop.y1) - max(crop.y0, peer_crop.y0)
        if overlap_y > 20:
            return True
    return False


def _column_issues(page: fitz.Page, item: dict[str, Any],
                   peers: list[dict[str, Any]],
                   graphic_rects: list[fitz.Rect]) -> list[dict[str, Any]]:
    crop = _rect(item.get("rect_pt"))
    if crop is None:
        return [{
            "code": "missing_crop_rect",
            "severity": FAIL,
            "message": "metadata has no rect_pt",
        }]

    page_rect = page.rect
    mid_x = page_rect.width / 2
    crop_dist = _distribution(graphic_rects, crop, mid_x)
    band = fitz.Rect(page_rect.x0, crop.y0, page_rect.x1, crop.y1)
    band_dist = _distribution(graphic_rects, band, mid_x)
    issues: list[dict[str, Any]] = []

    if crop.width > page_rect.width * 0.70 and not _has_both_sides(crop_dist):
        issues.append({
            "code": "suspicious_full_width_crop",
            "severity": WARN,
            "message": (
                "crop is full-width but graphic content is only detected "
                f"on left={crop_dist['left']} right={crop_dist['right']}"
            ),
        })

    if crop.width < page_rect.width * 0.55 and _has_both_sides(band_dist):
        if not _has_peer_in_opposite_column(item, peers, mid_x):
            issues.append({
                "code": "missed_cross_column_content",
                "severity": WARN,
                "message": (
                    "crop is single-column but page band has graphics on "
                    f"both sides left={band_dist['left']} right={band_dist['right']}"
                ),
            })

    if item.get("graphics_bbox") is None and item.get("type") == "figure":
        issues.append({
            "code": "missing_graphics",
            "severity": FAIL,
            "message": "no drawing/image bbox detected inside figure crop",
        })

    return issues


def _dilate(mask: np.ndarray, iterations: int = 2) -> np.ndarray:
    out = mask
    for _ in range(iterations):
        padded = np.pad(out, 1, mode="constant", constant_values=False)
        grown = np.zeros_like(out, dtype=bool)
        for dy in range(3):
            for dx in range(3):
                grown |= padded[dy:dy + out.shape[0], dx:dx + out.shape[1]]
        out = grown
    return out


def _visual_bands(mask: np.ndarray) -> list[dict[str, int]]:
    row_density = mask.mean(axis=1)
    active = row_density > 0.012
    bands: list[dict[str, int]] = []
    start = None

    for idx, is_active in enumerate(active.tolist() + [False]):
        if is_active and start is None:
            start = idx
        elif not is_active and start is not None:
            end = idx
            if end - start >= max(4, int(mask.shape[0] * 0.025)):
                band_mask = mask[start:end, :]
                col_density = band_mask.mean(axis=0)
                active_cols = np.nonzero(col_density > 0.006)[0]
                if len(active_cols):
                    x0 = int(active_cols[0])
                    x1 = int(active_cols[-1]) + 1
                    area = int(band_mask.sum())
                    bands.append({
                        "area": area,
                        "x0": x0,
                        "y0": start,
                        "x1": x1,
                        "y1": end,
                    })
            start = None

    min_width = mask.shape[1] * 0.18
    min_area = max(80, int(mask.size * 0.002))
    return [
        band for band in bands
        if band["x1"] - band["x0"] >= min_width and band["area"] >= min_area
    ]


def _merged_figure_issue(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("type") != "figure":
        return None

    path = _path_from_result(item)
    if not path.exists():
        return {
            "code": "missing_png",
            "severity": FAIL,
            "message": f"PNG does not exist: {path}",
        }

    try:
        img = Image.open(path).convert("L")
    except Exception as exc:
        return {
            "code": "unreadable_png",
            "severity": FAIL,
            "message": f"cannot open PNG: {exc}",
        }

    max_dim = max(img.size)
    if max_dim > 800:
        scale = 800 / max_dim
        img = img.resize((max(1, int(img.width * scale)),
                          max(1, int(img.height * scale))), Image.LANCZOS)

    arr = np.asarray(img, dtype=np.uint8)
    mask = arr < 245
    if mask.mean() < 0.001:
        return None

    mask = _dilate(mask, iterations=2)
    bands = _visual_bands(mask)
    bands.sort(key=lambda band: band["y0"])

    if len(bands) < 2:
        return None

    for first, second in zip(bands, bands[1:]):
        gap = second["y0"] - first["y1"]
        if gap >= max(12, int(img.height * 0.06)):
            return {
                "code": "possible_merged_figures",
                "severity": WARN,
                "message": (
                    "PNG has multiple large visual bands separated "
                    f"by {gap}px"
                ),
                "components": bands[:5],
            }

    return None


def _horizontal_merged_figure_issue(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("type") != "figure":
        return None

    path = _path_from_result(item)
    if not path.exists():
        return None

    try:
        img = Image.open(path).convert("L")
    except Exception:
        return None

    if img.width < 350:
        return None

    arr = np.asarray(img, dtype=np.uint8)
    mask = arr < 245
    if mask.mean() < 0.001:
        return None

    col_density = mask.mean(axis=0)
    mid_x = img.width // 2
    search_width = int(img.width * 0.15)
    start_x = max(0, mid_x - search_width)
    end_x = min(img.width, mid_x + search_width)

    gap_cols = [x for x in range(start_x, end_x) if col_density[x] < 0.005]

    if gap_cols:
        left_mask = mask[:, :min(gap_cols)]
        right_mask = mask[:, max(gap_cols):]

        if left_mask.any() and right_mask.any():
            longest_gap = 0
            current_gap = 0
            prev_x = -2
            for x in gap_cols:
                if x == prev_x + 1:
                    current_gap += 1
                else:
                    current_gap = 1
                longest_gap = max(longest_gap, current_gap)
                prev_x = x

            if longest_gap >= max(4, int(img.width * 0.01)):
                return {
                    "code": "possible_merged_figures_horizontal",
                    "severity": WARN,
                    "message": (
                        "PNG has side-by-side figures separated "
                        f"by a vertical gap of {longest_gap}px"
                    ),
                }

    return None


def verify_results(pdf_path: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    pdf = fitz.open(str(pdf_path))
    by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        by_page[int(item.get("page", 0))].append(item)

    report_items: list[dict[str, Any]] = []
    summary = {
        "items": 0,
        "pass": 0,
        "warn": 0,
        "fail": 0,
        "issues": defaultdict(int),
    }

    graphic_cache: dict[int, list[fitz.Rect]] = {}
    for item in results:
        page_no = int(item.get("page", 0))
        if page_no < 1 or page_no > len(pdf):
            issues = [{
                "code": "invalid_page",
                "severity": FAIL,
                "message": f"page {page_no} is outside PDF page count {len(pdf)}",
            }]
        else:
            page = pdf[page_no - 1]
            graphic_cache.setdefault(page_no, _graphic_rects(page))
            peers = by_page[page_no]
            issues = []
            issues.extend(_column_issues(page, item, peers, graphic_cache[page_no]))
            issues.extend(_overlap_issues(item, peers))
            issues.extend(_text_issues(page, item, peers))
            merged_issue = _merged_figure_issue(item)
            if merged_issue is not None:
                issues.append(merged_issue)
            merged_issue_h = _horizontal_merged_figure_issue(item)
            if merged_issue_h is not None:
                issues.append(merged_issue_h)

        status = "pass"
        if any(issue["severity"] == FAIL for issue in issues):
            status = "fail"
        elif issues:
            status = "warn"

        summary["items"] += 1
        summary[status] += 1
        for issue in issues:
            summary["issues"][issue["code"]] += 1

        report_items.append({
            "status": status,
            "label": item.get("label"),
            "type": item.get("type"),
            "page": item.get("page"),
            "path": str(_path_from_result(item)),
            "rect_pt": item.get("rect_pt"),
            "col_detected": item.get("col_detected") or item.get("col"),
            "graphics_bbox": item.get("graphics_bbox"),
            "issues": issues,
        })

    pdf.close()
    summary["issues"] = dict(sorted(summary["issues"].items()))
    return {
        "pdf": str(pdf_path),
        "summary": summary,
        "items": report_items,
    }


def write_reports(report: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "qa_report.json"
    txt_path = out_dir / "qa_report.txt"
    json_path.write_text(json.dumps(_jsonable(report), indent=2), encoding="utf-8")

    lines = []
    summary = report["summary"]
    lines.append(f"PDF crop QA: {report['pdf']}")
    lines.append(
        f"Items: {summary['items']}  pass={summary['pass']} "
        f"warn={summary['warn']} fail={summary['fail']}"
    )
    if summary["issues"]:
        lines.append("Issues:")
        for code, count in summary["issues"].items():
            lines.append(f"  {code}: {count}")
    lines.append("")

    for item in report["items"]:
        lines.append(
            f"[{item['status'].upper()}] {item['label']} p.{item['page']} "
            f"{item['type']} {Path(item['path']).name}"
        )
        for issue in item["issues"]:
            lines.append(f"  - {issue['code']}: {issue['message']}")
            if issue.get("text"):
                lines.append(f"    text: {issue['text']}")
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, txt_path


def write_overlays(pdf_path: Path, report: dict[str, Any], out_dir: Path) -> list[Path]:
    overlay_dir = out_dir / "qa_overlay"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    pdf = fitz.open(str(pdf_path))
    paths: list[Path] = []

    suspicious_by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in report["items"]:
        if item["status"] != "pass":
            suspicious_by_page[int(item["page"])].append(item)

    for page_no, items in sorted(suspicious_by_page.items()):
        if page_no < 1 or page_no > len(pdf):
            continue
        page = pdf[page_no - 1]
        scale = 2.0
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale),
                              colorspace=fitz.csRGB)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        draw = ImageDraw.Draw(img)

        def draw_rect(values: list[float] | None, color: tuple[int, int, int],
                      width: int = 3) -> None:
            rect = _rect(values)
            if rect is None:
                return
            box = [rect.x0 * scale, rect.y0 * scale,
                   rect.x1 * scale, rect.y1 * scale]
            draw.rectangle(box, outline=color, width=width)

        for item in items:
            draw_rect(item.get("rect_pt"), (220, 30, 30), 4)
            draw_rect(item.get("graphics_bbox"), (30, 90, 220), 3)
            for issue in item["issues"]:
                draw_rect(issue.get("bbox"), (240, 150, 20), 2)

        path = overlay_dir / f"page-{page_no:03d}.png"
        img.save(path)
        paths.append(path)

    pdf.close()
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify PDF figure/table crops.")
    parser.add_argument("pdf_path")
    parser.add_argument("--metadata", required=True,
                        help="JSON metadata written from extract_figures.extract()")
    parser.add_argument("--out", default=None,
                        help="Report directory (default: metadata directory)")
    parser.add_argument("--overlay", action="store_true",
                        help="Write page overlay PNGs for suspicious crops")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    metadata_path = Path(args.metadata)
    out_dir = Path(args.out) if args.out else metadata_path.parent

    results = load_metadata(metadata_path)
    report = verify_results(pdf_path, results)
    json_path, txt_path = write_reports(report, out_dir)
    print(f"QA JSON -> {json_path}")
    print(f"QA text -> {txt_path}")
    if args.overlay:
        overlay_paths = write_overlays(pdf_path, report, out_dir)
        print(f"QA overlays -> {len(overlay_paths)} files")

    if report["summary"]["fail"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
