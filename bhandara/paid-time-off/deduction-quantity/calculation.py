"""Exact, independent conversion of approved leave hours into deduction days.

This module does not approve requests, decide eligibility, allocate grants, or
post to an employee leave ledger. The input is already approved by an external
system. Each request/date pair represents one approved day's usage.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any, Iterable, Mapping

INPUT_COLUMNS = ("request_id", "employee_id", "leave_date", "leave_type",
                 "duration_hours")
LEAVE_TYPES = frozenset({"연차", "대휴"})


def _identifier(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return ""
    return str(value).strip()


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("사용일이 YYYY-MM-DD 형식이 아닙니다")
    value = value.strip()
    if len(value) != 10:
        raise ValueError("사용일이 YYYY-MM-DD 형식이 아닙니다")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("사용일이 유효한 날짜가 아닙니다") from exc
    if parsed.isoformat() != value:
        raise ValueError("사용일이 YYYY-MM-DD 형식이 아닙니다")
    return parsed


def _hours(value: Any, label: str) -> Fraction:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{label}은(는) 양수여야 합니다")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label}은(는) 유효한 시간 숫자여야 합니다") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{label}은(는) 유한한 양수여야 합니다")
    return Fraction(number)


def quantity_text(value: Fraction) -> str:
    """Exact finite decimal, otherwise truncate at seven places (no rounding)."""
    if value < 0:
        raise ValueError("차감일수는 음수일 수 없습니다")
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        twos += 1
        denominator //= 2
    while denominator % 5 == 0:
        fives += 1
        denominator //= 5
    if denominator == 1:
        digits = max(twos, fives)
        scaled = value.numerator * (10 ** digits) // value.denominator
        return format(Decimal(scaled).scaleb(-digits), "f")
    scale = 10 ** 7
    scaled = value.numerator * scale // value.denominator
    whole, fraction = divmod(scaled, scale)
    return f"{whole}.{fraction:07d}"


def calculate_hours_deduction(
    duration_hours: Any, *, standard_daily_hours: Any = 8,
) -> Fraction:
    """One row's exact day quantity. The daily hours default is explicit: 8."""
    duration = _hours(duration_hours, "사용시간")
    daily = _hours(standard_daily_hours, "1일 기준시간")
    if duration > daily:
        raise ValueError("하루 사용시간이 1일 기준시간보다 큽니다")
    return duration / daily


def calculate_approved_rows(
    rows: Iterable[Mapping[str, Any]], *, standard_daily_hours: Any = 8,
) -> dict[str, Any]:
    """Calculate valid rows, report and skip invalid/duplicate rows independently.

    Multiple dates under one request_id are legitimate. The same request_id and
    leave_date appearing twice is ambiguous: *all* matching rows are skipped.
    Only rows with a valid employee_id contribute to employee summaries.
    """
    daily = _hours(standard_daily_hours, "1일 기준시간")
    source = list(rows)
    duplicates: Counter[tuple[str, date]] = Counter()
    for row in source:
        request_id = _identifier(row.get("request_id"))
        if not request_id:
            continue
        try:
            used_date = _date(row.get("leave_date"))
        except ValueError:
            continue
        duplicates[(request_id, used_date)] += 1

    quantities: dict[str, Fraction] = defaultdict(Fraction)
    calculated: Counter[str] = Counter()
    excluded: Counter[str] = Counter()
    details: list[dict[str, Any]] = []
    total_calculated = total_excluded = 0

    for position, row in enumerate(source, start=2):
        row_number = row.get("_excel_row", position)
        request_id = _identifier(row.get("request_id"))
        employee_id = _identifier(row.get("employee_id"))
        leave_type = row.get("leave_type")
        leave_type = leave_type.strip() if isinstance(leave_type, str) else leave_type
        original_date = row.get("leave_date")
        duration = row.get("duration_hours")
        reasons: list[str] = list(row.get("_source_errors", ()))
        used_date: date | None = None

        if not request_id:
            reasons.append("request_id 누락")
        if not employee_id:
            reasons.append("employee_id 누락")
        try:
            used_date = _date(original_date)
        except ValueError as exc:
            reasons.append(str(exc))
        if leave_type not in LEAVE_TYPES:
            reasons.append("leave_type 누락·미지원 (연차/대휴)")
        if request_id and used_date and duplicates[(request_id, used_date)] > 1:
            reasons.append("동일 request_id·leave_date 중복")
        quantity: Fraction | None = None
        try:
            quantity = calculate_hours_deduction(
                duration, standard_daily_hours=standard_daily_hours)
        except ValueError as exc:
            reasons.append(str(exc))

        if reasons:
            total_excluded += 1
            if employee_id:
                excluded[employee_id] += 1
            quantity = None
        else:
            assert quantity is not None
            total_calculated += 1
            quantities[employee_id] += quantity
            calculated[employee_id] += 1

        details.append({
            "excel_row": row_number,
            "request_id": request_id or None,
            "employee_id": employee_id or None,
            "leave_date": used_date.isoformat() if used_date else original_date,
            "leave_type": leave_type,
            "duration_hours": duration,
            "deduction_days": quantity_text(quantity) if quantity is not None else None,
            # Exact transport columns for downstream allocation: not 7-digit display.
            "exact_numerator": str(quantity.numerator) if quantity is not None else None,
            "exact_denominator": str(quantity.denominator) if quantity is not None else None,
            "status": "계산 제외" if reasons else "계산 완료",
            "reason": "; ".join(reasons),
        })

    summaries = []
    for employee_id in sorted(set(calculated) | set(excluded)):
        valid = calculated[employee_id]
        bad = excluded[employee_id]
        status = "일부 제외" if bad and valid else (
            "계산 제외" if bad else "계산 완료")
        summaries.append({
            "employee_id": employee_id,
            "deduction_days": quantity_text(quantities[employee_id]) if valid else None,
            "valid_rows": valid,
            "excluded_rows": bad,
            "status": status,
        })
    return {
        "summaries": summaries,
        "details": details,
        "calculated_rows": total_calculated,
        "excluded_rows": total_excluded,
        "standard_daily_hours": quantity_text(daily),
    }
