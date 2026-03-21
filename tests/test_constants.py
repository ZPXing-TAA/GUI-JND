from __future__ import annotations

import unittest

from jnd_gui.constants import INTER_CLIP_GAP_MS, INTER_CLIP_GAP_SECONDS, INTER_CLIP_WAIT_PROMPT


class ConstantsTests(unittest.TestCase):
    def test_inter_clip_gap_matches_requested_three_seconds(self) -> None:
        self.assertEqual(INTER_CLIP_GAP_SECONDS, 3)
        self.assertEqual(INTER_CLIP_GAP_MS, 3000)

    def test_inter_clip_wait_prompt_uses_configured_gap(self) -> None:
        self.assertEqual(
            INTER_CLIP_WAIT_PROMPT,
            "Clip A finished. Clip B will start in 3 seconds.",
        )


if __name__ == "__main__":
    unittest.main()
