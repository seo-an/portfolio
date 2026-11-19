"""P1-5b: cross-check *listed* leave/attendance adjustments against Worktime.

Worktime's one-row-per-employee/day contains at most one leave reference and
NO approved leave intervals, deduction amounts, or payroll decisions.
Those must be explicitly provided by another authority. Matching a reference
is not authentication and does not make earnings complete.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import re
from typing import Any, Iterable, Mapping

from bhandara.payroll.settlement_coverage import _day as _verified_day, _text as _verified_text
from bhandara.payroll.worktime_bridge import review_worktime_facts


class AttendanceSettlementError(ValueError):
    """A leave or pay reduction is unverified, inconsistent or ambiguous."""


PLAN_FIELDS = frozenset({
    "schema_version", "period_from", "period_to", "snapshot_ref",
    "settlement_snapshot_ref", "worktime_sha256", "absence_codes", "events",
})
EVENT_FIELDS = frozenset({
    "event_id", "employee_id", "work_date", "contract_id",
    "event_kind", "worktime_code", "leave_request_id",
    "start_at", "end_at", "approved_minutes", "treatment",
    "base_reduction_won", "base_amount_not_pre_adjusted",
    "approval_status", "approval_ref", "policy_ref", "evidence_ref",
})
TREATMENTS = frozenset({"PAID_LEAVE", "UNPAID_LEAVE", "UNPAID_ABSENCE"})


def _text(value: Any, field: str) -> str:
    try:
        return _verified_text(value, field)
    except ValueError as exc:
        raise AttendanceSettlementError(f"{field}: safe nonempty text required") from exc


def _day(value: Any, field: str) -> date:
    try:
        return _verified_day(value, field)
    except ValueError as exc:
        raise AttendanceSettlementError(f"{field}: canonical YYYY-MM-DD required") from exc


def _exact(source: Any, fields: frozenset[str], name: str) -> Mapping[str, Any]:
    if not isinstance(source, Mapping) or set(source) != fields:
        raise AttendanceSettlementError(f"{name}: exact fields required")
    return source


def _minutes(value: Any, field: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < 0 or (positive and value == 0):
        raise AttendanceSettlementError(f"{field}: nonnegative integer minutes required")
    return value


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
        raise AttendanceSettlementError(f"{field}: local YYYY-MM-DDTHH:MM required")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise AttendanceSettlementError(f"{field}: invalid timestamp") from exc


def _interval(row: Mapping[str, Any], name: str) -> tuple[datetime, datetime, int]:
    start = _timestamp(row["start_at"], f"{name}.start_at")
    end = _timestamp(row["end_at"], f"{name}.end_at")
    if start.date() != _day(row["work_date"], f"{name}.work_date"):
        raise AttendanceSettlementError(f"{name}: work_date must be start date")
    length = int((end - start).total_seconds() // 60)
    if length <= 0 or length > 1440 or end - start != timedelta(minutes=length):
        raise AttendanceSettlementError(f"{name}: positive whole-minute interval <=24h required")
    return start, end, length


def _segment_contract(
    coverage: Mapping[str, Any], employee: str, start: date, end: date,
) -> str:
    spans = coverage.get("segments_by_employee")
    if not isinstance(spans, Mapping) or employee not in spans:
        raise AttendanceSettlementError("event: employee missing from contract coverage")
    segment_ids: set[str] = set()
    cursor = start
    while cursor <= end:
        found = [
            part["contract_id"] for part in spans[employee]
            if part["segment_from"] <= cursor.isoformat() <= part["segment_to"]
        ]
        if len(found) != 1:
            raise AttendanceSettlementError("event: calendar day missing or ambiguous contract coverage")
        segment_ids.add(found[0])
        cursor += timedelta(days=1)
    if len(segment_ids) != 1:
        raise AttendanceSettlementError("event: crosses a contract change without split settlement")
    return next(iter(segment_ids))


def _preflight_source(
    source: Mapping[str, Any], coverage: Mapping[str, Any], worktime_sha256: str,
) -> tuple[str, str]:
    source = _exact(source, PLAN_FIELDS, "attendance_plan")
    if source["schema_version"] != "0.1":
        raise AttendanceSettlementError("attendance_plan: unsupported schema_version")
    if ((source["period_from"], source["period_to"])
            != (coverage["period_from"], coverage["period_to"])):
        raise AttendanceSettlementError("attendance_plan: period mismatch")
    if source["settlement_snapshot_ref"] != coverage["snapshot_ref"]:
        raise AttendanceSettlementError("attendance_plan: settlement snapshot mismatch")
    snapshot = _text(source["snapshot_ref"], "snapshot_ref")
    if not isinstance(worktime_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", worktime_sha256):
        raise AttendanceSettlementError("worktime_sha256: lowercase SHA-256 required")
    if source["worktime_sha256"] != worktime_sha256:
        raise AttendanceSettlementError("attendance_plan: Worktime fingerprint mismatch")
    if not isinstance(source["events"], (list, tuple)):
        raise AttendanceSettlementError("attendance_plan.events: list required")
    codes = source["absence_codes"]
    if not isinstance(codes, (list, tuple)) or not codes:
        raise AttendanceSettlementError("attendance_plan.absence_codes: explicit nonempty list required")
    if any(not isinstance(v, str) or not v.strip() for v in codes):
        raise AttendanceSettlementError("absence_codes: nonempty text codes required")
    if len(set(codes)) != len(codes):
        raise AttendanceSettlementError("absence_codes: duplicate classification")
    for code in codes:
        _text(code, "absence_codes")
    return snapshot, source["period_to"]


def _index_worktime(
    rows: Iterable[Mapping[str, Any]], coverage: Mapping[str, Any],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    workers = coverage["segments_by_employee"]
    # Reuse strict 10-column validation, employee/period checks and distinct days.
    validated = tuple(rows)
    review_worktime_facts(
        validated, employee_ids=workers,
        period_from=coverage["period_from"], period_to=coverage["period_to"],
    )
    indexed = {(row["employee_id"], row["work_date"]): row for row in validated}
    for (worker, day), row in indexed.items():
        employment = coverage["employment"][worker]
        if not employment["begin"] <= _day(day, "work_date") <= employment["end"]:
            if (row["actual_min"] not in (None, 0) or row["leave_type"] is not None
                    or row["leave_request_id"] is not None):
                raise AttendanceSettlementError("WORKTIME: worked/leave fact outside verified employment")
    return indexed


def _listed_overtime_check(
    events: list[dict[str, Any]],
    approved_overtime_segments: Iterable[Mapping[str, Any]] | None,
    coverage: Mapping[str, Any],
) -> str:
    if approved_overtime_segments is None:
        return "NOT_ASSESSED"
    from bhandara.payroll.overtime_candidates import APPROVAL_FIELDS, _interval as _overtime_interval
    seen: set[str] = set()
    for source in approved_overtime_segments:
        row = _exact(source, APPROVAL_FIELDS, "approved_overtime_segments")
        segment_id = _text(row["segment_id"], "approved_overtime_segments.segment_id")
        if segment_id in seen or row["approval_status"] != "APPROVED":
            raise AttendanceSettlementError("approved overtime: duplicated or not approved")
        seen.add(segment_id)
        try:
            begin, end, _ = _overtime_interval(row, "approved_overtime")
        except ValueError as exc:
            raise AttendanceSettlementError("approved overtime: invalid time interval") from exc
        worker = _text(row["employee_id"], "approved overtime employee_id")
        if worker not in coverage["segments_by_employee"]:
            raise AttendanceSettlementError("approved overtime: unselected employee")
        last_work_day = (end - timedelta(minutes=1)).date()
        if _segment_contract(coverage, worker, begin.date(), last_work_day) == "":
            raise AttendanceSettlementError("approved overtime: no contract")
        for leave in events:
            if leave["employee_id"] != worker:
                continue
            if begin < leave["end"] and leave["start"] < end:
                raise AttendanceSettlementError(
                    "approved overtime: overlaps paid/unpaid leave or absence interval"
                )
    return "LISTED_SEGMENTS_NO_OVERLAP"


def reconcile_attendance_adjustments(
    coverage: Mapping[str, Any],
    worktime_rows: Iterable[Mapping[str, Any]],
    *,
    attendance_plan: Mapping[str, Any],
    worktime_sha256: str,
    approved_overtime_segments: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate explicit candidate base reductions, never infer from short days.

    A PAID_LEAVE event MUST explicitly carry a zero reduction and contract
    full-cycle base inclusion must be asserted. UNPAID_LEAVE or UNPAID_ABSENCE
    MUST carry an independently authorized integer KRW reduction. Worktime
    alone cannot value either treatment. Events are limited to one per day in
    v0.1 because Worktime exposes only one leave reference per daily row.
    """
    snapshot, period_end = _preflight_source(
        attendance_plan, coverage, worktime_sha256,
    )
    facts = _index_worktime(worktime_rows, coverage)
    used_events: set[str] = set()
    reviewed_days: set[tuple[str, str]] = set()
    leave_references: dict[str, tuple[str, str]] = {}
    per_worker: dict[str, int] = defaultdict(int)
    events: list[dict[str, Any]] = []
    spans: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    for raw in attendance_plan["events"]:
        row = _exact(raw, EVENT_FIELDS, "attendance_event")
        event_id = _text(row["event_id"], "event_id")
        worker = _text(row["employee_id"], "employee_id")
        contract_id = _text(row["contract_id"], "contract_id")
        approval_ref = _text(row["approval_ref"], "approval_ref")
        policy_ref = _text(row["policy_ref"], "policy_ref")
        evidence_ref = _text(row["evidence_ref"], "evidence_ref")
        code = _text(row["worktime_code"], "worktime_code")
        if event_id in used_events:
            raise AttendanceSettlementError("attendance_event: duplicate event_id")
        used_events.add(event_id)
        day = _day(row["work_date"], "work_date").isoformat()
        key = (worker, day)
        if key in reviewed_days:
            raise AttendanceSettlementError("attendance_event: multiple events per Worktime day unsupported")
        reviewed_days.add(key)
        if row["approval_status"] != "APPROVED":
            raise AttendanceSettlementError("attendance_event: APPROVED status required")
        if row["base_amount_not_pre_adjusted"] is not True:
            raise AttendanceSettlementError("attendance_event: explicit non-pre-adjusted base required")
        treatment = row["treatment"]
        if treatment not in TREATMENTS:
            raise AttendanceSettlementError("attendance_event: unsupported wage treatment")
        kind = row["event_kind"]
        if (kind != "LEAVE" and kind != "ATTENDANCE") or (
            treatment == "UNPAID_ABSENCE" and kind != "ATTENDANCE"
        ) or (treatment != "UNPAID_ABSENCE" and kind != "LEAVE"):
            raise AttendanceSettlementError("attendance_event: treatment/kind mismatch")
        start, end, length = _interval(row, "attendance_event")
        requested_minutes = _minutes(row["approved_minutes"], "approved_minutes", positive=True)
        if length != requested_minutes:
            raise AttendanceSettlementError("attendance_event: approved minutes differ from explicit interval")
        if end > datetime.combine(_day(period_end, "period_to") + timedelta(days=1),
                                  datetime.min.time()):
            raise AttendanceSettlementError("attendance_event: interval extends outside payroll period")
        contract = _segment_contract(
            coverage, worker, start.date(), (end - timedelta(minutes=1)).date(),
        )
        if contract != contract_id:
            raise AttendanceSettlementError("attendance_event: contract assignment mismatch")
        worktime = facts.get(key)
        if worktime is None:
            raise AttendanceSettlementError("attendance_event: matching Worktime day missing")
        scheduled = worktime["scheduled_min"]
        if scheduled is None or scheduled == 0 or requested_minutes > scheduled:
            raise AttendanceSettlementError("attendance_event: scheduled-minute coverage unresolved")
        if kind == "LEAVE":
            if worktime["attendance_type"] in attendance_plan["absence_codes"]:
                raise AttendanceSettlementError(
                    "attendance_event: declared absence status conflicts with leave"
                )
            request_id = _text(row["leave_request_id"], "leave_request_id")
            if (worktime["leave_request_id"] != request_id
                    or worktime["leave_type"] != code):
                raise AttendanceSettlementError("attendance_event: Worktime leave reference/type mismatch")
            former = leave_references.get(request_id)
            if former is not None and former != (worker, code):
                raise AttendanceSettlementError("attendance_event: leave request shared across workers/types")
            leave_references[request_id] = (worker, code)
        else:
            if code not in attendance_plan["absence_codes"]:
                raise AttendanceSettlementError(
                    "attendance_event: absence code is not declared by business policy"
                )
            if row["leave_request_id"] is not None or (
                worktime["attendance_type"] != code
                or worktime["leave_type"] is not None
                or worktime["leave_request_id"] is not None
            ):
                raise AttendanceSettlementError("attendance_event: Worktime attendance/leave conflict")
            if worktime["actual_min"] is None:
                raise AttendanceSettlementError("attendance_event: absence with unverified actual minutes")
        amount = _minutes(row["base_reduction_won"], "base_reduction_won")
        if treatment == "PAID_LEAVE":
            if amount:
                raise AttendanceSettlementError("attendance_event: paid leave cannot reduce base")
        elif amount == 0:
            raise AttendanceSettlementError("attendance_event: unpaid event needs explicit positive base reduction")
        per_worker[worker] += amount
        spans[worker].append((start, end))
        events.append({
            "event_id": event_id, "employee_id": worker, "work_date": day,
            "contract_id": contract, "event_kind": kind,
            "worktime_code": code, "treatment": treatment,
            "approved_minutes": requested_minutes,
            "base_reduction_won": amount,
            "approval_ref": approval_ref, "policy_ref": policy_ref,
            "evidence_ref": evidence_ref,
            "start": start, "end": end,
        })

    # An independently recorded Worktime leave reference must not disappear
    # simply because it is missing from the external plan. An attendance code
    # without a declared pay impact remains unclassified and cannot finalize pay.
    unclassified_attendance: list[dict[str, str]] = []
    for (worker, day), row in sorted(facts.items()):
        tagged = row["leave_type"] is not None or row["leave_request_id"] is not None
        if tagged and (worker, day) not in reviewed_days:
            raise AttendanceSettlementError("WORKTIME: unmatched leave fact; silent omission forbidden")
        if (row["attendance_type"] in attendance_plan["absence_codes"]
                and (worker, day) not in reviewed_days):
            raise AttendanceSettlementError(
                "WORKTIME: declared absence code without reviewed pay event"
            )
        if row["attendance_type"] is not None and (worker, day) not in reviewed_days:
            unclassified_attendance.append({
                "employee_id": worker, "work_date": day,
                "attendance_type": row["attendance_type"],
            })
    for worker, segments in spans.items():
        ordered = sorted(segments)
        for (_, previous_end), (next_start, _) in zip(ordered, ordered[1:]):
            if next_start < previous_end:
                raise AttendanceSettlementError("attendance_event: overlapping leave intervals")
    overtime_review = _listed_overtime_check(
        events, approved_overtime_segments, coverage,
    )

    return {
        "schema_version": "0.1", "snapshot_ref": snapshot,
        "settlement_snapshot_ref": coverage["snapshot_ref"],
        "worktime_sha256": worktime_sha256,
        "events": [{
            **{k: v for k, v in event.items() if k not in ("start", "end")},
            "start_at": event["start"].isoformat(timespec="minutes"),
            "end_at": event["end"].isoformat(timespec="minutes"),
        } for event in sorted(events, key=lambda v: (v["employee_id"], v["work_date"]))],
        "base_reductions_by_employee": dict(sorted(per_worker.items())),
        "unclassified_attendance": unclassified_attendance,
        "overtime_overlap_review": overtime_review,
        "worktime_missing_days": "NOT_ASSERTED_COMPLETE",
        "external_source_authenticity": "NOT_AUTHENTICATED_BY_THIS_MODULE",
        "leave_eligibility": "NOT_ASSESSED",
        "final_earnings_status": "INCOMPLETE",
        "approval_state": "NOT_APPROVED",
    }
