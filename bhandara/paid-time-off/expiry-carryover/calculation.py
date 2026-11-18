"""Independent PTO expiry/carryover classification at a closing boundary.

This module does not allocate requests, choose expiry dates, amend rights,
decide cash liability or call another PTO module. All validity dates, grant
balances and closing references must be provided by the Tool layer.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any, Iterable, Mapping


def closing_boundary(closing_id: str) -> date:
    """Closing-1.4-2025 => March 31, 2025; quarter is calendar-aligned."""
    if not isinstance(closing_id, str):
        raise ValueError("closing_id가 올바르지 않습니다")
    match = re.fullmatch(r"Closing-([1-4])\.4-([0-9]{4})", closing_id)
    if match is None:
        raise ValueError("closing_id는 Closing-1.4-2025 형식이어야 합니다")
    quarter, year = int(match.group(1)), int(match.group(2))
    month = quarter * 3
    try:
        return date(year, month, calendar.monthrange(year, month)[1])
    except ValueError as exc:
        raise ValueError("closing_id의 연도가 올바르지 않습니다") from exc


def _date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        raise ValueError(f"{field}: 날짜만 허용")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or len(value.strip()) != 10:
        raise ValueError(f"{field}: YYYY-MM-DD 필요")
    try:
        converted = date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field}: 날짜 오류") from exc
    if converted.isoformat() != value.strip():
        raise ValueError(f"{field}: YYYY-MM-DD 필요")
    return converted


def _nonnegative(value: Any) -> Fraction:
    if value is None or isinstance(value, bool):
        raise ValueError("발생 건별 잔여 수량 누락")
    if isinstance(value, Fraction):
        number = value
    else:
        try:
            decimal = Decimal(str(value).strip())
            if not decimal.is_finite():
                raise ValueError
            number = Fraction(decimal)
        except (InvalidOperation, ValueError, TypeError, ZeroDivisionError) as exc:
            raise ValueError("발생 건별 잔여 수량 오류") from exc
    if number < 0:
        raise ValueError("음수 부족분은 발생 건이 아닌 신청별 기록으로 전달해야 합니다")
    return number


def evaluate_expiry_carryover(
    balances: Iterable[Mapping[str, Any]],
    *,
    closing_id: str,
    balance_as_of: date,
) -> dict[str, Any]:
    """Classify a grant's *confirmed balance at this closing boundary*.

    The confirmed closing ID already provides the quarter's period_end;
    a separate user-entered opening date is not required. 'balance_as_of'
    validates that the upstream allocation snapshot covers the same date,
    rather than silently treating today's balance as a past closing balance.
    Any invalid grant is skipped with a reason, not assigned a guessed date.
    """
    boundary = closing_boundary(closing_id)
    if _date(balance_as_of, "balance_as_of") != boundary:
        raise ValueError("잔여 산정 기준일과 Closing 마감일이 다릅니다")
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    source = list(balances)
    counts = {}
    for row in source:
        identifier = str(row.get("grant_id") or "").strip()
        if identifier:
            counts[identifier] = counts.get(identifier, 0) + 1
    for row_number, row in enumerate(source, 1):
        try:
            grant_id = str(row.get("grant_id") or "").strip()
            employee = str(row.get("employee_id") or "").strip()
            leave_type = str(row.get("leave_type") or "").strip()
            if not grant_id or not employee or leave_type not in ("연차", "대휴"):
                raise ValueError("grant_id/employee_id/leave_type 누락·오류")
            if counts.get(grant_id, 0) > 1:
                raise ValueError("중복 grant_id")
            if grant_id in seen:
                raise ValueError("중복 grant_id")
            seen.add(grant_id)
            start = _date(row.get("valid_from"), "valid_from")
            expiry = _date(row.get("expires_on"), "expires_on")
            if start > expiry:
                raise ValueError("유효기간 순서 오류")
            remaining = _nonnegative(row.get("remaining_days"))
            if remaining == 0:
                status = "잔여 없음"
            elif start > boundary:
                status = "미도래"
            elif expiry <= boundary:
                status = "만료"
            else:
                status = "이월"
            expiry_days = remaining if status == "만료" else Fraction(0)
            carryover_days = remaining if status == "이월" else Fraction(0)
            entries.append({
                "grant_id": grant_id, "employee_id": employee,
                "leave_type": leave_type, "valid_from": start.isoformat(),
                "expires_on": expiry.isoformat(), "remaining_days": remaining,
                "expiry_days": expiry_days, "carryover_days": carryover_days,
                "status": status,
                "compensation_review": bool(
                    leave_type == "연차" and expiry_days > 0),
                "source_ref": row.get("source_ref"),
            })
        except ValueError as exc:
            errors.append({
                "row": row_number, "grant_id": row.get("grant_id"),
                "status": "계산 제외", "reason": str(exc),
            })
    return {
        "closing_id": closing_id, "period_end": boundary.isoformat(),
        "entries": entries, "errors": errors,
        "expiry_days": sum((r["expiry_days"] for r in entries), Fraction()),
        "carryover_days": sum((r["carryover_days"] for r in entries), Fraction()),
        "cash_payment_approved": False,
    }
