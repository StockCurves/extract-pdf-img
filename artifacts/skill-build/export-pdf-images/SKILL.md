---
name: export-pdf-images
description: Export figures and optionally tables from PDF files as PNG images with layout-aware cropping. Use when Codex needs to pull diagrams, charts, or other figure images out of academic or technical PDFs, especially multi-column papers, and must confirm caption cropping, output directory, and output filename or naming pattern before running when the user did not specify them.
---

# Export PDF Images

Export PNG crops from PDFs with a bundled Python extractor.

Prefer the bundled script over re-implementing extraction logic.

## Required Clarifications

Before running extraction, check whether the user already specified all three of these decisions:

1. Whether to keep figure captions inside the crop or exclude them.
2. Which output directory to write PNG files into.
3. Which output filename rule to use.

If any of the three is missing, ask a concise follow-up before running the script. Do not silently choose defaults.

Use this mapping when asking:

- Caption cropping: ask whether to keep captions in the image crop, or exclude figure captions.
- Output directory: ask for the exact destination folder.
- Output filename: ask for either a filename prefix or a filename template.

If the user says to use defaults after being asked, use:

- Keep figure captions in the crop.
- Output directory: `<pdf-stem>-png` next to the source PDF.
- Filename rule: `<pdf-stem>-fig001.png`, `<pdf-stem>-fig002.png`, and so on.

## Workflow

1. Confirm the PDF path exists.
2. Resolve the three required decisions above.
3. Decide whether tables should also be exported.
4. Run `scripts/extract_pdf_images.py`.
5. Report the output directory and the naming rule actually used.

## Run Extraction

Run the bundled script from this skill directory:

```bash
python scripts/extract_pdf_images.py <pdf_path> [options]
```

Common options:

- `--exclude-figure-captions`: crop figure images without the caption area.
- `--tables`: also export tables.
- `--out <dir>`: write output into a specific directory.
- `--output-stem <text>`: set the base prefix used by the default naming rule.
- `--filename-template <template>`: override naming with placeholders.
- `--caption`: append rendered caption text under each exported PNG.

## Filename Rules

Use `--filename-template` when the user wants explicit control over output names.

Supported placeholders:

- `{stem}`: source PDF stem, or `--output-stem` when supplied.
- `{kind}`: `fig` for figures, `tbl` for tables.
- `{index}`: zero-padded per-kind index such as `001`.
- `{page}`: 1-based page number.
- `{label}`: sanitized caption label.

Example:

```bash
python scripts/extract_pdf_images.py paper.pdf --out exports --filename-template "{stem}-p{page}-{kind}{index}-{label}.png"
```

## Notes

- The script depends on `PyMuPDF` and `Pillow`.
- This extractor is tuned for academic and technical PDFs with caption-driven figure detection.
- If the user asks only for figures, do not enable `--tables`.
