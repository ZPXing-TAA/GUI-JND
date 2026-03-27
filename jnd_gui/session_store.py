from __future__ import annotations

import json
import os
from pathlib import Path

from jnd_gui.constants import (
    APP_SPEC_VERSION,
    ERROR,
    FINISHED,
    PHASE1,
    PHASE1_STATUSES,
    PHASE2,
    PHASE2_STATUSES,
    REFERENCE_CONFIG,
    RESOLUTION_ORDER,
    RESULTS_DIR_NAME,
    RUNNING,
    VALID_PRESENTATION_ORDERS,
    VALID_RESPONSES,
)
from jnd_gui.errors import SpecError
from jnd_gui.models import (
    ExperimentUnit,
    FinalSafeSet,
    Phase1Result,
    Phase2Result,
    SceneScanResult,
    SessionBundle,
    SessionMeta,
    SessionState,
    TrialRecord,
)
from jnd_gui.utils import atomic_write_json, read_json_file, timestamp_now


class SessionStore:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or (Path.cwd() / RESULTS_DIR_NAME)).resolve()

    def session_dir_for(self, subject_id: str, unit: ExperimentUnit) -> Path:
        return (
            self.root_dir
            / subject_id
            / unit.device
            / unit.action_type
            / unit.scene_folder_name
        ).resolve()

    def subject_training_state_path(self, subject_id: str) -> Path:
        return (self.root_dir / subject_id / "subject_training_state.json").resolve()

    def create_new_session(self, subject_id: str, scan_result: SceneScanResult, rng_seed: int) -> SessionBundle:
        session_dir = self.session_dir_for(subject_id, scan_result.experiment_unit)
        if session_dir.exists():
            raise SpecError(
                f"Session directory already exists: {session_dir}. Version 1 does not overwrite existing sessions in the GUI."
            )

        session_dir.mkdir(parents=True, exist_ok=False)
        created_at = timestamp_now()
        meta = SessionMeta(
            subject_id=subject_id,
            device=scan_result.experiment_unit.device,
            action_type=scan_result.experiment_unit.action_type,
            country=scan_result.experiment_unit.country,
            route_suffix=scan_result.experiment_unit.route_suffix,
            occurrence=scan_result.experiment_unit.occurrence,
            scene_folder_name=scan_result.experiment_unit.scene_folder_name,
            scene_folder=scan_result.experiment_unit.scene_folder,
            reference_config=REFERENCE_CONFIG,
            reference_path=scan_result.reference_path,
            created_at=created_at,
            app_spec_version=APP_SPEC_VERSION,
        )
        state = SessionState(
            status=RUNNING,
            current_screen="training_intro",
            current_phase="training",
            current_resolution=None,
            phase1_completed_resolutions=[],
            phase2_completed_resolutions=[],
            next_trial_index=1,
            rng_seed=rng_seed,
            updated_at=created_at,
        )
        self.write_session_meta(session_dir, meta)
        self.write_session_state(session_dir, state)
        self.write_candidate_power_prior_manifest(
            session_dir,
            scan_result.candidate_power_prior_manifest,
        )
        self.raw_trials_path(session_dir).touch()
        self.write_phase1_results(session_dir, [])
        self.write_phase2_results(session_dir, [])
        return SessionBundle(
            session_dir=session_dir,
            meta=meta,
            state=state,
            raw_trials=[],
            phase1_results=[],
            phase2_results=[],
        )

    def load_session(self, subject_id: str, unit: ExperimentUnit) -> SessionBundle | None:
        session_dir = self.session_dir_for(subject_id, unit)
        if not session_dir.exists():
            return None

        meta_path = self.session_meta_path(session_dir)
        state_path = self.session_state_path(session_dir)
        manifest_path = self.candidate_power_prior_manifest_path(session_dir)
        if not meta_path.exists() or not state_path.exists() or not manifest_path.exists():
            raise SpecError(
                f"Session directory is corrupted: missing session meta, session state, or candidate power prior manifest in {session_dir}."
            )
        manifest_payload = read_json_file(manifest_path)
        if not isinstance(manifest_payload, dict):
            raise SpecError(
                "candidate_power_prior_manifest.json is corrupted: expected a JSON object."
            )

        meta = SessionMeta.from_dict(read_json_file(meta_path))
        state = SessionState.from_dict(read_json_file(state_path))
        raw_trials = self._load_raw_trials(session_dir)
        phase1_results = self._load_phase1_results(session_dir)
        phase2_results = self._load_phase2_results(session_dir)

        bundle = SessionBundle(
            session_dir=session_dir,
            meta=meta,
            state=state,
            raw_trials=raw_trials,
            phase1_results=phase1_results,
            phase2_results=phase2_results,
        )
        self._validate_bundle(bundle)
        return bundle

    def write_session_meta(self, session_dir: Path, meta: SessionMeta) -> None:
        atomic_write_json(self.session_meta_path(session_dir), meta.to_dict())

    def write_session_state(self, session_dir: Path, state: SessionState) -> None:
        state.updated_at = timestamp_now()
        atomic_write_json(self.session_state_path(session_dir), state.to_dict())

    def append_raw_trial(self, session_dir: Path, trial_record: TrialRecord) -> None:
        path = self.raw_trials_path(session_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trial_record.to_dict(), ensure_ascii=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def write_phase1_results(self, session_dir: Path, results: list[Phase1Result]) -> None:
        atomic_write_json(
            self.phase1_result_path(session_dir),
            [result.to_dict() for result in results],
        )

    def write_phase2_results(self, session_dir: Path, results: list[Phase2Result]) -> None:
        atomic_write_json(
            self.phase2_result_path(session_dir),
            [result.to_dict() for result in results],
        )

    def write_final_safe_set(self, session_dir: Path, safe_set: FinalSafeSet) -> None:
        atomic_write_json(self.final_safe_set_path(session_dir), safe_set.to_dict())

    def write_candidate_power_prior_manifest(self, session_dir: Path, manifest: dict[str, object]) -> None:
        atomic_write_json(self.candidate_power_prior_manifest_path(session_dir), manifest)

    def load_candidate_power_prior_manifest(self, session_dir: Path) -> dict[str, object]:
        path = self.candidate_power_prior_manifest_path(session_dir)
        payload = read_json_file(path)
        if not isinstance(payload, dict):
            raise SpecError("candidate_power_prior_manifest.json is corrupted: expected a JSON object.")
        return payload

    def write_candidate_subjective_label_manifest(self, session_dir: Path, manifest: dict[str, object]) -> None:
        atomic_write_json(self.candidate_subjective_label_manifest_path(session_dir), manifest)

    def has_subject_completed_training(self, subject_id: str) -> bool:
        path = self.subject_training_state_path(subject_id)
        if not path.exists():
            return False
        payload = read_json_file(path)
        if not isinstance(payload, dict):
            raise SpecError("subject_training_state.json is corrupted: expected a JSON object.")
        if str(payload.get("subject_id", "")) != subject_id:
            raise SpecError("subject_training_state.json is corrupted: subject_id does not match the requested subject.")
        training_completed = payload.get("training_completed")
        if not isinstance(training_completed, bool):
            raise SpecError("subject_training_state.json is corrupted: training_completed must be a boolean.")
        completed_at = payload.get("completed_at")
        if training_completed and not isinstance(completed_at, str):
            raise SpecError("subject_training_state.json is corrupted: completed_at must be a string when training is completed.")
        source_session_dir = payload.get("source_session_dir")
        if training_completed and not isinstance(source_session_dir, str):
            raise SpecError(
                "subject_training_state.json is corrupted: source_session_dir must be a string when training is completed."
            )
        return training_completed

    def mark_subject_training_completed(self, subject_id: str, session_dir: Path) -> None:
        payload = {
            "subject_id": subject_id,
            "training_completed": True,
            "completed_at": timestamp_now(),
            "source_session_dir": str(session_dir.resolve()),
        }
        atomic_write_json(self.subject_training_state_path(subject_id), payload)

    def mark_session_finished(self, bundle: SessionBundle) -> None:
        bundle.state.status = FINISHED
        bundle.state.current_screen = "completion"
        bundle.state.current_phase = PHASE2
        bundle.state.current_resolution = None
        self.write_session_state(bundle.session_dir, bundle.state)

    def mark_session_error(self, bundle: SessionBundle | None) -> None:
        if bundle is None:
            return
        bundle.state.status = ERROR
        bundle.state.current_screen = "error"
        self.write_session_state(bundle.session_dir, bundle.state)

    @staticmethod
    def session_meta_path(session_dir: Path) -> Path:
        return session_dir / "session_meta.json"

    @staticmethod
    def session_state_path(session_dir: Path) -> Path:
        return session_dir / "session_state.json"

    @staticmethod
    def raw_trials_path(session_dir: Path) -> Path:
        return session_dir / "raw_trials.jsonl"

    @staticmethod
    def phase1_result_path(session_dir: Path) -> Path:
        return session_dir / "phase1_result.json"

    @staticmethod
    def phase2_result_path(session_dir: Path) -> Path:
        return session_dir / "phase2_result.json"

    @staticmethod
    def final_safe_set_path(session_dir: Path) -> Path:
        return session_dir / "final_jnd_safe_set.json"

    @staticmethod
    def candidate_power_prior_manifest_path(session_dir: Path) -> Path:
        return session_dir / "candidate_power_prior_manifest.json"

    @staticmethod
    def candidate_subjective_label_manifest_path(session_dir: Path) -> Path:
        return session_dir / "candidate_subjective_label_manifest.json"

    def _load_raw_trials(self, session_dir: Path) -> list[TrialRecord]:
        path = self.raw_trials_path(session_dir)
        if not path.exists():
            return []
        raw_trials: list[TrialRecord] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise SpecError(
                        f"Session raw trial log is corrupted at line {line_number}: {exc.msg}."
                    ) from exc
                raw_trials.append(TrialRecord.from_dict(payload))
        return raw_trials

    def _load_phase1_results(self, session_dir: Path) -> list[Phase1Result]:
        path = self.phase1_result_path(session_dir)
        if not path.exists():
            return []
        payload = read_json_file(path)
        if not isinstance(payload, list):
            raise SpecError("phase1_result.json is corrupted: expected a JSON array.")
        return [Phase1Result.from_dict(entry) for entry in payload]

    def _load_phase2_results(self, session_dir: Path) -> list[Phase2Result]:
        path = self.phase2_result_path(session_dir)
        if not path.exists():
            return []
        payload = read_json_file(path)
        if not isinstance(payload, list):
            raise SpecError("phase2_result.json is corrupted: expected a JSON array.")
        return [Phase2Result.from_dict(entry) for entry in payload]

    def _validate_bundle(self, bundle: SessionBundle) -> None:
        if bundle.meta.app_spec_version not in {APP_SPEC_VERSION, "1.1"}:
            raise SpecError(
                f"Unsupported app_spec_version '{bundle.meta.app_spec_version}' in session_meta.json."
            )
        if bundle.meta.reference_config != REFERENCE_CONFIG:
            raise SpecError("session_meta.json reference_config does not match the fixed spec reference.")
        if bundle.state.status not in {RUNNING, FINISHED, ERROR}:
            raise SpecError(f"Invalid session status '{bundle.state.status}' in session_state.json.")

        if bundle.state.next_trial_index < 1:
            raise SpecError("session_state.json has invalid next_trial_index; expected a positive integer.")

        for expected_index, trial in enumerate(bundle.raw_trials, start=1):
            if trial.trial_index != expected_index:
                raise SpecError(
                    "raw_trials.jsonl is corrupted: trial_index must be global, sequential, and start at 1."
                )
            if trial.presentation_order not in VALID_PRESENTATION_ORDERS:
                raise SpecError(f"Invalid presentation_order '{trial.presentation_order}' in raw trial log.")
            if trial.response not in VALID_RESPONSES:
                raise SpecError(f"Invalid response '{trial.response}' in raw trial log.")
            if trial.phase not in {PHASE1, PHASE2}:
                raise SpecError(f"Invalid phase '{trial.phase}' in raw trial log.")
            if trial.reference_config != REFERENCE_CONFIG:
                raise SpecError("raw_trials.jsonl contains a reference_config that does not match the fixed spec.")
            if (
                trial.subject_id != bundle.meta.subject_id
                or trial.device != bundle.meta.device
                or trial.action_type != bundle.meta.action_type
                or trial.country != bundle.meta.country
                or trial.route_suffix != bundle.meta.route_suffix
                or trial.occurrence != bundle.meta.occurrence
                or trial.scene_folder_name != bundle.meta.scene_folder_name
            ):
                raise SpecError("raw_trials.jsonl does not match session_meta.json.")

        seen_phase1: set[str] = set()
        for result in bundle.phase1_results:
            if result.resolution in seen_phase1:
                raise SpecError(f"Duplicate resolution '{result.resolution}' in phase1_result.json.")
            seen_phase1.add(result.resolution)
            if result.status not in PHASE1_STATUSES:
                raise SpecError(f"Invalid Phase 1 status '{result.status}'.")
            if result.status == "FOUND" and result.lowest_jnd_safe_fps is None:
                raise SpecError(
                    f"Phase 1 result for resolution '{result.resolution}' is FOUND but missing lowest_jnd_safe_fps."
                )
            if result.status != "FOUND" and result.lowest_jnd_safe_fps is not None:
                raise SpecError(
                    f"Phase 1 result for resolution '{result.resolution}' must use null fps unless status is FOUND."
                )
        phase1_order = [result.resolution for result in bundle.phase1_results]
        expected_phase1_order = [resolution for resolution in RESOLUTION_ORDER if resolution in phase1_order]
        if phase1_order != expected_phase1_order:
            raise SpecError("phase1_result.json is corrupted: resolutions must follow the fixed Phase 1 order.")

        seen_phase2: set[str] = set()
        found_resolutions = {
            result.resolution for result in bundle.phase1_results if result.status == "FOUND"
        }
        for result in bundle.phase2_results:
            if result.resolution in seen_phase2:
                raise SpecError(f"Duplicate resolution '{result.resolution}' in phase2_result.json.")
            seen_phase2.add(result.resolution)
            if result.resolution not in found_resolutions:
                raise SpecError(
                    f"Phase 2 result for resolution '{result.resolution}' has no Phase 1 FOUND entry."
                )
            for candidate_result in result.candidate_results:
                if candidate_result.status not in PHASE2_STATUSES:
                    raise SpecError(f"Invalid Phase 2 candidate status '{candidate_result.status}'.")
        phase2_order = [result.resolution for result in bundle.phase2_results]
        expected_phase2_order = [resolution for resolution in RESOLUTION_ORDER if resolution in phase2_order]
        if phase2_order != expected_phase2_order:
            raise SpecError("phase2_result.json is corrupted: resolutions must follow the fixed resolution order.")

    def reconcile_state(self, bundle: SessionBundle) -> bool:
        expected_next_trial_index = len(bundle.raw_trials) + 1
        phase1_completed = [result.resolution for result in bundle.phase1_results]
        phase2_completed = [result.resolution for result in bundle.phase2_results]

        changed = False
        if bundle.state.next_trial_index != expected_next_trial_index:
            bundle.state.next_trial_index = expected_next_trial_index
            changed = True
        if bundle.state.phase1_completed_resolutions != phase1_completed:
            bundle.state.phase1_completed_resolutions = phase1_completed
            changed = True
        if bundle.state.phase2_completed_resolutions != phase2_completed:
            bundle.state.phase2_completed_resolutions = phase2_completed
            changed = True
        return changed
