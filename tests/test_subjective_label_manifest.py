from __future__ import annotations

import unittest
from pathlib import Path

from jnd_gui.constants import REFERENCE_CONFIG
from jnd_gui.errors import SpecError
from jnd_gui.models import RenderConfig, SessionMeta, TrialRecord
from jnd_gui.subjective_label_manifest import build_candidate_subjective_label_manifest


def _trial(
    trial_index: int,
    phase: str,
    config: RenderConfig,
    response: str,
) -> TrialRecord:
    return TrialRecord(
        trial_index=trial_index,
        subject_id="S01",
        device="device01",
        action_type="run",
        country="natlan",
        route_suffix=30,
        occurrence=2,
        scene_folder_name="natlan_r30_run02",
        phase=phase,
        candidate_config=config,
        reference_config=REFERENCE_CONFIG,
        candidate_path=Path(f"/tmp/{config.resolution}_{config.fps}_{config.effect}_{config.shadow}.mp4"),
        reference_path=Path("/tmp/reference.mp4"),
        presentation_order="reference_first",
        response=response,
        response_time_ms=1000,
        timestamp="2026-03-27T12:00:00+08:00",
    )


class CandidateSubjectiveLabelManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.meta = SessionMeta(
            subject_id="S01",
            device="device01",
            action_type="run",
            country="natlan",
            route_suffix=30,
            occurrence=2,
            scene_folder_name="natlan_r30_run02",
            scene_folder=Path("/tmp/natlan_r30_run02"),
            reference_config=REFERENCE_CONFIG,
            reference_path=Path("/tmp/reference.mp4"),
            created_at="2026-03-27T12:00:00+08:00",
            app_spec_version="1.0",
        )

    def test_build_manifest_labels_every_candidate_with_observed_and_monotonic_closure(self) -> None:
        low_not_safe = RenderConfig("Low", 24, "Low", "Low")
        medium_safe = RenderConfig("Medium", 30, "Low", "Low")
        high_not_safe = RenderConfig("High", 45, "High", "High")
        ambiguous_observed = RenderConfig("Medium", 45, "Low", "Low")
        inferred_ambiguous = RenderConfig("High", 30, "High", "High")
        inferred_not_safe = RenderConfig("Lowest", 24, "Low", "Low")
        inferred_safe = RenderConfig("VeryHigh", 60, "High", "High")
        unresolved = RenderConfig("VeryHigh", 24, "Low", "Low")

        candidate_manifest = {
            "device": self.meta.device,
            "action_type": self.meta.action_type,
            "country": self.meta.country,
            "route_suffix": self.meta.route_suffix,
            "occurrence": self.meta.occurrence,
            "scene_folder_name": self.meta.scene_folder_name,
            "reference_config": REFERENCE_CONFIG.to_dict(),
            "candidates": [
                self._candidate_entry(low_not_safe, "1.mp4"),
                self._candidate_entry(medium_safe, "2.mp4"),
                self._candidate_entry(high_not_safe, "3.mp4"),
                self._candidate_entry(ambiguous_observed, "4.mp4"),
                self._candidate_entry(inferred_ambiguous, "5.mp4"),
                self._candidate_entry(inferred_not_safe, "6.mp4"),
                self._candidate_entry(inferred_safe, "7.mp4"),
                self._candidate_entry(unresolved, "8.mp4"),
            ],
        }
        raw_trials = [
            _trial(1, "phase1", low_not_safe, "Different"),
            _trial(2, "phase1", medium_safe, "Same"),
            _trial(3, "phase2", high_not_safe, "Different"),
            _trial(4, "phase1", ambiguous_observed, "Same"),
            _trial(5, "phase2", ambiguous_observed, "Different"),
            _trial(6, "training", medium_safe, "Different"),
        ]

        manifest = build_candidate_subjective_label_manifest(
            meta=self.meta,
            raw_trials=raw_trials,
            candidate_power_prior_manifest=candidate_manifest,
        )

        self.assertEqual(manifest["subject_id"], "S01")
        self.assertEqual(len(manifest["candidates"]), len(candidate_manifest["candidates"]))

        by_path = {entry["video_path"]: entry for entry in manifest["candidates"]}

        medium_entry = by_path["/tmp/2.mp4"]
        self.assertEqual(medium_entry["subjective_label"], "safe")
        self.assertEqual(medium_entry["label_source"], "observed")
        self.assertEqual(medium_entry["observed_trial_indices"], [2])
        self.assertEqual(medium_entry["observed_responses"], ["Same"])
        self.assertEqual(medium_entry["power_label_type"], "relative_power_prior")

        ambiguous_entry = by_path["/tmp/4.mp4"]
        self.assertEqual(ambiguous_entry["subjective_label"], "ambiguous")
        self.assertEqual(ambiguous_entry["label_source"], "observed")
        self.assertEqual(ambiguous_entry["observed_trial_indices"], [4, 5])
        self.assertIn("conflict", ambiguous_entry["notes"])

        inferred_safe_entry = by_path["/tmp/7.mp4"]
        self.assertEqual(inferred_safe_entry["subjective_label"], "safe")
        self.assertEqual(inferred_safe_entry["label_source"], "inferred_monotonic")
        self.assertEqual(inferred_safe_entry["safe_supporters"], [medium_safe.to_dict()])
        self.assertEqual(inferred_safe_entry["not_safe_supporters"], [])

        inferred_not_safe_entry = by_path["/tmp/6.mp4"]
        self.assertEqual(inferred_not_safe_entry["subjective_label"], "not_safe")
        self.assertEqual(inferred_not_safe_entry["label_source"], "inferred_monotonic")
        self.assertEqual(
            inferred_not_safe_entry["not_safe_supporters"],
            [low_not_safe.to_dict(), high_not_safe.to_dict()],
        )

        inferred_ambiguous_entry = by_path["/tmp/5.mp4"]
        self.assertEqual(inferred_ambiguous_entry["subjective_label"], "ambiguous")
        self.assertEqual(inferred_ambiguous_entry["label_source"], "inferred_monotonic")
        self.assertEqual(inferred_ambiguous_entry["safe_supporters"], [medium_safe.to_dict()])
        self.assertEqual(inferred_ambiguous_entry["not_safe_supporters"], [high_not_safe.to_dict()])

        unresolved_entry = by_path["/tmp/8.mp4"]
        self.assertEqual(unresolved_entry["subjective_label"], "unknown")
        self.assertEqual(unresolved_entry["label_source"], "unresolved")
        self.assertEqual(unresolved_entry["safe_supporters"], [])
        self.assertEqual(unresolved_entry["not_safe_supporters"], [])

        for entry in manifest["candidates"]:
            self.assertIn("subjective_label", entry)
            self.assertIn("label_source", entry)

    def test_build_manifest_rejects_raw_trial_config_missing_from_candidate_manifest(self) -> None:
        candidate_manifest = {
            "device": self.meta.device,
            "action_type": self.meta.action_type,
            "country": self.meta.country,
            "route_suffix": self.meta.route_suffix,
            "occurrence": self.meta.occurrence,
            "scene_folder_name": self.meta.scene_folder_name,
            "reference_config": REFERENCE_CONFIG.to_dict(),
            "candidates": [
                self._candidate_entry(RenderConfig("Medium", 30, "Low", "Low"), "only.mp4"),
            ],
        }

        with self.assertRaises(SpecError):
            build_candidate_subjective_label_manifest(
                meta=self.meta,
                raw_trials=[_trial(1, "phase1", RenderConfig("Low", 24, "Low", "Low"), "Different")],
                candidate_power_prior_manifest=candidate_manifest,
            )

    @staticmethod
    def _candidate_entry(config: RenderConfig, filename: str) -> dict[str, object]:
        return {
            "video_path": f"/tmp/{filename}",
            "render_config": config.to_dict(),
            "power_prior_tuple": {
                "fps_rank": config.fps,
                "resolution_rank": 0,
                "effect_rank": 0,
                "shadow_rank": 0,
            },
            "power_prior_order_key": [0, 0, 0, 0],
            "power_label_type": "relative_power_prior",
            "power_label_source": "inferred_prior",
        }


if __name__ == "__main__":
    unittest.main()
