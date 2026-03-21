from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CandidateKey = tuple[str, int, str, str]


@dataclass(frozen=True)
class RenderConfig:
    resolution: str
    fps: int
    effect: str
    shadow: str

    def key(self) -> CandidateKey:
        return (self.resolution, self.fps, self.effect, self.shadow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution": self.resolution,
            "fps": self.fps,
            "effect": self.effect,
            "shadow": self.shadow,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RenderConfig":
        return cls(
            resolution=str(payload["resolution"]),
            fps=int(payload["fps"]),
            effect=str(payload["effect"]),
            shadow=str(payload["shadow"]),
        )


@dataclass(frozen=True)
class ExperimentUnit:
    device: str
    label_folder: str
    recording_id: str
    region: str
    scene_index: int
    route_id: int
    scene_folder: Path

    @property
    def action_type(self) -> str:
        return self.label_folder

    @property
    def scene_id(self) -> str:
        return self.recording_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "label_folder": self.label_folder,
            "recording_id": self.recording_id,
            "action_type": self.label_folder,
            "scene_id": self.recording_id,
            "region": self.region,
            "scene_index": self.scene_index,
            "route_id": self.route_id,
            "scene_folder": str(self.scene_folder),
        }


@dataclass(frozen=True)
class TrialRecord:
    trial_index: int
    subject_id: str
    device: str
    label_folder: str
    recording_id: str
    phase: str
    candidate_config: RenderConfig
    reference_config: RenderConfig
    candidate_path: Path
    reference_path: Path
    presentation_order: str
    response: str
    response_time_ms: int
    timestamp: str

    @property
    def action_type(self) -> str:
        return self.label_folder

    @property
    def scene_id(self) -> str:
        return self.recording_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_index": self.trial_index,
            "subject_id": self.subject_id,
            "device": self.device,
            "label_folder": self.label_folder,
            "recording_id": self.recording_id,
            "action_type": self.label_folder,
            "scene_id": self.recording_id,
            "phase": self.phase,
            "candidate_config": self.candidate_config.to_dict(),
            "reference_config": self.reference_config.to_dict(),
            "candidate_path": str(self.candidate_path),
            "reference_path": str(self.reference_path),
            "presentation_order": self.presentation_order,
            "response": self.response,
            "response_time_ms": self.response_time_ms,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TrialRecord":
        return cls(
            trial_index=int(payload["trial_index"]),
            subject_id=str(payload["subject_id"]),
            device=str(payload["device"]),
            label_folder=str(payload.get("label_folder", payload["action_type"])),
            recording_id=str(payload.get("recording_id", payload["scene_id"])),
            phase=str(payload["phase"]),
            candidate_config=RenderConfig.from_dict(payload["candidate_config"]),
            reference_config=RenderConfig.from_dict(payload["reference_config"]),
            candidate_path=Path(str(payload["candidate_path"])),
            reference_path=Path(str(payload["reference_path"])),
            presentation_order=str(payload["presentation_order"]),
            response=str(payload["response"]),
            response_time_ms=int(payload["response_time_ms"]),
            timestamp=str(payload["timestamp"]),
        )


@dataclass(frozen=True)
class Phase1Result:
    resolution: str
    lowest_jnd_safe_fps: int | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution": self.resolution,
            "lowest_jnd_safe_fps": self.lowest_jnd_safe_fps,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Phase1Result":
        fps = payload.get("lowest_jnd_safe_fps")
        return cls(
            resolution=str(payload["resolution"]),
            lowest_jnd_safe_fps=None if fps is None else int(fps),
            status=str(payload["status"]),
        )


@dataclass(frozen=True)
class Phase2CandidateResult:
    effect: str
    shadow: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {"effect": self.effect, "shadow": self.shadow, "status": self.status}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Phase2CandidateResult":
        return cls(
            effect=str(payload["effect"]),
            shadow=str(payload["shadow"]),
            status=str(payload["status"]),
        )


@dataclass(frozen=True)
class Phase2Result:
    resolution: str
    fps_star: int
    candidate_results: list[Phase2CandidateResult]
    status: str = "COMPLETE"
    inconsistency_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution": self.resolution,
            "fps_star": self.fps_star,
            "candidate_results": [result.to_dict() for result in self.candidate_results],
            "status": self.status,
            "inconsistency_reason": self.inconsistency_reason,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Phase2Result":
        return cls(
            resolution=str(payload["resolution"]),
            fps_star=int(payload["fps_star"]),
            candidate_results=[
                Phase2CandidateResult.from_dict(entry)
                for entry in payload.get("candidate_results", [])
            ],
            status=str(payload.get("status", "COMPLETE")),
            inconsistency_reason=payload.get("inconsistency_reason"),
        )


