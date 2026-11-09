"""Work-schedule cycle resolution for PTO-related time conversion."""

from __future__ import annotations

from datetime import date
from typing import Iterable


ALLOWED_DAY_TYPES = {"WORK", "HOLIDAY", "OFF"}


def validate_schedule_rows(rows: Iterable[dict]) -> list[dict]:
    rows = list(rows)
    grouped: dict[str, list[dict]] = {}

    for row in rows:
        schedule_id = str(row["schedule_id"]).strip()
        day_type = str(row["day_type"]).strip().upper()
        sequence = int(row["sequence"])

        if not schedule_id:
            raise ValueError("schedule_id is required")
        if day_type not in ALLOWED_DAY_TYPES:
            raise ValueError(f"invalid day_type: {day_type}")
        if sequence < 1:
            raise ValueError("sequence must be >= 1")
        if day_type != "WORK" and row.get("scheduled_work_hours") not in (None, "", 0, 0.0):
            raise ValueError("non-WORK cycle day must not have positive scheduled_work_hours")

        normalized = dict(row)
        normalized["schedule_id"] = schedule_id
        normalized["day_type"] = day_type
        normalized["sequence"] = sequence
        grouped.setdefault(schedule_id, []).append(normalized)

    for schedule_id, schedule_rows in grouped.items():
        sequences = sorted(row["sequence"] for row in schedule_rows)
        expected = list(range(1, len(schedule_rows) + 1))
        if sequences != expected:
            raise ValueError(
                f"{schedule_id}: sequence must be contiguous from 1; "
                f"found {sequences}"
            )

    return [row for group in grouped.values() for row in group]


def resolve_cycle_sequence(
    work_date: date,
    cycle_anchor_date: date,
    start_sequence: int,
    cycle_length: int,
) -> int:
    if cycle_length < 1:
        raise ValueError("cycle_length must be >= 1")
    if not 1 <= start_sequence <= cycle_length:
        raise ValueError("start_sequence must be within the cycle")

    offset = (work_date - cycle_anchor_date).days
    return ((start_sequence - 1 + offset) % cycle_length) + 1


def resolve_schedule_day(
    schedule_rows: Iterable[dict],
    schedule_id: str,
    work_date: date,
    cycle_anchor_date: date,
    start_sequence: int,
) -> dict:
    rows = [
        row for row in validate_schedule_rows(schedule_rows)
        if row["schedule_id"] == schedule_id
    ]
    if not rows:
        raise KeyError(f"unknown schedule_id: {schedule_id}")

    sequence = resolve_cycle_sequence(
        work_date=work_date,
        cycle_anchor_date=cycle_anchor_date,
        start_sequence=start_sequence,
        cycle_length=len(rows),
    )
    return next(row for row in rows if row["sequence"] == sequence)
