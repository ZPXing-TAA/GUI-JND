from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QElapsedTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from jnd_gui.constants import BUTTON_NO_NOTICEABLE_DIFF, BUTTON_VISIBLE_DIFF, RESPONSE_DIFFERENT, RESPONSE_SAME
from jnd_gui.trial_player import SequentialTrialPlayer


class StartScreen(QWidget):
    start_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        title = QLabel("JND Subjective Experiment")
        title.setStyleSheet("font-size: 28px; font-weight: 700;")

        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Enter subject id")

        self.scene_folder_input = QLineEdit()
        self.scene_folder_input.setPlaceholderText("Select recording folder")

        browse_button = QPushButton("Browse Folder")
        browse_button.clicked.connect(self._browse_folder)

        self.start_button = QPushButton("Start Experiment")
        self.start_button.clicked.connect(self._emit_start_requested)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #b00020;")

        self.warning_box = QTextEdit()
        self.warning_box.setReadOnly(True)
        self.warning_box.setPlaceholderText("Validation warnings will appear here.")
        self.warning_box.setMaximumHeight(140)

        folder_row = QHBoxLayout()
        folder_row.addWidget(self.scene_folder_input, stretch=1)
        folder_row.addWidget(browse_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(QLabel("Subject ID"))
        layout.addWidget(self.subject_input)
        layout.addWidget(QLabel("Recording Folder"))
        layout.addLayout(folder_row)
        layout.addWidget(self.start_button)
        layout.addWidget(self.info_label)
        layout.addWidget(self.error_label)
        layout.addWidget(QLabel("Warnings"))
        layout.addWidget(self.warning_box)
        layout.addStretch(1)

    def populate_inputs(self, subject_id: str, scene_folder: str) -> None:
        self.subject_input.setText(subject_id)
        self.scene_folder_input.setText(scene_folder)

    def show_validation(
        self,
        info_lines: list[str] | None = None,
        warnings: list[str] | None = None,
        error_message: str | None = None,
    ) -> None:
        self.info_label.setText("\n".join(info_lines or []))
        self.warning_box.setPlainText("\n".join(warnings or []))
        self.error_label.setText(error_message or "")

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Recording Folder")
        if folder:
            self.scene_folder_input.setText(folder)

    def _emit_start_requested(self) -> None:
        self.start_requested.emit(self.subject_input.text(), self.scene_folder_input.text())


class ResumeScreen(QWidget):
    resume_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        title = QLabel("Resume Existing Session")
        title.setStyleSheet("font-size: 28px; font-weight: 700;")

        self.details_label = QLabel("")
        self.details_label.setWordWrap(True)

        resume_button = QPushButton("Resume Session")
        resume_button.clicked.connect(self.resume_requested.emit)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.cancel_requested.emit)

        button_row = QHBoxLayout()
        button_row.addWidget(resume_button)
        button_row.addWidget(cancel_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(self.details_label)
        layout.addLayout(button_row)
        layout.addStretch(1)

    def set_details(self, lines: list[str]) -> None:
        self.details_label.setText("\n".join(lines))


class MessageScreen(QWidget):
    primary_clicked = Signal()
    secondary_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel("")
        self.title_label.setStyleSheet("font-size: 28px; font-weight: 700;")

        self.body_label = QLabel("")
        self.body_label.setWordWrap(True)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.primary_button = QPushButton("")
        self.primary_button.clicked.connect(self.primary_clicked.emit)

        self.secondary_button = QPushButton("")
        self.secondary_button.clicked.connect(self.secondary_clicked.emit)
        self.secondary_button.hide()

        button_row = QHBoxLayout()
        button_row.addWidget(self.primary_button)
        button_row.addWidget(self.secondary_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(16)
        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.detail_label)
        layout.addLayout(button_row)
        layout.addStretch(1)

    def configure(
        self,
        title: str,
        body_lines: list[str],
        detail_lines: list[str],
        primary_label: str,
        secondary_label: str | None = None,
    ) -> None:
        self.title_label.setText(title)
        self.body_label.setText("\n".join(body_lines))
        self.detail_label.setText("\n".join(detail_lines))
        self.primary_button.setText(primary_label)
        self.secondary_button.setVisible(bool(secondary_label))
        if secondary_label:
            self.secondary_button.setText(secondary_label)


class TrialScreen(QWidget):
    response_submitted = Signal(str, int)
    playback_error = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.title_label = QLabel("Compare the two clips and judge whether there is a noticeable visible difference.")
        self.title_label.setStyleSheet("font-size: 24px; font-weight: 700;")
        self.title_label.setWordWrap(True)
        self.progress_label = QLabel("")
        self.clip_label = QLabel("Clip -")
        self.clip_label.setStyleSheet("font-size: 22px; font-weight: 600;")
        self.status_label = QLabel("Awaiting playback.")
        self.status_label.setWordWrap(True)

        self.player = SequentialTrialPlayer(self)
        self.player.clip_changed.connect(self._on_clip_changed)
        self.player.status_changed.connect(self.status_label.setText)
        self.player.playback_complete.connect(self._on_playback_complete)
        self.player.playback_error.connect(self.playback_error.emit)

        self.no_diff_button = QPushButton(BUTTON_NO_NOTICEABLE_DIFF)
        self.no_diff_button.clicked.connect(lambda: self._submit_response(RESPONSE_SAME))
        self.visible_diff_button = QPushButton(BUTTON_VISIBLE_DIFF)
        self.visible_diff_button.clicked.connect(lambda: self._submit_response(RESPONSE_DIFFERENT))
        self._set_response_buttons_enabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self.no_diff_button)
        button_row.addWidget(self.visible_diff_button)

        header_box = QFrame()
        header_layout = QVBoxLayout(header_box)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.progress_label)
        header_layout.addWidget(self.clip_label)
        header_layout.addWidget(self.status_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(header_box)
        layout.addWidget(self.player, stretch=1)
        layout.addLayout(button_row)

        self._response_timer = QElapsedTimer()
        self._response_enabled = False

    def start_trial(
        self,
        progress_text: str,
        reference_path: Path,
        candidate_path: Path,
        presentation_order: str,
    ) -> None:
        self.progress_label.setText(progress_text)
        self.clip_label.setText("Clip -")
        self.status_label.setText("Preparing playback.")
        self._response_enabled = False
        self._set_response_buttons_enabled(False)
        self.player.load_trial(reference_path, candidate_path, presentation_order)

    def stop_trial(self) -> None:
        self.player.stop()
        self._response_enabled = False
        self._set_response_buttons_enabled(False)

    def _on_clip_changed(self, clip_label: str) -> None:
        self.clip_label.setText(f"Clip {clip_label}")

    def _on_playback_complete(self) -> None:
        self._response_timer.start()
        self._response_enabled = True
        self._set_response_buttons_enabled(True)

    def _set_response_buttons_enabled(self, enabled: bool) -> None:
        self.no_diff_button.setEnabled(enabled)
        self.visible_diff_button.setEnabled(enabled)

    def _submit_response(self, response: str) -> None:
        if not self._response_enabled:
            return
        self._response_enabled = False
        self._set_response_buttons_enabled(False)
        response_time_ms = int(self._response_timer.elapsed())
        self.response_submitted.emit(response, response_time_ms)
