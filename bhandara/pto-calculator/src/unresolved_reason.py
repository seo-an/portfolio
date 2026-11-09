"""Classify deterministic UNDETERMINED reasons by required resolution path."""

from __future__ import annotations

from bhandara.common.contracts.pto_diagnostics import (
    ACTION_REQUIRED,
    BLOCKED,
    ERROR,
    REVIEW_REQUIRED,
    build_diagnostic,
)


COMPANY_POLICY_REQUIRED = "COMPANY_POLICY_REQUIRED"
DATA_REQUIRED = "DATA_REQUIRED"
CONFLICT_RESOLUTION_REQUIRED = "CONFLICT_RESOLUTION_REQUIRED"
RULE_REQUIRED = "RULE_REQUIRED"


COMPANY_POLICY_REASONS = {
    "BEREAVEMENT_LEAVE",
    "SICK_LEAVE",
    "LEAVE_OF_ABSENCE",
}

DATA_REASONS = {
    "UNRESOLVED_SCHEDULED_WORKDAY",
    "MISSING_SCHEDULED_WORK_HOURS",
    "MISSING_REDUCED_HOURS",
    "INVALID_REDUCED_HOURS",
    "INCOMPLETE_ATTENDANCE_FOR_REDUCED_HOURS",
    "OBSERVED_HOURS_BELOW_REMAINING_OBLIGATION",
}

CONFLICT_REASONS = {
    "EVENT_CONFLICT",
}

RULE_REASONS = {
    "UNKNOWN_EVENT",
    "EVENT_NOT_APPROVED",
    "REDUCED_HOURS_REQUIRES_COMPOSITION",
    "ATTENDANCE_POLICY_UNRESOLVED",
}


def classify_unresolved_reason(reason: str) -> str:
    """Return the action category for an unresolved deterministic reason."""
    if reason in COMPANY_POLICY_REASONS:
        return COMPANY_POLICY_REQUIRED
    if reason in DATA_REASONS:
        return DATA_REQUIRED
    if reason in CONFLICT_REASONS:
        return CONFLICT_RESOLUTION_REQUIRED
    return RULE_REQUIRED


MISSING_DATA_DIAGNOSTIC_REASONS = {
    "UNRESOLVED_SCHEDULED_WORKDAY",
    "MISSING_SCHEDULED_WORK_HOURS",
    "MISSING_REDUCED_HOURS",
    "INCOMPLETE_ATTENDANCE_FOR_REDUCED_HOURS",
}


def build_unresolved_diagnostic(reason: str, *, work_date=None) -> dict:
    """Build a diagnostic only after a PTO result is known to be unresolved."""
    resolution_path = classify_unresolved_reason(reason)

    if resolution_path == CONFLICT_RESOLUTION_REQUIRED:
        category = "CONFLICT"
        action = "Resolve the conflicting PTO facts before finalizing the result."
    elif reason in MISSING_DATA_DIAGNOSTIC_REASONS:
        category = "MISSING_DATA"
        action = "Provide or correct the required PTO data before finalizing the result."
    else:
        category = "VALIDATION"
        action = "Review and resolve the PTO policy or rule before finalizing the result."

    context = {"reason": reason, "resolution_path": resolution_path}
    if work_date is not None:
        context["work_date"] = work_date

    return build_diagnostic(
        reason,
        ERROR,
        "PTO attendance resolution is incomplete and blocks finalization.",
        states=[BLOCKED, ACTION_REQUIRED, REVIEW_REQUIRED],
        category=category,
        action=action,
        context=context,
    )
