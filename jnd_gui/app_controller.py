from __future__ import annotations

import random
from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from jnd_gui.constants import PHASE1, PHASE2, REFERENCE_CONFIG, RESOLUTION_ORDER, RUNNING, TRAINING
from jnd_gui.dataset_parser import scan_scene_folder
from jnd_gui.errors import SpecError
from jnd_gui.models import Phase1Result, ScheduledTrial, SceneScanResult, SessionBundle, TrialRecord
from jnd_gui.scheduler import (
    build_final_safe_set,
    deterministic_presentation_order,
    evaluate_phase1_history,
    evaluate_phase2_progress,
    format_render_config,
    phase1_transition_counts,
    phase1_trials_for_resolution,
    phase2_queue_from_phase1,
    phase2_result_has_prior_contradiction,
    phase2_trials_for_resolution,
    select_training_configs,
)
from jnd_gui.screens import MessageScreen, ResumeScreen, StartScreen, TrialScreen
from jnd_gui.session_store import SessionStore
from jnd_gui.subjective_label_manifest import build_candidate_subjective_label_manifest
from jnd_gui.utils import timestamp_now


class JNDExperimentWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JND Subjective Experiment GUI")
        self.resize(1200, 860)

        self.store = SessionStore()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.start_screen = StartScreen()
        self.resume_screen = ResumeScreen()
        self.message_screen = MessageScreen()
        self.trial_screen = TrialScreen()

        self.stack.addWidget(self.start_screen)
        self.stack.addWidget(self.resume_screen)
        self.stack.addWidget(self.message_screen)
        self.stack.addWidget(self.trial_screen)

        self.start_screen.start_requested.connect(self._handle_start_requested)
        self.resume_screen.resume_requested.connect(self._resume_existing_session)
        self.resume_screen.cancel_requested.connect(self._cancel_resume)
        self.message_screen.primary_clicked.connect(self._handle_message_primary)
        self.message_screen.secondary_clicked.connect(self._handle_message_secondary)
        self.trial_screen.response_submitted.connect(self._handle_trial_response)
        self.trial_screen.next_trial_requested.connect(self._handle_next_trial_requested)
        self.trial_screen.playback_error.connect(self._handle_playback_error)

        self._pending_primary_action = None
        self._pending_secondary_action = None
        self._scan_result: SceneScanResult | None = None
        self._bundle: SessionBundle | None = None
        self._training_configs = []
        self._training_index = 0
        self._active_trial: ScheduledTrial | None = None
        self._resume_subject_id = ""
        self._resume_scene_folder = ""
        self._phase2_transition_acknowledged = False

        self.stack.setCurrentWidget(self.start_screen)

    def _handle_start_requested(self, subject_id: str, scene_folder: str) -> None:
        subject_id = subject_id.strip()
        scene_folder = scene_folder.strip()
        self._resume_subject_id = subject_id
        self._resume_scene_folder = scene_folder
        self.start_screen.show_validation([], [], None)

        if not subject_id:
            self.start_screen.show_validation(error_message="Subject ID must be non-empty.")
            return
        if not scene_folder:
            self.start_screen.show_validation(error_message="Scene folder must be selected.")
            return

        try:
            self._scan_result = scan_scene_folder(scene_folder)
            info_lines = [
                f"Device: {self._scan_result.experiment_unit.device}",
                f"Action Type: {self._scan_result.experiment_unit.action_type}",
                f"Country: {self._scan_result.experiment_unit.country}",
                f"Route Suffix: {self._scan_result.experiment_unit.route_suffix}",
                f"Occurrence: {self._scan_result.experiment_unit.occurrence}",
                f"Scene Folder Name: {self._scan_result.experiment_unit.scene_folder_name}",
                f"Valid candidate videos found: {len(self._scan_result.candidate_map)}",
            ]
            self.start_screen.show_validation(
                info_lines=info_lines,
                warnings=self._scan_result.warnings,
                error_message=None,
            )
            self._phase2_transition_acknowledged = False

            existing_bundle = self.store.load_session(subject_id, self._scan_result.experiment_unit)
            if existing_bundle is not None:
                if existing_bundle.state.status != RUNNING:
                    raise SpecError(
                        "A session directory already exists for this subject and recording with terminal status "
                        f"{existing_bundle.state.status}. Version 1 will not overwrite it in the GUI."
                    )
                if existing_bundle.meta.scene_folder.resolve() != self._scan_result.experiment_unit.scene_folder.resolve():
                    raise SpecError(
                        "The selected scene folder does not match the original session folder. Refusing to guess which dataset to resume."
                    )
                self._bundle = existing_bundle
                self._show_resume_screen()
                return

            training_already_completed = self.store.has_subject_completed_training(subject_id)
            self._training_configs = select_training_configs(self._scan_result.candidate_map)
            rng_seed = random.SystemRandom().randint(1, 2**31 - 1)
            self._bundle = self.store.create_new_session(subject_id, self._scan_result, rng_seed)
            self._training_index = 0
            if training_already_completed:
                self._show_training_skipped_intro()
            else:
                self._show_training_intro()
        except SpecError as exc:
            self.start_screen.show_validation(error_message=str(exc))
            self._scan_result = None
            self._bundle = None
        except OSError as exc:
            self.start_screen.show_validation(
                error_message=f"Unable to create or access session files safely: {exc}."
            )
            self._scan_result = None
            self._bundle = None

    def _show_resume_screen(self) -> None:
        assert self._bundle is not None
        details = [
            f"Subject ID: {self._bundle.meta.subject_id}",
            f"Scene Folder Name: {self._bundle.meta.scene_folder_name}",
            f"Action Type: {self._bundle.meta.action_type}",
            f"Current phase: {self._bundle.state.current_phase}",
            f"Last update time: {self._bundle.state.updated_at}",
        ]
        self.resume_screen.set_details(details)
        self.stack.setCurrentWidget(self.resume_screen)

    def _cancel_resume(self) -> None:
        self._bundle = None
        self._scan_result = None
        self.start_screen.populate_inputs(self._resume_subject_id, self._resume_scene_folder)
        self.stack.setCurrentWidget(self.start_screen)

    def _resume_existing_session(self) -> None:
        try:
            self._ensure_ready_for_resume()
            assert self._bundle is not None
            if self.store.reconcile_state(self._bundle):
                self.store.write_session_state(self._bundle.session_dir, self._bundle.state)

            if not self._bundle.raw_trials and not self._bundle.phase1_results and self._bundle.state.current_phase == TRAINING:
                if self.store.has_subject_completed_training(self._bundle.meta.subject_id):
                    self._show_training_skipped_intro()
                else:
                    self._training_configs = select_training_configs(self._scan_result.candidate_map)
                    self._training_index = 0
                    self._show_training_intro()
                return
            if not self._bundle.raw_trials and not self._bundle.phase1_results and self._bundle.state.current_screen in {
                "training_complete",
                "formal_intro",
            }:
                if self._bundle.state.current_screen == "training_complete":
                    self._show_training_complete_transition()
                else:
                    self._show_formal_intro()
                return

            self._advance_formal_flow()
        except SpecError as exc:
            self._show_fatal_error(str(exc), "Check the session files and restart with a safe dataset.")

    def _ensure_ready_for_resume(self) -> None:
        if self._scan_result is None or self._bundle is None:
            raise SpecError("Resume requested without validated session context.")
        if self._bundle.meta.reference_config != REFERENCE_CONFIG:
            raise SpecError("session_meta.json does not match the fixed reference config in the implementer spec.")
        if self._bundle.meta.subject_id != self._resume_subject_id:
            raise SpecError("The resume session subject does not match the requested subject.")
        unit = self._scan_result.experiment_unit
        if (
            self._bundle.meta.device != unit.device
            or self._bundle.meta.action_type != unit.action_type
            or self._bundle.meta.country != unit.country
            or self._bundle.meta.route_suffix != unit.route_suffix
            or self._bundle.meta.occurrence != unit.occurrence
            or self._bundle.meta.scene_folder_name != unit.scene_folder_name
        ):
            raise SpecError("The selected scene folder does not match the experiment unit stored in session_meta.json.")
        if self._bundle.meta.reference_path.resolve() != self._scan_result.reference_path.resolve():
            raise SpecError(
                "The current reference video path does not match the path stored in session_meta.json. Refusing to mix assets across resume."
            )

    def _show_training_intro(self) -> None:
        assert self._bundle is not None
        if not self._training_configs:
            assert self._scan_result is not None
            self._training_configs = select_training_configs(self._scan_result.candidate_map)
        self._update_state(current_screen="training_intro", current_phase=TRAINING, current_resolution=None)
        self._show_message(
            title="Training",
            body_lines=[
                "Two videos will be shown one after another.",
                "Choose whether there is a noticeable visible difference.",
                "Training results are not part of the formal data.",
            ],
            detail_lines=[],
            primary_label="Begin Training",
            primary_action=self._begin_training,
        )

    def _show_training_skipped_intro(self) -> None:
        assert self._bundle is not None
        self._update_state(current_screen="formal_intro", current_phase="phase1", current_resolution=None)
        self._show_message(
            title="Formal Experiment",
            body_lines=[
                "Training was already completed for this participant.",
                "Formal experiment is about to start.",
                "Judge visible difference only.",
            ],
            detail_lines=[],
            primary_label="Start Phase 1",
            primary_action=self._advance_formal_flow,
        )

    def _begin_training(self) -> None:
        self._training_index = 0
        self._show_training_trial()

    def _show_training_trial(self, auto_start: bool = False) -> None:
        assert self._scan_result is not None
        assert self._bundle is not None
        if not self._training_configs:
            raise SpecError("Training trial requested without available training configs.")
        candidate_config = self._training_configs[self._training_index]
        candidate_path = self._scan_result.candidate_map[candidate_config.key()]
        presentation_order = random.choice(["reference_first", "candidate_first"])
        self._active_trial = ScheduledTrial(
            phase=TRAINING,
            resolution=candidate_config.resolution,
            candidate_config=candidate_config,
            candidate_path=candidate_path,
            reference_path=self._scan_result.reference_path,
            presentation_order=presentation_order,
            formal_trial_index=None,
            progress_label=f"Training trial {self._training_index + 1}/3",
        )
        self._update_state(current_screen="training_trial", current_phase=TRAINING, current_resolution=None)
        self.trial_screen.start_trial(
            phase_text="Training",
            progress_text=self._active_trial.progress_label,
            reference_path=self._active_trial.reference_path,
            candidate_path=self._active_trial.candidate_path,
            presentation_order=self._active_trial.presentation_order,
            auto_start=auto_start,
        )
        self.stack.setCurrentWidget(self.trial_screen)

    def _show_training_complete_transition(self) -> None:
        assert self._bundle is not None
        self._update_state(current_screen="training_complete", current_phase="phase1", current_resolution=None)
        self._show_message(
            title="Training Complete",
            body_lines=[
                "Training is complete.",
                "Formal experiment is next.",
            ],
            detail_lines=[],
            primary_label="Start Formal Experiment",
            primary_action=self._show_formal_intro,
        )

    def _show_formal_intro(self) -> None:
        assert self._bundle is not None
        self._update_state(current_screen="formal_intro", current_phase="phase1", current_resolution=None)
        self._show_message(
            title="Formal Experiment",
            body_lines=[
                "Training is complete.",
                "Formal experiment is about to start.",
                "Judge visible difference only.",
            ],
            detail_lines=[],
            primary_label="Start Phase 1",
            primary_action=self._advance_formal_flow,
        )

    def _advance_formal_flow(self, auto_start_trial: bool = False) -> None:
        assert self._bundle is not None
        assert self._scan_result is not None

        try:
            while True:
                self._validate_formal_progress_consistency()
                phase1_result_map = {result.resolution: result for result in self._bundle.phase1_results}
                next_phase1_resolution = next(
                    (resolution for resolution in RESOLUTION_ORDER if resolution not in phase1_result_map),
                    None,
                )
                if next_phase1_resolution is not None:
                    decision = evaluate_phase1_history(
                        next_phase1_resolution,
                        phase1_trials_for_resolution(self._bundle.raw_trials, next_phase1_resolution),
                    )
                    if decision.kind == "complete":
                        self._record_phase1_result(decision.result)
                        continue
                    if decision.config.key() not in self._scan_result.candidate_map:
                        self._record_phase1_result(
                            Phase1Result(
                                resolution=next_phase1_resolution,
                                lowest_jnd_safe_fps=None,
                                status="MISSING_ASSET",
                            )
                        )
                        continue
                    self._start_formal_trial(PHASE1, next_phase1_resolution, decision.config, auto_start=auto_start_trial)
                    return

                phase2_queue = phase2_queue_from_phase1(self._bundle.phase1_results)
                if not phase2_queue:
                    self._finalize_session()
                    return

                if not self._has_phase2_started():
                    found_count, skipped_count = phase1_transition_counts(self._bundle.phase1_results)
                    self._show_phase2_transition(found_count, skipped_count)
                    return

                phase2_result_map = {result.resolution: result for result in self._bundle.phase2_results}
                next_phase2_item = next(
                    (
                        item
                        for item in phase2_queue
                        if item[0] not in phase2_result_map
                    ),
                    None,
                )
                if next_phase2_item is None:
                    self._finalize_session()
                    return

                resolution, fps_star = next_phase2_item
                decision = evaluate_phase2_progress(
                    resolution,
                    fps_star,
                    self._scan_result.candidate_map,
                    phase2_trials_for_resolution(self._bundle.raw_trials, resolution),
                )
                if decision.kind == "complete":
                    self._record_phase2_result(decision.result)
                    continue
                self._start_formal_trial(PHASE2, resolution, decision.config, auto_start=auto_start_trial)
                return
        except SpecError as exc:
            self._show_fatal_error(str(exc), "Inspect the current session files before continuing.")

    def _validate_formal_progress_consistency(self) -> None:
        assert self._bundle is not None
        phase1_completed = {result.resolution for result in self._bundle.phase1_results}
        next_phase1_resolution = next(
            (resolution for resolution in RESOLUTION_ORDER if resolution not in phase1_completed),
            None,
        )

        allowed_phase1 = set(phase1_completed)
        if next_phase1_resolution is not None:
            allowed_phase1.add(next_phase1_resolution)
        disallowed_phase1 = sorted(
            {
                trial.candidate_config.resolution
                for trial in self._bundle.raw_trials
                if trial.phase == PHASE1 and trial.candidate_config.resolution not in allowed_phase1
            }
        )
        if disallowed_phase1:
            raise SpecError(
                "Resume state is corrupted: Phase 1 raw trials exist for later resolutions before the current Phase 1 resolution finished."
            )

        if next_phase1_resolution is not None:
            if self._bundle.phase2_results or any(trial.phase == PHASE2 for trial in self._bundle.raw_trials):
                raise SpecError(
                    "Resume state is corrupted: Phase 2 data exists before all Phase 1 resolutions were finalized."
                )
            return

        phase2_queue = [resolution for resolution, _fps in phase2_queue_from_phase1(self._bundle.phase1_results)]
        phase2_completed = {result.resolution for result in self._bundle.phase2_results}
        next_phase2_resolution = next(
            (resolution for resolution in phase2_queue if resolution not in phase2_completed),
            None,
        )
        allowed_phase2 = set(phase2_completed)
        if next_phase2_resolution is not None:
            allowed_phase2.add(next_phase2_resolution)
        disallowed_phase2 = sorted(
            {
                trial.candidate_config.resolution
                for trial in self._bundle.raw_trials
                if trial.phase == PHASE2 and trial.candidate_config.resolution not in allowed_phase2
            }
        )
        if disallowed_phase2:
            raise SpecError(
                "Resume state is corrupted: Phase 2 raw trials exist for later resolutions before the current Phase 2 resolution finished."
            )

    def _show_phase2_transition(self, found_count: int, skipped_count: int) -> None:
        assert self._bundle is not None
        self._update_state(current_screen="phase_transition", current_phase="phase2", current_resolution=None)
        self._show_message(
            title="Phase 1 Complete",
            body_lines=[
                "Phase 1 is complete.",
                f"Resolutions with FOUND: {found_count}",
                f"Resolutions skipped from Phase 2: {skipped_count}",
            ],
            detail_lines=[],
            primary_label="Start Phase 2",
            primary_action=self._start_phase2,
        )

    def _start_phase2(self) -> None:
        self._bundle.state.current_phase = "phase2"
        self._phase2_transition_acknowledged = True
        self._advance_formal_flow()

    def _start_formal_trial(self, phase: str, resolution: str, candidate_config, auto_start: bool = False) -> None:
        assert self._bundle is not None
        assert self._scan_result is not None
        trial_index = self._bundle.state.next_trial_index
        candidate_path = self._scan_result.candidate_map.get(candidate_config.key())
        if candidate_path is None:
            raise SpecError(
                f"Required candidate asset is missing for {format_render_config(candidate_config)}."
            )
        presentation_order = deterministic_presentation_order(self._bundle.state.rng_seed, trial_index)
        self._active_trial = ScheduledTrial(
            phase=phase,
            resolution=resolution,
            candidate_config=candidate_config,
            candidate_path=candidate_path,
            reference_path=self._scan_result.reference_path,
            presentation_order=presentation_order,
            formal_trial_index=trial_index,
            progress_label=f"Formal trial {trial_index}",
        )
        self._update_state(current_screen="trial", current_phase=phase, current_resolution=resolution)
        self.trial_screen.start_trial(
            phase_text="Phase 1" if phase == PHASE1 else "Phase 2",
            progress_text=self._active_trial.progress_label,
            reference_path=self._active_trial.reference_path,
            candidate_path=self._active_trial.candidate_path,
            presentation_order=self._active_trial.presentation_order,
            auto_start=auto_start,
        )
        self.stack.setCurrentWidget(self.trial_screen)

    def _handle_trial_response(self, response: str, response_time_ms: int) -> None:
        if self._active_trial is None:
            return
        if self._active_trial.phase == TRAINING:
            self.trial_screen.show_post_response_ready()
            return

        assert self._bundle is not None
        trial = self._active_trial
        record = TrialRecord(
            trial_index=trial.formal_trial_index or self._bundle.state.next_trial_index,
            subject_id=self._bundle.meta.subject_id,
            device=self._bundle.meta.device,
            action_type=self._bundle.meta.action_type,
            country=self._bundle.meta.country,
            route_suffix=self._bundle.meta.route_suffix,
            occurrence=self._bundle.meta.occurrence,
            scene_folder_name=self._bundle.meta.scene_folder_name,
            phase=trial.phase,
            candidate_config=trial.candidate_config,
            reference_config=REFERENCE_CONFIG,
            candidate_path=trial.candidate_path,
            reference_path=trial.reference_path,
            presentation_order=trial.presentation_order,
            response=response,
            response_time_ms=response_time_ms,
            timestamp=timestamp_now(),
        )

        try:
            self.store.append_raw_trial(self._bundle.session_dir, record)
            self._bundle.raw_trials.append(record)
            self._bundle.state.next_trial_index = record.trial_index + 1
            self.store.write_session_state(self._bundle.session_dir, self._bundle.state)
            self.trial_screen.show_post_response_ready()
        except (OSError, SpecError) as exc:
            self._show_fatal_error(
                f"Unable to write formal trial data safely: {exc}",
                "Check disk permissions and session files before retrying.",
            )

    def _handle_next_trial_requested(self) -> None:
        if self._active_trial is None:
            return

        completed_trial = self._active_trial
        self._active_trial = None

        if completed_trial.phase == TRAINING:
            self._training_index += 1
            if self._training_index < len(self._training_configs):
                self._show_training_trial(auto_start=True)
            else:
                assert self._bundle is not None
                try:
                    self.store.mark_subject_training_completed(
                        self._bundle.meta.subject_id,
                        self._bundle.session_dir,
                    )
                except OSError as exc:
                    self._show_fatal_error(
                        f"Unable to persist subject training status safely: {exc}",
                        "Check disk permissions and session files before retrying.",
                    )
                    return
                self._show_training_complete_transition()
            return

        self._advance_formal_flow(auto_start_trial=True)

    def _record_phase1_result(self, result: Phase1Result | None) -> None:
        if result is None:
            raise SpecError("Phase 1 completion was requested without a result.")
        assert self._bundle is not None
        self._bundle.phase1_results.append(result)
        self._bundle.phase1_results.sort(key=lambda item: ["VeryHigh", "High", "Medium", "Low", "Lowest"].index(item.resolution))
        self._bundle.state.phase1_completed_resolutions = [
            item.resolution for item in self._bundle.phase1_results
        ]
        self.store.write_phase1_results(self._bundle.session_dir, self._bundle.phase1_results)
        self.store.write_session_state(self._bundle.session_dir, self._bundle.state)

    def _record_phase2_result(self, result) -> None:
        if result is None:
            raise SpecError("Phase 2 completion was requested without a result.")
        assert self._bundle is not None
        self._bundle.phase2_results.append(result)
        order = [resolution for resolution, _fps in phase2_queue_from_phase1(self._bundle.phase1_results)]
        self._bundle.phase2_results.sort(key=lambda item: order.index(item.resolution))
        self._bundle.state.phase2_completed_resolutions = [
            item.resolution for item in self._bundle.phase2_results
        ]
        self.store.write_phase2_results(self._bundle.session_dir, self._bundle.phase2_results)
        self.store.write_session_state(self._bundle.session_dir, self._bundle.state)

    def _finalize_session(self) -> None:
        assert self._bundle is not None
        candidate_power_prior_manifest = self.store.load_candidate_power_prior_manifest(self._bundle.session_dir)
        final_safe_set = build_final_safe_set(
            subject_id=self._bundle.meta.subject_id,
            device=self._bundle.meta.device,
            action_type=self._bundle.meta.action_type,
            country=self._bundle.meta.country,
            route_suffix=self._bundle.meta.route_suffix,
            occurrence=self._bundle.meta.occurrence,
            scene_folder_name=self._bundle.meta.scene_folder_name,
            phase1_results=self._bundle.phase1_results,
            phase2_results=self._bundle.phase2_results,
        )
        candidate_subjective_label_manifest = build_candidate_subjective_label_manifest(
            meta=self._bundle.meta,
            raw_trials=self._bundle.raw_trials,
            candidate_power_prior_manifest=candidate_power_prior_manifest,
        )
        self.store.write_final_safe_set(self._bundle.session_dir, final_safe_set)
        self.store.write_candidate_subjective_label_manifest(
            self._bundle.session_dir,
            candidate_subjective_label_manifest,
        )
        self.store.mark_session_finished(self._bundle)
        detail_lines = [
            f"Output directory: {self._bundle.session_dir}",
            f"Formal trials completed: {len(self._bundle.raw_trials)}",
            f"Final safe configs: {len(final_safe_set.jnd_safe_set)}",
            f"Candidate label entries: {len(candidate_subjective_label_manifest['candidates'])}",
        ]
        if final_safe_set.estimated_lowest_power_safe_config is not None:
            detail_lines.append(
                "Estimated lowest-power safe config: "
                f"{format_render_config(final_safe_set.estimated_lowest_power_safe_config)}"
            )
        ambiguous_phase2 = sum(
            1 for result in self._bundle.phase2_results if phase2_result_has_prior_contradiction(result)
        )
        if ambiguous_phase2:
            detail_lines.append(
                f"Phase 2 ambiguous branches: {ambiguous_phase2}"
            )
        self._show_message(
            title="Experiment Complete",
            body_lines=[
                "Experiment complete.",
                "Data saved successfully.",
            ],
            detail_lines=detail_lines,
            primary_label="Close",
            primary_action=self.close,
        )

    def _has_phase2_started(self) -> bool:
        assert self._bundle is not None
        if self._bundle.phase2_results or any(trial.phase == PHASE2 for trial in self._bundle.raw_trials):
            return True
        if self._phase2_transition_acknowledged:
            return True
        return self._bundle.state.current_screen == "trial" and self._bundle.state.current_phase == PHASE2

    def _show_message(
        self,
        title: str,
        body_lines: list[str],
        detail_lines: list[str],
        primary_label: str,
        primary_action,
        secondary_label: str | None = None,
        secondary_action=None,
    ) -> None:
        self._pending_primary_action = primary_action
        self._pending_secondary_action = secondary_action
        self.message_screen.configure(title, body_lines, detail_lines, primary_label, secondary_label)
        self.stack.setCurrentWidget(self.message_screen)

    def _handle_message_primary(self) -> None:
        if callable(self._pending_primary_action):
            self._pending_primary_action()

    def _handle_message_secondary(self) -> None:
        if callable(self._pending_secondary_action):
            self._pending_secondary_action()

    def _handle_playback_error(self, error_message: str) -> None:
        self._show_fatal_error(
            f"Playback failed: {error_message}",
            "Inspect the media asset and restart from the current session.",
        )

    def _update_state(
        self,
        *,
        current_screen: str,
        current_phase: str,
        current_resolution: str | None,
    ) -> None:
        assert self._bundle is not None
        self._bundle.state.current_screen = current_screen
        self._bundle.state.current_phase = current_phase
        self._bundle.state.current_resolution = current_resolution
        self.store.write_session_state(self._bundle.session_dir, self._bundle.state)

    def _show_fatal_error(self, message: str, next_action: str) -> None:
        try:
            self.store.mark_session_error(self._bundle)
        except OSError:
            pass
        self.trial_screen.stop_trial()
        QMessageBox.critical(self, "Fatal Error", f"{message}\n\nNext action: {next_action}")
        self._show_message(
            title="Fatal Error",
            body_lines=[message],
            detail_lines=[f"Suggested next action: {next_action}"],
            primary_label="Close",
            primary_action=self.close,
        )
