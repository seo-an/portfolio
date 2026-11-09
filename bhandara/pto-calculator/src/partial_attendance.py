"""Compose reduced-hours statutory credit with observed daily attendance."""

from __future__ import annotations

from datetime import time
from typing import Any


PARTIAL_TIME_EVENTS = {
    "CHILDCARE_REDUCED_HOURS",
    "PREGNANCY_REDUCED_HOURS",
}


def _hours_between(start: time, end: time) -> float:
    start_seconds = start.hour * 3600 + start.minute * 60 + start.second
    end_seconds = end.hour * 3600 + end.minute * 60 + end.second
    if end_seconds < start_seconds:
        end_seconds += 24 * 3600
    return (end_seconds - start_seconds) / 3600


def observed_work_hours(attendance: dict[str, Any]) -> float | None:
    """Return observed net hours from complete clock facts, else None."""
    clock_in = attendance.get("clock_in")
    clock_out = attendance.get("clock_out")
    if clock_in is None or clock_out is None:
        return None

    gross = _hours_between(clock_in, clock_out)
    break_min = attendance.get("break_min") or 0
    net = gross - float(break_min) / 60
    return max(net, 0.0)


def compose_reduced_hours_attendance(
    *,
    schedule: dict[str, Any],
    attendance: dict[str, Any],
    event: dict[str, Any],
) -> dict[str, Any]:
    """Resolve PTO attendance for one approved statutory reduced-hours day.

    This function does not calculate wages, overtime, or legal working-time
    premiums. It only checks whether observed net attendance covers the
    remaining scheduled obligation after approved statutory reduced hours.
    """
    scheduled_hours = schedule.get("scheduled_work_hours")
    reduced_hours = event.get("reduced_hours")

    if scheduled_hours is None:
        return {
            "resolved": False,
            "reason": "MISSING_SCHEDULED_WORK_HOURS",
        }
    if reduced_hours is None:
        return {
            "resolved": False,
            "reason": "MISSING_REDUCED_HOURS",
        }

    scheduled_hours = float(scheduled_hours)
    reduced_hours = float(reduced_hours)
    if reduced_hours < 0 or reduced_hours > scheduled_hours:
        return {
            "resolved": False,
            "reason": "INVALID_REDUCED_HOURS",
        }

    observed_hours = observed_work_hours(attendance)
    if observed_hours is None:
        return {
            "resolved": False,
            "reason": "INCOMPLETE_ATTENDANCE_FOR_REDUCED_HOURS",
        }

    required_observed_hours = max(scheduled_hours - reduced_hours, 0.0)
    if observed_hours + 1e-9 < required_observed_hours:
        return {
            "resolved": False,
            "reason": "OBSERVED_HOURS_BELOW_REMAINING_OBLIGATION",
            "scheduled_hours": scheduled_hours,
            "reduced_hours": reduced_hours,
            "required_observed_hours": required_observed_hours,
            "observed_hours": observed_hours,
        }

    return {
        "resolved": True,
        "reason": "REDUCED_HOURS_ATTENDANCE_SATISFIED",
        "scheduled_hours": scheduled_hours,
        "reduced_hours": reduced_hours,
        "required_observed_hours": required_observed_hours,
        "observed_hours": observed_hours,
    }
