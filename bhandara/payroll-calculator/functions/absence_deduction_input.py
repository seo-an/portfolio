"""Convert explicit absence events and daily schedules into deduction-day input."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class AbsenceDeductionInputError(RuntimeError):
    """Raised when absence events cannot be converted into deduction days."""

    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Absence deduction input failed: {message}")


def _date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise AbsenceDeductionInputError(
                f"{field} must use YYYY-MM-DD: {value!r}"
            ) from exc
    raise AbsenceDeductionInputError(f"{field} must be a date or YYYY-MM-DD string")


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AbsenceDeductionInputError(
            f"{field} must be decimal-compatible"
        ) from exc
    if result < 0:
        raise AbsenceDeductionInputError(f"{field} must not be negative")
    return result


def build_deduction_day_input(
    events: list[dict[str, Any]],
    worktime_rows: list[dict[str, Any]],
    worker_id: str,
    payroll_period: str,
) -> dict[str, Any]:
    """Convert unpaid hours to schedule-relative deduction days.

    One scheduled day is 1.0 regardless of whether that worker's scheduled
    hours are 4, 8, or another positive value.
    """
    target_worker = str(worker_id).strip()
    if not target_worker:
        raise AbsenceDeductionInputError("worker_id must not be empty")

    try:
        year_text, month_text = str(payroll_period).split("-")
        year, month = int(year_text), int(month_text)
        date(year, month, 1)
    except (TypeError, ValueError) as exc:
        raise AbsenceDeductionInputError("payroll_period must use YYYY-MM") from exc

    schedules: dict[date, Decimal] = {}
    for row in worktime_rows:
        if str(row.get("worker_id", "")).strip() != target_worker:
            continue
        work_date = _date(row.get("work_date"), "work_date")
        if (work_date.year, work_date.month) != (year, month):
            continue
        if work_date in schedules:
            raise AbsenceDeductionInputError(
                f"duplicate worktime row for {target_worker} on {work_date.isoformat()}"
            )
        schedules[work_date] = _decimal(row.get("scheduled_hours"), "scheduled_hours")

    seen_events: set[tuple[str, date]] = set()
    lines: list[dict[str, Any]] = []
    total_days = Decimal("0")

    for event in events:
        if str(event.get("worker_id", "")).strip() != target_worker:
            continue
        work_date = _date(event.get("work_date"), "work_date")
        if (work_date.year, work_date.month) != (year, month):
            continue

        event_type = str(event.get("event_type", "")).strip()
        key = (target_worker, work_date)
        if key in seen_events:
            raise AbsenceDeductionInputError(
                f"overlapping absence events for {target_worker} on "
                f"{work_date.isoformat()}"
            )
        seen_events.add(key)

        scheduled_hours = schedules.get(work_date)
        if scheduled_hours is None:
            raise AbsenceDeductionInputError(
                f"scheduled_hours not found for {target_worker} on {work_date.isoformat()}"
            )
        if scheduled_hours <= 0:
            raise AbsenceDeductionInputError(
                f"absence event cannot be applied to non-scheduled day "
                f"{work_date.isoformat()}"
            )

        unpaid_hours = _decimal(event.get("unpaid_hours"), "unpaid_hours")
        if unpaid_hours <= 0:
            raise AbsenceDeductionInputError("unpaid_hours must be greater than zero")
        if unpaid_hours > scheduled_hours:
            raise AbsenceDeductionInputError(
                f"unpaid_hours exceeds scheduled_hours on {work_date.isoformat()}"
            )

        deduction_days = unpaid_hours / scheduled_hours
        total_days += deduction_days
        lines.append(
            {
                "worker_id": target_worker,
                "work_date": work_date,
                "event_type": event_type,
                "unpaid_hours": unpaid_hours,
                "scheduled_hours": scheduled_hours,
                "deduction_days": deduction_days,
            }
        )

    return {
        "worker_id": target_worker,
        "payroll_period": payroll_period,
        "deduction_days": total_days,
        "lines": lines,
    }
