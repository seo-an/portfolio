"""Calculate statutory premium components from Worktime quantities and ordinary hourly wage."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


class PremiumCalculationError(RuntimeError):
    """Raised when a premium amount cannot be calculated deterministically."""

    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Premium calculation failed: {message}")


def _decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except Exception as exc:
        raise PremiumCalculationError(f"{field} must be decimal-compatible") from exc
    if number < 0:
        raise PremiumCalculationError(f"{field} must not be negative")
    return number


def calculate_premium_item(
    mapped_item: dict[str, Any],
    ordinary_hourly_wage: Any,
    payroll_legal_policy: dict[str, Any],
) -> dict[str, Any]:
    code = mapped_item["pay_item_code"]
    rule = payroll_legal_policy.get("premium_rules", {}).get(code)
    if rule is None:
        raise PremiumCalculationError(f"no premium rule for {code}")
    if rule.get("component") != "가산분":
        raise PremiumCalculationError(f"{code}: unsupported component semantics")

    hourly = _decimal(ordinary_hourly_wage, "ordinary_hourly_wage")
    quantities = mapped_item.get("quantities", {})
    components: list[dict[str, Any]] = []

    source_rule = rule["worktime_source"]
    if isinstance(source_rule, str):
        quantity = _decimal(quantities.get(source_rule, 0), source_rule)
        multiplier = _decimal(rule["ordinary_hourly_wage_multiplier"], "multiplier")
        components.append({
            "worktime_source": source_rule,
            "quantity": quantity,
            "multiplier": multiplier,
            "calculated_amount": hourly * quantity * multiplier,
        })
    elif isinstance(source_rule, dict):
        for source, raw_multiplier in source_rule.items():
            quantity = _decimal(quantities.get(source, 0), source)
            multiplier = _decimal(raw_multiplier, f"{source}.multiplier")
            components.append({
                "worktime_source": source,
                "quantity": quantity,
                "multiplier": multiplier,
                "calculated_amount": hourly * quantity * multiplier,
            })
    else:
        raise PremiumCalculationError(f"{code}: invalid worktime_source rule")

    return {
        "worker_id": mapped_item["worker_id"],
        "work_date": mapped_item["work_date"],
        "pay_item_code": code,
        "component": "가산분",
        "ordinary_hourly_wage": hourly,
        "components": components,
        "calculated_amount": sum(
            (item["calculated_amount"] for item in components), Decimal("0")
        ),
    }
