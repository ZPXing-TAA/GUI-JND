from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QVBoxLayout, QWidget

from jnd_gui.constants import PRESENTATION_CANDIDATE_FIRST, PRESENTATION_REFERENCE_FIRST


END_PAUSE_THRESHOLD_MS = 80


class SequentialTrialPlayer(QWidget):
    clip_changed = Signal(str)
    status_changed = Signal(str)
    clip_finished = Signal(str)
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
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.errorOccurred.connect(self._on_error)

        self._clips: dict[str, Path] = {}
        self._active_clip_label: str | None = None
        self._end_processed = False

    def prepare_trial(
        self,
        reference_path: Path,
        candidate_path: Path,
        presentation_order: str,
    ) -> None:
        self.stop()
        if presentation_order == PRESENTATION_REFERENCE_FIRST:
            self._clips = {"A": reference_path, "B": candidate_path}
        elif presentation_order == PRESENTATION_CANDIDATE_FIRST:
            self._clips = {"A": candidate_path, "B": reference_path}
        else:
            self.playback_error.emit(f"Unexpected presentation order '{presentation_order}'.")
            return

        self.clip_changed.emit("A")
        self.status_changed.emit("Ready to start clip A.")

    def play_clip(self, clip_label: str) -> None:
        clip_path = self._clips.get(clip_label)
        if clip_path is None:
            self.playback_error.emit(f"Clip '{clip_label}' is unavailable for the current trial.")
            return

        self._active_clip_label = clip_label
        self._end_processed = False
        self.clip_changed.emit(clip_label)
        self.status_changed.emit(f"Playing clip {clip_label}.")
        self.player.setSource(QUrl.fromLocalFile(str(clip_path)))
        self.player.play()

    def stop(self) -> None:
        self.player.stop()
        self._clips = {}
        self._active_clip_label = None
        self._end_processed = False

    def _on_position_changed(self, position: int) -> None:
        if self._active_clip_label is None or self._end_processed:
            return
        duration = self.player.duration()
        if duration <= 0:
            return
        if position < max(duration - END_PAUSE_THRESHOLD_MS, 0):
            return
        self._finish_active_clip()

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status != QMediaPlayer.MediaStatus.EndOfMedia:
            return
        self._finish_active_clip()

    def _finish_active_clip(self) -> None:
        if self._active_clip_label is None or self._end_processed:
            return
        self._end_processed = True
        duration = self.player.duration()
        if duration > 0:
            self.player.setPosition(max(duration - 1, 0))
        self.player.pause()
        finished_label = self._active_clip_label
        self.status_changed.emit(f"Clip {finished_label} finished.")
        self.clip_finished.emit(finished_label)
        self._active_clip_label = None

    def _on_error(self, _error: QMediaPlayer.Error, error_string: str) -> None:
        if not error_string:
            error_string = "Unknown media playback error."
        self.playback_error.emit(error_string)
