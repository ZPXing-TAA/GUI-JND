# JND Subjective Experiment UI Implementer Spec

This document is the implementation-facing, unified specification for the JND subjective experiment GUI.

For implementation purposes, this document is the source of truth and overrides conflicts in:

- `subjective_experiment_spec.md`
- `trial_scheduler_and_logging_spec.md`
- `experiment_controller_design.md`

The goal is to let a new implementer build the full interface and the required experiment flow without needing to resolve design ambiguity on their own.

---

# 1. Product Goal

Build a GUI application that runs one subjective experiment session for one experiment unit:

`ExperimentUnit = (device, action_type, country, route_suffix, occurrence, scene_folder_name)`

The app must:

1. Load a scene folder.
2. Parse all candidate videos into canonical render configs.
3. Find the reference video.
4. Run training trials.
5. Run Phase 1 FPS search.
6. Run Phase 2 graphics reduction trials.
7. Save logs and intermediate results incrementally.
8. Resume an interrupted session.
9. Export the final JND-safe set.

The app is for running the experiment, not for later aggregate analysis across subjects.

---

# 2. Fixed Decisions

These choices are final for implementation:

1. Trial presentation is sequential `A/B` playback, not left/right side-by-side.
2. Each trial randomizes whether the reference is shown first or second.
3. Internal response values are always:
   - `Same`
   - `Different`
4. UI button labels shown to the participant are:
   - `No noticeable difference`
   - `Visible difference`
5. Session outputs are stored in one session-centric directory, not split across multiple top-level result folders.
6. Raw formal trial logs are append-only `jsonl`.
7. Phase 1 uses boundary confirmation and may return:
   - `FOUND`
   - `NOT_FOUND`
   - `MISSING_ASSET`
   - `AMBIGUOUS`
8. Phase 2 only runs for resolutions whose Phase 1 result is `FOUND`.
9. Final `jnd_safe_set` includes:
   - the baseline safe Phase 1 config `(resolution, fps_star, High, High)`
   - any additional Phase 2 safe configs
10. The GUI only supports the migrated final scene folder naming format.
11. The GUI does not support the old or intermediate scene folder formats.
12. The GUI must not require any ancestor directory to be literally named `Recordings`.

---

# 3. Dataset Rules

## 3.1 Scene Folder

Input is a single scene folder:

`<any_root>/{device}/{action_type}/{scene_folder_name}/`

Example:

`/Users/xingzhengpeng/CODEZONE/PCO/Power-Optimization/Recordings/huaweipura/run/natlan_r30_run02/`

The GUI must validate the final path components only.

It must not require any ancestor directory to be named `Recordings`.

## 3.2 Scene Folder Name Format

Only the migrated final format is supported:

`scene_folder_name = {country}_r{route_suffix:02d}_{label}{occurrence:02d}`

Example:

`natlan_r30_run02`

Field meaning:

- `country`: region or nation name, such as `natlan`
- `route_suffix`: route number, fixed to two digits in the folder name
- `label`: action label embedded in the folder name
- `occurrence`: occurrence count for that label within the same route

The parent directory `action_type` and the parsed `label` must match.

Example:

- parent directory = `run`
- scene folder name = `natlan_r30_run02`
- parsed `label` = `run`

This is valid.

Example of invalid mismatch:

- parent directory = `run`
- scene folder name = `natlan_r30_glide01`

This must be rejected.

## 3.3 Unsupported Scene Folder Formats

The GUI must reject the following older scene folder naming styles:

- `{country}_{global_action_index}_h{route_suffix}`
- `{country}_r{route_suffix:02d}_s{segment:02d}`

Examples of unsupported folders:

- `natlan_21_h30`
- `natlan_r30_s03`

Do not auto-detect or auto-migrate them inside the GUI.

## 3.4 Path Interpretation Rules

The GUI must not assume:

- sibling scene folders are complete
- sibling scene folders are contiguous
- route-wide global order can be reconstructed from the folder name alone

The current naming scheme does not preserve route-wide total order.

The GUI only needs to operate on the selected scene folder and must not try to infer the full route sequence.

## 3.5 Supported Video Filename Formats

