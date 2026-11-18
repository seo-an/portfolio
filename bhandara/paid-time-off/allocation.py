"""Pure Tool-level grant allocation. No module imports, I/O or policy inference.

Input grants are already approved/normalized, with externally decided validity.
Input deductions are already converted to days. Re-running with the current
approved request snapshot naturally replaces earlier allocations after cancel.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any, Iterable, Mapping


def _id(value: Any, field: str) -> str:
    if value is None or isinstance(value, bool) or not str(value).strip():
        raise ValueError(f"{field} 누락")
    return str(value).strip()


def _date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        raise ValueError(f"{field}: 날짜만 입력해야 합니다")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or len(value.strip()) != 10:
        raise ValueError(f"{field}: YYYY-MM-DD 형식이 아닙니다")
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field}: 올바른 날짜가 아닙니다") from exc
    if parsed.isoformat() != value.strip():
        raise ValueError(f"{field}: YYYY-MM-DD 형식이 아닙니다")
    return parsed


def _days(value: Any, field: str, *, positive: bool = False) -> Fraction:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field}: 수량 누락·오류")
    try:
        if isinstance(value, Fraction):
            amount = value
        else:
            number = Decimal(str(value).strip())
            if not number.is_finite():
                raise ValueError
            amount = Fraction(number)
    except (InvalidOperation, ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError(f"{field}: 수량 오류") from exc
    if amount < 0 or (positive and amount == 0):
        raise ValueError(f"{field}: {'양수' if positive else '0 이상'}여야 합니다")
    return amount


def quantity_text(value: Fraction) -> str:
    """Exact finite decimal; otherwise truncate display to seven places."""
    sign = "-" if value < 0 else ""
    number = abs(value)
    rest = number.denominator
    twos = fives = 0
    while rest % 2 == 0:
        twos += 1
        rest //= 2
    while rest % 5 == 0:
        fives += 1
        rest //= 5
    if rest == 1:
        digits = max(twos, fives)
        integer = number.numerator * 10 ** digits // number.denominator
        return sign + format(Decimal(integer).scaleb(-digits), "f")
    scale = 10 ** 7
    scaled = number.numerator * scale // number.denominator
    return f"{sign}{scaled // scale}.{scaled % scale:07d}"


def _issue(kind: str, row: int, message: str) -> dict:
    return {"source": kind, "row": row, "status": "계산 제외", "reason": message}


def allocate_usage(
    grants: Iterable[Mapping[str, Any]],
    deductions: Iterable[Mapping[str, Any]],
    *,
    as_of_date: date,
) -> dict[str, Any]:
    """Allocate by use date, then earliest expiry, grant date and grant_id.

    Grants require grant_id, employee_id, leave_type, grant_date, valid_from,
    expires_on, source_ref, available_days. 'available_days' is already the
    reflected quantity or the prior closing's confirmed opening balance.
    Deductions require request_id, employee_id, leave_type, leave_date and
    deduction_days. No new entitlements, expiry dates or offsets are inferred.

    All assigned quantities are stored as exact Fractions in returned objects;
    quantity_text is presentation-only. An invalid input in a known employee/
    type bucket blocks that bucket rather than manufacture a false shortage.
    """
    cutoff = _date(as_of_date, "as_of_date")
    raw_grants, raw_requests = list(grants), list(deductions)
    issues: list[dict] = []
    blocked: set[tuple[str, str]] = set()

    # Duplicate IDs have no reliable canonical row: exclude all occurrences.
    grant_counts = Counter(str(r.get("grant_id", "")).strip() for r in raw_grants
                           if r.get("grant_id") is not None)
    parsed_grants: list[dict] = []
    for index, row in enumerate(raw_grants, 1):
        key = (str(row.get("employee_id") or "").strip(),
               str(row.get("leave_type") or "").strip())
        try:
            grant_id = _id(row.get("grant_id"), "grant_id")
            employee = _id(row.get("employee_id"), "employee_id")
            leave_type = _id(row.get("leave_type"), "leave_type")
            if leave_type not in ("연차", "대휴"):
                raise ValueError("leave_type: 연차/대휴만 허용")
            if grant_counts[grant_id] > 1:
                raise ValueError("중복 grant_id")
            granted = _date(row.get("grant_date"), "grant_date")
            start = _date(row.get("valid_from"), "valid_from")
            end = _date(row.get("expires_on"), "expires_on")
            if start > end:
                raise ValueError("유효기간 시작일이 종료일 이후입니다")
            if start < granted:
                raise ValueError("사용 가능 시작일이 최초 발생일보다 빠릅니다")
            source = _id(row.get("source_ref"), "source_ref")
            days = _days(row.get("available_days"), "available_days")
            parsed_grants.append({
                "grant_id": grant_id, "employee_id": employee,
                "leave_type": leave_type, "grant_date": granted,
                "valid_from": start, "expires_on": end,
                "source_ref": source, "available_days": days,
            })
        except ValueError as exc:
            issues.append(_issue("grant", index, str(exc)))
            if key[0] and key[1]:
                blocked.add(key)

    request_counts = Counter()
    for row in raw_requests:
        try:
            request_counts[(_id(row.get("request_id"), "request_id"),
                            _date(row.get("leave_date"), "leave_date"))] += 1
        except ValueError:
            continue

    parsed_requests: list[dict] = []
    for index, row in enumerate(raw_requests, 1):
        key = (str(row.get("employee_id") or "").strip(),
               str(row.get("leave_type") or "").strip())
        try:
            req = _id(row.get("request_id"), "request_id")
            employee = _id(row.get("employee_id"), "employee_id")
            leave_type = _id(row.get("leave_type"), "leave_type")
            if leave_type not in ("연차", "대휴"):
                raise ValueError("leave_type: 연차/대휴만 허용")
            if row.get("status", "계산 완료") != "계산 완료":
                raise ValueError("상위 차감 계산에서 제외된 신청입니다")
            used = _date(row.get("leave_date"), "leave_date")
            if request_counts[(req, used)] > 1:
                raise ValueError("동일 request_id·leave_date 중복")
            amount = _days(row.get("deduction_days"), "deduction_days",
                           positive=True)
            parsed_requests.append({
                "request_id": req, "employee_id": employee,
                "leave_type": leave_type, "leave_date": used,
                "deduction_days": amount,
            })
        except ValueError as exc:
            issues.append(_issue("deduction", index, str(exc)))
            if key[0] and key[1]:
                blocked.add(key)

    by_group: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for grant in parsed_grants:
        by_group[(grant["employee_id"], grant["leave_type"])].append(grant)
    for rows in by_group.values():
        rows.sort(key=lambda g: (g["expires_on"], g["grant_date"], g["grant_id"]))

    completed: dict[str, Fraction] = defaultdict(Fraction)
    reserved: dict[str, Fraction] = defaultdict(Fraction)
    shortages: dict[tuple[str, str], Fraction] = defaultdict(Fraction)
    future_shortages: dict[tuple[str, str], Fraction] = defaultdict(Fraction)
    allocations: list[dict] = []
    for req in sorted(parsed_requests,
                      key=lambda r: (r["leave_date"], r["request_id"])):
        key = (req["employee_id"], req["leave_type"])
        if key in blocked:
            continue
        remaining = req["deduction_days"]
        is_future = req["leave_date"] > cutoff
        for grant in by_group.get(key, ()):
            if not (grant["valid_from"] <= req["leave_date"] <= grant["expires_on"]):
                continue
            identifier = grant["grant_id"]
            available = (grant["available_days"] - completed[identifier]
                         - reserved[identifier])
            taking = min(remaining, max(Fraction(0), available))
            if not taking:
                continue
            (reserved if is_future else completed)[identifier] += taking
            allocations.append({
                **req, "grant_id": identifier, "allocated_days": taking,
                "status": "예약" if is_future else "사용",
            })
            remaining -= taking
            if not remaining:
                break
        if remaining:
            (future_shortages if is_future else shortages)[key] += remaining
            allocations.append({
                **req, "grant_id": None, "allocated_days": remaining,
                "status": "예약부족" if is_future else "부족",
            })

    balances = []
    for grant in parsed_grants:
        key = (grant["employee_id"], grant["leave_type"])
        if key in blocked:
            continue
        identifier = grant["grant_id"]
        balances.append({
            **grant,
            "used_days": completed[identifier],
            "reserved_days": reserved[identifier],
            "remaining_days": grant["available_days"] - completed[identifier],
            "remaining_after_reservations": (
                grant["available_days"] - completed[identifier] - reserved[identifier]),
        })
    # Shortage is a signed employee/type balance, not a negative grant.
    # Future confirmed grants do not increase today's spendable amount.
    summary_keys = (set(by_group) | set(shortages) | set(future_shortages)) - blocked
    summary = []
    for key in sorted(summary_keys):
        employee, leave_type = key
        usable = sum((
            item["remaining_days"] for item in balances
            if (item["employee_id"], item["leave_type"]) == key
            and item["valid_from"] <= cutoff <= item["expires_on"]
        ), Fraction())
        negative = -shortages.get(key, Fraction())
        summary.append({
            "employee_id": employee, "leave_type": leave_type,
            "current_valid_grant_balance": usable,
            "shortage_balance": negative,
            "net_remaining_days": usable + negative,
            "future_shortage_balance": -future_shortages.get(key, Fraction()),
        })
    for employee, leave_type in sorted(blocked):
        issues.append({
            "source": "allocation", "employee_id": employee,
            "leave_type": leave_type, "status": "판정 안됨",
            "reason": "입력 오류로 해당 직원·유형 배정 생략",
        })
    return {
        "allocations": allocations, "balances": balances,
        "summary": summary,
        "shortages": dict(shortages),
        "future_shortages": dict(future_shortages),
        "issues": issues, "blocked_groups": sorted(blocked),
        "as_of_date": cutoff.isoformat(),
    }
