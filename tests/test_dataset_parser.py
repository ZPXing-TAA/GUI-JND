from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jnd_gui.dataset_parser import parse_experiment_unit, parse_render_config_from_filename, scan_scene_folder
from jnd_gui.errors import SpecError


class DatasetParserTests(unittest.TestCase):
    def test_parse_canonical_and_legacy_names(self) -> None:
        canonical, warning = parse_render_config_from_filename("High_45_High_High.mp4")
        self.assertIsNone(warning)
        self.assertEqual(canonical.fps, 45)

        legacy, warning = parse_render_config_from_filename("High_High_24_Low_High.mp4")
        self.assertIsNone(warning)
        self.assertEqual(legacy.effect, "Low")

    def test_scan_scene_folder_with_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = (
                Path(temp_dir)
                / "huaweipura"
                / "run"
                / "natlan_r30_run02"
            )
            scene_dir.mkdir(parents=True)
            (scene_dir / "VeryHigh_60_High_High.mp4").touch()
            (scene_dir / "High_High_45_High_High.mp4").touch()
            (scene_dir / "bad_name.mp4").touch()

            result = scan_scene_folder(scene_dir)
            self.assertEqual(result.experiment_unit.device, "huaweipura")
            self.assertEqual(result.experiment_unit.action_type, "run")
            self.assertEqual(result.experiment_unit.scene_folder_name, "natlan_r30_run02")
            self.assertEqual(result.experiment_unit.country, "natlan")
            self.assertEqual(result.experiment_unit.route_suffix, 30)
            self.assertEqual(result.experiment_unit.occurrence, 2)
            self.assertEqual(len(result.candidate_map), 2)
            self.assertEqual(result.candidate_power_prior_manifest["action_type"], "run")
            self.assertEqual(result.candidate_power_prior_manifest["scene_folder_name"], "natlan_r30_run02")
            self.assertEqual(
                result.candidate_power_prior_manifest["candidates"][0]["render_config"]["resolution"],
                "High",
            )
            self.assertEqual(
                result.candidate_power_prior_manifest["candidates"][0]["power_label_type"],
                "relative_power_prior",
            )
            self.assertEqual(len(result.warnings), 1)

    def test_missing_reference_is_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = (
                Path(temp_dir)
                / "huaweipura"
                / "run"
                / "natlan_r30_run02"
            )
            scene_dir.mkdir(parents=True)
            (scene_dir / "High_45_High_High.mp4").touch()

            with self.assertRaises(SpecError):
                scan_scene_folder(scene_dir)

    def test_duplicate_canonical_mapping_is_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = (
                Path(temp_dir)
                / "huaweipura"
                / "run"
                / "natlan_r30_run02"
            )
            scene_dir.mkdir(parents=True)
            (scene_dir / "VeryHigh_60_High_High.mp4").touch()
            (scene_dir / "High_45_High_High.mp4").touch()
            (scene_dir / "High_High_45_High_High.mp4").touch()

            with self.assertRaises(SpecError):
                scan_scene_folder(scene_dir)

    def test_parse_current_recording_dir_requires_label_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = (
                Path(temp_dir)
                / "huaweipura"
                / "swim"
                / "natlan_r30_run02"
            )
            scene_dir.mkdir(parents=True)

            with self.assertRaises(SpecError):
                parse_experiment_unit(scene_dir)

    def test_parse_legacy_recording_dir_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = (
                Path(temp_dir)
                / "huaweipura"
                / "run"
                / "natlan_21_h30"
            )
            scene_dir.mkdir(parents=True)

            with self.assertRaises(SpecError):
                parse_experiment_unit(scene_dir)

    def test_parse_transition_recording_dir_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_dir = (
                Path(temp_dir)
                / "huaweipura"
                / "run"
                / "natlan_r30_s03"
            )
            scene_dir.mkdir(parents=True)

            with self.assertRaises(SpecError):
                parse_experiment_unit(scene_dir)


if __name__ == "__main__":
    unittest.main()
