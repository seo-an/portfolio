"""P1-2: Pure, auditable *candidate* compensation for approved work intervals.

No Worktime clock delta or daily minutes creates payable overtime. A separate
verified actual-work interval and approved, classified sub-interval are required.
The explicit policy determines how the contractual daily rate is translated to
a per-minute component. Calculated candidates are NEVER a pay approval.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
import re
from typing import Any, Iterable, Mapping

from bhandara.payroll.overtime_stacking import (
    OvertimeStackingError, review_approved_stacking,
)


class OvertimeCandidateError(ValueError):
    """Insufficient evidence or ambiguous pay rules: fail the candidate run."""


WORK_FIELDS = frozenset({
    "evidence_id", "employee_id", "work_date", "start_at", "end_at", "verification_ref",
})
APPROVAL_FIELDS = frozenset({
    "segment_id", "work_evidence_id", "employee_id", "work_date",
    "start_at", "end_at", "rule_id", "approval_status", "approval_ref",
    "classification_ref", "base_pay_includes_time", "base_inclusion_ref",
})
SUPPORTED_CATEGORIES = frozenset({"OVERTIME", "NIGHT", "HOLIDAY", "EARLY", "LATE"})
ROUNDING = {"DOWN": ROUND_DOWN, "HALF_UP": ROUND_HALF_UP}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OvertimeCandidateError(f"{field}: nonempty text required")
    result = value.strip()
    if result[0] in ("=", "+", "-", "@", "\t", "\n", "\r"):
        raise OvertimeCandidateError(f"{field}: unsafe text")
    return result


def _date(value: Any, field: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise OvertimeCandidateError(f"{field}: YYYY-MM-DD required")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise OvertimeCandidateError(f"{field}: invalid date") from exc
    return result


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
        raise OvertimeCandidateError(f"{field}: local YYYY-MM-DDTHH:MM required")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise OvertimeCandidateError(f"{field}: invalid local time") from exc
    return result


def _clock(value: Any, field: str) -> time | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        raise OvertimeCandidateError(f"{field}: HH:MM or null required")
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise OvertimeCandidateError(f"{field}: invalid clock") from exc


def _decimal(value: Any, field: str, *, positive: bool = False, integral: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise OvertimeCandidateError(f"{field}: numeric required")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise OvertimeCandidateError(f"{field}: invalid decimal") from exc
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise OvertimeCandidateError(f"{field}: nonnegative finite number required")
    if integral and number != number.to_integral_value():
        raise OvertimeCandidateError(f"{field}: integer required")
    return number


def _row_fields(row: Any, fields: frozenset[str], name: str) -> Mapping[str, Any]:
    if not isinstance(row, Mapping) or set(row) != fields:
        raise OvertimeCandidateError(f"{name}: exact fields required")
    return row


def _interval(row: Mapping[str, Any], kind: str) -> tuple[datetime, datetime, int]:
    start = _timestamp(row["start_at"], f"{kind}.start_at")
    end = _timestamp(row["end_at"], f"{kind}.end_at")
    if start.date() != _date(row["work_date"], f"{kind}.work_date"):
        raise OvertimeCandidateError(f"{kind}: work_date must equal interval start date")
    if not start < end or end - start > timedelta(days=1):
        raise OvertimeCandidateError(f"{kind}: interval must be positive and <= 24h")
    minutes = int((end - start).total_seconds() // 60)
    if minutes == 0:
        raise OvertimeCandidateError(f"{kind}: positive whole-minute interval required")
    return start, end, minutes


def _no_overlap(intervals: Mapping[str, list[tuple[datetime, datetime]]], kind: str) -> None:
    for values in intervals.values():
        by_start = sorted(values)
        for (_, previous_end), (next_start, _) in zip(by_start, by_start[1:]):
            if next_start < previous_end:
                raise OvertimeCandidateError(f"{kind}: overlapping intervals require a stacking policy")


def _qualifies(start: datetime, end: datetime, first: time | None, last: time | None) -> bool:
    if first is None and last is None:
        return True
    if first is None or last is None or first == last:
        return False
    # A night window such as 22:00->06:00 can start on the previous date.
    for offset in (-1, 0, 1):
        anchor = start.date() + timedelta(days=offset)
        lower = datetime.combine(anchor, first)
        upper = datetime.combine(anchor, last)
        if upper <= lower:
            upper += timedelta(days=1)
        if lower <= start and end <= upper:
            return True
    return False


def _rules(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise OvertimeCandidateError("overtime_rules: object rows required")
        identifier = _text(row.get("rule_id"), "rule_id")
        category = _text(row.get("category"), "category")
        if identifier in result:
            raise OvertimeCandidateError("overtime_rules: duplicate rule_id")
        if category not in SUPPORTED_CATEGORIES:
            raise OvertimeCandidateError("overtime_rules: unsupported category")
        start = _clock(row.get("qualifying_from"), "qualifying_from")
        end = _clock(row.get("qualifying_to"), "qualifying_to")
        if (start is None) != (end is None) or (start is not None and start == end):
            raise OvertimeCandidateError("overtime_rules: invalid qualifying clock window")
        if category == "NIGHT" and (start is None or end is None):
            raise OvertimeCandidateError("NIGHT: explicit clock window required")
        threshold = int(_decimal(row.get("minimum_minutes"), "minimum_minutes", integral=True))
        multiplier = _decimal(row.get("daily_rate_multiplier"), "daily_rate_multiplier", positive=True)
        result[identifier] = {
            "category": category, "from": start, "to": end,
            "minimum_minutes": threshold, "multiplier": multiplier,
            "policy_ref": _text(row.get("policy_ref"), "policy_ref"),
        }
    return result


def _work_evidence(
    rows: Iterable[Mapping[str, Any]],
    contract_ids: set[str],
    worktime: Mapping[tuple[str, str], Decimal | None],
) -> dict[str, dict[str, Any]]:
    evidence = {}
    spans: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    by_day: dict[tuple[str, str], int] = defaultdict(int)
    for source in rows:
        row = _row_fields(source, WORK_FIELDS, "verified_work")
        key = _text(row["evidence_id"], "evidence_id")
        employee = _text(row["employee_id"], "employee_id")
        _text(row["verification_ref"], "verification_ref")
        if key in evidence:
            raise OvertimeCandidateError("verified_work: duplicate evidence_id")
        if employee not in contract_ids:
            raise OvertimeCandidateError("verified_work: employee outside Payroll contracts")
        start, end, minutes = _interval(row, "verified_work")
        work_key = (employee, row["work_date"])
        if work_key not in worktime or worktime[work_key] is None:
            raise OvertimeCandidateError("verified_work: Worktime actual minutes missing")
        spans[employee].append((start, end))
        by_day[work_key] += minutes
        evidence[key] = {"employee_id": employee, "work_date": row["work_date"],
                         "start": start, "end": end}
    _no_overlap(spans, "verified_work")
    for day, minutes in by_day.items():
        if minutes > worktime[day]:
            raise OvertimeCandidateError("verified_work: evidence minutes exceed Worktime actual minutes")
    return evidence


def _policy(policy: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any], str]:
    if not isinstance(policy, Mapping):
        raise OvertimeCandidateError("policy: object required")
    if policy.get("multiplier_semantics") != "TOTAL_RATE":
        raise OvertimeCandidateError("policy: explicit TOTAL_RATE multiplier semantics required")
    if policy.get("rounding_scope") != "EMPLOYEE_RULE_PERIOD":
        raise OvertimeCandidateError("policy: employee/rule/period rounding scope required")
    mode = policy.get("rounding_mode")
    if mode not in ROUNDING:
        raise OvertimeCandidateError("policy: explicit DOWN or HALF_UP rounding mode required")
    divisors = policy.get("reference_day_minutes_by_contract")
    labels = policy.get("rule_labels")
    if not isinstance(divisors, Mapping) or not isinstance(labels, Mapping):
        raise OvertimeCandidateError("policy: contract divisors and rule labels required")
    return divisors, labels, mode


def calculate_overtime_candidates(
    contracts: Mapping[str, Mapping[str, Any]],
    worktime_rows: Iterable[Mapping[str, Any]],
    overtime_rules: Iterable[Mapping[str, Any]],
    *,
    verified_work: Iterable[Mapping[str, Any]],
    approved_segments: Iterable[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute additional *candidate components* from fully explicit evidence.

    daily_base_rate / reference_day_minutes * approved_minutes * factor.
    Factor is TOTAL_RATE if base is excluded; TOTAL_RATE-1 if independently
    proven already included in base. This is an arithmetic convention for
    preview, NOT an assertion of labor-law eligibility or complete payment.
    Overlapping approved segments are refused unless explicitly permitted by
    exact active-category sets; duplicate ordinary base pay is always blocked.
    """
    if not contracts:
        raise OvertimeCandidateError("contracts: selected worker contracts required")
    divisors, labels, rounding_mode = _policy(policy)
    rules = _rules(overtime_rules)
    worktime: dict[tuple[str, str], Decimal | None] = {}
    for source in worktime_rows:
        if not isinstance(source, Mapping):
            raise OvertimeCandidateError("WORKTIME: object row required")
        employee = _text(source.get("employee_id"), "employee_id")
        day = _date(source.get("work_date"), "work_date").isoformat()
        key = (employee, day)
        if employee not in contracts or key in worktime:
            raise OvertimeCandidateError("WORKTIME: unknown worker or duplicate employee/date")
        minutes = source.get("actual_min")
        worktime[key] = None if minutes is None else _decimal(minutes, "actual_min", integral=True)

    evidence = _work_evidence(verified_work, set(contracts), worktime)
    stacking_segments: list[dict[str, Any]] = []
    segment_unit_rates: dict[str, tuple[str, str, Decimal]] = {}
    segment_ids: set[str] = set()
    amounts: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    durations: dict[tuple[str, str], int] = defaultdict(int)
    audit: dict[tuple[str, str], list[str]] = defaultdict(list)
    for source in approved_segments:
        row = _row_fields(source, APPROVAL_FIELDS, "approved_segment")
        segment_id = _text(row["segment_id"], "segment_id")
        if segment_id in segment_ids:
            raise OvertimeCandidateError("approved_segment: duplicate segment_id")
        segment_ids.add(segment_id)
        employee = _text(row["employee_id"], "employee_id")
        ref = _text(row["work_evidence_id"], "work_evidence_id")
        _text(row["approval_ref"], "approval_ref")
        _text(row["classification_ref"], "classification_ref")
        _text(row["base_inclusion_ref"], "base_inclusion_ref")
        if row["approval_status"] != "APPROVED":
            raise OvertimeCandidateError("approved_segment: explicit APPROVED status required")
        if type(row["base_pay_includes_time"]) is not bool:
            raise OvertimeCandidateError("base_pay_includes_time: explicit boolean required")
        if employee not in contracts or ref not in evidence:
            raise OvertimeCandidateError("approved_segment: unselected employee or unknown work evidence")
        start, end, minutes = _interval(row, "approved_segment")
        parent = evidence[ref]
        if (parent["employee_id"] != employee or parent["work_date"] != row["work_date"]
                or not parent["start"] <= start or end > parent["end"]):
            raise OvertimeCandidateError("approved_segment: outside verified actual work interval")
        rule_id = _text(row["rule_id"], "rule_id")
        if rule_id not in rules:
            raise OvertimeCandidateError("approved_segment: unmatched rule_id")
        rule = rules[rule_id]
        stacking_segments.append({
            "employee_id": employee, "segment_id": segment_id,
            "start_at": start, "end_at": end,
            "category": rule["category"],
            "base_pay_includes_time": row["base_pay_includes_time"],
        })
        if not _qualifies(start, end, rule["from"], rule["to"]):
            raise OvertimeCandidateError("approved_segment: outside qualifying clock window")
        if minutes < rule["minimum_minutes"]:
            raise OvertimeCandidateError("approved_segment: below minimum; manual wage review required")

        contract = contracts[employee]
        contract_id = _text(contract.get("contract_id"), "contract_id")
        if contract_id not in divisors:
            raise OvertimeCandidateError("policy: reference_day_minutes missing for contract")
        divisor = _decimal(divisors[contract_id], "reference_day_minutes", positive=True, integral=True)
        daily_rate = _decimal(contract.get("daily_base_rate"), "daily_base_rate", positive=True, integral=True)
        factor = rule["multiplier"] - (1 if row["base_pay_includes_time"] else 0)
        if factor < 0:
            raise OvertimeCandidateError("rule multiplier smaller than included base rate")
        label = _text(labels.get(rule_id), "rule_labels")
        segment_unit_rates[segment_id] = (employee, rule_id, daily_rate / divisor)
        item = (employee, rule_id)
        amounts[item] += daily_rate * Decimal(minutes) * factor / divisor
        durations[item] += minutes
        audit[item].append(segment_id)

    # Perform the half-open time sweep *before* publishing any monetary result.
    # A missing policy keeps P1-2's original strict no-overlap behavior.
    try:
        stacking_review = review_approved_stacking(
            stacking_segments, overlap_policy=policy.get("overlap_policy"),
        )
    except OvertimeStackingError as exc:
        raise OvertimeCandidateError(str(exc)) from exc

    # When the same minute's ordinary base is NOT in contracted base pay,
    # the original P1-2 per-segment arithmetic includes that 1x once in
    # *every* concurrent TOTAL_RATE. Keep it only in the policy-named owner.
    # This adjusts raw Decimal components before employee/rule rounding.
    for overlap in stacking_review["overlap_slices"]:
        if overlap["base_prepaid"]:
            continue
        owner = overlap["ordinary_base_owner_segment_id"]
        for segment_id in overlap["segment_ids"]:
            if segment_id == owner:
                continue
            employee, rule_id, one_minute_base = segment_unit_rates[segment_id]
            amounts[(employee, rule_id)] -= (
                one_minute_base * Decimal(overlap["overlap_minutes"])
            )
    rows = []
    for (employee, rule_id), amount in sorted(amounts.items()):
        if amount < 0:
            raise OvertimeCandidateError(
                "approved stacking: negative premium after ordinary base allocation"
            )
        rows.append({
            "employee_id": employee, "item_id": rule_id,
            "label": _text(labels[rule_id], "rule_labels"),
            "category": rules[rule_id]["category"],
            "minutes": durations[(employee, rule_id)],
            "amount": int(amount.to_integral_value(rounding=ROUNDING[rounding_mode])),
            "segment_ids": sorted(audit[(employee, rule_id)]),
            "status": "CALCULATED_CANDIDATE_NOT_APPROVED",
        })
    return {
        "schema_version": "0.1",
        "rows": rows,
        "earnings_complete": False,
        "payable_minutes_finalized": False,
        "stacking_review": stacking_review,
        "approval_state": "NOT_APPROVED",
    }
