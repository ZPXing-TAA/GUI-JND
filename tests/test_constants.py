from __future__ import annotations

import unittest

from jnd_gui.constants import INTER_CLIP_GAP_MS, INTER_CLIP_GAP_SECONDS, INTER_CLIP_WAIT_PROMPT


class ConstantsTests(unittest.TestCase):
    def test_inter_clip_gap_matches_requested_one_second(self) -> None:
        self.assertEqual(INTER_CLIP_GAP_SECONDS, 1)
        self.assertEqual(INTER_CLIP_GAP_MS, 1000)

    def test_inter_clip_wait_prompt_uses_configured_gap(self) -> None:
        self.assertEqual(
            INTER_CLIP_WAIT_PROMPT,
            "Clip A finished. Clip B will start in 1 seconds.",
        )


if __name__ == "__main__":
    unittest.main()
