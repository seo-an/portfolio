"""Apply final payroll amount processing without mutating the Settlement Ledger."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any


class AmountProcessingError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Amount processing failed: {message}")


def _decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AmountProcessingError(f"{field} must be decimal-compatible") from exc


def truncate_to_unit(amount: Decimal, unit: Decimal) -> Decimal:
    if unit <= 0:
        raise AmountProcessingError("unit must be greater than zero")
    return (amount / unit).to_integral_value(rounding=ROUND_DOWN) * unit


def process_final_amount(
    worker_id: str,
    payroll_period: str,
    amount: Any,
    policy: dict[str, Any],
) -> dict[str, Any]:
    normalized_worker_id = str(worker_id).strip()
    if not normalized_worker_id:
        raise AmountProcessingError("worker_id must not be empty")

    source_amount = _decimal(amount, "amount")
    if source_amount < 0:
        raise AmountProcessingError("final payable amount must not be negative")

    config = policy.get("amount_processing", {})
    if config.get("apply_at") != "최종지급액":
        raise AmountProcessingError("v0.1 supports amount_processing.apply_at=최종지급액 only")
    if config.get("method") != "절사":
        raise AmountProcessingError("v0.1 supports amount_processing.method=절사 only")

    unit = _decimal(config.get("unit"), "amount_processing.unit")
    payable_amount = truncate_to_unit(source_amount, unit)
    remainder = source_amount - payable_amount

    ledger_request = None
    if remainder:
        remainder_policy = config.get("remainder", {})
        if remainder_policy.get("handling") != "settlement_ledger":
            raise AmountProcessingError("non-zero remainder requires settlement_ledger handling")
        transaction_type = str(remainder_policy.get("transaction_type", "")).strip()
        if not transaction_type:
            raise AmountProcessingError("remainder.transaction_type is required")
        ledger_request = {
            "worker_id": normalized_worker_id,
            "transaction_type": transaction_type,
            "origin_period": payroll_period,
            "origin_pay_item_code": "",
            "amount": remainder,
            "direction": "지급",
            "settlement_period": "",
            "related_transaction_id": "",
            "note": "Final payroll amount truncation remainder",
        }

    return {
        "worker_id": normalized_worker_id,
        "payroll_period": payroll_period,
        "calculated_amount": source_amount,
        "payable_amount": payable_amount,
        "rounding_adjustment": payable_amount - source_amount,
        "rounding_remainder": remainder,
        "ledger_transaction_request": ledger_request,
    }
