"""Aggregate Payroll Results before final amount processing."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


class PayrollTotalsError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Payroll totals failed: {message}")


def _amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PayrollTotalsError("calculated_amount must be decimal-compatible") from exc
    if not amount.is_finite() or amount < 0:
        raise PayrollTotalsError("calculated_amount must be finite and non-negative")
    return amount


def aggregate_payroll_results(
    results: Iterable[Mapping[str, Any]],
    worker_id: Any,
    payroll_period: Any,
    settlement_adjustment: Any = Decimal("0"),
) -> dict[str, Any]:
    """Aggregate positive-magnitude Payroll Results into a net payable amount."""
    worker = str(worker_id).strip()
    period = str(payroll_period).strip()
    if not worker:
        raise PayrollTotalsError("worker_id must not be empty")
    if not period:
        raise PayrollTotalsError("payroll_period must not be empty")

    pay_total = Decimal("0")
    deduction_total = Decimal("0")
    settlement_total = Decimal("0")
    selected = []

    for result in results:
        if str(result.get("worker_id", "")).strip() != worker:
            continue
        if str(result.get("payroll_period", "")).strip() != period:
            continue

        amount = _amount(result.get("calculated_amount"))
        direction = result.get("direction")
        if direction == "pay":
            pay_total += amount
        elif direction == "deduction":
            deduction_total += amount
        elif direction == "settlement":
            settlement_total += amount
        else:
            raise PayrollTotalsError(f"unsupported direction: {direction!r}")
        selected.append(result)

    try:
        adjustment = Decimal(str(settlement_adjustment))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PayrollTotalsError("settlement_adjustment must be decimal-compatible") from exc
    if not adjustment.is_finite():
        raise PayrollTotalsError("settlement_adjustment must be finite")

    net = pay_total - deduction_total + settlement_total + adjustment
    if net < 0:
        raise PayrollTotalsError("net payable amount must not be negative")

    return {
        "worker_id": worker,
        "payroll_period": period,
        "pay_total": pay_total,
        "deduction_total": deduction_total,
        "settlement_total": settlement_total,
        "settlement_adjustment": adjustment,
        "calculated_net_amount": net,
        "result_count": len(selected),
    }
