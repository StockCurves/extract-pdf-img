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

## Architecture & Logic
The core engine (`extract_figures.py`) operates in several phases:
1. **Caption Parsing**: Identifies all text blocks matching "Fig. X" or "TABLE X", determining their initial column placement (left, right, or full) based on page coordinates.
2. **Boundary Discovery**: For each caption, it scans outward (up for figures, down for tables) to find the nearest text block that acts as a boundary.
3. **Full-Width Verification**: It tests a tentative "full-width" region. If graphics exist across both columns and no independent `opp_cap` (opposite caption) claims the space, the element is promoted to full-width.
4. **Rendering**: The computed `fitz.Rect` boundary is rendered to a 300 DPI pixmap and saved as a PNG.
