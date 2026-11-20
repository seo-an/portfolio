"""P1-5b-2b-2: explicit leave wage decisions, without revaluing PTO days.

PTO Closing provides request *quantities*, not monetary entitlements.
Only independently approved wage decisions may reduce the P1-5a base
candidate or its existing fixed allowance items. The existing Worktime
single-request attendance settlement is reconciled, never applied twice.
No tax, pension, gross, or payable wage amount is finalized here.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from bhandara.payroll.pto_closing_review import PTOClosingReviewError


class LeaveWageAdjustmentError(ValueError):
    """Incomplete or contradictory monetary decisions for verified PTO use."""


FIELDS = frozenset({"schema_version", "pto_closing_id", "policy_ref", "decisions"})
DECISION_FIELDS = frozenset({
    "employee_id", "request_id", "leave_date", "pto_leave_type",
    "treatment", "base_reduction_won", "fixed_reductions",
    "approval_status", "approval_ref", "evidence_ref",
    "base_not_pre_adjusted", "fixed_not_pre_adjusted",
})
FIXED_FIELDS = frozenset({"allowance_id", "amount_won", "policy_ref"})
TREATMENTS = {"PAID_LEAVE", "UNPAID_LEAVE"}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LeaveWageAdjustmentError(f"{field}: nonempty text required")
    value = value.strip()
    if value[0] in "=+-@\t\r\n":
        raise LeaveWageAdjustmentError(f"{field}: unsafe reference")
    return value


def _won(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise LeaveWageAdjustmentError(f"{field}: nonnegative integer KRW required")
    return value


def _request_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return tuple(
        _text(row.get(field), field)
        for field in ("employee_id", "request_id", "leave_date", "pto_leave_type")
    )


def reconcile_leave_wage_decisions(
    pto_review: Mapping[str, Any],
    attendance_review: Mapping[str, Any],
    *,
    wage_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Require ONE independently approved monetary decision per PTO request.

    The original attendance adapter has already adjusted the base for its
    single Worktime-anchored request. Do not subtract that money again.
    """
    if not isinstance(wage_plan, Mapping) or set(wage_plan) != FIELDS:
        raise LeaveWageAdjustmentError("leave_wage_plan: exact fields required")
    if wage_plan["schema_version"] != "0.1":
        raise LeaveWageAdjustmentError("leave_wage_plan: unsupported schema")
    if wage_plan["pto_closing_id"] != pto_review.get("closing_id"):
        raise LeaveWageAdjustmentError("leave_wage_plan: mismatched confirmed Closing")
    policy = _text(wage_plan["policy_ref"], "policy_ref")
    if not isinstance(wage_plan["decisions"], (list, tuple)):
        raise LeaveWageAdjustmentError("decisions: list required")
    source_requests = pto_review.get("requests")
    if (pto_review.get("source_consistency") != "MATCHED_FOR_CURRENT_QUARTER_MONTH"
            or pto_review.get("closing_confirmed") is not True
            or not isinstance(source_requests, list)):
        raise LeaveWageAdjustmentError("PTO: confirmed source review required")
    expected: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    for request in source_requests:
        key = _request_key(request)
        if key in expected:
            raise LeaveWageAdjustmentError("PTO: duplicate source request")
        expected[key] = request

    # P1-5b-1 may also have non-PTO absence events; only the approved
    # Worktime leave IDs are candidates for matching these PTO requests.
    existing: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for event in attendance_review.get("events", []):
        if event["event_kind"] != "LEAVE":
            continue
        key = (event["employee_id"], event["work_date"],
               event.get("leave_request_id"))
        # P1-5b-1 review exposes event IDs and dates but not the raw request
        # ID. That identifier is supplied explicitly from the verified
        # attendance_plan in the outer flow.
        if key[2] is not None:
            if key in existing:
                raise LeaveWageAdjustmentError("attendance: repeated leave request")
            existing[key] = event

    by_request = {}
    base_total: dict[str, int] = defaultdict(int)
    fixed_totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in wage_plan["decisions"]:
        if not isinstance(row, Mapping) or set(row) != DECISION_FIELDS:
            raise LeaveWageAdjustmentError("decision: exact fields required")
        key = _request_key(row)
        if key not in expected or key in by_request:
            raise LeaveWageAdjustmentError("decision: unknown or duplicate PTO request")
        if row["approval_status"] != "APPROVED":
            raise LeaveWageAdjustmentError("decision: independent wage approval required")
        approval = _text(row["approval_ref"], "approval_ref")
        evidence = _text(row["evidence_ref"], "evidence_ref")
        treatment = row["treatment"]
        if treatment not in TREATMENTS:
            raise LeaveWageAdjustmentError("decision: PAID_LEAVE/UNPAID_LEAVE required")
        if row["base_not_pre_adjusted"] is not True or row["fixed_not_pre_adjusted"] is not True:
            raise LeaveWageAdjustmentError("decision: pre-adjusted wage cannot be reduced again")
        amount = _won(row["base_reduction_won"], "base_reduction_won")
        if treatment == "PAID_LEAVE" and amount:
            raise LeaveWageAdjustmentError("decision: paid leave cannot reduce base")
        if treatment == "UNPAID_LEAVE" and not amount:
            raise LeaveWageAdjustmentError("decision: unpaid leave needs explicit positive base reduction")
        reductions = row["fixed_reductions"]
        if not isinstance(reductions, (list, tuple)):
            raise LeaveWageAdjustmentError("fixed_reductions: explicit list required")
        fixed = {}
        for item in reductions:
            if not isinstance(item, Mapping) or set(item) != FIXED_FIELDS:
                raise LeaveWageAdjustmentError("fixed_reductions: exact fields required")
            code = _text(item["allowance_id"], "allowance_id")
            _text(item["policy_ref"], "fixed_reduction.policy_ref")
            value = _won(item["amount_won"], "amount_won")
            if code in fixed or value == 0:
                raise LeaveWageAdjustmentError("fixed_reductions: duplicate ID or zero reduction")
            fixed[code] = value
            fixed_totals[key[0]][code] += value
        if treatment == "PAID_LEAVE" and fixed:
            # Paid leave may still trigger a distinct allowance condition,
            # but it needs a separate policy contract, not this deduction path.
            raise LeaveWageAdjustmentError("decision: paid leave fixed allowance reduction unsupported")
        base_total[key[0]] += amount
        by_request[key] = {
            "employee_id": key[0], "request_id": key[1],
            "leave_date": key[2], "pto_leave_type": key[3],
            "treatment": treatment, "base_reduction_won": amount,
            "fixed_reductions": fixed,
            "approval_ref": approval, "evidence_ref": evidence,
        }
    if set(by_request) != set(expected):
        raise LeaveWageAdjustmentError("decisions: missing approved wage treatment for PTO requests")
    return {
        "schema_version": "0.1",
        "pto_closing_id": pto_review["closing_id"],
        "policy_ref": policy,
        "requests": [by_request[key] for key in sorted(by_request)],
        "base_reductions_by_employee": dict(base_total),
        "fixed_reductions_by_employee": {
            worker: dict(values) for worker, values in fixed_totals.items()
        },
        "wage_source_authenticity": "NOT_AUTHENTICATED_BY_THIS_MODULE",
        "approval_state": "NOT_APPROVED",
        "earnings_complete": False,
    }


