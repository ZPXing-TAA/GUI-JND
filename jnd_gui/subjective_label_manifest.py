from __future__ import annotations

from collections import defaultdict
from typing import Any

from jnd_gui.constants import (
    EFFECT_VALUES,
    FPS_VALUES,
    PHASE1,
    PHASE2,
    REFERENCE_CONFIG,
    RESPONSE_DIFFERENT,
    RESPONSE_SAME,
    RESOLUTION_PRIOR_ORDER,
    SHADOW_VALUES,
)
from jnd_gui.errors import SpecError
from jnd_gui.models import CandidateKey, RenderConfig, SessionMeta, TrialRecord


_FORMAL_PHASES = {PHASE1, PHASE2}
_PRESERVED_CANDIDATE_FIELDS = (
    "power_prior_tuple",
    "power_prior_order_key",
    "power_label_type",
    "power_label_source",
)

_FPS_RANK = {fps: index for index, fps in enumerate(FPS_VALUES)}
_RESOLUTION_RANK = {
    resolution: index for index, resolution in enumerate(RESOLUTION_PRIOR_ORDER)
}
_EFFECT_RANK = {effect: index for index, effect in enumerate(EFFECT_VALUES)}
_SHADOW_RANK = {shadow: index for index, shadow in enumerate(SHADOW_VALUES)}


def build_candidate_subjective_label_manifest(
    meta: SessionMeta,
    raw_trials: list[TrialRecord],
    candidate_power_prior_manifest: dict[str, Any],
) -> dict[str, Any]:
    candidate_entries = _validate_candidate_power_prior_manifest(meta, candidate_power_prior_manifest)
    candidate_configs = [RenderConfig.from_dict(entry["render_config"]) for entry in candidate_entries]
    candidate_keys = {config.key() for config in candidate_configs}

    formal_trials = [trial for trial in raw_trials if trial.phase in _FORMAL_PHASES]
    for trial in formal_trials:
        if trial.candidate_config.key() not in candidate_keys:
            raise SpecError(
                "raw_trials.jsonl contains a candidate_config that is missing from candidate_power_prior_manifest.json."
            )

    observed_map = _build_observed_map(formal_trials)
    observed_safe = [entry for entry in observed_map.values() if entry["label"] == "safe"]
    observed_not_safe = [entry for entry in observed_map.values() if entry["label"] == "not_safe"]

    resolved_candidates: list[dict[str, Any]] = []
    for entry in candidate_entries:
        config = RenderConfig.from_dict(entry["render_config"])
        key = config.key()
        resolved_entry = {
            "subject_id": meta.subject_id,
            "video_path": str(entry["video_path"]),
            "render_config": config.to_dict(),
            "observed_trial_indices": [],
            "observed_responses": [],
            "safe_supporters": [],
            "not_safe_supporters": [],
        }
        for field in _PRESERVED_CANDIDATE_FIELDS:
            if field in entry:
                resolved_entry[field] = entry[field]

        observed = observed_map.get(key)
        if observed is not None:
            resolved_entry["subjective_label"] = observed["label"]
            resolved_entry["label_source"] = "observed"
            resolved_entry["observed_trial_indices"] = observed["trial_indices"]
            resolved_entry["observed_responses"] = observed["responses"]
            if observed["label"] == "ambiguous":
                resolved_entry["notes"] = "Observed responses conflict; marked ambiguous."
            resolved_candidates.append(resolved_entry)
            continue

        safe_supporters = [
            supporter["config"]
            for supporter in observed_safe
            if _dominates(config, supporter["config"])
        ]
        not_safe_supporters = [
            supporter["config"]
            for supporter in observed_not_safe
            if _dominates(supporter["config"], config)
        ]
        resolved_entry["safe_supporters"] = [
            supporter.to_dict() for supporter in _sort_configs(safe_supporters)
        ]
        resolved_entry["not_safe_supporters"] = [
            supporter.to_dict() for supporter in _sort_configs(not_safe_supporters)
        ]

        if safe_supporters and not_safe_supporters:
            resolved_entry["subjective_label"] = "ambiguous"
            resolved_entry["label_source"] = "inferred_monotonic"
            resolved_entry["notes"] = "Monotonic closure produced both safe and not-safe supporters."
        elif safe_supporters:
            resolved_entry["subjective_label"] = "safe"
            resolved_entry["label_source"] = "inferred_monotonic"
        elif not_safe_supporters:
            resolved_entry["subjective_label"] = "not_safe"
            resolved_entry["label_source"] = "inferred_monotonic"
        else:
            resolved_entry["subjective_label"] = "unknown"
            resolved_entry["label_source"] = "unresolved"

        resolved_candidates.append(resolved_entry)

    return {
        "subject_id": meta.subject_id,
        "device": meta.device,
        "action_type": meta.action_type,
        "country": meta.country,
        "route_suffix": meta.route_suffix,
        "occurrence": meta.occurrence,
        "scene_folder_name": meta.scene_folder_name,
        "reference_config": meta.reference_config.to_dict(),
        "candidates": resolved_candidates,
    }


