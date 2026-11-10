"""Map validated Worktime facts to payroll pay-item inputs without calculating money."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


class PayItemMappingError(RuntimeError):
    """Raised when Registry and Worktime contracts cannot be mapped safely."""

    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Pay item mapping failed: {message}")


def _registry_worktime_items(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in registry["items"]
        if item.get("worktime_linked") is True
        and "payroll_calculator" in item.get("allowed_sources", [])
    ]


def _single_worktime_value(row: dict[str, Any], source: str) -> Decimal | None:
    if source == "late_early_leave_minutes":
        return Decimal(str(row.get("late_minutes", 0))) + Decimal(str(row.get("early_leave_minutes", 0)))
    if source in {"weekly_holiday_eligibility", "unpaid_leave_hours"}:
        return None
    if source not in row:
        raise PayItemMappingError(f"Worktime source is missing from handoff: {source}")
    return Decimal(str(row[source]))


def _resolve_quantities(row: dict[str, Any], source: str | list[str]) -> dict[str, Decimal]:
    sources = [source] if isinstance(source, str) else source
    quantities: dict[str, Decimal] = {}
    for name in sources:
        value = _single_worktime_value(row, name)
        if value is not None and value != 0:
            if value < 0:
                raise PayItemMappingError(f"{name}: mapped quantity must not be negative")
            quantities[name] = value
    return quantities


def map_worktime_pay_items(
    worktime_row: dict[str, Any],
    registry: dict[str, Any],
) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []

    for item in _registry_worktime_items(registry):
        source = item.get("worktime_source")
        if not source:
            raise PayItemMappingError(f"{item['code']}: worktime_source is required")

        quantities = _resolve_quantities(worktime_row, source)
        if not quantities:
            continue

        unit = "minutes" if set(quantities) == {"late_early_leave_minutes"} else "hours"
        mapped.append(
            {
                "worker_id": worktime_row["worker_id"],
                "work_date": worktime_row["work_date"],
                "pay_item_code": item["code"],
                "source": "worktime",
                "worktime_source": source,
                "quantities": quantities,
                "quantity": sum(quantities.values(), Decimal("0")),
                "unit": unit,
            }
        )

    return mapped
