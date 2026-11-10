"""Derive minute-precise daily Worktime facts from approved clock/schedule inputs.

This is a conservative standard-hours adapter, not a legal determination for
flexible/selective regimes. Ambiguities are flagged and cannot be period-closed.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


class DailyWorktimeError(ValueError):
    pass


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise DailyWorktimeError(f"{field} must be numeric")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DailyWorktimeError(f"{field} must be numeric") from exc
    if not number.is_finite() or number < 0:
        raise DailyWorktimeError(f"{field} must be finite and non-negative")
    return number


def _clock(value: Any, work_date: date, field: str) -> tuple[datetime, bool]:
    if not isinstance(value, str) or not value.strip():
        raise DailyWorktimeError(f"{field} is required")
    raw = value.strip()
    time_only = "T" not in raw and " " not in raw
    try:
        result = datetime.fromisoformat(f"{work_date.isoformat()}T{raw}" if time_only else raw)
    except ValueError as exc:
        raise DailyWorktimeError(f"{field} must be HH:MM or ISO datetime") from exc
    if result.tzinfo is not None or result.second or result.microsecond:
        raise DailyWorktimeError(f"{field} requires naive minute precision")
    if result.date() < work_date or result.date() > work_date + timedelta(days=1):
        raise DailyWorktimeError(f"{field} outside work_date range")
    return result, time_only


def _interval(row: Mapping[str, Any], day: date, start_name: str, end_name: str):
    start, _ = _clock(row.get(start_name), day, start_name)
    end, short_end = _clock(row.get(end_name), day, end_name)
    if end <= start and short_end:
        end += timedelta(days=1)
    length = int((end - start).total_seconds() // 60)
    if not 0 < length <= 24 * 60:
        raise DailyWorktimeError(f"{start_name}/{end_name}: duration must be (0, 24h]")
    return start, end, length


def _night_minutes(start: datetime, end: datetime) -> int:
    total = 0
    for offset in (-1, 0, 1):
        midnight = datetime.combine(start.date() + timedelta(days=offset), datetime.min.time())
        night_start = midnight + timedelta(hours=22)
        night_end = midnight + timedelta(days=1, hours=6)
        total += max(0, int((min(end, night_end) - max(start, night_start)).total_seconds() // 60))
    return total


def _hours(minutes: int) -> Decimal:
    return Decimal(minutes) / Decimal(60)


def _flag(code: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": "REVIEW", "message": message}


def _reference(value: Any) -> str:
    """Normalize nullable approval/source identifiers without treating None as 'None'."""
    return "" if value is None else str(value).strip()


def calculate_daily_worktime(row: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate Worktime Result fields; never silently approve legal exceptions."""
    worker = _reference(row.get("worker_id"))
    if not worker:
        raise DailyWorktimeError("worker_id is required")
    try:
        day = date.fromisoformat(str(row["work_date"]))
    except (KeyError, ValueError) as exc:
        raise DailyWorktimeError("work_date must be YYYY-MM-DD") from exc

    if not isinstance(row.get("holiday_work"), bool):
        raise DailyWorktimeError("holiday_work must be explicitly true or false")
    schedule_start, schedule_end, scheduled_minutes = _interval(
        row, day, "scheduled_start", "scheduled_end")
    actual_start, actual_end, gross_minutes = _interval(
        row, day, "clock_in", "clock_out")
    break_minutes = _decimal(row.get("break_min"), "break_min")
    if break_minutes != break_minutes.to_integral_value() or break_minutes >= gross_minutes:
        raise DailyWorktimeError("break_min must be an integer smaller than gross duration")
    net_minutes = gross_minutes - int(break_minutes)
    scheduled_break = _decimal(row.get("scheduled_break_min", break_minutes), "scheduled_break_min")
    if scheduled_break != scheduled_break.to_integral_value() or scheduled_break >= scheduled_minutes:
        raise DailyWorktimeError("scheduled_break_min must be an integer smaller than scheduled duration")
    scheduled_minutes -= int(scheduled_break)

    system = _reference(row.get("worktime_system"))
    rule_ref = _reference(row.get("rule_ref"))
    if not system or not rule_ref:
        raise DailyWorktimeError("worktime_system and rule_ref are required")

    holiday = row["holiday_work"]
    standard_day_minutes = 480
    ordinary_minutes = 0 if holiday else min(net_minutes, scheduled_minutes, standard_day_minutes)
    overtime_minutes = 0 if holiday else max(0, net_minutes - standard_day_minutes)
    night_gross = _night_minutes(actual_start, actual_end)
    flags = []
    if system != "standard":
        flags.append(_flag("NON_STANDARD_SETTLEMENT_REVIEW", "기간제 근로시간제는 별도 법정 정산 검토 필요"))
    if not holiday and ordinary_minutes + overtime_minutes != net_minutes:
        flags.append(_flag("UNCLASSIFIED_HOURS_REVIEW", "소정시간 초과·법정 연장 미만 근로의 임금처리 검토 필요"))
    if scheduled_minutes > standard_day_minutes and not holiday:
        flags.append(_flag("LONG_SCHEDULE_REVIEW", "일 8시간 초과 소정시간 검토 필요"))
    if overtime_minutes and not _reference(row.get("overtime_approval_ref")):
        flags.append(_flag("OVERTIME_APPROVAL_MISSING", "연장근로 승인 근거 누락"))
    if holiday and not _reference(row.get("holiday_approval_ref")):
        flags.append(_flag("HOLIDAY_APPROVAL_MISSING", "휴일근로 승인 근거 누락"))
    if night_gross and break_minutes:
        flags.append(_flag("NIGHT_BREAK_ALLOCATION_REQUIRED", "휴게시간의 야간 중첩 위치 미확정"))
    if net_minutes < scheduled_minutes:
        flags.append(_flag("SHORT_WORK_REVIEW", "소정시간 미달 사유·유급처리 확인 필요"))
    if not _reference(row.get("approval_ref")):
        flags.append(_flag("TIMESHEET_APPROVAL_MISSING", "근태기록 승인 근거 누락"))

    late = max(0, int((actual_start - schedule_start).total_seconds() // 60))
    early = max(0, int((schedule_end - actual_end).total_seconds() // 60))
    if (late or early) and not _reference(row.get("schedule_variance_approval_ref")):
        flags.append(_flag("SCHEDULE_VARIANCE_REVIEW", "지각·조퇴·시차 근로의 승인 및 임금처리 확인 필요"))
    holiday_within = min(net_minutes, 480) if holiday else 0
    holiday_over = max(0, net_minutes - 480) if holiday else 0
    absence = _decimal(row.get("approved_absence_hours", 0), "approved_absence_hours")
    if absence and not _reference(row.get("absence_approval_ref")):
        flags.append(_flag("ABSENCE_APPROVAL_MISSING", "결근시간 승인 근거 누락"))

    return {
        "worker_id": worker,
        "work_date": day.isoformat(),
        "worktime_system": system,
        "rule_ref": rule_ref,
        "scheduled_hours": _hours(scheduled_minutes),
        "worked_hours": _hours(net_minutes),
        "ordinary_hours": _hours(ordinary_minutes),
        "overtime_hours": _hours(overtime_minutes),
        # Do not publish possibly overstated night hours when break allocation is unknown.
        "night_hours": _hours(night_gross) if not break_minutes else Decimal("0"),
        "holiday_work_hours_within_8": _hours(holiday_within),
        "holiday_work_hours_over_8": _hours(holiday_over),
        "absence_hours": absence,
        "late_minutes": late,
        "early_leave_minutes": early,
        "validation_flags": flags,
        "approval_ref": _reference(row.get("approval_ref")),
        "input_source_ref": _reference(row.get("input_source_ref")),
    }


def calculate_worktime_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise DailyWorktimeError("rows must be a list")
    results = [calculate_daily_worktime(row) for row in rows]
    keys = [(item["worker_id"], item["work_date"]) for item in results]
    if len(keys) != len(set(keys)):
        raise DailyWorktimeError("duplicate worker_id/work_date")
    return sorted(results, key=lambda item: (item["worker_id"], item["work_date"]))
