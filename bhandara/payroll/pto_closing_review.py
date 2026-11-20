"""Read-only bridge: exact PTO deduction quantities -> usage -> confirmed Closing.

This module DOES NOT compute PTO entitlement or salary, revise Closing, infer
leave pay treatment, or alter Worktime's one-request-per-day contract.
An independently supplied multi-request list is audited but NOT automatically
fed into the older single-event-per-day payroll attendance adapter.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from fractions import Fraction
import importlib
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.settlement_coverage import _day as _iso_day

_usage = importlib.import_module("bhandara.paid-time-off.runner_usage")


class PTOClosingReviewError(ValueError):
    """Conflicting or incomplete PTO source, quantity or approval reference."""


CLAIM_FIELDS = frozenset({
    "employee_id", "request_id", "leave_date", "pto_leave_type",
    "worktime_code", "start_at", "end_at", "approved_minutes",
    "minutes_per_pto_day",
})
DETAIL_FIELDS = (
    "employee_id", "request_id", "leave_date", "leave_type",
    "grant_id", "차감일수", "처리구분",
)
DEDUCTION_FIELDS = (
    "request_id", "employee_id", "leave_date", "leave_type", "상태",
    "차감일수", "_exact_numerator", "_exact_denominator",
)
MONTH_FIELDS = tuple(f"{i}월" for i in range(1, 13))


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PTOClosingReviewError(f"{name}: text required")
    value = value.strip()
    if value[0] in "=+-@\t\r\n":
        raise PTOClosingReviewError(f"{name}: unsafe text")
    return value


def _date(value: Any, name: str) -> date:
    try:
        return _iso_day(value, name)
    except ValueError as exc:
        raise PTOClosingReviewError(f"{name}: ISO date required") from exc


def _time(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
        raise PTOClosingReviewError(f"{name}: local minute timestamp required")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise PTOClosingReviewError(f"{name}: invalid timestamp") from exc


def _quantity(value: Any, name: str, *, allow_zero=True, displayed=False) -> Fraction:
    if value is None or isinstance(value, bool) or (isinstance(value, float) and not displayed):
        raise PTOClosingReviewError(f"{name}: exact integer/decimal/fraction required")
    try:
        amount = Fraction(str(value))
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise PTOClosingReviewError(f"{name}: invalid quantity") from exc
    if amount < 0 or (amount == 0 and not allow_zero):
        raise PTOClosingReviewError(f"{name}: invalid quantity sign")
    return amount


def _metadata(file: Path, key: str) -> tuple[dict[str, Any], str]:
    if file.name != key or not file.is_file():
        raise PTOClosingReviewError(f"source: explicit {key} required")
    before = sha256_file(file)
    try:
        meta = _usage._policy(file)
    except (ValueError, OSError) as exc:
        raise PTOClosingReviewError(f"{key}: invalid policy sheet") from exc
    if sha256_file(file) != before:
        raise PTOClosingReviewError(f"{key}: modified while reading")
    return meta, before


def _rows(file: Path, sheet: str, fields: tuple[str, ...], *, optional=False) -> list[dict[str, Any]]:
    try:
        return _usage.read_rows(file, sheet, fields, optional_sheet=optional)
    except (ValueError, OSError) as exc:
        raise PTOClosingReviewError(f"{file.name}/{sheet}: cannot read source contract") from exc


def _index_worktime(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    indexed = {}
    for source in rows:
        worker = _text(source.get("employee_id"), "WORKTIME.employee_id")
        day = _date(source.get("work_date"), "WORKTIME.work_date").isoformat()
        key = (worker, day)
        if key in indexed:
            raise PTOClosingReviewError("WORKTIME: duplicate employee/day")
        indexed[key] = source
    return indexed


def _claims(
    rows: Iterable[Mapping[str, Any]],
    worktime: Mapping[tuple[str, str], Mapping[str, Any]],
    month: int,
    year: int,
) -> dict[tuple[str, str, str, str], Fraction]:
    """Allow multiple external PTO claims/day, one Worktime reference anchor."""
    result: dict[tuple[str, str, str, str], Fraction] = {}
    intervals: dict[tuple[str, str], list[tuple[datetime, datetime, str, str]]] = defaultdict(list)
    for raw in rows:
        if not isinstance(raw, Mapping) or set(raw) != CLAIM_FIELDS:
            raise PTOClosingReviewError("pto_claims: exact contract fields required")
        worker = _text(raw["employee_id"], "claim.employee_id")
        request = _text(raw["request_id"], "claim.request_id")
        leave = _text(raw["pto_leave_type"], "claim.pto_leave_type")
        code = _text(raw["worktime_code"], "claim.worktime_code")
        if leave not in ("연차", "대휴"):
            raise PTOClosingReviewError("claim: PTO leave type must be 연차 or 대휴")
        day = _date(raw["leave_date"], "claim.leave_date")
        if (day.year, day.month) != (year, month):
            raise PTOClosingReviewError("claim: leave outside selected payroll month")
        start = _time(raw["start_at"], "claim.start_at")
        end = _time(raw["end_at"], "claim.end_at")
        if start.date() != day or end.date() != day or end <= start:
            raise PTOClosingReviewError("claim: same-day positive interval required")
        minutes = (end - start).total_seconds() / 60
        if not minutes.is_integer() or type(raw["approved_minutes"]) is not int or int(minutes) != raw["approved_minutes"]:
            raise PTOClosingReviewError("claim: approved minutes differ from interval")
        per_day = raw["minutes_per_pto_day"]
        if type(per_day) is not int or per_day <= 0 or raw["approved_minutes"] > per_day:
            raise PTOClosingReviewError("claim: explicit valid PTO daily minute divisor required")
        key = (worker, request, day.isoformat(), leave)
        if key in result:
            raise PTOClosingReviewError("claim: duplicate employee/request/date/type")
        result[key] = Fraction(raw["approved_minutes"], per_day)
        intervals[(worker, day.isoformat())].append((start, end, request, code))
        if (worker, day.isoformat()) not in worktime:
            raise PTOClosingReviewError("claim: Worktime employee/day missing")
        fact = worktime[(worker, day.isoformat())]
        scheduled = fact.get("scheduled_min")
        if type(scheduled) is not int or scheduled <= 0:
            raise PTOClosingReviewError("claim: scheduled time is unresolved")
    for key, time_spans in intervals.items():
        ordered = sorted(time_spans)
        for prev, current in zip(ordered, ordered[1:]):
            if current[0] < prev[1]:
                raise PTOClosingReviewError("claim: overlapping same-day leave intervals")
        fact = worktime[key]
        if sum(int((end-start).total_seconds()/60) for start,end,_,_ in ordered) > fact["scheduled_min"]:
            raise PTOClosingReviewError("claim: total PTO minutes exceed scheduled minutes")
        if not any(fact.get("leave_request_id") == request
                   and fact.get("leave_type") == code
                   for _, _, request, code in ordered):
            raise PTOClosingReviewError("claim: Worktime leave ID/type anchor missing")
    return result


def reconcile_pto_closing(
    *,
    usage_file: str | Path,
    closing_file: str | Path | None,
    deduction_file: str | Path,
    worktime_rows: Iterable[Mapping[str, Any]],
    pto_claims: Iterable[Mapping[str, Any]],
    period_from: str,
    period_to: str,
) -> dict[str, Any]:
    """Same PTO request/quantity reconciliation for confirmed and pre-close data.

    No Closing file means a strictly pinned as-of Usage/Deduction snapshot,
    not a claimed final quarter. Confirmed Closing validation stays strict.
    """
    start, end = _date(period_from, "period_from"), _date(period_to, "period_to")
    if (start.day != 1 or start.year != end.year or start.month != end.month or
            end != (date(end.year + (end.month == 12), end.month % 12 + 1, 1)
                    - timedelta(days=1))):
        raise PTOClosingReviewError("payroll period: exact full calendar month required")
    usage, deduction = Path(usage_file), Path(deduction_file)
    usage_meta, usage_sha = _metadata(usage, "usage-ledger-result.xlsx")
    _, deduction_sha = _metadata(deduction, "deduction-quantity-result.xlsx")
    confirmed = closing_file is not None
    closing = Path(closing_file) if confirmed else None
    closing_meta, closing_sha = (
        _metadata(closing, "closing-result.xlsx")
        if confirmed else ({}, None)
    )
    if confirmed:
        closing_id = closing_meta.get("참조 ID")
    else:
        # The pending source identity changes whenever the Usage snapshot does.
        # This prevents a wage decision for an older same-day snapshot from
        # being silently applied to newly revised PTO requests.
        cutoff = _date(usage_meta.get("실행 기준일"), "PTO usage as-of")
        if not start <= cutoff <= end:
            raise PTOClosingReviewError("PTO usage: pre-close as-of outside payroll month")
        if str(usage_meta.get("마감 판정 ID")) != "없음":
            raise PTOClosingReviewError("PTO usage: provisional snapshot must not claim Closing")
        if usage_meta.get("계산 상태") != "계산 완료":
            raise PTOClosingReviewError("PTO usage: unresolved provisional snapshot")
        if usage_meta.get("Deduction SHA256") != deduction_sha:
            raise PTOClosingReviewError("PTO usage: provisional Deduction fingerprint mismatch")
        closing_id = f"PRE_CLOSING:{cutoff.isoformat()}:{usage_sha}"
    if confirmed:
        match = re.fullmatch(r"Closing-([1-4])\.4-(\d{4})", str(closing_id))
        if not match:
            raise PTOClosingReviewError("Closing: invalid closing ID")
        quarter, year = int(match[1]), int(match[2])
        if year != start.year or (start.month - 1) // 3 + 1 != quarter:
            raise PTOClosingReviewError("Closing: payroll month is not in current quarter")
        cutoff = date(year, quarter * 3, (31 if quarter in (1, 4) else 30))
        if closing_meta.get("마감 기준일") != cutoff.isoformat():
            raise PTOClosingReviewError("Closing: closing cutoff mismatch")
        if closing_meta.get("확정여부") != "확정":
            raise PTOClosingReviewError("Closing: explicit confirmation required")
        if closing_meta.get("사용내역 SHA256") != usage_sha:
            raise PTOClosingReviewError("Closing: usage ledger fingerprint mismatch")
        if str(closing_meta.get("검토 필요 건수")) != "0":
            raise PTOClosingReviewError("Closing: unresolved source issues")
        if (usage_meta.get("마감 판정 ID") != closing_id
                or usage_meta.get("실행 기준일") != cutoff.isoformat()
                or usage_meta.get("계산 상태") != "계산 완료"):
            raise PTOClosingReviewError("PTO usage: cutoff/closing ID/completion mismatch")
        year = start.year
    else:
        year = start.year

    if _rows(usage, "검토사항", ("employee_id", "reason"), optional=True):
        raise PTOClosingReviewError("PTO usage: unresolved review items")

    detail_rows = _rows(usage, "사용상세", DETAIL_FIELDS)
    deduction_rows = _rows(deduction, "차감상세", DEDUCTION_FIELDS)
    monthly = {}
    if confirmed:
        closing_rows = _rows(closing, "_수량정본", ("employee_id", MONTH_FIELDS[start.month-1]))
        report_rows = _rows(closing, "마감보고", ("employee_id", "마감상태"))
        roster = {}
        for row in report_rows:
            worker = _text(row["employee_id"], "Closing employee_id")
            if worker in roster:
                raise PTOClosingReviewError("Closing: duplicate employee")
            if row["마감상태"] == "자료확인 필요":
                raise PTOClosingReviewError("Closing: employee still requires source review")
            roster[worker] = row["마감상태"]
        for row in closing_rows:
            worker = _text(row["employee_id"], "Closing exact employee_id")
            if worker in monthly:
                raise PTOClosingReviewError("Closing: duplicate exact employee")
            monthly[worker] = _quantity(row[MONTH_FIELDS[start.month-1]], "Closing exact monthly usage")
        if set(roster) != set(monthly):
            raise PTOClosingReviewError("Closing: report/exact employee roster mismatch")

    expected: dict[tuple[str, str, str, str], Fraction] = {}
    monthly_deductions: dict[str, Fraction] = defaultdict(Fraction)
    for row in deduction_rows:
        day = _date(row["leave_date"], "PTO deduction date")
        if (day.year, day.month) != (year, start.month) or (
                not confirmed and day > cutoff):
            continue
        key = (
            _text(row["employee_id"], "deduction.employee_id"),
            _text(row["request_id"], "deduction.request_id"),
            day.isoformat(), _text(row["leave_type"], "deduction.leave_type"),
        )
        if key in expected:
            raise PTOClosingReviewError("PTO deduction: duplicate request/day")
        if row["상태"] != "계산 완료":
            raise PTOClosingReviewError("PTO deduction: unresolved selected-month request")
        num, den = row["_exact_numerator"], row["_exact_denominator"]
        if (not re.fullmatch(r"[0-9]+", str(num)) or
            not re.fullmatch(r"[0-9]+", str(den)) or int(num) <= 0 or int(den) <= 0):
            raise PTOClosingReviewError("PTO deduction: missing exact fraction")
        expected[key] = Fraction(int(num), int(den))
        monthly_deductions[key[0]] += expected[key]

    # Displayed usage rows may contain multiple allocation lines per request.
    # The exact deduction fraction, NOT the 7-decimal display, is the
    # quantity authority. The display sum is checked with a bounded
    # per-line truncation tolerance and never used to determine salary.
    displayed: dict[tuple[str, str, str, str], Fraction] = defaultdict(Fraction)
    allocation_lines: dict[tuple[str, str, str, str], int] = defaultdict(int)
    grant_rows: set[tuple[tuple[str, str, str, str], str]] = set()
    for row in detail_rows:
        day = _date(row["leave_date"], "usage.leave_date")
        if (day.year, day.month) != (year, start.month):
            continue
        if not confirmed and day > cutoff:
            raise PTOClosingReviewError("PTO usage: future request included in as-of snapshot")
        key = (
            _text(row["employee_id"], "usage.employee_id"),
            _text(row["request_id"], "usage.request_id"),
            day.isoformat(), _text(row["leave_type"], "usage.leave_type"),
        )
        status = row["처리구분"]
        if status not in ("사용", "부족"):
            raise PTOClosingReviewError("PTO usage: unresolved/reserved/inherited request in selected month")
        grant = _text(row["grant_id"], "usage.grant_id") if row["grant_id"] else f"_SHORTAGE_{row['_source_row']}"
        ident = (key, grant)
        if ident in grant_rows:
            raise PTOClosingReviewError("PTO usage: duplicated grant allocation")
        grant_rows.add(ident)
        displayed[key] += _quantity(row["차감일수"], "usage displayed days", allow_zero=False, displayed=True)
        allocation_lines[key] += 1

    if set(displayed) != set(expected):
        raise PTOClosingReviewError("PTO: deduction/usage request populations differ")
    for key, amount in expected.items():
        if abs(amount - displayed[key]) > Fraction(allocation_lines[key], 10_000_000):
            raise PTOClosingReviewError("PTO: usage display disagrees with exact deduction")
    if confirmed:
        for worker, closing_amount in monthly.items():
            if monthly_deductions[worker] != closing_amount:
                raise PTOClosingReviewError("PTO: exact deduction does not equal Closing monthly amount")
        if set(monthly_deductions) - set(monthly):
            raise PTOClosingReviewError("PTO: deduction employee missing from Closing")
    else:
        # Current as-of usage has no confirmed monthly Closing quantity.
        # The same exact request and displayed-usage checks above apply.
        monthly = dict(monthly_deductions)

    # The Worktime ten-column contract stays untouched; a day's single
    # anchor must refer to at least one of multiple external PTO requests.
    indexed = _index_worktime(worktime_rows)
    claims = _claims(tuple(pto_claims), indexed, start.month, year)
    if set(claims) != set(expected):
        raise PTOClosingReviewError("PTO: claim/approved deduction request populations differ")
    for key, amount in claims.items():
        if amount != expected[key]:
            raise PTOClosingReviewError("PTO: approved minutes/divisor disagree with exact deduction")

    originals = [(usage, usage_sha), (deduction, deduction_sha)]
    if confirmed:
        originals.append((closing, closing_sha))
    for file, sha in originals:
        if sha256_file(file) != sha:
            raise PTOClosingReviewError("PTO: source workbook changed during review")
    return {
        "schema_version": "0.1",
        "period_from": period_from, "period_to": period_to,
        "closing_id": closing_id,
        "closing_confirmed": confirmed,
        "closing_status": "마감 확정" if confirmed else "마감 전",
        "as_of_date": cutoff.isoformat(),
        "change_possible": not confirmed,
        "source_sha256": {"usage": usage_sha, "closing": closing_sha, "deduction": deduction_sha},
        "monthly_usage_days": {
            worker: str(quantity) for worker, quantity in sorted(monthly.items())
        },
        "requests": [
            {"employee_id": key[0], "request_id": key[1],
             "leave_date": key[2], "leave_type": key[3],
             "exact_deducted_days": str(value)}
            for key, value in sorted(expected.items())
        ],
        "multiple_requests_per_workday": any(
            sum(k[0] == worker and k[2] == day for k in claims) > 1
            for worker, day in {(key[0], key[2]) for key in claims}
        ),
        "source_consistency": (
            "MATCHED_FOR_CURRENT_QUARTER_MONTH" if confirmed
            else "MATCHED_PROVISIONAL_AS_OF"
        ),
        "source_authenticity": "NOT_AUTHENTICATED_BY_THIS_MODULE",
        "salary_treatment": "NOT_ASSESSED",
        "approval_state": "NOT_APPROVED",
        "earnings_complete": False,
    }