def apply_leave_wage_decisions(
    payroll_rows: list[dict[str, Any]],
    settlement_review: Mapping[str, Any],
    attendance_review: Mapping[str, Any],
    wage_review: Mapping[str, Any],
    *,
    attendance_plan: Mapping[str, Any],
) -> None:
    """Mutate only in-memory employee candidate items BEFORE one Output render."""
    roster = {row["employee_id"]: row for row in payroll_rows}
    if len(roster) != len(payroll_rows):
        raise LeaveWageAdjustmentError("payroll: duplicated employee")
    existing: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for raw in attendance_plan["events"]:
        if raw["event_kind"] != "LEAVE":
            continue
        key = (raw["employee_id"], raw["work_date"], raw["leave_request_id"])
        if key in existing:
            raise LeaveWageAdjustmentError("attendance: duplicate anchored request")
        existing[key] = raw
    audited = {
        (item["employee_id"], item["work_date"], item["event_id"]): item
        for item in attendance_review["events"]
        if item["event_kind"] == "LEAVE"
    }
    accounted_anchors = set()
    addition: dict[str, int] = defaultdict(int)
    for item in wage_review["requests"]:
        worker, day, request = item["employee_id"], item["leave_date"], item["request_id"]
        if worker not in roster:
            raise LeaveWageAdjustmentError("wage decision: employee missing from payroll")
        key = (worker, day, request)
        if key in existing:
            old = existing[key]
            audit = audited.get((worker, day, old["event_id"]))
            if audit is None:
                raise LeaveWageAdjustmentError("attendance: source event missing")
            if (old["treatment"] != item["treatment"]
                    or old["base_reduction_won"] != item["base_reduction_won"]
                    or audit["base_reduction_won"] != item["base_reduction_won"]):
                raise LeaveWageAdjustmentError("attendance: base reduction/treatment conflicts with PTO decision")
            accounted_anchors.add(key)
        else:
            addition[worker] += item["base_reduction_won"]
    # A Worktime-anchored leave event must not be left outside monetary
    # reconciliation if it is among the submitted PTO requests. Non-PTO
    # attendance events remain outside this optional PTO-only review.
    known = {(r["employee_id"], r["leave_date"], r["request_id"]) for r in wage_review["requests"]}
    for key in existing:
        if key not in known:
            raise LeaveWageAdjustmentError("attendance: leave event not covered by PTO wage decisions")
    for worker, extra in addition.items():
        if extra > roster[worker]["base_pay"]:
            raise LeaveWageAdjustmentError("base: extra leave reductions exceed candidate wage")
    for worker, totals in wage_review["fixed_reductions_by_employee"].items():
        items = {item["item_id"]: item for item in roster[worker]["fixed_allowances"]}
        for code, reduction in totals.items():
            if code not in items or reduction > items[code]["amount"]:
                raise LeaveWageAdjustmentError("fixed allowance: absent or reduction exceeds candidate")
    for worker, extra in addition.items():
        roster[worker]["base_pay"] -= extra
    for worker, totals in wage_review["fixed_reductions_by_employee"].items():
        items = {item["item_id"]: item for item in roster[worker]["fixed_allowances"]}
        for code, reduction in totals.items():
            items[code]["amount"] -= reduction
    # Update review fields to match visible base/fixed candidate amounts.
    audits = {row["employee_id"]: row for row in settlement_review["employees"]}
    for worker, row in roster.items():
        audit = audits[worker]
        if worker in addition:
            audit["base_pay_candidate"] = row["base_pay"]
            audit["base_reduction_candidate"] = (
                (audit["base_reduction_candidate"] or 0) + addition[worker]
            )
        if worker in wage_review["fixed_reductions_by_employee"]:
            audit["fixed_allowance_candidates"] = [dict(item) for item in row["fixed_allowances"]]
    settlement_review["pto_wage_reconciliation"] = "EXPLICIT_REQUEST_DECISIONS_APPLIED_AS_CANDIDATES"
