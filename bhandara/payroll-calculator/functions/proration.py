"""Calculate calendar-day proration for monthly recurring payroll items."""

from __future__ import annotations

import calendar
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class ProrationError(RuntimeError):
    """Raised when a proration request cannot be calculated deterministically."""

    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Proration failed: {message}")


def _date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ProrationError(f"{field} must use YYYY-MM-DD: {value!r}") from exc
    raise ProrationError(f"{field} must be a date or YYYY-MM-DD string")


def _decimal(value: Any, field: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ProrationError(f"{field} must be decimal-compatible") from exc
    if amount < 0:
        raise ProrationError(f"{field} must not be negative")
    return amount


def calendar_month_period(payroll_period: str) -> tuple[date, date]:
    try:
        year_text, month_text = str(payroll_period).split("-")
        year = int(year_text)
        month = int(month_text)
        last_day = calendar.monthrange(year, month)[1]
    except (TypeError, ValueError) as exc:
        raise ProrationError("payroll_period must use YYYY-MM") from exc
    return date(year, month, 1), date(year, month, last_day)


def intersect_period(
    left_from: Any,
    left_to: Any,
    right_from: Any,
    right_to: Any,
) -> tuple[date, date] | None:
    start = max(_date(left_from, "left_from"), _date(right_from, "right_from"))
    end = min(_date(left_to, "left_to"), _date(right_to, "right_to"))
    if end < start:
        return None
    return start, end


def inclusive_days(period_from: date, period_to: date) -> int:
    if period_to < period_from:
        raise ProrationError("period_to precedes period_from")
    return (period_to - period_from).days + 1


def prorate_calendar_days(
    monthly_amount: Any,
    payroll_period: str,
    applicable_from: Any,
    applicable_to: Any,
) -> dict[str, Any]:
    """Prorate one monthly amount inside one calendar-month payroll period."""
    amount = _decimal(monthly_amount, "monthly_amount")
    payroll_from, payroll_to = calendar_month_period(payroll_period)
    overlap = intersect_period(
        payroll_from, payroll_to, applicable_from, applicable_to
    )

    denominator_days = inclusive_days(payroll_from, payroll_to)
    if overlap is None:
        return {
            "payroll_period": payroll_period,
            "applicable_from": None,
            "applicable_to": None,
            "applicable_days": 0,
            "payroll_period_days": denominator_days,
            "proration_ratio": Decimal("0"),
            "monthly_amount": amount,
            "prorated_amount": Decimal("0"),
        }

    overlap_from, overlap_to = overlap
    applicable_days = inclusive_days(overlap_from, overlap_to)
    ratio = Decimal(applicable_days) / Decimal(denominator_days)
    prorated_amount = (
        amount * Decimal(applicable_days) / Decimal(denominator_days)
    )

    return {
        "payroll_period": payroll_period,
        "applicable_from": overlap_from,
        "applicable_to": overlap_to,
        "applicable_days": applicable_days,
        "payroll_period_days": denominator_days,
        "proration_ratio": ratio,
        "monthly_amount": amount,
        "prorated_amount": prorated_amount,
    }


def prorate_pay_item(
    pay_item_code: str,
    monthly_amount: Any,
    payroll_period: str,
    applicable_from: Any,
    applicable_to: Any,
    registry: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Apply Registry and company-policy boundaries before proration."""
    items = {item["code"]: item for item in registry.get("items", [])}
    item = items.get(pay_item_code)
    if item is None:
        raise ProrationError(f"unknown pay item: {pay_item_code}")

    proration_rule = item.get("proration")
    if proration_rule == "미적용":
        raise ProrationError(f"{pay_item_code}: proration is not allowed")
    if proration_rule not in {"적용", "회사정책"}:
        raise ProrationError(
            f"{pay_item_code}: unsupported proration rule {proration_rule!r}"
        )

    item_policy = policy.get("proration", {}).get(pay_item_code)
    if not item_policy:
        raise ProrationError(f"{pay_item_code}: proration policy is required")
    if item_policy.get("method") != "역일수":
        raise ProrationError(
            f"{pay_item_code}: v0.1 supports proration.method=역일수 only"
        )

    result = prorate_calendar_days(
        monthly_amount,
        payroll_period,
        applicable_from,
        applicable_to,
    )
    result["pay_item_code"] = pay_item_code
    result["method"] = "역일수"
    return result


def build_compensation_proration_segments(
    compensation_rows: list[dict[str, Any]],
    worker_id: str,
    payroll_period: str,
    pay_item_code: str,
    registry: dict[str, Any],
    policy: dict[str, Any],
    employment_from: Any | None = None,
    employment_to: Any | None = None,
    payable_from: Any | None = None,
    payable_to: Any | None = None,
) -> list[dict[str, Any]]:
    """Build prorated segments from effective-dated compensation history.

    The compensation effective period determines the payable segment.
    A caller's requested/calculation period does not shorten monthly fixed pay.
    """
    try:
        from .compensation_resolver import validate_no_overlaps
    except ImportError:
        from compensation_resolver import validate_no_overlaps

    target_worker = str(worker_id).strip()
    if not target_worker:
        raise ProrationError("worker_id must not be empty")

    normalized = validate_no_overlaps(compensation_rows)
    payroll_from, payroll_to = calendar_month_period(payroll_period)

    employment_start = (
        _date(employment_from, "employment_from")
        if employment_from is not None
        else payroll_from
    )
    employment_end = (
        _date(employment_to, "employment_to")
        if employment_to is not None
        else None
    )
    if employment_end is not None and employment_end < employment_start:
        raise ProrationError("employment_to precedes employment_from")

    payable_period = intersect_period(
        payroll_from,
        payroll_to,
        employment_start,
        employment_end or payroll_to,
    )
    if payable_period is None:
        return []
    period_from, period_to = payable_period

    if payable_from is not None:
        eligibility_start = _date(payable_from, "payable_from")
        eligibility_end = (
            _date(payable_to, "payable_to")
            if payable_to is not None
            else payroll_to
        )
        if payable_to is not None and eligibility_end < eligibility_start:
            raise ProrationError("payable_to precedes payable_from")
        if eligibility_start > payroll_to:
            return []
        eligibility_overlap = intersect_period(
            period_from,
            period_to,
            eligibility_start,
            eligibility_end,
        )
        if eligibility_overlap is None:
            return []
        period_from, period_to = eligibility_overlap
    elif payable_to is not None:
        raise ProrationError("payable_to requires payable_from")

    segments: list[dict[str, Any]] = []

    for row in sorted(
        (item for item in normalized if item["worker_id"] == target_worker),
        key=lambda item: item["effective_from"],
    ):
        monthly_amount = row.get(pay_item_code)
        if monthly_amount is None:
            continue

        effective_to = row["effective_to"] or payroll_to
        overlap = intersect_period(
            period_from,
            period_to,
            row["effective_from"],
            effective_to,
        )
        if overlap is None:
            continue

        segment_from, segment_to = overlap
        result = prorate_pay_item(
            pay_item_code,
            monthly_amount,
            payroll_period,
            segment_from,
            segment_to,
            registry,
            policy,
        )
        result["worker_id"] = target_worker
        result["compensation_effective_from"] = row["effective_from"]
        result["compensation_effective_to"] = row["effective_to"]
        result["employment_from"] = employment_start
        result["employment_to"] = employment_end
        result["payable_from"] = (
            _date(payable_from, "payable_from")
            if payable_from is not None
            else None
        )
        result["payable_to"] = (
            _date(payable_to, "payable_to")
            if payable_to is not None
            else None
        )
        segments.append(result)

    return segments


def build_prorated_recurring_item(
    compensation_rows: list[dict[str, Any]],
    worker_id: str,
    payroll_period: str,
    pay_item_code: str,
    registry: dict[str, Any],
    policy: dict[str, Any],
    employment_from: Any | None = None,
    employment_to: Any | None = None,
    payable_from: Any | None = None,
    payable_to: Any | None = None,
) -> dict[str, Any]:
    """Aggregate compensation proration segments without rounding."""
    segments = build_compensation_proration_segments(
        compensation_rows,
        worker_id,
        payroll_period,
        pay_item_code,
        registry,
        policy,
        employment_from=employment_from,
        employment_to=employment_to,
        payable_from=payable_from,
        payable_to=payable_to,
    )
    calculated_amount = sum(
        (segment["prorated_amount"] for segment in segments),
        Decimal("0"),
    )
    return {
        "worker_id": str(worker_id).strip(),
        "pay_item_code": pay_item_code,
        "calculated_amount": calculated_amount,
        "proration_segments": segments,
    }
