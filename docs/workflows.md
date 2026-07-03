# Workflows

This page documents the common local workflows after the repo reorganization.

## 1. Run the Web App

```bash
python app.py
```

- Serves the Flask UI on port `5000`.
- Uploaded PDFs and extracted PNGs are written under `artifacts/output/`.

## 2. Extract Figures or Tables from a PDF

```bash
python extract_figures.py path/to/sample.pdf
python extract_figures.py path/to/sample.pdf --tables
```

- Use `--out` if you want a custom destination.
- Without `--out`, the extractor creates a `<pdf-stem>-png` folder near the source PDF.

## 3. Run End-to-End QA

```bash
python test_extract.py tests/fixtures/pdf_samples/07533501_p5.pdf --qa --qa-overlay
```

This flow:

1. Runs the extractor.
2. Checks each exported PNG for obvious corruption or blank output.
3. Writes `extract_metadata.json`.
4. Writes `qa_report.json` and `qa_report.txt`.
5. Optionally writes `qa_overlay/page-XXX.png`.

## 4. Re-Verify Saved Metadata Without Re-Extracting

```bash
python verify_crops.py tests/fixtures/pdf_samples/07533501_p5.pdf --metadata tests/fixtures/pdf_samples/07533501_p5-png/extract_metadata.json --overlay
```

Use this when extraction output already exists and you only want report-only QA.

## 5. Run Unit Tests

```bash
python -m unittest discover -s tests/unit
```

This is the fastest verification path for caption matching and helper behavior.

## 6. Use Helper Scripts

`tools/qa/`

- Repeatable QA helpers and experiments that validate output.

`tools/debug/`

- Investigation-only scripts for inspecting geometry or page regions.
- These may assume a specific fixture or preserved artifact path.

## 7. Where New Files Should Go

- New application code: `src/extract_png_from_pdf/`
- New unit tests: `tests/unit/`
- New stable fixture PDFs: `tests/fixtures/`
- New repeatable QA helpers: `tools/qa/`
- New ad hoc debugging helpers: `tools/debug/`
- New generated output: `artifacts/output/`
- New debug dumps or logs: `artifacts/debug/` or `artifacts/logs/`