The application must support both:

Legacy 5-token format:

`{resolution}_{redundant}_{fps}_{effect}_{shadow}.mp4`

Example:

`High_High_24_High_High.mp4`

Canonical 4-token format:

`{resolution}_{fps}_{effect}_{shadow}.mp4`

Example:

`High_24_High_High.mp4`

## 3.6 Allowed Values

Resolution:

- `Lowest`
- `Low`
- `Medium`
- `High`
- `VeryHigh`

FPS:

- `24`
- `30`
- `45`
- `60`

Effect:

- `Low`
- `High`

Shadow:

- `Low`
- `High`

## 3.7 Reference Video

Reference config is always:

`("VeryHigh", 60, "High", "High")`

If the reference video is missing, the app must fail fast before formal trials begin.

---

# 4. Canonical Data Model

## 4.1 RenderConfig

```json
{
  "resolution": "High",
  "fps": 45,
  "effect": "High",
  "shadow": "High"
}
```

## 4.2 ExperimentUnit

```json
{
  "device": "huaweipura",
  "action_type": "run",
  "country": "natlan",
  "route_suffix": 30,
  "occurrence": 2,
  "scene_folder_name": "natlan_r30_run02",
  "scene_folder": "/abs/path/to/huaweipura/run/natlan_r30_run02"
}
```

## 4.3 Candidate Map

Internal structure:

`candidate_map[(resolution, fps, effect, shadow)] = absolute_video_path`

This is internal only and does not need to be serialized directly.

## 4.4 TrialRecord

This is the only formal raw trial log schema.

```json
{
  "trial_index": 5,
  "subject_id": "S01",
  "device": "huaweipura",
  "action_type": "run",
  "country": "natlan",
  "route_suffix": 30,
  "occurrence": 2,
  "scene_folder_name": "natlan_r30_run02",
  "phase": "phase1",
  "candidate_config": {
    "resolution": "High",
    "fps": 45,
    "effect": "High",
    "shadow": "High"
  },
  "reference_config": {
    "resolution": "VeryHigh",
    "fps": 60,
    "effect": "High",
    "shadow": "High"
  },
  "candidate_path": "/abs/path/to/High_High_45_High_High.mp4",
  "reference_path": "/abs/path/to/VeryHigh_VeryHigh_60_High_High.mp4",
  "presentation_order": "candidate_first",
  "response": "Same",
  "response_time_ms": 3100,
  "timestamp": "2026-03-18T14:12:05+08:00"
}
```

Rules:

1. `trial_index` is global across the formal session and starts at `1`.
2. Training trials are not written into `raw_trials.jsonl`.
3. `presentation_order` must be one of:
   - `reference_first`
   - `candidate_first`
4. `response` must be one of:
   - `Same`
   - `Different`

---

# 5. Session Output Structure

Each session writes into one directory:

`Results/{subject_id}/{device}/{action_type}/{scene_folder_name}/`

Example:

`Results/S01/huaweipura/run/natlan_r30_run02/`

Files:

- `session_meta.json`
- `session_state.json`
- `raw_trials.jsonl`
- `phase1_result.json`
- `phase2_result.json`
- `final_jnd_safe_set.json`

## 5.1 session_meta.json

Contains static session information:

```json
{
  "subject_id": "S01",
  "device": "huaweipura",
  "action_type": "run",
  "country": "natlan",
  "route_suffix": 30,
  "occurrence": 2,
  "scene_folder_name": "natlan_r30_run02",
  "scene_folder": "/abs/path/to/scene_folder",
  "reference_config": {
    "resolution": "VeryHigh",
    "fps": 60,
    "effect": "High",
    "shadow": "High"
  },
  "reference_path": "/abs/path/to/reference.mp4",
  "created_at": "2026-03-18T14:00:00+08:00",
  "app_spec_version": "1.0"
}
```

## 5.2 session_state.json

Contains current runtime state for resume:

```json
{
  "status": "RUNNING",
  "current_screen": "trial",
  "current_phase": "phase1",
  "current_resolution": "High",
  "phase1_completed_resolutions": ["VeryHigh"],
  "phase2_completed_resolutions": [],
  "next_trial_index": 8,
  "rng_seed": 12345,
  "updated_at": "2026-03-18T14:30:00+08:00"
}
```

