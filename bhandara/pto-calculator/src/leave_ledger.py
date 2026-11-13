"""Provisional PTO usage and pre-expiry balance, independent of payroll.

Only explicitly approved annual leave debits the known accrual balance.
No missing history, statutory expiry, company carryover or pay rate is inferred.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from .event_type import normalize_event_detail

ZERO = Decimal("0")
ONE = Decimal("1")
HALF = Decimal("0.5")
FULL_UNITS = {"DAY", "FULL", "FULL_DAY", "1"}
HALF_UNITS = {"HALF", "HALF_DAY", "0.5", "AM_HALF", "PM_HALF"}
HOUR_UNITS = {"HOUR", "HOURS", "HOURLY"}


def _event_days(row: dict) -> tuple[Decimal | None, str, str | None]:
    """Convert an approved annual-leave event only when its unit is unambiguous."""
    detail = normalize_event_detail(row.get("event_type"))
    subtype = detail["event_subtype"]
    unit = str(row.get("unit") or "").strip().upper().replace(" ", "_")
    if subtype in {"AM_HALF", "PM_HALF"}:
        if unit and unit not in HALF_UNITS:
            return None, subtype, "LEAVE_UNIT_CONFLICT"
        return HALF, subtype, None
    if subtype == "HALF_DAY":
        if unit and unit not in HALF_UNITS:
            return None, subtype, "LEAVE_UNIT_CONFLICT"
        return HALF, subtype, None
    if subtype == "HOURLY":
        return None, subtype, "HOURLY_CONVERSION_POLICY_REQUIRED"
    if unit in FULL_UNITS:
        return ONE, "FULL", None
    if unit in HALF_UNITS:
        return HALF, unit, None
    if unit in HOUR_UNITS:
        return None, "HOURLY", "HOURLY_CONVERSION_POLICY_REQUIRED"
    return None, unit or "UNKNOWN", "LEAVE_UNIT_UNRECOGNIZED"


def _granted_days(grants: list[dict], as_of_date: date) -> tuple[Decimal, int]:
    known = ZERO
    unknown = 0
    for grant in grants:
        if grant.get("grant_date") > as_of_date:
            continue
        raw = grant.get("raw_days")
        if raw is None:
            unknown += 1
            continue
        amount = Decimal(str(raw))
        if not amount.is_finite() or amount < ZERO:
            raise ValueError("invalid PTO grant amount")
        known += amount
    return known, unknown


def calculate_leave_ledger(
    *,
    employee_id: str,
    grants: list[dict],
    event_rows: list[dict],
    as_of_date: date,
    period_start: date,
    hire_date: date,
    termination_date: date | None = None,
) -> dict:
    """Return *known* accrual/use figures, never an approved leave balance.

    Usage files may contain only a single month; expiration rules and opening
    balances are not known. Numeric remainder is explicitly pre-expiry and
    provisional, not an available-to-book or payroll payable balance.
    """
    granted, unresolved_grants = _granted_days(grants, as_of_date)
    seen_ids: set[str] = set()
    candidates: list[dict] = []
    issues: list[str] = []
    non_leave: list[dict] = []

    for row in event_rows:
        if row.get("employee_id") != employee_id:
            continue
        day = row.get("event_date")
        if not isinstance(day, date) or day > as_of_date:
            continue
        detail = normalize_event_detail(row.get("event_type"))
        category = detail["event_type"]
        if category != "ANNUAL_LEAVE":
            non_leave.append({
                "event_date": day, "event_type": category,
                "raw_event_type": detail["raw_event_type"],
            })
            if category is None:
                issues.append("UNKNOWN_EVENT_TYPE")
            continue
        status = str(row.get("status") or "").strip().upper()
        request_id = str(row.get("request_id") or "").strip()
        days, leave_part, problem = _event_days(row)
        if day < hire_date or (termination_date and day > termination_date):
            problem = "EVENT_OUTSIDE_EMPLOYMENT"
        if not request_id or request_id in seen_ids:
            problem = "DUPLICATE_OR_MISSING_REQUEST_ID"
        if request_id:
            seen_ids.add(request_id)
        if status != "APPROVED":
            # Unapproved requests may be visible, but must never debit PTO.
            days = None
            problem = "NOT_APPROVED"
        candidates.append({
            "request_id": request_id, "event_date": day,
            "raw_event_type": detail["raw_event_type"], "leave_part": leave_part,
            "status": status, "days": days, "reason": problem,
        })

    # Overlapping approved leave on a single date cannot be deducted safely.
    by_date = defaultdict(list)
    for item in candidates:
        if item["status"] == "APPROVED":
            by_date[item["event_date"]].append(item)
    for same_day in by_date.values():
        if len(same_day) <= 1:
            continue
        parts = {item["leave_part"] for item in same_day}
        complementary = (
            len(same_day) == 2 and parts == {"AM_HALF", "PM_HALF"}
            and all(item["reason"] is None for item in same_day)
        )
        if not complementary:
            for item in same_day:
                item["reason"] = "OVERLAPPING_ANNUAL_LEAVE"
                item["days"] = None

    used = ZERO
    usage = []
    for item in candidates:
        value = item["days"] if item["reason"] is None else None
        if value is not None:
            used += value
        elif item["status"] == "APPROVED":
            issues.append(item["reason"] or "LEAVE_USAGE_UNRESOLVED")
        usage.append({
            **{key: value for key, value in item.items() if key != "days"},
            "days": str(value) if value is not None else None,
        })

    if unresolved_grants:
        issues.append("PTO_GRANT_UNRESOLVED")
    if used > granted:
        issues.append("KNOWN_USAGE_EXCEEDS_KNOWN_GRANTS")
    # Every client must understand this remainder is never fully verified:
    # a short calculation window cannot reconstruct historic grants/usage.
    issues.extend(("GRANT_AND_USAGE_HISTORY_NOT_VERIFIED", "EXPIRY_POLICY_NOT_VERIFIED"))
    provisional = granted - used
    return {
        "as_of_date": as_of_date.isoformat(),
        "calculation_window_start": period_start.isoformat(),
        "known_granted_days": str(granted),
        "known_used_days": str(used),
        "provisional_remaining_before_expiry_days": str(provisional),
        "confirmed_balance_days": None,
        "expired_days": None,
        "opening_balance_days": None,
        "unresolved_grant_count": unresolved_grants,
        "usage": usage,
        "other_events": non_leave,
        "review_codes": sorted(set(issues)),
        "status": "REVIEW_REQUIRED",
        "approved": False,
        "finalizable": False,
    }
