from __future__ import annotations

import random

from jnd_gui.constants import (
    ESTIMATED_SAFE_CONFIG_SOURCE,
    PHASE2_STATUSES,
    PRESENTATION_CANDIDATE_FIRST,
    PRESENTATION_REFERENCE_FIRST,
    REFERENCE_CONFIG,
    RESOLUTION_ORDER,
    RESPONSE_DIFFERENT,
    RESPONSE_SAME,
)
from jnd_gui.errors import SpecError
from jnd_gui.models import (
    FinalSafeSet,
    Phase1Decision,
    Phase1Result,
    Phase2CandidateResult,
    Phase2Decision,
    Phase2Result,
    RenderConfig,
    TrialRecord,
)
from jnd_gui.power_prior import (
    choose_estimated_lowest_power_safe_config,
    sort_configs_by_power_prior,
)
from jnd_gui.utils import timestamp_now


def format_render_config(config: RenderConfig) -> str:
    return (
        f"Resolution={config.resolution}, FPS={config.fps}, "
        f"Effect={config.effect}, Shadow={config.shadow}"
    )


def select_training_configs(candidate_map: dict[tuple[str, int, str, str], object]) -> list[RenderConfig]:
    configs = [RenderConfig(*key) for key in candidate_map if key != REFERENCE_CONFIG.key()]
    if not configs:
        raise SpecError(
            "No non-reference candidate videos were found. Training requires at least one candidate clip."
        )
    configs = sort_configs_by_power_prior(configs)
    obvious = configs[0]
    medium = configs[len(configs) // 2]
    near_reference = configs[-1]
    return [obvious, medium, near_reference]


def phase1_trials_for_resolution(raw_trials: list[TrialRecord], resolution: str) -> list[TrialRecord]:
    return [
        trial
        for trial in raw_trials
        if trial.phase == "phase1" and trial.candidate_config.resolution == resolution
    ]


def phase2_trials_for_resolution(raw_trials: list[TrialRecord], resolution: str) -> list[TrialRecord]:
    return [
        trial
        for trial in raw_trials
        if trial.phase == "phase2" and trial.candidate_config.resolution == resolution
    ]


def evaluate_phase1_history(resolution: str, history: list[TrialRecord]) -> Phase1Decision:
    for record in history:
        config = record.candidate_config
        if config.resolution != resolution or config.effect != "High" or config.shadow != "High":
            raise SpecError(
                f"Resume state is corrupted: Phase 1 history for resolution '{resolution}' contains an unexpected config."
            )

    responses = [(record.candidate_config.fps, record.response) for record in history]
    if not responses:
        return Phase1Decision("need_trial", config=RenderConfig(resolution, 45, "High", "High"))

    first_fps, first_response = responses[0]
    if first_fps != 45:
        raise SpecError(
            f"Resume state is corrupted: Phase 1 at resolution '{resolution}' must begin with 45 FPS."
        )

    if first_response == RESPONSE_SAME:
        return _evaluate_phase1_after_45_same(resolution, responses)
    if first_response == RESPONSE_DIFFERENT:
        return _evaluate_phase1_after_45_different(resolution, responses)
    raise SpecError(f"Unexpected response '{first_response}' in Phase 1 history.")


def _evaluate_phase1_after_45_same(
    resolution: str, responses: list[tuple[int, str]]
) -> Phase1Decision:
    if len(responses) == 1:
        return Phase1Decision("need_trial", config=RenderConfig(resolution, 30, "High", "High"))

    second_fps, second_response = responses[1]
    if second_fps != 30:
        raise SpecError(
            f"Resume state is corrupted: expected 30 FPS after 45 FPS Same at resolution '{resolution}'."
        )

    if second_response == RESPONSE_SAME:
        return _evaluate_phase1_after_30_same(resolution, responses)
    if second_response == RESPONSE_DIFFERENT:
        if len(responses) == 2:
            return Phase1Decision("need_trial", config=RenderConfig(resolution, 30, "High", "High"))
        if len(responses) > 3:
            raise SpecError(
                f"Resume state is corrupted: extra Phase 1 trials exist after 30 FPS boundary confirmation for '{resolution}'."
            )
        confirm_fps, confirm_response = responses[2]
        if confirm_fps != 30:
            raise SpecError(
                f"Resume state is corrupted: expected 30 FPS confirmation at resolution '{resolution}'."
            )
        if confirm_response == RESPONSE_DIFFERENT:
            return Phase1Decision("complete", result=Phase1Result(resolution, 45, "FOUND"))
        return Phase1Decision("complete", result=Phase1Result(resolution, None, "AMBIGUOUS"))
    raise SpecError(f"Unexpected response '{second_response}' in Phase 1 history.")


def _evaluate_phase1_after_30_same(
    resolution: str, responses: list[tuple[int, str]]
) -> Phase1Decision:
    if len(responses) == 2:
        return Phase1Decision("need_trial", config=RenderConfig(resolution, 24, "High", "High"))

    third_fps, third_response = responses[2]
    if third_fps != 24:
        raise SpecError(
            f"Resume state is corrupted: expected 24 FPS after 30 FPS Same at resolution '{resolution}'."
        )
    if third_response == RESPONSE_SAME:
        if len(responses) > 3:
            raise SpecError(
                f"Resume state is corrupted: extra Phase 1 trials exist after FOUND at 24 FPS for '{resolution}'."
            )
        return Phase1Decision("complete", result=Phase1Result(resolution, 24, "FOUND"))
    if third_response == RESPONSE_DIFFERENT:
        if len(responses) == 3:
            return Phase1Decision("need_trial", config=RenderConfig(resolution, 24, "High", "High"))
        if len(responses) > 4:
            raise SpecError(
                f"Resume state is corrupted: extra Phase 1 trials exist after 24 FPS boundary confirmation for '{resolution}'."
            )
        confirm_fps, confirm_response = responses[3]
        if confirm_fps != 24:
            raise SpecError(
                f"Resume state is corrupted: expected 24 FPS confirmation at resolution '{resolution}'."
            )
        if confirm_response == RESPONSE_DIFFERENT:
            return Phase1Decision("complete", result=Phase1Result(resolution, 30, "FOUND"))
        return Phase1Decision("complete", result=Phase1Result(resolution, None, "AMBIGUOUS"))
    raise SpecError(f"Unexpected response '{third_response}' in Phase 1 history.")


def _evaluate_phase1_after_45_different(
    resolution: str, responses: list[tuple[int, str]]
) -> Phase1Decision:
    if len(responses) == 1:
        return Phase1Decision("need_trial", config=RenderConfig(resolution, 60, "High", "High"))

    second_fps, second_response = responses[1]
    if second_fps != 60:
        raise SpecError(
            f"Resume state is corrupted: expected 60 FPS after 45 FPS Different at resolution '{resolution}'."
        )

    if second_response == RESPONSE_SAME:
        if len(responses) == 2:
            return Phase1Decision("need_trial", config=RenderConfig(resolution, 45, "High", "High"))
        if len(responses) > 3:
            raise SpecError(
                f"Resume state is corrupted: extra Phase 1 trials exist after 45 FPS confirmation for '{resolution}'."
            )
        confirm_fps, confirm_response = responses[2]
        if confirm_fps != 45:
            raise SpecError(
                f"Resume state is corrupted: expected 45 FPS confirmation at resolution '{resolution}'."
            )
        if confirm_response == RESPONSE_DIFFERENT:
            return Phase1Decision("complete", result=Phase1Result(resolution, 60, "FOUND"))
        return Phase1Decision("complete", result=Phase1Result(resolution, None, "AMBIGUOUS"))
    if second_response == RESPONSE_DIFFERENT:
        if len(responses) == 2:
            return Phase1Decision("need_trial", config=RenderConfig(resolution, 60, "High", "High"))
        if len(responses) > 3:
            raise SpecError(
                f"Resume state is corrupted: extra Phase 1 trials exist after 60 FPS confirmation for '{resolution}'."
            )
        confirm_fps, confirm_response = responses[2]
        if confirm_fps != 60:
            raise SpecError(
                f"Resume state is corrupted: expected 60 FPS confirmation at resolution '{resolution}'."
            )
        if confirm_response == RESPONSE_DIFFERENT:
            return Phase1Decision("complete", result=Phase1Result(resolution, None, "NOT_FOUND"))
        return Phase1Decision("complete", result=Phase1Result(resolution, None, "AMBIGUOUS"))
    raise SpecError(f"Unexpected response '{second_response}' in Phase 1 history.")


def phase2_queue_from_phase1(phase1_results: list[Phase1Result]) -> list[tuple[str, int]]:
    phase1_map = {result.resolution: result for result in phase1_results}
    queue: list[tuple[str, int]] = []
    for resolution in RESOLUTION_ORDER:
        result = phase1_map.get(resolution)
        if result is None or result.status != "FOUND" or result.lowest_jnd_safe_fps is None:
            continue
        queue.append((resolution, result.lowest_jnd_safe_fps))
    return queue


def phase2_candidate_order(resolution: str, fps_star: int) -> list[RenderConfig]:
    return [
        RenderConfig(resolution, fps_star, "Low", "Low"),
        RenderConfig(resolution, fps_star, "Low", "High"),
        RenderConfig(resolution, fps_star, "High", "Low"),
    ]


def _phase2_inconsistency_reason(
    resolution: str,
    fps_star: int,
    candidate_results: list[Phase2CandidateResult],
) -> str | None:
    first_safe_config: RenderConfig | None = None
    for config, result in zip(phase2_candidate_order(resolution, fps_star), candidate_results):
        if result.status == "SAFE" and first_safe_config is None:
            first_safe_config = config
            continue
        if result.status == "NOT_SAFE" and first_safe_config is not None:
            return (
                "Relative power prior contradiction: "
                f"{format_render_config(first_safe_config)} was judged SAFE before higher-power "
                f"{format_render_config(config)} was judged NOT_SAFE. "
                "The branch is marked AMBIGUOUS because Version 1 does not support retest."
            )
    return None


def evaluate_phase2_progress(
    resolution: str,
    fps_star: int,
    candidate_map: dict[tuple[str, int, str, str], object],
    history: list[TrialRecord],
) -> Phase2Decision:
    expected = phase2_candidate_order(resolution, fps_star)
    if len(history) > len(expected):
        raise SpecError(
            f"Resume state is corrupted: too many Phase 2 trials exist for resolution '{resolution}'."
        )

    candidate_results: list[Phase2CandidateResult] = []
    for index, config in enumerate(expected):
        if index < len(history):
            record = history[index]
            if record.candidate_config != config:
                raise SpecError(
                    f"Resume state is corrupted: unexpected Phase 2 candidate order at resolution '{resolution}'."
                )
            status = "SAFE" if record.response == RESPONSE_SAME else "NOT_SAFE"
            candidate_results.append(
                Phase2CandidateResult(effect=config.effect, shadow=config.shadow, status=status)
            )
            continue

        if config.key() not in candidate_map:
            candidate_results.append(
                Phase2CandidateResult(effect=config.effect, shadow=config.shadow, status="MISSING_ASSET")
            )
            continue

        return Phase2Decision("need_trial", config=config)

    inconsistency_reason = _phase2_inconsistency_reason(resolution, fps_star, candidate_results)
    return Phase2Decision(
        "complete",
        result=Phase2Result(
            resolution=resolution,
            fps_star=fps_star,
            candidate_results=candidate_results,
            status="AMBIGUOUS" if inconsistency_reason else "COMPLETE",
            inconsistency_reason=inconsistency_reason,
        ),
    )


def build_final_safe_set(
    subject_id: str,
    device: str,
    label_folder: str,
    recording_id: str,
    phase1_results: list[Phase1Result],
    phase2_results: list[Phase2Result],
) -> FinalSafeSet:
    phase2_map = {result.resolution: result for result in phase2_results}
    safe_configs: list[RenderConfig] = []

    for resolution, fps_star in phase2_queue_from_phase1(phase1_results):
        safe_configs.append(RenderConfig(resolution, fps_star, "High", "High"))
        phase2_result = phase2_map.get(resolution)
        if phase2_result is None or phase2_result.status == "AMBIGUOUS":
            continue
        for candidate in phase2_result.candidate_results:
            if candidate.status != "SAFE":
                continue
            safe_configs.append(
                RenderConfig(resolution, phase2_result.fps_star, candidate.effect, candidate.shadow)
            )

    safe_configs = sort_configs_by_power_prior(safe_configs)
    estimated_config = choose_estimated_lowest_power_safe_config(safe_configs)

    return FinalSafeSet(
        subject_id=subject_id,
        device=device,
        label_folder=label_folder,
        recording_id=recording_id,
        reference_config=REFERENCE_CONFIG,
        jnd_safe_set=safe_configs,
        estimated_lowest_power_safe_config=estimated_config,
        estimated_lowest_power_safe_config_source=(
            ESTIMATED_SAFE_CONFIG_SOURCE if estimated_config is not None else None
        ),
        generated_at=timestamp_now(),
    )


def phase1_transition_counts(phase1_results: list[Phase1Result]) -> tuple[int, int]:
    found = sum(1 for result in phase1_results if result.status == "FOUND")
    skipped = sum(1 for result in phase1_results if result.status != "FOUND")
    return found, skipped


def deterministic_presentation_order(rng_seed: int, trial_index: int) -> str:
    rng = random.Random((rng_seed << 16) ^ trial_index)
    if rng.randint(0, 1) == 0:
        return PRESENTATION_REFERENCE_FIRST
    return PRESENTATION_CANDIDATE_FIRST


def validate_phase2_result(result: Phase2Result) -> None:
    if result.status not in {"COMPLETE", "AMBIGUOUS"}:
        raise SpecError(f"Invalid Phase 2 result status '{result.status}'.")
    for candidate_result in result.candidate_results:
        if candidate_result.status not in PHASE2_STATUSES:
            raise SpecError(f"Invalid Phase 2 status '{candidate_result.status}'.")
