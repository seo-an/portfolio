"""Compose base and premium components into total worktime-linked payroll amounts."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


class WorktimePayCalculationError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Worktime pay calculation failed: {message}")


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise WorktimePayCalculationError(f"{field} must be decimal-compatible") from exc
    if result < 0:
        raise WorktimePayCalculationError(f"{field} must not be negative")
    return result


def calculate_worktime_pay_total(
    premium_result: dict[str, Any],
    base_component_policy: str,
) -> dict[str, Any]:
    """Add the 1.0 base component only when policy says it is separately payable."""
    if base_component_policy not in {"별도지급", "기지급", "중첩"}:
        raise WorktimePayCalculationError(
            "base component policy must be one of: 별도지급, 기지급, 중첩"
        )

    hourly = _decimal(premium_result["ordinary_hourly_wage"], "ordinary_hourly_wage")
    premium_amount = _decimal(premium_result["calculated_amount"], "premium_amount")
    components = premium_result.get("components", [])

    base_amount = Decimal("0")
    if base_component_policy == "별도지급":
        total_quantity = sum(
            (_decimal(item["quantity"], "quantity") for item in components),
            Decimal("0"),
        )
        base_amount = hourly * total_quantity

    return {
        "worker_id": premium_result["worker_id"],
        "work_date": premium_result["work_date"],
        "pay_item_code": premium_result["pay_item_code"],
        "base_component_policy": base_component_policy,
        "ordinary_hourly_wage": hourly,
        "base_amount": base_amount,
        "premium_amount": premium_amount,
        "calculated_amount": base_amount + premium_amount,
        "premium_components": components,
    }
