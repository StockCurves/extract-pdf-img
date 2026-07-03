from pathlib import Path
import runpy
import sys

ROOT_DIR = Path(__file__).resolve().parent
TOOL_PATH = ROOT_DIR / "tools" / "qa" / "test_extract.py"

if __name__ == "__main__":
    sys.path.insert(0, str(ROOT_DIR / "src"))
    runpy.run_path(str(TOOL_PATH), run_name="__main__")
