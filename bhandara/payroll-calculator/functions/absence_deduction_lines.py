"""Build traceable Payroll deduction lines from normalized absence events."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

try:
    from .absence_deduction import calculate_statutory_fallback
    from .absence_deduction_input import build_deduction_day_input
except ImportError:
    from absence_deduction import calculate_statutory_fallback
    from absence_deduction_input import build_deduction_day_input


PAY_ITEM_BY_EVENT_TYPE = {
    "absence": "absence_deduction",
    "unpaid_leave": "unpaid_leave_deduction",
}


class AbsenceDeductionLineError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Absence deduction line failed: {message}")


def build_absence_deduction_lines(
    events: list[dict[str, Any]],
    worktime_rows: list[dict[str, Any]],
    worker_id: str,
    payroll_period: str,
    monthly_amount: Any,
    scheduled_workdays: Any,
    paid_treatment_days: Any,
) -> list[dict[str, Any]]:
    """Create separate deduction lines for absence and unpaid leave."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        event_type = str(event.get("event_type", "")).strip()
        if event_type not in PAY_ITEM_BY_EVENT_TYPE:
            raise AbsenceDeductionLineError(f"unsupported event_type: {event_type}")
        grouped[event_type].append(event)

    lines = []
    for event_type in ("absence", "unpaid_leave"):
        event_rows = grouped.get(event_type, [])
        if not event_rows:
            continue

        deduction_input = build_deduction_day_input(
            event_rows,
            worktime_rows,
            worker_id,
            payroll_period,
        )
        if deduction_input["deduction_days"] == Decimal("0"):
            continue

        calculation = calculate_statutory_fallback(
            monthly_amount=monthly_amount,
            payroll_period=payroll_period,
            deduction_days=deduction_input["deduction_days"],
            scheduled_workdays=scheduled_workdays,
            paid_treatment_days=paid_treatment_days,
        )
        lines.append({
            "pay_item_code": PAY_ITEM_BY_EVENT_TYPE[event_type],
            "calculated_amount": calculation["selected_amount"],
            "event_type": event_type,
            "deduction_days": deduction_input["deduction_days"],
            "event_lines": deduction_input["lines"],
            "calculation_trace": calculation,
        })

    return lines
