"""Validate employment and pay-item eligibility facts for Payroll."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping


PAYABLE_RULES = {
    "from_eligibility_date",
    "next_month",
    "eligibility_month_full",
}


class PayrollFactContractError(ValueError):
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
            raise PayrollFactContractError(
                f"{field} must use YYYY-MM-DD: {value!r}"
            ) from exc
    raise PayrollFactContractError(
        f"{field} must be a date or YYYY-MM-DD string"
    )


def _optional_date(value: Any, field: str) -> date | None:
    if value in (None, ""):
        return None
    return _date(value, field)


def _worker_id(row: Mapping[str, Any]) -> str:
    worker_id = str(row.get("worker_id", "")).strip()
    if not worker_id:
        raise PayrollFactContractError("worker_id is required")
    return worker_id


def validate_employment_fact(row: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise PayrollFactContractError("employment fact must be a mapping")
    worker_id = _worker_id(row)
    employment_from = _date(row.get("employment_from"), "employment_from")
    employment_to = _optional_date(row.get("employment_to"), "employment_to")
    if employment_to is not None and employment_to < employment_from:
        raise PayrollFactContractError(
            f"{worker_id}: employment_to precedes employment_from"
        )
    return {
        "worker_id": worker_id,
        "employment_from": employment_from,
        "employment_to": employment_to,
    }


def validate_pay_item_eligibility(
    row: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise PayrollFactContractError("eligibility fact must be a mapping")
    worker_id = _worker_id(row)
    pay_item_code = str(row.get("pay_item_code", "")).strip()
    if not pay_item_code:
        raise PayrollFactContractError("pay_item_code is required")

    known_codes = {
        str(item.get("code"))
        for item in registry.get("items", [])
        if isinstance(item, Mapping)
    }
    if pay_item_code not in known_codes:
        raise PayrollFactContractError(
            f"unknown pay_item_code: {pay_item_code}"
        )

    eligibility_from = _date(row.get("eligibility_from"), "eligibility_from")
    eligibility_to = _optional_date(row.get("eligibility_to"), "eligibility_to")
    if eligibility_to is not None and eligibility_to < eligibility_from:
        raise PayrollFactContractError(
            f"{worker_id}/{pay_item_code}: eligibility_to precedes eligibility_from"
        )

    payable_rule = str(row.get("payable_rule", "")).strip()
    if payable_rule not in PAYABLE_RULES:
        raise PayrollFactContractError(
            f"{worker_id}/{pay_item_code}: unsupported payable_rule: {payable_rule!r}"
        )

    return {
        "worker_id": worker_id,
        "pay_item_code": pay_item_code,
        "eligibility_from": eligibility_from,
        "eligibility_to": eligibility_to,
        "payable_rule": payable_rule,
    }
