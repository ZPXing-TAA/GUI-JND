from __future__ import annotations

import os
import platform
import sys

def configure_runtime_environment(
    environ: dict[str, str] | None = None,
    system_name: str | None = None,
) -> None:
    environ = os.environ if environ is None else environ
    system_name = platform.system() if system_name is None else system_name
    if system_name == "Darwin":
        # Qt 6 FFmpeg on macOS may route H.264 through VideoToolbox, which is
        # unstable for some scrcpy-generated recordings. Default to software
        # decoding unless the operator explicitly configured another policy.
        environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", ",")


def main() -> int:
    configure_runtime_environment()
    from PySide6.QtWidgets import QApplication

    from jnd_gui.app_controller import JNDExperimentWindow

    app = QApplication(sys.argv)
    app.setApplicationName("JND Subjective Experiment GUI")
    window = JNDExperimentWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