`status` must be one of:

- `RUNNING`
- `FINISHED`
- `ERROR`

## 5.3 raw_trials.jsonl

Append one JSON object per completed formal trial.

Do not rewrite the full file after every trial.

## 5.4 phase1_result.json

Use an array of per-resolution results:

```json
[
  {
    "resolution": "VeryHigh",
    "lowest_jnd_safe_fps": 45,
    "status": "FOUND"
  },
  {
    "resolution": "High",
    "lowest_jnd_safe_fps": null,
    "status": "NOT_FOUND"
  }
]
```

## 5.5 phase2_result.json

Use an array of per-resolution results:

```json
[
  {
    "resolution": "VeryHigh",
    "fps_star": 45,
    "candidate_results": [
      { "effect": "Low", "shadow": "High", "status": "SAFE" },
      { "effect": "High", "shadow": "Low", "status": "SAFE" },
      { "effect": "Low", "shadow": "Low", "status": "NOT_SAFE" }
    ]
  }
]
```

Candidate `status` must be one of:

- `SAFE`
- `NOT_SAFE`
- `MISSING_ASSET`

## 5.6 final_jnd_safe_set.json

```json
{
  "subject_id": "S01",
  "device": "huaweipura",
  "action_type": "run",
  "country": "natlan",
  "route_suffix": 30,
  "occurrence": 2,
  "scene_folder_name": "natlan_r30_run02",
  "reference_config": {
    "resolution": "VeryHigh",
    "fps": 60,
    "effect": "High",
    "shadow": "High"
  },
  "jnd_safe_set": [
    { "resolution": "VeryHigh", "fps": 45, "effect": "High", "shadow": "High" },
    { "resolution": "VeryHigh", "fps": 45, "effect": "Low", "shadow": "High" },
    { "resolution": "VeryHigh", "fps": 45, "effect": "High", "shadow": "Low" }
  ],
  "generated_at": "2026-03-18T15:10:00+08:00"
}
```

---

# 6. End-to-End Experiment Flow

The app runs in this order:

1. User enters `subject_id` and selects `scene_folder`.
2. App parses the experiment unit from the path.
3. App scans the folder and builds `candidate_map`.
4. App locates the reference video.
5. App creates or loads the session directory.
6. If an unfinished session exists, app offers resume.
7. App runs training flow.
8. App runs Phase 1 in fixed resolution order:
   - `VeryHigh`
   - `High`
   - `Medium`
   - `Low`
   - `Lowest`
9. App saves `phase1_result.json` after each resolution completes.
10. App builds the Phase 2 queue from resolutions whose Phase 1 result is `FOUND`.
11. App runs Phase 2 in the same resolution order.
12. App saves `phase2_result.json` after each resolution completes.
13. App merges results into `final_jnd_safe_set.json`.
14. App updates `session_state.json` to `FINISHED`.
15. App shows completion screen.

---

# 7. UI State Machine

Recommended states:

- `INIT`
- `SESSION_CHECK`
- `TRAINING_INTRO`
- `TRAINING_TRIAL`
- `FORMAL_INTRO`
- `TRIAL`
- `PHASE_TRANSITION`
- `COMPLETION`
- `ERROR`

---

# 8. Screen Specifications

## 8.1 Start Screen

Purpose:

- collect session input
- validate scene folder
- start or resume session

Inputs:

- `subject_id`
- `scene_folder`

Buttons:

- `Browse Folder`
- `Start Experiment`

Behavior:

1. `subject_id` must be non-empty.
2. `scene_folder` must exist.
3. The selected folder must match the final migrated scene folder format.
4. The parent `action_type` directory and parsed label in the scene folder name must match.
5. On start, parse folder metadata immediately.
6. If parsing fails, show error and stay on start screen.
7. If reference video is missing, block progress and show explicit error.

Recommended visible info after folder validation:

- device
- action type
- country
- route suffix
- occurrence
- scene folder name
- number of valid candidate videos found

## 8.2 Resume Decision Screen

