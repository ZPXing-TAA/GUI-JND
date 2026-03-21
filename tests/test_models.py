from __future__ import annotations

import unittest
from pathlib import Path

from jnd_gui.models import FinalSafeSet, RenderConfig, SessionMeta, TrialRecord


class ModelCompatibilityTests(unittest.TestCase):
    def test_session_meta_to_dict_writes_main_spec_keys(self) -> None:
        meta = SessionMeta(
            subject_id="S01",
            device="huaweipura",
            action_type="run",
            country="natlan",
            route_suffix=30,
            occurrence=2,
            scene_folder_name="natlan_r30_run02",
            scene_folder=Path("/tmp/huaweipura/run/natlan_r30_run02"),
            reference_config=RenderConfig("VeryHigh", 60, "High", "High"),
            reference_path=Path("/tmp/reference.mp4"),
            created_at="2026-03-21T10:00:00+08:00",
            app_spec_version="1.0",
        )

        payload = meta.to_dict()
        self.assertEqual(payload["action_type"], "run")
        self.assertEqual(payload["country"], "natlan")
        self.assertEqual(payload["route_suffix"], 30)
        self.assertEqual(payload["occurrence"], 2)
        self.assertEqual(payload["scene_folder_name"], "natlan_r30_run02")

    def test_session_meta_from_dict_accepts_legacy_keys(self) -> None:
        meta = SessionMeta.from_dict(
            {
                "subject_id": "S01",
                "device": "huaweipura",
                "label_folder": "run",
                "recording_id": "natlan_r30_run02",
                "region": "natlan",
                "route_id": 30,
                "scene_index": 2,
                "scene_id": "natlan_r30_run02",
                "scene_folder": "/tmp/huaweipura/run/natlan_r30_run02",
                "reference_config": {
                    "resolution": "VeryHigh",
                    "fps": 60,
                    "effect": "High",
                    "shadow": "High",
                },
                "reference_path": "/tmp/reference.mp4",
                "created_at": "2026-03-21T10:00:00+08:00",
                "app_spec_version": "1.0",
            }
        )

        self.assertEqual(meta.action_type, "run")
        self.assertEqual(meta.scene_folder_name, "natlan_r30_run02")
        self.assertEqual(meta.country, "natlan")
        self.assertEqual(meta.route_suffix, 30)
        self.assertEqual(meta.occurrence, 2)

    def test_trial_record_from_dict_accepts_legacy_keys(self) -> None:
        record = TrialRecord.from_dict(
            {
                "trial_index": 1,
                "subject_id": "S01",
                "device": "huaweipura",
                "label_folder": "run",
                "recording_id": "natlan_r30_run02",
                "region": "natlan",
                "route_id": 30,
                "scene_index": 2,
                "scene_id": "natlan_r30_run02",
                "phase": "phase1",
                "candidate_config": {
                    "resolution": "High",
                    "fps": 45,
                    "effect": "High",
                    "shadow": "High",
                },
                "reference_config": {
                    "resolution": "VeryHigh",
                    "fps": 60,
                    "effect": "High",
                    "shadow": "High",
                },
                "candidate_path": "/tmp/candidate.mp4",
                "reference_path": "/tmp/reference.mp4",
                "presentation_order": "reference_first",
                "response": "Same",
                "response_time_ms": 1200,
                "timestamp": "2026-03-21T10:00:00+08:00",
            }
        )

        self.assertEqual(record.action_type, "run")
        self.assertEqual(record.scene_folder_name, "natlan_r30_run02")
        self.assertEqual(record.country, "natlan")

    def test_final_safe_set_to_dict_writes_main_spec_and_prior_fields(self) -> None:
        safe_set = FinalSafeSet(
            subject_id="S01",
            device="huaweipura",
            action_type="run",
            country="natlan",
            route_suffix=30,
            occurrence=2,
            scene_folder_name="natlan_r30_run02",
            reference_config=RenderConfig("VeryHigh", 60, "High", "High"),
            jnd_safe_set=[RenderConfig("High", 45, "High", "High")],
            estimated_lowest_power_safe_config=RenderConfig("High", 45, "High", "High"),
            estimated_lowest_power_safe_config_source="relative_power_prior",
            generated_at="2026-03-21T10:00:00+08:00",
        )

        payload = safe_set.to_dict()
        self.assertEqual(payload["action_type"], "run")
        self.assertEqual(payload["country"], "natlan")
        self.assertEqual(payload["route_suffix"], 30)
        self.assertEqual(payload["occurrence"], 2)
        self.assertEqual(payload["scene_folder_name"], "natlan_r30_run02")
        self.assertEqual(payload["estimated_lowest_power_safe_config"]["fps"], 45)
        self.assertEqual(payload["estimated_lowest_power_safe_config_source"], "relative_power_prior")


if __name__ == "__main__":
    unittest.main()
