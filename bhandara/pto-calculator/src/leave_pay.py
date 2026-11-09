"""Assign company leave pay tiers to materialized daily event rows."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from .company_leave_policy import validate_pay_tiers


def _service_year_start(hire_date: date, work_date: date) -> date:
    year = work_date.year
    try:
        candidate = hire_date.replace(year=year)
    except ValueError:
        candidate = date(year, 2, 28)
    if candidate > work_date:
        year -= 1
        try:
            candidate = hire_date.replace(year=year)
        except ValueError:
            candidate = date(year, 2, 28)
    return candidate


def _continuous_case_groups(rows: list[dict]) -> dict[int, int]:
    groups: dict[int, int] = {}
    case = 0
    previous_date = None
    for index, row in enumerate(rows):
        current = row["event_date"]
        if previous_date is None or current > previous_date + timedelta(days=1):
            case += 1
        groups[index] = case
        previous_date = current
    return groups


def _accumulation_key(
    row: dict,
    *,
    basis: str,
    hire_date: date | None,
    continuous_case: int | None,
) -> tuple:
    if basis == "PER_REQUEST":
        request_id = row.get("request_id")
        if not request_id:
            raise ValueError("PER_REQUEST pay accumulation requires request_id")
        return ("REQUEST", request_id)
    if basis == "CALENDAR_YEAR":
        return ("CALENDAR_YEAR", row["event_date"].year)
    if basis == "SERVICE_YEAR":
        if hire_date is None:
            raise ValueError("SERVICE_YEAR pay accumulation requires hire_date")
        return ("SERVICE_YEAR", _service_year_start(hire_date, row["event_date"]))
    if basis == "CONTINUOUS_CASE":
        return ("CONTINUOUS_CASE", continuous_case)
    raise ValueError(f"unsupported accumulation basis: {basis}")


def _pay_status_for_day(day_number: int, tiers: list[dict]) -> str:
    for tier in tiers:
        if day_number < tier["from_day"]:
            continue
        if tier["to_day"] is None or day_number <= tier["to_day"]:
            return tier["pay_status"]
    raise ValueError(f"no pay tier covers accumulated day {day_number}")


def assign_leave_pay_tiers(
    event_rows: Iterable[dict],
    *,
    pay_rule: dict,
    hire_date: date | None = None,
) -> list[dict]:
    """Attach pay status by deterministic accumulation order.

    Pay status is company-policy metadata only. It does not determine PTO
    attendance credit.
    """
    validated = validate_pay_tiers(
        pay_rule["tiers"],
        accumulation_basis=pay_rule["accumulation_basis"],
    )
    basis = validated["accumulation_basis"]
    rows = sorted(
        (dict(row) for row in event_rows),
        key=lambda row: (row["event_date"], str(row.get("request_id") or "")),
    )

    case_groups = _continuous_case_groups(rows) if basis == "CONTINUOUS_CASE" else {}
    counters: dict[tuple, int] = {}

    for index, row in enumerate(rows):
        key = _accumulation_key(
            row,
            basis=basis,
            hire_date=hire_date,
            continuous_case=case_groups.get(index),
        )
        counters[key] = counters.get(key, 0) + 1
        accumulated_day = counters[key]
        row["pay_accumulation_basis"] = basis
        row["pay_accumulated_day"] = accumulated_day
        row["pay_status"] = _pay_status_for_day(
            accumulated_day,
            validated["tiers"],
        )

    return rows
