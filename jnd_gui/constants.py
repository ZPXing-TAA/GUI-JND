from __future__ import annotations

from jnd_gui.models import RenderConfig


APP_SPEC_VERSION = "1.0"
RESULTS_DIR_NAME = "Results"

RESOLUTION_ORDER = ["VeryHigh", "High", "Medium", "Low", "Lowest"]
RESOLUTION_PRIOR_ORDER = ["Lowest", "Low", "Medium", "High", "VeryHigh"]
FPS_VALUES = [24, 30, 45, 60]
EFFECT_VALUES = ["Low", "High"]
SHADOW_VALUES = ["Low", "High"]

POWER_LABEL_TYPE = "relative_power_prior"
POWER_LABEL_SOURCE = "inferred_prior"
ESTIMATED_SAFE_CONFIG_SOURCE = "relative_power_prior"

REFERENCE_CONFIG = RenderConfig("VeryHigh", 60, "High", "High")

PHASE1 = "phase1"
PHASE2 = "phase2"
TRAINING = "training"

RUNNING = "RUNNING"
FINISHED = "FINISHED"
ERROR = "ERROR"

RESPONSE_SAME = "Same"
RESPONSE_DIFFERENT = "Different"
VALID_RESPONSES = {RESPONSE_SAME, RESPONSE_DIFFERENT}

PRESENTATION_REFERENCE_FIRST = "reference_first"
PRESENTATION_CANDIDATE_FIRST = "candidate_first"
VALID_PRESENTATION_ORDERS = {
    PRESENTATION_REFERENCE_FIRST,
    PRESENTATION_CANDIDATE_FIRST,
}

BUTTON_NO_NOTICEABLE_DIFF = "No noticeable difference"
BUTTON_VISIBLE_DIFF = "Visible difference"

PHASE1_STATUSES = {"FOUND", "NOT_FOUND", "MISSING_ASSET", "AMBIGUOUS"}
PHASE2_STATUSES = {"SAFE", "NOT_SAFE", "MISSING_ASSET"}
