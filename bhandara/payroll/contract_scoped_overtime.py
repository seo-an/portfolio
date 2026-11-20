"""P1-5b-2a: combine independently reviewed leave with contract-scoped overtime.

This adapter deliberately leaves PTO, Worktime, P1-2 candidate arithmetic,
P1-3 source reconciliation, P1-5a contract coverage, P1-5b-1 attendance
reconciliation and the final one-sheet Output contract unchanged.

Explicit contract-by-contract rounding is a DIFFERENT rule from the original
single-contract per-employee/rule/period candidate arithmetic; the separate
rollup policy must acknowledge it. No legal entitlement is inferred.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.attendance_reconciliation import reconcile_attendance_adjustments
from bhandara.payroll.core import resolve_contract_pay
from bhandara.payroll.evidence_reconciliation import reconcile_overtime_evidence
from bhandara.payroll.input_excel import PayrollInputs
from bhandara.payroll.overtime_candidates import (
    OvertimeCandidateError, _interval, calculate_overtime_candidates,
)
from bhandara.payroll.output import build_payroll_register
from bhandara.payroll.leave_wage_adjustments import (
    reconcile_leave_wage_decisions, apply_leave_wage_decisions,
)
from bhandara.payroll.pto_closing_review import reconcile_pto_closing
from bhandara.payroll.settlement_coverage import validate_settlement_coverage
from bhandara.payroll.segmented_settlement import _build_segmented_components
from bhandara.payroll.worktime_bridge import _verify_worktime_workbook, review_worktime_facts
from bhandara.worktime.output_excel import read_worktime_xlsx


class ContractOvertimeAdapterError(ValueError):
    """Missing contract allocation, source consistency or explicit rollup policy."""


ROLLUP_FIELDS = frozenset({"mode", "policy_ref"})
ROLLUP_MODE = "ROUND_PER_CONTRACT_RULE_THEN_SUM"

def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractOvertimeAdapterError(f"{name}: safe nonempty text required")
    result = value.strip()
    if result[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        raise ContractOvertimeAdapterError(f"{name}: unsafe policy text")
    return result


def _rollup_policy(policy: Any, rate_policy: Mapping[str, Any]) -> str:
    if not isinstance(policy, Mapping) or set(policy) != ROLLUP_FIELDS:
        raise ContractOvertimeAdapterError("rollup_policy: exact mode and policy_ref required")
    if policy["mode"] != ROLLUP_MODE:
        raise ContractOvertimeAdapterError("rollup_policy: explicit per-contract rounding required")
    if not isinstance(rate_policy, Mapping) or rate_policy.get("rounding_scope") != "EMPLOYEE_RULE_PERIOD":
        raise ContractOvertimeAdapterError("rate_policy: P1-2 employee/rule/period rounding required")
    return _text(policy["policy_ref"], "rollup_policy.policy_ref")


def _covered_contract(coverage: Mapping[str, Any], row: Mapping[str, Any], kind: str) -> str:
    try:
        start, end, _ = _interval(row, kind)
    except OvertimeCandidateError as exc:
        raise ContractOvertimeAdapterError(f"{kind}: invalid approved interval") from exc
    employee = _text(row.get("employee_id"), f"{kind}.employee_id")
    spans = coverage["segments_by_employee"]
    if employee not in spans:
        raise ContractOvertimeAdapterError(f"{kind}: employee outside verified contract coverage")
    cursor = start.date()
    last = (end - timedelta(microseconds=1)).date()
    matched: set[str] = set()
    while cursor <= last:
        allocations = [
            part["contract_id"] for part in spans[employee]
            if part["segment_from"] <= cursor.isoformat() <= part["segment_to"]
        ]
        if len(allocations) != 1:
            raise ContractOvertimeAdapterError(
                f"{kind}: work interval outside continuous employment/contract assignment"
            )
        matched.add(allocations[0])
        cursor += timedelta(days=1)
    if len(matched) != 1:
        raise ContractOvertimeAdapterError(
            f"{kind}: crosses mid-period contract boundary; independently split and reapprove"
        )
    return next(iter(matched))


def _partition_evidence(
    coverage: Mapping[str, Any],
    verified_work: Iterable[Mapping[str, Any]],
    approved_segments: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], dict[str, list[Mapping[str, Any]]]]:
    """Never rewrite, split, or invent an evidence ID or an approved interval."""
    by_scope: dict[tuple[str, str], dict[str, list[Mapping[str, Any]]]] = defaultdict(
        lambda: {"verified_work": [], "approved_segments": []}
    )
    evidence_scope: dict[str, tuple[str, str]] = {}
    for row in verified_work:
        evidence_id = _text(row.get("evidence_id"), "evidence_id")
        if evidence_id in evidence_scope:
            raise ContractOvertimeAdapterError("verified_work: duplicate evidence_id")
        worker = _text(row.get("employee_id"), "employee_id")
        contract_id = _covered_contract(coverage, row, "verified_work")
        scope = (worker, contract_id)
        evidence_scope[evidence_id] = scope
        by_scope[scope]["verified_work"].append(row)
    used_segments: set[str] = set()
    for row in approved_segments:
        segment_id = _text(row.get("segment_id"), "segment_id")
        worker = _text(row.get("employee_id"), "employee_id")
        if segment_id in used_segments:
            raise ContractOvertimeAdapterError("approved_segment: duplicate segment_id")
        used_segments.add(segment_id)
        scope = (worker, _covered_contract(coverage, row, "approved_segment"))
        if evidence_scope.get(_text(row.get("work_evidence_id"), "work_evidence_id")) != scope:
            raise ContractOvertimeAdapterError(
                "approved_segment: work evidence and approval belong to different contracts"
            )
        by_scope[scope]["approved_segments"].append(row)
    return dict(sorted(by_scope.items()))


def _worktime_for_contract(
    rows: Iterable[Mapping[str, Any]], coverage: Mapping[str, Any],
    worker: str, contract_id: str,
) -> list[Mapping[str, Any]]:
    spans = [
        item for item in coverage["segments_by_employee"][worker]
        if item["contract_id"] == contract_id
    ]
    if len(spans) != 1:
        raise ContractOvertimeAdapterError("contract: expected exactly one allocated span")
    span = spans[0]
    return [
        row for row in rows
        if (row["employee_id"] == worker
            and span["segment_from"] <= row["work_date"] <= span["segment_to"])
    ]


def _attach_overtime_items(
    payroll_rows: list[dict[str, Any]],
    candidate_rows: Iterable[Mapping[str, Any]],
) -> None:
    """Append checked item amounts before the one and only Output render."""
    roster = {row["employee_id"]: row for row in payroll_rows}
    for item in candidate_rows:
        employee = roster.get(item["employee_id"])
        if employee is None:
            raise ContractOvertimeAdapterError("candidate: employee not present in register")
        if employee["overtime_allowances"]:
            if any(old["item_id"] == item["item_id"]
                   for old in employee["overtime_allowances"]):
                raise ContractOvertimeAdapterError("candidate: duplicate overtime item")
        employee["overtime_allowances"].append({
            "item_id": item["item_id"],
            "label": item["label"],
            "amount": item["amount"],
        })


def build_contract_scoped_overtime_preview(
    inputs: PayrollInputs,
    worktime_xlsx: str | Path,
    *,
    settlement_plan: Mapping[str, Any],
    attendance_plan: Mapping[str, Any],
    period_from: str,
    period_to: str,
    verified_work: Iterable[Mapping[str, Any]],
    approved_segments: Iterable[Mapping[str, Any]],
    evidence_registry: Mapping[str, Any],
    rate_policy: Mapping[str, Any],
    rollup_policy: Mapping[str, Any],
    pto_sources: Mapping[str, Any] | None = None,
    pto_wage_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Contract-scoped approved overtime is a *candidate*, never final wages.

    Existing function boundaries are preserved. Crossing-contract intervals
    fail instead of inventing a different verified time interval.
    """
    if "overtime_rules" not in inputs.rows:
        raise ContractOvertimeAdapterError("inputs: overtime_rules role is required")
    rollup_ref = _rollup_policy(rollup_policy, rate_policy)
    coverage = validate_settlement_coverage(
        inputs.for_role("contracts"), plan=settlement_plan,
        period_from=period_from, period_to=period_to,
    )
    source_work = tuple(verified_work)
    source_approvals = tuple(approved_segments)
    reviewed_evidence = reconcile_overtime_evidence(
        verified_work=source_work, approved_segments=source_approvals,
        registry=evidence_registry,
        overtime_rules=inputs.for_role("overtime_rules"),
        period_from=period_from, period_to=period_to,
    )
    # Partition the independently reconciled evidence *before* the
    # attendance bridge, so cross-contract intervals are never passed to
    # a single-contract pay function or misread as one rate.
    by_scope = _partition_evidence(coverage, source_work, source_approvals)
    path = Path(worktime_xlsx)
    if path.name != "worktime-result.xlsx" or not path.is_file():
        raise ContractOvertimeAdapterError("WORKTIME: worktime-result.xlsx required")
    fingerprint = sha256_file(path)
    # Worktime: inspect and parse once for every downstream fact/approval
    # check. No intermediate Payroll register is built at this stage.
    _verify_worktime_workbook(path)
    worktime_rows = read_worktime_xlsx(path)
    if sha256_file(path) != fingerprint:
        raise ContractOvertimeAdapterError("WORKTIME: source changed during read")
    attendance = reconcile_attendance_adjustments(
        coverage, worktime_rows,
        attendance_plan=attendance_plan, worktime_sha256=fingerprint,
        approved_overtime_segments=source_approvals,
    )
    worktime_review = review_worktime_facts(
        worktime_rows, employee_ids=coverage["segments_by_employee"],
        period_from=period_from, period_to=period_to,
    )
    pto_review = None
    if pto_sources is not None:
        required = {"usage_file", "closing_file", "deduction_file", "pto_claims"}
        if not isinstance(pto_sources, Mapping) or set(pto_sources) != required:
            raise ContractOvertimeAdapterError("pto_sources: four explicit source fields required")
        pto_review = reconcile_pto_closing(
            usage_file=pto_sources["usage_file"],
            closing_file=pto_sources["closing_file"],
            deduction_file=pto_sources["deduction_file"],
            pto_claims=pto_sources["pto_claims"],
            worktime_rows=worktime_rows,
            period_from=period_from, period_to=period_to,
        )
    if pto_wage_plan is not None and pto_review is None:
        raise ContractOvertimeAdapterError("pto_wage_plan: verified PTO sources are required")
    components = _build_segmented_components(
        inputs, coverage=coverage,
        period_from=period_from, period_to=period_to,
        base_reductions=attendance["base_reductions_by_employee"],
    )
    settlement_review = components["settlement_review"]
    settlement_review["paid_leave_verification"] = (
        "LISTED_EVENTS_MATCH_WORKTIME_NOT_AUTHENTICATED"
    )
    settlement_review["worktime_integration"] = (
        "FACTS_REVIEWED_NOT_PAYROLL_APPROVAL"
    )
    settlement_review["overtime_reconciliation"] = (
        "LISTED_APPROVED_SEGMENTS_CHECKED_NOT_COMPLETE"
    )

    aggregated: dict[tuple[str, str], dict[str, Any]] = {}
    scoped_reviews: list[dict[str, Any]] = []
    for (worker, contract_id), subset in by_scope.items():
        contract = resolve_contract_pay([coverage["contracts_by_id"][contract_id]])
        if set(contract) != {worker}:
            raise ContractOvertimeAdapterError("contract: selected employee mismatch")
        scoped = calculate_overtime_candidates(
            contract, _worktime_for_contract(worktime_rows, coverage, worker, contract_id),
            inputs.for_role("overtime_rules"),
            verified_work=subset["verified_work"],
            approved_segments=subset["approved_segments"],
            policy=rate_policy,
        )
        for item in scoped["rows"]:
            key = (worker, item["item_id"])
            if key not in aggregated:
                aggregated[key] = {
                    "employee_id": worker, "item_id": item["item_id"],
                    "label": item["label"], "category": item["category"],
                    "minutes": 0, "amount": 0, "segment_ids": [],
                    "status": "CALCULATED_CANDIDATE_NOT_APPROVED",
                }
            bucket = aggregated[key]
            if bucket["label"] != item["label"] or bucket["category"] != item["category"]:
                raise ContractOvertimeAdapterError("candidate: rule label/category mismatch across contracts")
            bucket["amount"] += item["amount"]  # integer after contract-level rounding
            bucket["minutes"] += item["minutes"]
            bucket["segment_ids"].extend(item["segment_ids"])
        scoped_reviews.append({
            "employee_id": worker,
            "contract_id": contract_id,
            "daily_base_rate": str(contract[worker]["daily_base_rate"]),
            "reference_day_minutes": str(rate_policy["reference_day_minutes_by_contract"].get(contract_id)),
            "verified_work_ids": sorted(item["evidence_id"] for item in subset["verified_work"]),
            "approved_segment_ids": sorted(item["segment_id"] for item in subset["approved_segments"]),
            "candidates": scoped["rows"],
            "stacking_review": scoped["stacking_review"],
        })

    rows = [aggregated[key] for key in sorted(aggregated)]
    # Additional per-request monetary decisions can only be applied after
    # exact PTO source review, and before the single dynamic Output render.
    pto_wage_review = None
    if pto_wage_plan is not None:
        pto_wage_review = reconcile_leave_wage_decisions(
            pto_review, attendance, wage_plan=pto_wage_plan,
        )
        apply_leave_wage_decisions(
            components["payroll_rows"], settlement_review, attendance,
            pto_wage_review, attendance_plan=attendance_plan,
        )
    _attach_overtime_items(components["payroll_rows"], rows)
    out = {
        "payroll_register": build_payroll_register(components["payroll_rows"]),
        "settlement_review": settlement_review,
        "status": "PARTIAL_REVIEW_ONLY",
        "approval_state": "NOT_APPROVED",
        "attendance_review": attendance,
        "worktime_review": worktime_review,
    }
    if pto_review is not None:
        out["pto_closing_review"] = pto_review
    if pto_wage_review is not None:
        out["pto_wage_review"] = pto_wage_review
    out["overtime_candidate_review"] = {
        "schema_version": "0.1",
        "rows": rows,
        "contract_scopes": scoped_reviews,
        "rollup_mode": ROLLUP_MODE,
        "rollup_policy_ref": rollup_ref,
        "candidate_rounding": "PER_CONTRACT_RULE_BEFORE_EMPLOYEE_ROLLUP",
        "earnings_complete": False,
        "payable_minutes_finalized": False,
        "approval_state": "NOT_APPROVED",
    }
    out["evidence_review"] = {
        key: value for key, value in reviewed_evidence.items()
        if key not in ("verified_work", "approved_segments")
    }
    if sha256_file(path) != fingerprint:
        raise ContractOvertimeAdapterError("WORKTIME: source changed after candidate composition")
    return out
