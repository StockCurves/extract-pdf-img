import unittest

import extract_figures
import verify_crops


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


if __name__ == "__main__":
    unittest.main()
