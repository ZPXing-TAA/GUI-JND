from __future__ import annotations

import unittest

from main import configure_runtime_environment


class MainTests(unittest.TestCase):
    def test_configure_runtime_environment_disables_hw_decode_on_macos(self) -> None:
        environ: dict[str, str] = {}

        configure_runtime_environment(environ, system_name="Darwin")

        self.assertEqual(environ["QT_FFMPEG_DECODING_HW_DEVICE_TYPES"], ",")

    def test_configure_runtime_environment_preserves_explicit_override(self) -> None:
        environ = {"QT_FFMPEG_DECODING_HW_DEVICE_TYPES": "videotoolbox"}

        configure_runtime_environment(environ, system_name="Darwin")

        self.assertEqual(environ["QT_FFMPEG_DECODING_HW_DEVICE_TYPES"], "videotoolbox")

    def test_configure_runtime_environment_is_noop_off_macos(self) -> None:
        environ: dict[str, str] = {}

        configure_runtime_environment(environ, system_name="Linux")

        self.assertNotIn("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", environ)


if __name__ == "__main__":
    unittest.main()
