from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extract_png_from_pdf.app import app, convert_pdf_to_pngs, main


if __name__ == "__main__":
    main()
