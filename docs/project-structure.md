# Project Structure

This repo is organized around four concerns: application code, tests, helper
tools, and generated artifacts.

## Top-Level Layout

```text
src/
  extract_png_from_pdf/
tests/
  unit/
  fixtures/
tools/
  qa/
  debug/
artifacts/
  output/
  debug/
  logs/
  review/
docs/
knowledge/
static/
templates/
```

## Directory Roles

`src/extract_png_from_pdf/`

- Main application package.
- `app.py` hosts the Flask app and routes runtime output into `artifacts/output/`.
- `extract_figures.py` contains the caption-driven extraction logic.
- `verify_crops.py` contains report-only QA checks and overlay generation.

`tests/unit/`

- Fast automated tests intended to run often.
- These should stay independent from large runtime artifacts when possible.

`tests/fixtures/`

- Checked-in sample PDFs and small reference outputs used by tests or manual QA.
- Use this for stable reproducible samples, not for every ad hoc run.

`tools/qa/`

- Helper scripts that actively validate behavior.
- Includes `test_extract.py` plus experimental scripts related to QA or external compilation.

`tools/debug/`

- One-off diagnostic scripts used while investigating geometry, caption, or region issues.
- Keep these separate from repeatable QA flows.

`artifacts/output/`

- Default destination for current local runs.
- Safe place for generated PNGs, extracted metadata, QA reports, and overlays.

`artifacts/output/legacy_output/`

- Preserved older outputs moved out of the repo root for reference.
- Treat this as archival material, not the default working area.

`artifacts/debug/`

- Text dumps and intermediate debug files produced during investigations.

`artifacts/logs/`

- Local Flask/server logs.

`artifacts/review/`

- Manual review screenshots and other visual inspection material.

`knowledge/`

- Durable project notes and decisions.

## Root Compatibility Files

The repo keeps these root-level wrappers for convenience:

- `app.py`
- `extract_figures.py`
- `verify_crops.py`
- `test_extract.py`

They forward to the package or helper script locations so existing commands do
not break after reorganization.
