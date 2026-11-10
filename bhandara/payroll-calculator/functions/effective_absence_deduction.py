"""Calculate absence deductions against compensation effective on each event date."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

try:
    from .absence_deduction import calculate_statutory_fallback
    from .compensation_resolver import resolve_compensation
except ImportError:
    from absence_deduction import calculate_statutory_fallback
    from compensation_resolver import resolve_compensation


PAY_ITEM_BY_EVENT_TYPE = {
    "absence": "absence_deduction",
    "unpaid_leave": "unpaid_leave_deduction",
}


class EffectiveAbsenceDeductionError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(
            f"❌ [payroll-calculator] Effective absence deduction failed: {message}"
        )


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise EffectiveAbsenceDeductionError(
            f"work_date must use YYYY-MM-DD: {value!r}"
        ) from exc


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise EffectiveAbsenceDeductionError(
            f"{field} must be decimal-compatible"
        ) from exc
    if result < 0:
        raise EffectiveAbsenceDeductionError(f"{field} must not be negative")
    return result


def build_effective_absence_deduction_lines(
    events: list[dict[str, Any]],
    worktime_rows: list[dict[str, Any]],
    compensation_rows: list[dict[str, Any]],
    worker_id: str,
    payroll_period: str,
    scheduled_workdays: Any,
    paid_treatment_days: Any,
) -> list[dict[str, Any]]:
    """Resolve monthly base salary per event date and aggregate by deduction item."""
    target_worker = str(worker_id).strip()
    schedule_by_date = {}
    for row in worktime_rows:
        if str(row.get("worker_id", "")).strip() != target_worker:
            continue
        work_date = _date(row.get("work_date"))
        if work_date in schedule_by_date:
            raise EffectiveAbsenceDeductionError(
                f"duplicate worktime row on {work_date.isoformat()}"
            )
        schedule_by_date[work_date] = _decimal(
            row.get("scheduled_hours"), "scheduled_hours"
        )

    traces: dict[str, list[dict[str, Any]]] = defaultdict(list)
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    days: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    seen: set[date] = set()

    for event in events:
        if str(event.get("worker_id", "")).strip() != target_worker:
            continue
        work_date = _date(event.get("work_date"))
        if work_date.strftime("%Y-%m") != payroll_period:
            continue

        event_type = str(event.get("event_type", "")).strip()
        if event_type not in PAY_ITEM_BY_EVENT_TYPE:
            raise EffectiveAbsenceDeductionError(
                f"unsupported event_type: {event_type}"
            )
        if work_date in seen:
            raise EffectiveAbsenceDeductionError(
                f"overlapping absence events on {work_date.isoformat()}"
            )
        seen.add(work_date)

        scheduled_hours = schedule_by_date.get(work_date)
        if scheduled_hours is None:
            raise EffectiveAbsenceDeductionError(
                f"scheduled_hours not found on {work_date.isoformat()}"
            )
        if scheduled_hours <= 0:
            raise EffectiveAbsenceDeductionError(
                f"absence event cannot be applied to non-scheduled day "
                f"{work_date.isoformat()}"
            )

        unpaid_hours = _decimal(event.get("unpaid_hours"), "unpaid_hours")
        if unpaid_hours <= 0:
            raise EffectiveAbsenceDeductionError(
                "unpaid_hours must be greater than zero"
            )
        if unpaid_hours > scheduled_hours:
            raise EffectiveAbsenceDeductionError(
                f"unpaid_hours exceeds scheduled_hours on {work_date.isoformat()}"
            )

        deduction_days = unpaid_hours / scheduled_hours
        compensation = resolve_compensation(
            compensation_rows, target_worker, work_date
        )
        monthly_amount = compensation.get("base_salary")
        if monthly_amount is None:
            raise EffectiveAbsenceDeductionError(
                f"base_salary not found on {work_date.isoformat()}"
            )

        calculation = calculate_statutory_fallback(
            monthly_amount=monthly_amount,
            payroll_period=payroll_period,
            deduction_days=deduction_days,
            scheduled_workdays=scheduled_workdays,
            paid_treatment_days=paid_treatment_days,
        )
        pay_item_code = PAY_ITEM_BY_EVENT_TYPE[event_type]
        totals[pay_item_code] += calculation["selected_amount"]
        days[pay_item_code] += deduction_days
        traces[pay_item_code].append({
            "work_date": work_date,
            "event_type": event_type,
            "unpaid_hours": unpaid_hours,
            "scheduled_hours": scheduled_hours,
            "deduction_days": deduction_days,
            "monthly_amount": monthly_amount,
            "compensation_effective_from": compensation["effective_from"],
            "compensation_effective_to": compensation["effective_to"],
            "calculation_trace": calculation,
        })

    lines = []
    for event_type in ("absence", "unpaid_leave"):
        pay_item_code = PAY_ITEM_BY_EVENT_TYPE[event_type]
        if pay_item_code not in totals:
            continue
        lines.append({
            "pay_item_code": pay_item_code,
            "calculated_amount": totals[pay_item_code],
            "deduction_days": days[pay_item_code],
            "event_lines": traces[pay_item_code],
        })
    return lines
