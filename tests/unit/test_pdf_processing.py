import os
import shutil
import unittest
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extract_png_from_pdf.app import convert_pdf_to_pngs

class TestPDFProcessing(unittest.TestCase):
    def setUp(self):
        self.test_pdf = ROOT_DIR / "tests" / "fixtures" / "pdf_samples" / "07533501_p5.pdf"
        self.output_dir = ROOT_DIR / "artifacts" / "output" / "test_circuit"
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_pdf_to_png_conversion(self):
        os.makedirs(self.output_dir, exist_ok=True)
        png_paths = convert_pdf_to_pngs(self.test_pdf, self.output_dir)

        self.assertTrue(len(png_paths) > 0)
        for path in png_paths:
            self.assertTrue(os.path.exists(path))
            self.assertTrue(str(path).endswith(".png"))

if __name__ == '__main__':
    unittest.main()
