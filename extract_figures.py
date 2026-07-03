from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extract_png_from_pdf.extract_figures import *  # noqa: F401,F403
from extract_png_from_pdf.extract_figures import main


if __name__ == "__main__":
    main()
