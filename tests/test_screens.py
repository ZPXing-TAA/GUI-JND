from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from jnd_gui.screens import TrialScreen
except ModuleNotFoundError:
    QApplication = None
    TrialScreen = None


@unittest.skipIf(QApplication is None or TrialScreen is None, "PySide6 is unavailable in this environment.")
class TrialScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_stage_action_button_matches_response_row_width(self) -> None:
        widget = TrialScreen()
        widget.show()
        self.app.processEvents()

        expected_width = (
            widget.no_diff_button.sizeHint().width()
            + widget.visible_diff_button.sizeHint().width()
            + widget._response_button_row.spacing()
        )

        self.assertEqual(widget.stage_action_button.width(), expected_width)
        widget.close()


if __name__ == "__main__":
    unittest.main()
