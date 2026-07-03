# Robust PDF Figure Extractor

A robust, layout-aware Python script for extracting figures and tables from complex, multi-column academic PDFs.

## Overview
Academic PDFs typically present extreme challenges for standard extraction tools: figures are often composed of hundreds of fragmented vector lines, full-width figures break multi-column text flows, and sub-figures are frequently stacked or placed side-by-side. 

This tool uses deep geometric and drawing-aware verification (via `PyMuPDF`) to correctly parse document layouts. It accurately calculates bounding boxes for figures and tables, differentiates between single-column and page-spanning elements, and prevents adjacent figures from being falsely merged.

## Features
- **Vector & Raster Support**: Analyzes both embedded images and native PDF vector drawing paths to determine graphic bounds.
- **Intelligent Layout Awareness**: Automatically detects whether a figure spans a single column or the full width of the page.
- **Side-by-Side Figure Resolution**: Uses advanced geometric invariants (like caption-line crossing tests) to prevent adjacent, single-column figures from bleeding into each other.
- **Table Extraction**: Respects academic layout conventions (table captions are ABOVE the content; figure captions are BELOW).
- **High-Resolution Export**: Renders the exact cropped region of the PDF to high-quality PNGs, preserving vector sharpness and embedded fonts.

## Dependencies
- Python 3.8+
- `PyMuPDF` (`fitz`): For PDF parsing, geometry extraction, and rendering.
- `Pillow` (`PIL`): For image saving and processing.

Install dependencies using:
```bash
pip install PyMuPDF Pillow
```

## Usage

Run the extraction script directly on a target PDF:

```bash
python extract_figures.py <path_to_pdf> [options]
```

### Examples

**Extract all figures (default behavior):**
```bash
python extract_figures.py sample.pdf
```
*This will create a `sample-png` directory and save all detected figures as `sample-fig001.png`, etc.*

**Extract both figures and tables:**
```bash
python extract_figures.py sample.pdf --tables
```

**Extract figures without the `Fig.` caption area:**
```bash
python extract_figures.py sample.pdf --exclude-figure-captions
```

**Run the web app locally:**
```bash
python app.py
```
Then open `http://127.0.0.1:5000`.

### Test Suite
To verify the extraction logic against expected outputs (useful for regression testing during development), use the included `test_extract.py` utility:

```bash
python test_extract.py sample.pdf --expected-figs 19 --tables
```
This script will run the extraction and then verify the dimensions, column detection, and exact counts of the exported assets.

To also produce report-only crop QA for column coverage, crop overlap/merge
signals, and extra text inside crops:

```bash
python test_extract.py sample.pdf --tables --qa --qa-overlay
```

This writes `extract_metadata.json`, `qa_report.json`, `qa_report.txt`, and
optional page overlays into the output directory. If metadata already exists,
run the verifier without re-extracting crops:

```bash
python verify_crops.py sample.pdf --metadata sample-png/extract_metadata.json --overlay
```

For curated fixture PDFs that are checked into this repo, see
[docs/workflows.md](docs/workflows.md).

## Project Layout

```text
src/extract_png_from_pdf/  Core Flask app and extraction logic
tests/unit/                Automated unit tests
tests/fixtures/            Sample PDFs and checked-in fixture outputs
tools/qa/                  QA and verification helper scripts
tools/debug/               One-off debug and inspection scripts
docs/                      Project structure and workflow notes
artifacts/output/          Runtime extraction output
artifacts/debug/           Saved debug text dumps
artifacts/logs/            Local server logs
artifacts/review/          Manual review images
```

## Common Paths

- `src/extract_png_from_pdf/app.py`: Flask entry and runtime output routing
- `src/extract_png_from_pdf/extract_figures.py`: extraction engine
- `src/extract_png_from_pdf/verify_crops.py`: report-only crop QA
- `tests/unit/`: fast unit tests
- `tests/fixtures/pdf_samples/`: checked-in sample PDFs and expected artifacts
- `artifacts/output/`: local extraction results from current runs
- `artifacts/output/legacy_output/`: older preserved outputs kept for reference

## Common Workflows

Run unit tests:

```bash
python -m unittest discover -s tests/unit
```

Run extraction QA on a checked-in sample:

```bash
python test_extract.py tests/fixtures/pdf_samples/07533501_p5.pdf --qa --qa-overlay
```

Run the standalone verifier against saved metadata:

```bash
python verify_crops.py ^
  tests/fixtures/pdf_samples/07533501_p5.pdf ^
  --metadata tests/fixtures/pdf_samples/07533501_p5-png/extract_metadata.json ^
  --overlay
```

Use the helper scripts in `tools/` when you need extra inspection:

- `tools/qa/`: scripted validation, QA runs, and external compile experiments
- `tools/debug/`: ad hoc geometry / region inspection during bug hunts

More detail is in [docs/project-structure.md](docs/project-structure.md) and
[docs/workflows.md](docs/workflows.md).

## Architecture & Logic
The core engine (`extract_figures.py`) operates in several phases:
1. **Caption Parsing**: Identifies all text blocks matching "Fig. X" or "TABLE X", determining their initial column placement (left, right, or full) based on page coordinates.
2. **Boundary Discovery**: For each caption, it scans outward (up for figures, down for tables) to find the nearest text block that acts as a boundary.
3. **Full-Width Verification**: It tests a tentative "full-width" region. If graphics exist across both columns and no independent `opp_cap` (opposite caption) claims the space, the element is promoted to full-width.
4. **Rendering**: The computed `fitz.Rect` boundary is rendered to a 300 DPI pixmap and saved as a PNG.
