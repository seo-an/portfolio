"""Materialize approved period-based leave facts without inventing duration."""

from __future__ import annotations

from datetime import timedelta


def materialize_approved_period_event(source_event: dict) -> list[dict]:
    """Expand an explicitly approved start/end period to daily event rows."""
    start = source_event.get("event_start_date")
    end = source_event.get("event_end_date")

    if start is None or end is None:
        raise ValueError("period event requires event_start_date and event_end_date")
    if end < start:
        raise ValueError("event_end_date must be on or after event_start_date")
    if str(source_event.get("status") or "").upper() != "APPROVED":
        raise ValueError("only APPROVED period events may be materialized")

    rows = []
    current = start
    while current <= end:
        row = dict(source_event)
        row["event_date"] = current
        row["unit"] = "DAY"
        row["materialized_from_period"] = {
            "event_start_date": start,
            "event_end_date": end,
        }
        rows.append(row)
        current += timedelta(days=1)
    return rows
