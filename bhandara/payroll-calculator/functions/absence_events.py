"""Normalize unpaid attendance events and evaluate weekly attendance eligibility."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


EVENT_TYPES = {"absence", "unpaid_leave"}
ATTENDANCE_TREATMENTS = {"absence", "leave"}


class AbsenceEventError(RuntimeError):
    """Raised when an absence event cannot be interpreted safely."""

    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Absence event failed: {message}")


def _date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise AbsenceEventError(f"{field} must use YYYY-MM-DD: {value!r}") from exc
    raise AbsenceEventError(f"{field} must be a date or YYYY-MM-DD string")


def _hours(value: Any) -> Decimal:
    try:
        hours = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AbsenceEventError("unpaid_hours must be decimal-compatible") from exc
    if hours <= 0:
        raise AbsenceEventError("unpaid_hours must be greater than zero")
    return hours


def normalize_absence_event(event: dict[str, Any]) -> dict[str, Any]:
    """Validate an explicit unpaid attendance event without inferring HR policy."""
    required = (
        "worker_id",
        "work_date",
        "event_type",
        "unpaid_hours",
        "attendance_treatment",
    )
    missing = [field for field in required if field not in event]
    if missing:
        raise AbsenceEventError(f"missing required fields: {', '.join(missing)}")

    worker_id = str(event["worker_id"]).strip()
    if not worker_id:
        raise AbsenceEventError("worker_id must not be empty")

    event_type = str(event["event_type"]).strip()
    if event_type not in EVENT_TYPES:
        raise AbsenceEventError(
            f"event_type must be one of: {', '.join(sorted(EVENT_TYPES))}"
        )

    attendance_treatment = str(event["attendance_treatment"]).strip()
    if attendance_treatment not in ATTENDANCE_TREATMENTS:
        raise AbsenceEventError(
            "attendance_treatment must be one of: "
            + ", ".join(sorted(ATTENDANCE_TREATMENTS))
        )

    return {
        **event,
        "worker_id": worker_id,
        "work_date": _date(event["work_date"], "work_date"),
        "event_type": event_type,
        "unpaid_hours": _hours(event["unpaid_hours"]),
        "attendance_treatment": attendance_treatment,
    }


def evaluate_weekly_attendance(
    events: list[dict[str, Any]],
    worker_id: str,
    week_start: Any,
    week_end: Any,
) -> dict[str, Any]:
    """Evaluate only whether explicit events break weekly attendance.

    This does not by itself decide statutory weekly-holiday entitlement.
    Other requirements, including the applicable schedule and whether the
    worker has scheduled work in the week, remain separate inputs.
    """
    start = _date(week_start, "week_start")
    end = _date(week_end, "week_end")
    if end < start:
        raise AbsenceEventError("week_end precedes week_start")

    target_worker = str(worker_id).strip()
    if not target_worker:
        raise AbsenceEventError("worker_id must not be empty")

    weekly_events = [
        normalize_absence_event(event)
        for event in events
        if str(event.get("worker_id", "")).strip() == target_worker
        and start <= _date(event.get("work_date"), "work_date") <= end
    ]
    attendance_breaking = [
        event for event in weekly_events
        if event["attendance_treatment"] == "absence"
    ]

    return {
        "worker_id": target_worker,
        "week_start": start,
        "week_end": end,
        "attendance_maintained": not attendance_breaking,
        "attendance_breaking_events": attendance_breaking,
        "weekly_events": weekly_events,
    }
