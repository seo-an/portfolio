"""Build a traceable retroactive settlement from historical payroll results."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class RetroactiveSettlementError(RuntimeError):
    """Raised when a retroactive settlement cannot be built deterministically."""

    def __init__(self, message: str) -> None:
        super().__init__(
            f"❌ [payroll-calculator] Retroactive settlement failed: {message}"
        )


def _decimal(value: Any, field: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RetroactiveSettlementError(
            f"{field} must be decimal-compatible"
        ) from exc
    if not amount.is_finite() or amount < 0:
        raise RetroactiveSettlementError(
            f"{field} must be finite and non-negative"
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
            raise RetroactiveSettlementError(
                f"{field} must use YYYY-MM-DD: {value!r}"
            ) from exc
    raise RetroactiveSettlementError(
        f"{field} must be a date or YYYY-MM-DD string"
    )


def build_retroactive_settlement(
    origin_pay_item_code: Any,
    origin_from: Any,
    origin_to: Any,
    original_amount: Any,
    recalculated_amount: Any,
) -> dict[str, Any]:
    """Compare finalized historical amount with a recalculated amount."""
    code = str(origin_pay_item_code).strip() if origin_pay_item_code is not None else ""
    if not code:
        raise RetroactiveSettlementError(
            "origin_pay_item_code must not be empty"
        )

    period_from = _date(origin_from, "origin_from")
    period_to = _date(origin_to, "origin_to")
    if period_to < period_from:
        raise RetroactiveSettlementError(
            "origin_to precedes origin_from"
        )

    original = _decimal(original_amount, "original_amount")
    recalculated = _decimal(recalculated_amount, "recalculated_amount")
    difference = recalculated - original

    if difference > 0:
        settlement_pay_item_code = "retroactive_pay"
        direction = "pay"
    elif difference < 0:
        settlement_pay_item_code = "retroactive_deduction"
        direction = "deduction"
    else:
        settlement_pay_item_code = None
        direction = "none"

    return {
        "origin_pay_item_code": code,
        "origin_from": period_from,
        "origin_to": period_to,
        "original_amount": original,
        "recalculated_amount": recalculated,
        "difference": difference,
        "settlement_amount": abs(difference),
        "settlement_pay_item_code": settlement_pay_item_code,
        "direction": direction,
    }
