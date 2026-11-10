"""Aggregate deterministic payroll earnings and deductions before amount processing."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


class PayrollAggregationError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Payroll aggregation failed: {message}")


def _amount(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise PayrollAggregationError(f"{field} must be decimal-compatible") from exc


def _lines(source: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in items:
        code = item["pay_item_code"]
        result.append({
            **item,
            "pay_item_code": code,
            "source": source,
            "calculated_amount": _amount(
                item["calculated_amount"], f"{code}.calculated_amount"
            ),
        })
    return result


def aggregate_earnings(
    recurring_items: list[dict[str, Any]],
    worktime_items: list[dict[str, Any]],
    variable_items: list[dict[str, Any]],
    settlement_adjustment: Any = Decimal("0"),
    deduction_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Aggregate earnings and explicit deductions.

    deduction_items is optional to preserve the existing caller contract.
    """
    earning_lines = []
    earning_lines.extend(_lines("compensation", recurring_items))
    earning_lines.extend(_lines("worktime", worktime_items))
    earning_lines.extend(_lines("payroll_input", variable_items))

    deduction_lines = _lines("payroll_calculator", deduction_items or [])

    gross = sum(
        (line["calculated_amount"] for line in earning_lines), Decimal("0")
    )
    deductions = sum(
        (line["calculated_amount"] for line in deduction_lines), Decimal("0")
    )
    if deductions < 0:
        raise PayrollAggregationError("deduction total must not be negative")

    adjustment = _amount(settlement_adjustment, "settlement_adjustment")
    return {
        "earning_lines": earning_lines,
        "deduction_lines": deduction_lines,
        "calculated_gross_earnings": gross,
        "calculated_total_deductions": deductions,
        "settlement_adjustment": adjustment,
        "calculated_payable_before_amount_processing": (
            gross - deductions + adjustment
        ),
    }
