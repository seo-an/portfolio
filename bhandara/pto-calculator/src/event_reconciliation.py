"""Reconcile employee events for one employee-date without guessing conflicts."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from bhandara.common.contracts.pto_diagnostics import REVIEW_REQUIRED, WARNING, build_diagnostic


ACTIVE_EVENT_STATUSES = {"APPROVED"}


def find_daily_employee_events(
    event_rows: Iterable[dict],
    employee_id: str,
    event_date: date,
) -> list[dict]:
    """Return all event rows for an employee-date, including inactive history."""
    return [
        row for row in event_rows
        if row.get("employee_id") == employee_id
        and row.get("event_date") == event_date
    ]


def reconcile_daily_employee_event(
    event_rows: Iterable[dict],
    employee_id: str,
    event_date: date,
) -> dict:
    """Select at most one active event and expose conflicts for review."""

    matched = find_daily_employee_events(event_rows, employee_id, event_date)
    active = [
        row for row in matched
        if str(row.get("status") or "").upper() in ACTIVE_EVENT_STATUSES
    ]

    if len(active) > 1:
        diagnostic = build_diagnostic(
            "MULTIPLE_ACTIVE_EMPLOYEE_EVENTS",
            WARNING,
            "Multiple approved employee events are active for the same employee and date.",
            states=[REVIEW_REQUIRED],
            category="CONFLICT",
            context={
                "employee_id": employee_id,
                "event_date": event_date,
                "active_event_count": len(active),
            },
        )
        return {
            "event": None,
            "matched_events": matched,
            "active_events": active,
            "status": "CONFLICT",
            "flags": ["MULTIPLE_ACTIVE_EMPLOYEE_EVENTS"],
            "requires_review": True,
            "diagnostics": [diagnostic],
        }

    return {
        "event": active[0] if active else None,
        "matched_events": matched,
        "active_events": active,
        "status": "RESOLVED" if active else "NONE",
        "flags": [],
        "requires_review": False,
        "diagnostics": [],
    }