Show only if session directory already exists and `session_state.json` says `RUNNING`.

Display:

- subject id
- scene folder name
- current phase
- current resolution
- last update time

Buttons:

- `Resume Session`
- `Cancel`

For version 1, do not offer overwrite-from-scratch inside the GUI.

## 8.3 Training Intro Screen

Purpose:

- explain the task
- prepare the participant for sequential `A/B` comparison

Show:

- short text: two videos will be shown one after another
- short text: choose whether there is a noticeable difference
- short text: training results are not part of formal data

Button:

- `Begin Training`

## 8.4 Training Trial Screen

Use the same layout as formal trials, but do not write to `raw_trials.jsonl`.

Recommended training count:

- exactly `3` training trials

Training pair selection heuristic:

1. one obviously different pair using the lowest-quality available candidate
2. one medium-difference pair using a mid-quality available candidate
3. one near-reference pair using the best non-reference available candidate

If not enough variety exists, use the closest available fallback and continue.

After the last training trial, show a transition button:

- `Start Formal Experiment`

## 8.5 Formal Intro Screen

Show:

- training complete
- formal experiment is about to start
- remind participant to judge visible difference only

Button:

- `Start Phase 1`

## 8.6 Formal Trial Screen

This is the main screen and must support both Phase 1 and Phase 2.

Visible elements:

- phase label
- current resolution label
- current candidate config label
- progress label
- video area
- clip label `A` or `B`
- response buttons

Playback rules:

1. A and B are shown sequentially.
2. The order is determined by `presentation_order`.
3. The participant must not answer until both clips finish.
4. Response buttons remain disabled during playback.
5. Response timer starts when the second clip finishes.
6. After response, the app saves trial data immediately before advancing.

Response buttons:

- `No noticeable difference`
- `Visible difference`

Internal mapping:

- `No noticeable difference` -> `Same`
- `Visible difference` -> `Different`

Progress label recommendation:

- show current phase
- show current resolution
- show formal trial index

Do not show speculative remaining total because branching makes it dynamic.

## 8.7 Phase Transition Screen

Show when:

- training ends
- Phase 1 ends and Phase 2 is about to begin

After Phase 1, display:

- Phase 1 complete
- number of resolutions with `FOUND`
- number of resolutions skipped because of `NOT_FOUND`, `MISSING_ASSET`, or `AMBIGUOUS`

Button:

- `Start Phase 2`

If no resolutions qualify for Phase 2:

- skip Phase 2 entirely
- proceed directly to finalization

## 8.8 Completion Screen

Show:

- experiment complete
- data saved
- output directory

Optional summary:

- number of formal trials completed
- number of final safe configs

Button:

- `Close`

## 8.9 Error Screen or Modal

Used for fatal errors only.

Show:

- human-readable error message
- suggested next action

Examples:

- reference video missing
- unsupported scene folder format
- unable to write session files
- session state corrupted

---

# 9. Trial Playback Contract

The playback layer must accept:

- `reference_path`
- `candidate_path`
- `presentation_order`

Behavior:

1. Build trial labels `A` and `B` from order.
2. Play clip A to completion.
3. Play clip B to completion.
4. Enable response input only after both clips complete.
5. Return user response and response time.

No side-by-side playback.

No per-trial free navigation between unrelated clips.

Version 1 does not require replay support.

---

# 10. Phase 1 Scheduling Logic

## 10.1 Goal

For each resolution, find the lowest FPS that is still visually indistinguishable from the reference while keeping:

- `effect = High`
- `shadow = High`

Candidates are:

- `24`
- `30`
- `45`
- `60`

The implementation may assume perceptual quality is monotonic with FPS for fixed resolution/effect/shadow.

## 10.2 Resolution Order

Run Phase 1 in this fixed order:

1. `VeryHigh`
2. `High`
3. `Medium`
4. `Low`
5. `Lowest`

## 10.3 Primary Decision Path

For one resolution:

