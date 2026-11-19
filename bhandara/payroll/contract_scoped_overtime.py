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
from bhandara.payroll.attendance_preview import build_attendance_adjusted_preview
from bhandara.payroll.core import resolve_contract_pay
from bhandara.payroll.evidence_reconciliation import reconcile_overtime_evidence
from bhandara.payroll.input_excel import PayrollInputs
from bhandara.payroll.overtime_candidates import (
    OvertimeCandidateError, _interval, calculate_overtime_candidates,
)
from bhandara.payroll.output import build_payroll_register
from bhandara.payroll.settlement_coverage import validate_settlement_coverage
from bhandara.worktime.output_excel import read_worktime_xlsx


class ContractOvertimeAdapterError(ValueError):
    """Missing contract allocation, source consistency or explicit rollup policy."""


ROLLUP_FIELDS = frozenset({"mode", "policy_ref"})
ROLLUP_MODE = "ROUND_PER_CONTRACT_RULE_THEN_SUM"
ITEM_CATEGORIES = ("fixed_allowances", "performance_bonuses", "deductions")


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


def _merge_candidates(
    original: Mapping[str, Any],
    candidate_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rehydrate the existing dynamic register via its public columns/rows.

    The output's dynamic item columns are already filtered to nonzero amounts.
    Keep the existing base, fixed allowances, bonuses, and employee names,
    preserving the user's one-sheet Output and completion-gate contracts.
    """
    columns = original["columns"]
    if any(col.get("source") == "overtime_allowances" for col in columns):
        raise ContractOvertimeAdapterError("register: overtime already present; double-payment blocked")
    by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_worker[row["employee_id"]].append({
            "item_id": row["item_id"], "label": row["label"],
            "amount": row["amount"],
        })
    valid = {row["employee_id"] for row in original["rows"]}
    if set(by_worker) - valid:
        raise ContractOvertimeAdapterError("candidate: employee not present in register")
    merged = []
    for employee in original["rows"]:
        worker = employee["employee_id"]
        source = {
            "employee_id": worker,
            "base_pay": employee["base_pay"],
            "overtime_allowances": by_worker.get(worker, []),
            "earnings_complete": False,
            "deductions_complete": False,
        }
        if "employee_name" in employee:
            source["employee_name"] = employee["employee_name"]
        for category in ITEM_CATEGORIES:
            source[category] = [
                {
                    "item_id": column["item_id"],
                    "label": column["label"],
                    "amount": employee[column["key"]],
                }
                for column in columns if column.get("source") == category
                and employee.get(column["key"]) is not None
            ]
        merged.append(source)
    return build_payroll_register(merged)


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
    # P1-5b-1 checks leave/absence vs submitted overtime intervals before
    # applying any base adjustment. It also checks Worktime's source SHA.
    attendance_preview = build_attendance_adjusted_preview(
        inputs, path,
        settlement_plan=settlement_plan, attendance_plan=attendance_plan,
        period_from=period_from, period_to=period_to,
        approved_overtime_segments=source_approvals,
    )
    if sha256_file(path) != fingerprint:
        raise ContractOvertimeAdapterError("WORKTIME: source changed during attendance review")
    worktime_rows = read_worktime_xlsx(path)
    if sha256_file(path) != fingerprint:
        raise ContractOvertimeAdapterError("WORKTIME: source changed during overtime review")

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
    # Audit traceability is not an approval. The separate registry was checked
    # for content consistency, not independently authenticated.
    out = dict(attendance_preview)
    out["payroll_register"] = _merge_candidates(attendance_preview["payroll_register"], rows)
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
    out["settlement_review"]["overtime_reconciliation"] = (
        "LISTED_APPROVED_SEGMENTS_CHECKED_NOT_COMPLETE"
    )
    out["status"] = "PARTIAL_REVIEW_ONLY"
    out["approval_state"] = "NOT_APPROVED"
    if sha256_file(path) != fingerprint:
        raise ContractOvertimeAdapterError("WORKTIME: source changed after candidate composition")
    return out
