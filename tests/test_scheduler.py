from __future__ import annotations

import unittest
from pathlib import Path

from jnd_gui.constants import PRESENTATION_REFERENCE_FIRST, RESPONSE_DIFFERENT, RESPONSE_SAME
from jnd_gui.models import Phase1Result, Phase2Result, RenderConfig, TrialRecord
from jnd_gui.scheduler import (
    build_final_safe_set,
    evaluate_phase1_history,
    evaluate_phase2_progress,
    phase2_result_has_prior_contradiction,
    phase2_queue_from_phase1,
    select_training_configs,
)


def make_trial(
    phase: str,
    resolution: str,
    fps: int,
    response: str,
    effect: str = "High",
    shadow: str = "High",
) -> TrialRecord:
    config = RenderConfig(resolution, fps, effect, shadow)
    return TrialRecord(
        trial_index=1,
        subject_id="S01",
        device="device",
        action_type="run",
        country="natlan",
        route_suffix=30,
        occurrence=2,
        scene_folder_name="natlan_r30_run02",
        phase=phase,
        candidate_config=config,
        reference_config=RenderConfig("VeryHigh", 60, "High", "High"),
        candidate_path=Path("/candidate.mp4"),
        reference_path=Path("/reference.mp4"),
        presentation_order=PRESENTATION_REFERENCE_FIRST,
        response=response,
        response_time_ms=1000,
        timestamp="2026-03-18T14:12:05+08:00",
    )