def _validate_candidate_power_prior_manifest(
    meta: SessionMeta,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict):
        raise SpecError("candidate_power_prior_manifest.json is corrupted: expected a JSON object.")
    expected_fields = {
        "device": meta.device,
        "action_type": meta.action_type,
        "country": meta.country,
        "route_suffix": meta.route_suffix,
        "occurrence": meta.occurrence,
        "scene_folder_name": meta.scene_folder_name,
    }
    for field, expected in expected_fields.items():
        if manifest.get(field) != expected:
            raise SpecError(
                f"candidate_power_prior_manifest.json does not match session_meta.json for field '{field}'."
            )
    if manifest.get("reference_config") != REFERENCE_CONFIG.to_dict():
        raise SpecError(
            "candidate_power_prior_manifest.json reference_config does not match the fixed reference config."
        )
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list):
        raise SpecError("candidate_power_prior_manifest.json is corrupted: candidates must be a JSON array.")

    seen_keys: set[CandidateKey] = set()
    seen_paths: set[str] = set()
    validated_entries: list[dict[str, Any]] = []
    for index, entry in enumerate(candidates, start=1):
        if not isinstance(entry, dict):
            raise SpecError(
                f"candidate_power_prior_manifest.json is corrupted: candidate entry {index} must be a JSON object."
            )
        if "video_path" not in entry or "render_config" not in entry:
            raise SpecError(
                f"candidate_power_prior_manifest.json is corrupted: candidate entry {index} is missing video_path or render_config."
            )
        config = RenderConfig.from_dict(entry["render_config"])
        video_path = str(entry["video_path"])
        if config.key() in seen_keys:
            raise SpecError(
                "candidate_power_prior_manifest.json is corrupted: duplicate render_config found in candidates."
            )
        if video_path in seen_paths:
            raise SpecError(
                "candidate_power_prior_manifest.json is corrupted: duplicate video_path found in candidates."
            )
        seen_keys.add(config.key())
        seen_paths.add(video_path)
        validated_entries.append(entry)
    return validated_entries


def _build_observed_map(
    formal_trials: list[TrialRecord],
) -> dict[CandidateKey, dict[str, Any]]:
    grouped_trials: dict[CandidateKey, list[TrialRecord]] = defaultdict(list)
    for trial in formal_trials:
        grouped_trials[trial.candidate_config.key()].append(trial)

    observed_map: dict[CandidateKey, dict[str, Any]] = {}
    for key, trials in grouped_trials.items():
        sorted_trials = sorted(trials, key=lambda item: item.trial_index)
        responses = [trial.response for trial in sorted_trials]
        if all(response == RESPONSE_SAME for response in responses):
            label = "safe"
        elif all(response == RESPONSE_DIFFERENT for response in responses):
            label = "not_safe"
        else:
            label = "ambiguous"
        observed_map[key] = {
            "label": label,
            "config": sorted_trials[0].candidate_config,
            "trial_indices": [trial.trial_index for trial in sorted_trials],
            "responses": responses,
        }
    return observed_map


def _dominates(left: RenderConfig, right: RenderConfig) -> bool:
    return (
        _FPS_RANK[left.fps] >= _FPS_RANK[right.fps]
        and _RESOLUTION_RANK[left.resolution] >= _RESOLUTION_RANK[right.resolution]
        and _EFFECT_RANK[left.effect] >= _EFFECT_RANK[right.effect]
        and _SHADOW_RANK[left.shadow] >= _SHADOW_RANK[right.shadow]
    )


def _quality_sort_key(config: RenderConfig) -> tuple[int, int, int, int]:
    return (
        _FPS_RANK[config.fps],
        _RESOLUTION_RANK[config.resolution],
        _EFFECT_RANK[config.effect],
        _SHADOW_RANK[config.shadow],
    )


def _sort_configs(configs: list[RenderConfig]) -> list[RenderConfig]:
    return sorted(configs, key=_quality_sort_key)
