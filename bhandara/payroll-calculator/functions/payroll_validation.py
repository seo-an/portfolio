"""Payroll validation adapter over the Gearbox diagnostic contract."""

from __future__ import annotations

from typing import Any

from bhandara.common.contracts.pto_diagnostics import (
    ACTION_REQUIRED,
    ERROR,
    INFO,
    LEVELS,
    WARNING,
    DiagnosticContractError,
    build_diagnostic,
)

SEVERITIES = LEVELS


class PayrollValidationError(ValueError):
    pass


def build_validation(
    code: str,
    severity: str,
    message: str,
    *,
    action: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Payroll validation while preserving the legacy call signature."""
    normalized = str(severity).upper().strip()
    states = [ACTION_REQUIRED] if normalized == ACTION_REQUIRED else []
    level = WARNING if normalized == ACTION_REQUIRED else normalized

    try:
        return build_diagnostic(
            code,
            level,
            message,
            states=states,
            action=action,
            context=context,
        )
    except DiagnosticContractError as exc:
        raise PayrollValidationError(str(exc)) from exc


def summarize_validations(validations: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {level: 0 for level in LEVELS}
    requires_action = False

    for validation in validations:
        level = str(validation.get("level", "")).upper()
        if level not in counts:
            raise PayrollValidationError(f"unsupported level: {level!r}")
        counts[level] += 1

        states = validation.get("states", [])
        if not isinstance(states, list):
            raise PayrollValidationError("states must be a list")
        requires_action = requires_action or ACTION_REQUIRED in states

    has_error = counts[ERROR] > 0
    return {
        "counts": counts,
        "has_error": has_error,
        "requires_action": requires_action,
        "can_calculate": not has_error,
        "can_auto_finalize": not has_error and not requires_action,
    }