1. Test `(resolution, 45, High, High)`.
2. If response is `Same`, test `(resolution, 30, High, High)`.
3. If response to `30` is `Same`, test `(resolution, 24, High, High)`.
4. If response to `24` is `Same`, provisional result is `24`.
5. If response to `24` is `Different`, boundary is between `24` and `30`.
6. If response to `30` is `Different`, boundary is between `30` and `45`.
7. If response to `45` is `Different`, test `(resolution, 60, High, High)`.
8. If response to `60` is `Same`, boundary is between `45` and `60`.
9. If response to `60` is `Different`, provisional result is `NOT_FOUND`.

## 10.4 Boundary Confirmation Rule

When a boundary is first observed, repeat one confirmation trial before finalizing.

Boundary cases:

- `45 Same`, `30 Different` -> repeat `30`
- `30 Same`, `24 Different` -> repeat `24`
- `45 Different`, `60 Same` -> repeat `45`
- `45 Different`, `60 Different` -> repeat `60`

Decision after confirmation:

1. If confirmation matches the first boundary result, finalize.
2. If confirmation conflicts with the first boundary result, mark this resolution `AMBIGUOUS`.
3. `AMBIGUOUS` resolutions do not enter Phase 2.

Examples:

- `45 Same`, `30 Different`, `30 Different` -> `FOUND`, lowest safe FPS = `45`
- `30 Same`, `24 Different`, `24 Different` -> `FOUND`, lowest safe FPS = `30`
- `45 Different`, `60 Same`, `45 Different` -> `FOUND`, lowest safe FPS = `60`
- `45 Different`, `60 Different`, `60 Different` -> `NOT_FOUND`
- `45 Same`, `30 Different`, `30 Same` -> `AMBIGUOUS`

## 10.5 Missing Candidate Handling

If a required Phase 1 candidate file is missing:

1. Do not crash the session.
2. Mark the current resolution as `MISSING_ASSET`.
3. Set `lowest_jnd_safe_fps = null`.
4. Skip Phase 2 for that resolution.
5. Continue with the next resolution.

## 10.6 Phase 1 Result Object

```json
{
  "resolution": "High",
  "lowest_jnd_safe_fps": 45,
  "status": "FOUND"
}
```

Allowed `status` values:

- `FOUND`
- `NOT_FOUND`
- `MISSING_ASSET`
- `AMBIGUOUS`

Meaning:

- `FOUND`: lowest safe FPS was determined
- `NOT_FOUND`: even `60 FPS` is still visibly different from the reference
- `MISSING_ASSET`: required test asset was absent
- `AMBIGUOUS`: confirmation contradicted the first boundary result

---

# 11. Phase 2 Scheduling Logic

## 11.1 Goal

For each resolution whose Phase 1 result is `FOUND`, test graphics reductions at the safe FPS:

Base config:

`(resolution, fps_star, High, High)`

Candidates:

- `(resolution, fps_star, Low, High)`
- `(resolution, fps_star, High, Low)`
- `(resolution, fps_star, Low, Low)`

## 11.2 Execution Order

Use the exact candidate order above.

## 11.3 Decision Rule

For each candidate:

1. If asset is missing, record `MISSING_ASSET`.
2. Otherwise run one formal trial.
3. If response is `Same`, record `SAFE`.
4. If response is `Different`, record `NOT_SAFE`.

Version 1 does not use boundary confirmation in Phase 2.

## 11.4 Phase 2 Result Object

```json
{
  "resolution": "High",
  "fps_star": 45,
  "candidate_results": [
    { "effect": "Low", "shadow": "High", "status": "SAFE" },
    { "effect": "High", "shadow": "Low", "status": "NOT_SAFE" },
    { "effect": "Low", "shadow": "Low", "status": "MISSING_ASSET" }
  ]
}
```

---

# 12. Final Merge Logic

After all resolutions complete:

1. For each Phase 1 result with `status = FOUND`, add the baseline safe config:
   - `(resolution, fps_star, High, High)`
2. For the same resolution, add every Phase 2 candidate with `status = SAFE`.
3. Do not add configs from resolutions with:
   - `NOT_FOUND`
   - `MISSING_ASSET`
   - `AMBIGUOUS`

The final output is a set of safe configs, not a single winner.

---

# 13. Logging Rules

## 13.1 When to Save

Save immediately after:

