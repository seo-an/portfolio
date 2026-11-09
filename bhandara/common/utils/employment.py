"""Common employment-fact primitives for Gearbox."""

from __future__ import annotations

from datetime import date
from typing import Any

from bhandara.common.utils.date_interval import is_date_within_interval, validate_date_interval


def validate_employment_interval(
    employment_from: date,
    employment_to: date | None = None,
) -> None:
    """Validate an employment interval without imposing an identity contract."""
    try:
        validate_date_interval(employment_from, employment_to)
    except ValueError as exc:
        message = str(exc)
        message = message.replace("start_date", "employment_from")
        message = message.replace("end_date", "employment_to")
        raise ValueError(message) from exc


def is_within_employment_interval(
    employment_from: date,
    employment_to: date | None,
    target_date: date,
) -> bool:
    """Return whether target_date falls inside an inclusive employment interval."""
    validate_employment_interval(employment_from, employment_to)
    if not isinstance(target_date, date):
        raise ValueError("target_date must be a date")

    return is_date_within_interval(employment_from, employment_to, target_date)


def validate_employment_fact(fact: dict[str, Any]) -> None:
    """Validate the canonical Gearbox employment-fact contract."""
    worker_id = fact.get("worker_id")
    if not worker_id:
        raise ValueError("worker_id is required")

    validate_employment_interval(
        fact.get("employment_from"),
        fact.get("employment_to"),
    )


def is_within_employment(
    fact: dict[str, Any],
    target_date: date,
) -> bool:
    """Return whether target_date falls inside a canonical employment fact."""
    validate_employment_fact(fact)

    return is_within_employment_interval(
        fact["employment_from"],
        fact.get("employment_to"),
        target_date,
    )