class SchedulerTests(unittest.TestCase):
    def test_phase1_found_45_after_boundary_confirmation(self) -> None:
        history = [
            make_trial("phase1", "High", 45, RESPONSE_SAME),
            make_trial("phase1", "High", 30, RESPONSE_DIFFERENT),
            make_trial("phase1", "High", 30, RESPONSE_DIFFERENT),
        ]
        decision = evaluate_phase1_history("High", history)
        self.assertEqual(decision.kind, "complete")
        self.assertEqual(decision.result.status, "FOUND")
        self.assertEqual(decision.result.lowest_jnd_safe_fps, 45)

    def test_phase1_ambiguous_when_confirmation_conflicts(self) -> None:
        history = [
            make_trial("phase1", "High", 45, RESPONSE_SAME),
            make_trial("phase1", "High", 30, RESPONSE_DIFFERENT),
            make_trial("phase1", "High", 30, RESPONSE_SAME),
        ]
        decision = evaluate_phase1_history("High", history)
        self.assertEqual(decision.result.status, "AMBIGUOUS")

    def test_phase1_not_found_when_60_also_different_twice(self) -> None:
        history = [
            make_trial("phase1", "Low", 45, RESPONSE_DIFFERENT),
            make_trial("phase1", "Low", 60, RESPONSE_DIFFERENT),
            make_trial("phase1", "Low", 60, RESPONSE_DIFFERENT),
        ]
        decision = evaluate_phase1_history("Low", history)
        self.assertEqual(decision.result.status, "NOT_FOUND")

    def test_phase1_requests_confirmation_after_24_boundary(self) -> None:
        history = [
            make_trial("phase1", "Medium", 45, RESPONSE_SAME),
            make_trial("phase1", "Medium", 30, RESPONSE_SAME),
            make_trial("phase1", "Medium", 24, RESPONSE_DIFFERENT),
        ]
        decision = evaluate_phase1_history("Medium", history)
        self.assertEqual(decision.kind, "need_trial")
        self.assertEqual(decision.config.fps, 24)

    def test_phase1_requests_confirmation_after_30_boundary(self) -> None:
        history = [
            make_trial("phase1", "Medium", 45, RESPONSE_SAME),
            make_trial("phase1", "Medium", 30, RESPONSE_DIFFERENT),
        ]
        decision = evaluate_phase1_history("Medium", history)
        self.assertEqual(decision.kind, "need_trial")
        self.assertEqual(decision.config.fps, 30)

    def test_phase2_marks_missing_assets_without_trial(self) -> None:
        decision = evaluate_phase2_progress("High", 45, {}, [])
        self.assertEqual(decision.kind, "complete")
        self.assertEqual(
            [result.status for result in decision.result.candidate_results],
            ["MISSING_ASSET", "MISSING_ASSET", "MISSING_ASSET"],
        )

    def test_phase2_marks_prior_contradiction_as_ambiguous(self) -> None:
        candidate_map = {
            ("High", 45, "Low", "Low"): object(),
            ("High", 45, "Low", "High"): object(),
            ("High", 45, "High", "Low"): object(),
        }
        history = [
            make_trial("phase2", "High", 45, RESPONSE_SAME, effect="Low", shadow="Low"),
            make_trial("phase2", "High", 45, RESPONSE_DIFFERENT, effect="Low", shadow="High"),
            make_trial("phase2", "High", 45, RESPONSE_DIFFERENT, effect="High", shadow="Low"),
        ]

        decision = evaluate_phase2_progress("High", 45, candidate_map, history)

        self.assertEqual(decision.kind, "complete")
        self.assertTrue(phase2_result_has_prior_contradiction(decision.result))

    def test_training_configs_follow_power_prior_order(self) -> None:
        candidate_map = {
            ("VeryHigh", 60, "High", "High"): object(),
            ("Lowest", 24, "Low", "Low"): object(),
            ("Medium", 30, "Low", "High"): object(),
            ("High", 45, "High", "Low"): object(),
        }

        training = select_training_configs(candidate_map)

        self.assertEqual(training[0], RenderConfig("Lowest", 24, "Low", "Low"))
        self.assertEqual(training[1], RenderConfig("Medium", 30, "Low", "High"))
        self.assertEqual(training[2], RenderConfig("High", 45, "High", "Low"))

    def test_final_safe_set_merges_phase1_and_phase2(self) -> None:
        phase1_results = [
            Phase1Result("VeryHigh", 45, "FOUND"),
            Phase1Result("High", None, "NOT_FOUND"),
        ]
        phase2_results = [
            Phase2Result(
                resolution="VeryHigh",
                fps_star=45,
                candidate_results=[
                    type("Candidate", (), {"effect": "Low", "shadow": "Low", "status": "NOT_SAFE"})(),
                    type("Candidate", (), {"effect": "Low", "shadow": "High", "status": "SAFE"})(),
                    type("Candidate", (), {"effect": "High", "shadow": "Low", "status": "SAFE"})(),
                ],
            )
        ]
        safe_set = build_final_safe_set(
            subject_id="S01",
            device="device",
            action_type="run",
            country="natlan",
            route_suffix=30,
            occurrence=2,
            scene_folder_name="natlan_r30_run02",
            phase1_results=phase1_results,
            phase2_results=phase2_results,
        )
        self.assertEqual(len(safe_set.jnd_safe_set), 3)
        self.assertEqual(
            safe_set.estimated_lowest_power_safe_config,
            RenderConfig("VeryHigh", 45, "Low", "High"),
        )
        self.assertEqual(safe_set.estimated_lowest_power_safe_config_source, "relative_power_prior")
        queue = phase2_queue_from_phase1(phase1_results)
        self.assertEqual(queue, [("VeryHigh", 45)])

    def test_final_safe_set_skips_ambiguous_phase2_branch(self) -> None:
        safe_set = build_final_safe_set(
            subject_id="S01",
            device="device",
            action_type="run",
            country="natlan",
            route_suffix=30,
            occurrence=2,
            scene_folder_name="natlan_r30_run02",
            phase1_results=[Phase1Result("High", 45, "FOUND")],
            phase2_results=[
                Phase2Result(
                    resolution="High",
                    fps_star=45,
                    candidate_results=[
                        type("Candidate", (), {"effect": "Low", "shadow": "Low", "status": "SAFE"})(),
                        type("Candidate", (), {"effect": "Low", "shadow": "High", "status": "NOT_SAFE"})(),
                        type("Candidate", (), {"effect": "High", "shadow": "Low", "status": "NOT_SAFE"})(),
                    ],
                )
            ],
        )

        self.assertEqual(safe_set.jnd_safe_set, [RenderConfig("High", 45, "High", "High")])


if __name__ == "__main__":
    unittest.main()
