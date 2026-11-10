"""Validate Worktime Calculator output before Payroll consumes it."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


REQUIRED_FIELDS = (
    "worker_id",
    "work_date",
    "worktime_system",
    "rule_ref",
    "scheduled_hours",
    "worked_hours",
    "ordinary_hours",
    "overtime_hours",
    "night_hours",
    "holiday_work_hours_within_8",
    "holiday_work_hours_over_8",
    "absence_hours",
    "late_minutes",
    "early_leave_minutes",
    "validation_flags",
)

DECIMAL_HOUR_FIELDS = (
    "scheduled_hours",
    "worked_hours",
    "ordinary_hours",
    "overtime_hours",
    "night_hours",
    "holiday_work_hours_within_8",
    "holiday_work_hours_over_8",
    "absence_hours",
)

MINUTE_FIELDS = ("late_minutes", "early_leave_minutes")


class WorktimeHandoffError(RuntimeError):
    """Raised when Worktime output cannot safely enter Payroll."""

    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Worktime handoff rejected: {message}")


def _non_negative_decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise WorktimeHandoffError(f"{field} must be a decimal-compatible value") from exc
    if number < 0:
        raise WorktimeHandoffError(f"{field} must not be negative")
    return number


def _non_negative_integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise WorktimeHandoffError(f"{field} must be a non-negative integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise WorktimeHandoffError(f"{field} must be a non-negative integer") from exc
    if number < 0 or str(number) != str(value).strip():
        raise WorktimeHandoffError(f"{field} must be a non-negative integer")
    return number


def validate_worktime_row(row: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in row]
    if missing:
        raise WorktimeHandoffError(f"missing required fields: {', '.join(missing)}")

    if not str(row["worker_id"]).strip():
        raise WorktimeHandoffError("worker_id must not be empty")
    if not str(row["work_date"]).strip():
        raise WorktimeHandoffError("work_date must not be empty")
    if not str(row["worktime_system"]).strip():
        raise WorktimeHandoffError("worktime_system must not be empty")
    if not str(row["rule_ref"]).strip():
        raise WorktimeHandoffError("rule_ref must not be empty")

    normalized = dict(row)
    for field in DECIMAL_HOUR_FIELDS:
        normalized[field] = _non_negative_decimal(row[field], field)
    for field in MINUTE_FIELDS:
        normalized[field] = _non_negative_integer(row[field], field)

    flags = row["validation_flags"]
    if not isinstance(flags, list):
        raise WorktimeHandoffError("validation_flags must be a list")

    blocking = [
        flag for flag in flags
        if isinstance(flag, dict) and str(flag.get("severity", "")).upper() == "ERROR"
    ]
    if blocking:
        codes = [str(flag.get("code", "UNKNOWN")) for flag in blocking]
        raise WorktimeHandoffError(
            "blocking Worktime validation error(s): " + ", ".join(codes)
        )

    normalized["validation_flags"] = flags
    return normalized


def validate_worktime_handoff(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise WorktimeHandoffError("handoff payload must be a list")
    return [validate_worktime_row(row) for row in rows]
