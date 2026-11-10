"""Resolve effective-dated compensation rows for Payroll calculation."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from bhandara.common.utils.date_interval import is_date_within_interval


IDENTITY_FIELDS = {"worker_id", "effective_from", "effective_to"}


class CompensationResolutionError(RuntimeError):
    """Raised when compensation history cannot be resolved deterministically."""

    def __init__(self, message: str) -> None:
        super().__init__(f"[payroll-calculator] Compensation resolution failed: {message}")


def parse_date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise CompensationResolutionError(
                f"{field} must use YYYY-MM-DD: {value!r}"
            ) from exc
    raise CompensationResolutionError(f"{field} must be a date or YYYY-MM-DD string")


def optional_date(value: Any, field: str) -> date | None:
    if value in (None, ""):
        return None
    return parse_date(value, field)


def normalize_amount(value: Any, field: str) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CompensationResolutionError(f"{field} must be a numeric amount") from exc
    if amount < 0:
        raise CompensationResolutionError(f"{field} must not be negative")
    return amount


def normalize_compensation_row(row: dict[str, Any]) -> dict[str, Any]:
    worker_id = str(row.get("worker_id", "")).strip()
    if not worker_id:
        raise CompensationResolutionError("worker_id must not be empty")

    effective_from = parse_date(row.get("effective_from"), "effective_from")
    effective_to = optional_date(row.get("effective_to"), "effective_to")
    if effective_to is not None and effective_to < effective_from:
        raise CompensationResolutionError(
            f"{worker_id}: effective_to precedes effective_from"
        )

    normalized = dict(row)
    normalized["worker_id"] = worker_id
    normalized["effective_from"] = effective_from
    normalized["effective_to"] = effective_to

    for field, value in row.items():
        if field not in IDENTITY_FIELDS:
            normalized[field] = normalize_amount(value, field)
    return normalized


def is_effective_on(row: dict[str, Any], work_date: date) -> bool:
    return is_date_within_interval(
        row["effective_from"],
        row["effective_to"],
        work_date,
    )


def validate_no_overlaps(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [normalize_compensation_row(row) for row in rows]
    by_worker: dict[str, list[dict[str, Any]]] = {}

    for row in normalized:
        by_worker.setdefault(row["worker_id"], []).append(row)

    for worker_id, history in by_worker.items():
        ordered = sorted(history, key=lambda item: item["effective_from"])
        for previous, current in zip(ordered, ordered[1:]):
            previous_to = previous["effective_to"]
            if previous_to is None or current["effective_from"] <= previous_to:
                raise CompensationResolutionError(
                    f"{worker_id}: overlapping compensation periods "
                    f"{previous['effective_from']}~{previous_to or 'open'} and "
                    f"{current['effective_from']}~{current['effective_to'] or 'open'}"
                )
    return normalized


def resolve_compensation(
    rows: Iterable[dict[str, Any]],
    worker_id: str,
    work_date: Any,
) -> dict[str, Any]:
    target_date = parse_date(work_date, "work_date")
    target_worker = str(worker_id).strip()
    normalized = validate_no_overlaps(rows)

    matches = [
        row for row in normalized
        if row["worker_id"] == target_worker and is_effective_on(row, target_date)
    ]

    if not matches:
        raise CompensationResolutionError(
            f"{target_worker}: no compensation row effective on {target_date}"
        )
    if len(matches) > 1:
        raise CompensationResolutionError(
            f"{target_worker}: multiple compensation rows effective on {target_date}"
        )
    return matches[0]
