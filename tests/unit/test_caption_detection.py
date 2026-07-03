import unittest
from pathlib import Path
import sys

import fitz

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extract_png_from_pdf import extract_figures, verify_crops


class CaptionDetectionTests(unittest.TestCase):
    def test_chapter_number_caption_matches(self):
        match = extract_figures._FIG_PAT.match(
            "Figure 3.5.1: The CDA with the conventional chopper technique."
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "Figure 3.5.1:")

    def test_body_reference_does_not_match_caption(self):
        self.assertIsNone(
            extract_figures._FIG_PAT.match(
                "Figure 3.5.1 shows a conventional closed-loop PWM CDA."
            )
        )

    def test_qa_does_not_treat_body_reference_as_caption(self):
        self.assertFalse(
            verify_crops._looks_like_caption(
                "Figure 3.5.1 shows a conventional closed-loop PWM CDA."
            )
        )

    def test_qa_requires_complete_label_boundary(self):
        self.assertFalse(
            verify_crops._starts_with_complete_label(
                "Figure 3.5.1 shows a conventional closed-loop PWM CDA.",
                "Figure 3.",
            )
        )
        self.assertTrue(
            verify_crops._starts_with_complete_label(
                "Figure 3.5.1: The CDA with the conventional chopper technique.",
                "Figure 3.5.1:",
            )
        )

    def test_apply_padding_can_exclude_figure_caption_area(self):
        region = fitz.Rect(36, 100, 280, 220)
        page_rect = fitz.Rect(0, 0, 595, 842)
        padded = extract_figures._apply_padding(
            region,
            page_rect,
            4.0,
            max_bottom=200.0,
        )
        self.assertEqual(padded.y0, 96.0)
        self.assertEqual(padded.y1, 200.0)

    def test_apply_padding_keeps_bottom_padding_without_caption_limit(self):
        region = fitz.Rect(36, 100, 280, 220)
        page_rect = fitz.Rect(0, 0, 595, 842)
        padded = extract_figures._apply_padding(region, page_rect, 4.0)
        self.assertEqual(padded.y0, 96.0)
        self.assertEqual(padded.y1, 224.0)


if __name__ == "__main__":
    unittest.main()
