from __future__ import annotations

from pathlib import Path
from typing import Any

from jnd_gui.constants import (
    EFFECT_VALUES,
    FPS_VALUES,
    POWER_LABEL_SOURCE,
    POWER_LABEL_TYPE,
    RESOLUTION_PRIOR_ORDER,
    SHADOW_VALUES,
)
from jnd_gui.models import ExperimentUnit, RenderConfig


FPS_PRIOR_RANK = {fps: index for index, fps in enumerate(FPS_VALUES)}
RESOLUTION_PRIOR_RANK = {
    resolution: index for index, resolution in enumerate(RESOLUTION_PRIOR_ORDER)
}
EFFECT_PRIOR_RANK = {effect: index for index, effect in enumerate(EFFECT_VALUES)}
SHADOW_PRIOR_RANK = {shadow: index for index, shadow in enumerate(SHADOW_VALUES)}


def power_prior_tuple(config: RenderConfig) -> dict[str, int]:
    return {
        "fps_rank": FPS_PRIOR_RANK[config.fps],
        "resolution_rank": RESOLUTION_PRIOR_RANK[config.resolution],
        "effect_rank": EFFECT_PRIOR_RANK[config.effect],
        "shadow_rank": SHADOW_PRIOR_RANK[config.shadow],
    }


def power_prior_order_key(config: RenderConfig) -> list[int]:
    ranks = power_prior_tuple(config)
    return [
        ranks["fps_rank"],
        ranks["resolution_rank"],
        ranks["effect_rank"],
        ranks["shadow_rank"],
    ]


def power_prior_sort_key(config: RenderConfig) -> tuple[int, int, int, int]:
    order_key = power_prior_order_key(config)
    return (order_key[0], order_key[1], order_key[2], order_key[3])


def power_prior_payload(config: RenderConfig) -> dict[str, Any]:
    return {
        "render_config": config.to_dict(),
        "power_prior_tuple": power_prior_tuple(config),
        "power_prior_order_key": power_prior_order_key(config),
        "power_label_type": POWER_LABEL_TYPE,
        "power_label_source": POWER_LABEL_SOURCE,
    }


def sort_configs_by_power_prior(configs: list[RenderConfig]) -> list[RenderConfig]:
    return sorted(configs, key=power_prior_sort_key)


def choose_estimated_lowest_power_safe_config(
    configs: list[RenderConfig],
) -> RenderConfig | None:
    if not configs:
        return None
    return min(configs, key=power_prior_sort_key)


def build_candidate_power_prior_manifest(
    unit: ExperimentUnit,
    candidate_map: dict[tuple[str, int, str, str], Path],
    reference_config: RenderConfig,
) -> dict[str, Any]:
    sorted_candidates = sorted(
        candidate_map.items(),
        key=lambda item: (power_prior_sort_key(RenderConfig(*item[0])), str(item[1])),
    )
    candidates = []
    for candidate_key, video_path in sorted_candidates:
        config = RenderConfig(*candidate_key)
        entry = power_prior_payload(config)
        entry["video_path"] = str(video_path)
        entry["subjective_status"] = "unknown"
        candidates.append(entry)

    return {
        "device": unit.device,
        "label_folder": unit.label_folder,
        "recording_id": unit.recording_id,
        "action_type": unit.label_folder,
        "scene_id": unit.recording_id,
        "reference_config": power_prior_payload(reference_config)["render_config"],
        "candidates": candidates,
    }
