"""Prepare source rows for Payroll using resolved operating periods."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

try:
    from .operating_period_resolver import resolve_source_period
except ImportError:
    from operating_period_resolver import resolve_source_period


class OperatingInputPreparationError(ValueError):
    pass


def _date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise OperatingInputPreparationError(
                f"{field} must use YYYY-MM-DD: {value!r}"
            ) from exc
    raise OperatingInputPreparationError(
        f"{field} must be a date or YYYY-MM-DD string"
    )


def _optional_date(value: Any, field: str) -> date | None:
    if value in (None, ""):
        return None
    return _date(value, field)


def _overlaps(
    row_from: date,
    row_to: date | None,
    period_from: date,
    period_to: date,
) -> bool:
    return row_from <= period_to and (row_to is None or row_to >= period_from)


def prepare_compensation_rows(
    rows: list[dict[str, Any]],
    payroll_period: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Keep compensation history rows overlapping the resolved source period."""
    resolved = resolve_source_period(payroll_period, "compensation", config)
    selected = []
    for row in rows:
        effective_from = _date(row.get("effective_from"), "effective_from")
        effective_to = _optional_date(row.get("effective_to"), "effective_to")
        if effective_to is not None and effective_to < effective_from:
            raise OperatingInputPreparationError(
                "effective_to precedes effective_from"
            )
        if _overlaps(
            effective_from,
            effective_to,
            resolved["period_from"],
            resolved["period_to"],
        ):
            selected.append(row)
    return {"period": resolved, "rows": selected}


def prepare_worktime_rows(
    rows: list[dict[str, Any]],
    payroll_period: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Keep Worktime facts whose work_date falls inside the resolved source period."""
    resolved = resolve_source_period(payroll_period, "worktime", config)
    selected = [
        row for row in rows
        if resolved["period_from"]
        <= _date(row.get("work_date"), "work_date")
        <= resolved["period_to"]
    ]
    return {"period": resolved, "rows": selected}


def prepare_payroll_input_rows(
    rows: list[dict[str, Any]],
    payroll_period: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Resolve each payroll transaction's attribution without filtering it out.

    Payroll Input is a transaction source for the selected payroll run. Explicit
    origin dates describe historical attribution; they do not decide whether the
    transaction belongs to the run.
    """
    prepared = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise OperatingInputPreparationError(
                "payroll input row must be a mapping"
            )
        resolved = resolve_source_period(
            payroll_period,
            "payroll_input",
            config,
            origin_from=row.get("origin_from"),
            origin_to=row.get("origin_to"),
            payment_basis=row.get("payment_basis"),
            pay_item_code=row.get("pay_item_code"),
        )
        prepared.append({
            "row": dict(row),
            "period": resolved,
        })
    return {
        "payroll_period": payroll_period,
        "source": "payroll_input",
        "rows": prepared,
    }