@dataclass(frozen=True)
class SessionMeta:
    subject_id: str
    device: str
    label_folder: str
    recording_id: str
    scene_folder: Path
    reference_config: RenderConfig
    reference_path: Path
    created_at: str
    app_spec_version: str

    @property
    def action_type(self) -> str:
        return self.label_folder

    @property
    def scene_id(self) -> str:
        return self.recording_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "device": self.device,
            "label_folder": self.label_folder,
            "recording_id": self.recording_id,
            "action_type": self.label_folder,
            "scene_id": self.recording_id,
            "scene_folder": str(self.scene_folder),
            "reference_config": self.reference_config.to_dict(),
            "reference_path": str(self.reference_path),
            "created_at": self.created_at,
            "app_spec_version": self.app_spec_version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionMeta":
        return cls(
            subject_id=str(payload["subject_id"]),
            device=str(payload["device"]),
            label_folder=str(payload.get("label_folder", payload["action_type"])),
            recording_id=str(payload.get("recording_id", payload["scene_id"])),
            scene_folder=Path(str(payload["scene_folder"])),
            reference_config=RenderConfig.from_dict(payload["reference_config"]),
            reference_path=Path(str(payload["reference_path"])),
            created_at=str(payload["created_at"]),
            app_spec_version=str(payload["app_spec_version"]),
        )


@dataclass
class SessionState:
    status: str
    current_screen: str
    current_phase: str
    current_resolution: str | None
    phase1_completed_resolutions: list[str]
    phase2_completed_resolutions: list[str]
    next_trial_index: int
    rng_seed: int
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "current_screen": self.current_screen,
            "current_phase": self.current_phase,
            "current_resolution": self.current_resolution,
            "phase1_completed_resolutions": self.phase1_completed_resolutions,
            "phase2_completed_resolutions": self.phase2_completed_resolutions,
            "next_trial_index": self.next_trial_index,
            "rng_seed": self.rng_seed,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionState":
        return cls(
            status=str(payload["status"]),
            current_screen=str(payload["current_screen"]),
            current_phase=str(payload["current_phase"]),
            current_resolution=payload.get("current_resolution"),
            phase1_completed_resolutions=[
                str(value) for value in payload.get("phase1_completed_resolutions", [])
            ],
            phase2_completed_resolutions=[
                str(value) for value in payload.get("phase2_completed_resolutions", [])
            ],
            next_trial_index=int(payload["next_trial_index"]),
            rng_seed=int(payload["rng_seed"]),
            updated_at=str(payload["updated_at"]),
        )


@dataclass(frozen=True)
class FinalSafeSet:
    subject_id: str
    device: str
    label_folder: str
    recording_id: str
    reference_config: RenderConfig
    jnd_safe_set: list[RenderConfig]
    estimated_lowest_power_safe_config: RenderConfig | None
    estimated_lowest_power_safe_config_source: str | None
    generated_at: str

    @property
    def action_type(self) -> str:
        return self.label_folder

    @property
    def scene_id(self) -> str:
        return self.recording_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "device": self.device,
            "label_folder": self.label_folder,
            "recording_id": self.recording_id,
            "action_type": self.label_folder,
            "scene_id": self.recording_id,
            "reference_config": self.reference_config.to_dict(),
            "jnd_safe_set": [config.to_dict() for config in self.jnd_safe_set],
            "estimated_lowest_power_safe_config": (
                None
                if self.estimated_lowest_power_safe_config is None
                else self.estimated_lowest_power_safe_config.to_dict()
            ),
            "estimated_lowest_power_safe_config_source": self.estimated_lowest_power_safe_config_source,
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class SceneScanResult:
    experiment_unit: ExperimentUnit
    candidate_map: dict[CandidateKey, Path]
    reference_path: Path
    candidate_power_prior_manifest: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


@dataclass
class SessionBundle:
    session_dir: Path
    meta: SessionMeta
    state: SessionState
    raw_trials: list[TrialRecord]
    phase1_results: list[Phase1Result]
    phase2_results: list[Phase2Result]


@dataclass(frozen=True)
class Phase1Decision:
    kind: str
    config: RenderConfig | None = None
    result: Phase1Result | None = None


@dataclass(frozen=True)
class Phase2Decision:
    kind: str
    config: RenderConfig | None = None
    result: Phase2Result | None = None


@dataclass(frozen=True)
class ScheduledTrial:
    phase: str
    resolution: str
    candidate_config: RenderConfig
    candidate_path: Path
    reference_path: Path
    presentation_order: str
    formal_trial_index: int | None
    progress_label: str
