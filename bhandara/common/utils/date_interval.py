"""Generic inclusive date-interval primitives for Gearbox."""

from __future__ import annotations

from datetime import date


def validate_date_interval(
    start_date: date,
    end_date: date | None = None,
) -> None:
    """Validate an inclusive date interval with an optional open end."""
    if not isinstance(start_date, date):
        raise ValueError("start_date must be a date")
    if end_date is not None and not isinstance(end_date, date):
        raise ValueError("end_date must be a date or None")
    if end_date is not None and end_date < start_date:
        raise ValueError("end_date must be on or after start_date")


def is_date_within_interval(
    start_date: date,
    end_date: date | None,
    target_date: date,
) -> bool:
    """Return whether target_date falls inside an inclusive date interval."""
    validate_date_interval(start_date, end_date)
    if not isinstance(target_date, date):
        raise ValueError("target_date must be a date")

    return target_date >= start_date and (
        end_date is None or target_date <= end_date
    )
