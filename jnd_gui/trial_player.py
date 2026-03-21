from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QVBoxLayout, QWidget

from jnd_gui.constants import PRESENTATION_CANDIDATE_FIRST, PRESENTATION_REFERENCE_FIRST


class SequentialTrialPlayer(QWidget):
    clip_changed = Signal(str)
    status_changed = Signal(str)
    playback_complete = Signal()
    playback_error = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.video_widget = QVideoWidget(self)
        self.video_widget.setMinimumHeight(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_widget)

        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(1.0)

        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.errorOccurred.connect(self._on_error)

        self._clips: list[tuple[str, Path]] = []
        self._current_index = -1
        self._end_processed = False

    def load_trial(self, reference_path: Path, candidate_path: Path, presentation_order: str) -> None:
        if presentation_order == PRESENTATION_REFERENCE_FIRST:
            self._clips = [("A", reference_path), ("B", candidate_path)]
        elif presentation_order == PRESENTATION_CANDIDATE_FIRST:
            self._clips = [("A", candidate_path), ("B", reference_path)]
        else:
            self.playback_error.emit(f"Unexpected presentation order '{presentation_order}'.")
            return

        self._current_index = -1
        self._play_next_clip()

    def stop(self) -> None:
        self.player.stop()
        self._clips = []
        self._current_index = -1
        self._end_processed = False

    def _play_next_clip(self) -> None:
        self._current_index += 1
        self._end_processed = False
        if self._current_index >= len(self._clips):
            self.player.stop()
            self.status_changed.emit("Playback complete. Response input is now enabled.")
            self.playback_complete.emit()
            return

        clip_label, clip_path = self._clips[self._current_index]
        self.clip_changed.emit(clip_label)
        self.status_changed.emit(f"Playing clip {clip_label}.")
        self.player.setSource(QUrl.fromLocalFile(str(clip_path)))
        self.player.play()

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia and not self._end_processed:
            self._end_processed = True
            QTimer.singleShot(200, self._play_next_clip)

    def _on_error(self, _error: QMediaPlayer.Error, error_string: str) -> None:
        if not error_string:
            error_string = "Unknown media playback error."
        self.playback_error.emit(error_string)
