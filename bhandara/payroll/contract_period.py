"""Fail-closed calculation-period selection for the new Payroll preview.

calculation_period_from/to identify an *already declared payroll calculation*
window. They are NOT interpreted as the legal effective dates of a contract.
No legal contract validity, employment status, or prorated wages are inferred.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from calendar import monthrange
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


class PayrollPeriodError(ValueError):
    """Missing/ambiguous period or unsupported pay-cycle contract."""


def _date(value: Any, name: str) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise PayrollPeriodError(f"{name}: ISO YYYY-MM-DD string required")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise PayrollPeriodError(f"{name}: invalid date") from exc
    if parsed.isoformat() != value:
        raise PayrollPeriodError(f"{name}: canonical ISO date required")
    return parsed


def _period(period_from: str, period_to: str) -> tuple[date, date]:
    first, last = _date(period_from, "period_from"), _date(period_to, "period_to")
    if first > last:
        raise PayrollPeriodError("period_from: after period_to")
    return first, last


def _monthly_cycle(first: date, last: date) -> bool:
    return (
        first.day == 1
        and first.year == last.year
        and first.month == last.month
        and last.day == monthrange(first.year, first.month)[1]
    )


def _expected_cycle(row: Mapping[str, Any], first: date, last: date) -> None:
    """Avoid presenting a weekly installment as a monthly base-pay amount."""
    basis = row.get("pay_basis")
    if basis == "MONTHLY":
        if not _monthly_cycle(first, last):
            raise PayrollPeriodError("pay_basis: MONTHLY requires one complete calendar month")
        return
    if basis == "WEEKLY":
        if last - first != timedelta(days=6):
            raise PayrollPeriodError("pay_basis: WEEKLY requires seven inclusive calendar days")
        return
    if basis == "ANNUAL":
        raw = row.get("installments_per_year")
        try:
            installments = Decimal(str(raw))
        except (InvalidOperation, ValueError) as exc:
            raise PayrollPeriodError("installments_per_year: explicit number required") from exc
        if installments == 12 and _monthly_cycle(first, last):
            return
        if installments == 52 and last - first == timedelta(days=6):
            return
        raise PayrollPeriodError(
            "pay_basis: ANNUAL supports only 12 monthly or 52 weekly preview installments; "
            "other payment schedules require an explicit schedule policy"
        )
    raise PayrollPeriodError("pay_basis: unsupported cycle")


def select_contracts_for_period(
    rows: Iterable[Mapping[str, Any]],
    *,
    period_from: str,
    period_to: str,
) -> tuple[dict[str, Any], ...]:
    """Select records with an EXACT already-declared calculation window.

    Historical/future non-intersecting periods are excluded. Even a single
    intersecting partial window is refused: no employment-day proration,
    effective-date inference, rounding or automatic contract inheritance.
    """
    first, last = _period(period_from, period_to)
    by_employee: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        worker = row.get("employee_id")
        if not isinstance(worker, str) or not worker.strip():
            raise PayrollPeriodError("employee_id: text identifier required")
        try:
            start = _date(row.get("calculation_period_from"), "calculation_period_from")
            end = _date(row.get("calculation_period_to"), "calculation_period_to")
        except PayrollPeriodError as exc:
            raise PayrollPeriodError("contract contains an invalid declared period") from exc
        if start > end:
            raise PayrollPeriodError("calculation_period: reversed date range")
        if start <= last and end >= first:
            if (start, end) != (first, last):
                raise PayrollPeriodError(
                    "calculation_period: partial coverage or mid-period contract change; "
                    "explicit segment/adjustment approval is required"
                )
            by_employee[worker].append(dict(row))
    if not by_employee:
        raise PayrollPeriodError("calculation_period: no exact matching contract rows")
    selected = []
    for worker in sorted(by_employee):
        matches = by_employee[worker]
        if len(matches) != 1:
            raise PayrollPeriodError("calculation_period: multiple selected contracts for a worker")
        _expected_cycle(matches[0], first, last)
        selected.append(matches[0])
    return tuple(selected)
