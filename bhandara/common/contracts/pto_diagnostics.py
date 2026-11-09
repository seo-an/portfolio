"""Semantic contract for Gearbox diagnostics and result severity."""

from __future__ import annotations

from typing import Any, Iterable

SUCCESS = "SUCCESS"
UNSTABLE = "UNSTABLE"
FAILED = "FAILED"
RESULT_SEVERITIES = (SUCCESS, UNSTABLE, FAILED)

INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"
CRITICAL = "CRITICAL"
LEVELS = (INFO, WARNING, ERROR, CRITICAL)

ACTION_REQUIRED = "ACTION_REQUIRED"
CHECK_REQUIRED = "CHECK_REQUIRED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
BLOCKED = "BLOCKED"
STATES = (ACTION_REQUIRED, CHECK_REQUIRED, REVIEW_REQUIRED, BLOCKED)


class DiagnosticContractError(ValueError):
    pass


def _required_text(value: Any, field: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise DiagnosticContractError(f"{field} must not be empty")
    return text


def _normalize_states(states: Iterable[str] | None) -> list[str]:
    normalized: list[str] = []
    for state in states or ():
        value = str(state).upper().strip()
        if value not in STATES:
            raise DiagnosticContractError(f"unsupported state: {state!r}")
        if value not in normalized:
            normalized.append(value)
    return normalized


def build_diagnostic(
    code: Any,
    level: Any,
    message: Any,
    *,
    states: Iterable[str] | None = None,
    category: Any | None = None,
    action: Any | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_code = _required_text(code, "code")
    normalized_level = _required_text(level, "level").upper()
    normalized_message = _required_text(message, "message")
    normalized_states = _normalize_states(states)

    if normalized_level not in LEVELS:
        raise DiagnosticContractError(f"unsupported level: {level!r}")

    normalized_category = (
        str(category).upper().strip() if category not in (None, "") else None
    )
    normalized_action = (
        str(action).strip() if action not in (None, "") else None
    )
    if ACTION_REQUIRED in normalized_states and not normalized_action:
        raise DiagnosticContractError("ACTION_REQUIRED requires action")

    return {
        "code": normalized_code,
        "level": normalized_level,
        "states": normalized_states,
        "category": normalized_category,
        "message": normalized_message,
        "action": normalized_action,
        "context": dict(context or {}),
    }


def build_result(
    severity: Any,
    *,
    diagnostics: Iterable[dict[str, Any]] | None = None,
    result: Any = None,
) -> dict[str, Any]:
    normalized_severity = _required_text(severity, "severity").upper()
    if normalized_severity not in RESULT_SEVERITIES:
        raise DiagnosticContractError(
            f"unsupported result severity: {severity!r}"
        )
    return {
        "severity": normalized_severity,
        "diagnostics": list(diagnostics or ()),
        "result": result,
    }