- creating session meta
- updating session state
- finishing each formal trial
- finishing each resolution in Phase 1
- finishing each resolution in Phase 2
- generating final result

## 13.2 Formal Trial Write Order

For each formal trial:

1. run playback
2. collect response
3. append one line to `raw_trials.jsonl`
4. update `session_state.json`
5. continue

## 13.3 Training Logging

Training trials are not part of formal experimental data.

Version 1 does not need a separate persistent training log.

---

# 14. Resume Rules

If a session directory exists and `session_state.json` says `RUNNING`:

1. load `session_meta.json`
2. load `session_state.json`
3. load `phase1_result.json` if present
4. load `phase2_result.json` if present
5. reconstruct next step from those files
6. continue with `next_trial_index`

Resume behavior requirements:

1. Do not replay already completed formal trials.
2. Do not rewrite existing `raw_trials.jsonl` lines.
3. Continue from the unfinished resolution and phase.
4. Preserve the original `rng_seed` so future order randomization remains stable.

If files disagree in a way the app cannot safely reconcile:

1. mark session state `ERROR`
2. show a fatal error screen
3. do not guess

---

# 15. Error Handling

Fatal errors:

- scene folder invalid
- unsupported scene folder format
- action type and scene folder label mismatch
- reference video missing
- output directory cannot be created
- session files cannot be written
- resume state is corrupted beyond safe recovery

Non-fatal per-resolution or per-candidate issues:

- invalid candidate filename
- candidate asset missing

Rules:

1. Invalid filenames are skipped with warning.
2. Missing reference is fatal.
3. Missing candidate is non-fatal and should produce a status result.
4. Unexpected response values must not be accepted.

---

# 16. Suggested Module Split

This is a framework-agnostic split. The implementer can adapt names to the chosen stack.

- `dataset_parser`
  - parse scene folder path
  - parse scene folder name
  - enforce action type and label consistency
  - parse render config from filename
  - build candidate map

- `session_store`
  - create session directory
  - write/read session files
  - append raw trial logs
  - load resume state

- `scheduler`
  - Phase 1 state machine
  - Phase 2 queue builder
  - final merge logic

- `trial_player`
  - sequential A/B playback
  - order mapping
  - response timing

- `ui`
  - start screen
  - resume screen
  - training intro
  - trial screen
  - phase transition screen
  - completion screen
  - error screen

- `app_controller`
  - top-level orchestration
  - state transitions
  - interactions between UI, scheduler, playback, and storage

---

# 17. Acceptance Checklist

The implementation is complete when all of the following are true:

1. User can select a scene folder and enter a subject id.
2. App validates the folder and finds the reference video.
3. App can run sequential A/B training trials.
4. App can run Phase 1 with boundary confirmation.
5. App can produce `FOUND`, `NOT_FOUND`, `MISSING_ASSET`, and `AMBIGUOUS` correctly.
6. App can run Phase 2 for `FOUND` resolutions only.
7. Formal trial logs are appended to `raw_trials.jsonl`.
8. Intermediate results are written incrementally.
9. App can resume from `session_state.json`.
10. App writes `final_jnd_safe_set.json`.
11. App reaches a clear completion screen with saved output path.

---

# 18. Minimal Pseudocode

```text
start_app()
  -> collect subject_id + scene_folder
  -> parse experiment unit
  -> build candidate_map
  -> find reference
  -> create/load session
  -> if unfinished session exists: resume flow
  -> run training
  -> for resolution in [VeryHigh, High, Medium, Low, Lowest]:
       run phase1_for_resolution()
       save phase1 result
  -> build phase2 queue from FOUND resolutions
  -> for resolution in found_resolutions:
       run phase2_for_resolution()
       save phase2 result
  -> merge final safe set
  -> save final result
  -> mark session finished
  -> show completion screen
```

---

# 19. Final Notes For The Implementer

Keep the implementation behavior-first and deterministic.

Do not re-open design questions that this document already fixes.

If an edge case is not covered here, prefer:

1. preserving already collected data
2. failing explicitly on fatal uncertainty
3. continuing gracefully on per-candidate missing assets

End of spec.
