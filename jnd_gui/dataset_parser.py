from __future__ import annotations

import re
from pathlib import Path

from jnd_gui.constants import EFFECT_VALUES, FPS_VALUES, REFERENCE_CONFIG, RESOLUTION_ORDER, SHADOW_VALUES
from jnd_gui.errors import SpecError
from jnd_gui.models import ExperimentUnit, RenderConfig, SceneScanResult
from jnd_gui.power_prior import build_candidate_power_prior_manifest


CURRENT_SCENE_PATTERN = re.compile(
    r"^(?P<country>[a-z]+)_r(?P<route_suffix>\d{2})_(?P<label>[a-z_]+)(?P<occurrence>\d{2})$"
)


def parse_scene_folder_name(scene_folder_name: str, action_type: str) -> tuple[str, int, int]:
    current_match = CURRENT_SCENE_PATTERN.fullmatch(scene_folder_name)
    if current_match is None:
        raise SpecError(
            "Unsupported scene folder format "
            f"'{scene_folder_name}'. Expected migrated final format <country>_rRR_<label>NN only."
        )

    parsed_label = current_match.group("label")
    if parsed_label != action_type:
        raise SpecError(
            "Invalid scene folder: parent action_type does not match the label encoded in the scene folder name "
            f"('{action_type}' != '{parsed_label}')."
        )

    return (
        current_match.group("country"),
        int(current_match.group("route_suffix")),
        int(current_match.group("occurrence")),
    )


def parse_experiment_unit(scene_folder: str | Path) -> ExperimentUnit:
    folder = Path(scene_folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        raise SpecError(f"Scene folder does not exist or is not a directory: {folder}")

    if len(folder.parts) < 3:
        raise SpecError(
            f"Invalid scene folder: {folder}. Expected a path ending in {{device}}/{{action_type}}/{{scene_folder_name}}."
        )

    device, action_type, scene_folder_name = folder.parts[-3:]
    country, route_suffix, occurrence = parse_scene_folder_name(scene_folder_name, action_type)
    return ExperimentUnit(
        device=device,
        action_type=action_type,
        country=country,
        route_suffix=route_suffix,
        occurrence=occurrence,
        scene_folder_name=scene_folder_name,
        scene_folder=folder,
    )


def _invalid_filename_warning(file_name: str, reason: str) -> str:
    return f"Skipped invalid candidate filename '{file_name}': {reason}."


def parse_render_config_from_filename(file_name: str) -> tuple[RenderConfig | None, str | None]:
    path = Path(file_name)
    if path.suffix.lower() != ".mp4":
        return None, None

    stem_parts = path.stem.split("_")
    if len(stem_parts) == 4:
        resolution_token, fps_token, effect_token, shadow_token = stem_parts
    elif len(stem_parts) == 5:
        resolution_token, redundant_token, fps_token, effect_token, shadow_token = stem_parts
        if redundant_token != resolution_token:
            return None, _invalid_filename_warning(
                file_name,
                f"legacy redundant token '{redundant_token}' does not match resolution '{resolution_token}'",
            )
    else:
        return None, _invalid_filename_warning(
            file_name,
            f"expected 4 or 5 underscore-separated tokens, got {len(stem_parts)}",
        )

    if resolution_token not in RESOLUTION_ORDER:
        return None, _invalid_filename_warning(file_name, f"unsupported resolution '{resolution_token}'")
    try:
        fps_value = int(fps_token)
    except ValueError:
        return None, _invalid_filename_warning(file_name, f"invalid fps '{fps_token}'")
    if fps_value not in FPS_VALUES:
        return None, _invalid_filename_warning(file_name, f"unsupported fps '{fps_value}'")
    if effect_token not in EFFECT_VALUES:
        return None, _invalid_filename_warning(file_name, f"unsupported effect '{effect_token}'")
    if shadow_token not in SHADOW_VALUES:
        return None, _invalid_filename_warning(file_name, f"unsupported shadow '{shadow_token}'")

    return RenderConfig(resolution_token, fps_value, effect_token, shadow_token), None


def scan_scene_folder(scene_folder: str | Path) -> SceneScanResult:
    experiment_unit = parse_experiment_unit(scene_folder)
    candidate_map: dict[tuple[str, int, str, str], Path] = {}
    warnings: list[str] = []

    for entry in sorted(experiment_unit.scene_folder.iterdir(), key=lambda item: item.name):
        if not entry.is_file() or entry.suffix.lower() != ".mp4":
            continue
        config, warning = parse_render_config_from_filename(entry.name)
        if warning:
            warnings.append(warning)
            continue
        if config is None:
            continue
        key = config.key()
        resolved_path = entry.resolve()
        if key in candidate_map and candidate_map[key] != resolved_path:
            raise SpecError(
                "Unable to continue safely because multiple files map to the same canonical render config: "
                f"{candidate_map[key]} and {resolved_path}."
            )
        candidate_map[key] = resolved_path

    reference_path = candidate_map.get(REFERENCE_CONFIG.key())
    if reference_path is None:
        raise SpecError(
            "Reference video missing. Expected config (VeryHigh, 60, High, High) in canonical or legacy filename format."
        )

    return SceneScanResult(
        experiment_unit=experiment_unit,
        candidate_map=candidate_map,
        reference_path=reference_path,
        candidate_power_prior_manifest=build_candidate_power_prior_manifest(
            experiment_unit,
            candidate_map,
            REFERENCE_CONFIG,
        ),
        warnings=warnings,
    )
