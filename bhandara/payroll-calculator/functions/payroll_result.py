"""Normalize payroll calculation outputs into a common Payroll Result contract."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


class PayrollResultError(RuntimeError):
    """Raised when a payroll calculation result cannot be normalized."""

    def __init__(self, message: str) -> None:
        super().__init__(f"[payroll-calculator] Payroll result failed: {message}")


def _decimal(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PayrollResultError("calculated_amount must be decimal-compatible") from exc
    if not amount.is_finite() or amount < 0:
        raise PayrollResultError(
            "calculated_amount must be finite and non-negative"
        )
    return amount


def _date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise PayrollResultError(
                f"{field} must use YYYY-MM-DD: {value!r}"
            ) from exc
    raise PayrollResultError(f"{field} must be a date or YYYY-MM-DD string")


def _registry_item(registry: Mapping[str, Any], pay_item_code: str) -> Mapping[str, Any]:
    items = registry.get("items")
    if not isinstance(items, list):
        raise PayrollResultError("registry.items must be a list")
    for item in items:
        if isinstance(item, Mapping) and item.get("code") == pay_item_code:
            return item
    raise PayrollResultError(f"unknown pay_item_code: {pay_item_code}")


def _direction(item: Mapping[str, Any], pay_item_code: str) -> str:
    item_type = item.get("type")
    if item_type == "지급":
        return "pay"
    if item_type == "공제":
        return "deduction"
    if item_type == "정산":
        if pay_item_code == "retroactive_pay":
            return "pay"
        if pay_item_code == "retroactive_deduction":
            return "deduction"
        return "settlement"
    raise PayrollResultError(f"unsupported registry item type: {item_type!r}")


def build_payroll_result(
    worker_id: Any,
    payroll_period: Any,
    pay_item_code: Any,
    calculated_amount: Any,
    registry: Mapping[str, Any],
    *,
    origin_from: Any | None = None,
    origin_to: Any | None = None,
    origin_pay_item_code: Any | None = None,
    source: Any | None = None,
    calculation_trace: Any | None = None,
) -> dict[str, Any]:
    """Build a common calculation-stage result without final amount processing."""
    worker = str(worker_id).strip() if worker_id is not None else ""
    if not worker:
        raise PayrollResultError("worker_id must not be empty")

    period = str(payroll_period).strip() if payroll_period is not None else ""
    if not period:
        raise PayrollResultError("payroll_period must not be empty")

    code = str(pay_item_code).strip() if pay_item_code is not None else ""
    if not code:
        raise PayrollResultError("pay_item_code must not be empty")

    item = _registry_item(registry, code)
    amount = _decimal(calculated_amount)

    has_origin_from = origin_from not in (None, "")
    has_origin_to = origin_to not in (None, "")
    if has_origin_from != has_origin_to:
        raise PayrollResultError("origin_from and origin_to must be provided together")

    normalized_origin_from = _date(origin_from, "origin_from") if has_origin_from else None
    normalized_origin_to = _date(origin_to, "origin_to") if has_origin_to else None
    if (
        normalized_origin_from is not None
        and normalized_origin_to is not None
        and normalized_origin_to < normalized_origin_from
    ):
        raise PayrollResultError("origin_to precedes origin_from")

    origin_code = (
        str(origin_pay_item_code).strip()
        if origin_pay_item_code not in (None, "")
        else None
    )
    if item.get("trace_origin") is True:
        if not origin_code:
            raise PayrollResultError(
                f"{code} requires origin_pay_item_code"
            )
        if normalized_origin_from is None:
            raise PayrollResultError(
                f"{code} requires origin_from and origin_to"
            )

    normalized_source = str(source).strip() if source not in (None, "") else None

    return {
        "worker_id": worker,
        "payroll_period": period,
        "pay_item_code": code,
        "item_type": item.get("type"),
        "direction": _direction(item, code),
        "calculated_amount": amount,
        "origin_pay_item_code": origin_code,
        "origin_from": normalized_origin_from,
        "origin_to": normalized_origin_to,
        "source": normalized_source,
        "calculation_trace": calculation_trace,
    }
