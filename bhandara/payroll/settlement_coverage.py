"""P1-5a: validate explicit employee coverage and pay-cycle allocation windows.

The existing calculation_period_from/to are declared *calculation* windows,
not evidence of legal contract effectiveness. An independent employment fact
and approved segment instruction must be provided; references are NOT
authenticated by this module.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable, Mapping

from bhandara.payroll.contract_period import _expected_cycle, _period, _date, PayrollPeriodError


class SettlementCoverageError(ValueError):
    """Employment/contract coverage is missing, ambiguous, or contradictory."""


PLAN_FIELDS = frozenset({
    "schema_version", "period_from", "period_to", "snapshot_ref",
    "proration_method", "rounding_mode", "employment_facts", "allocations",
})
EMPLOYMENT_FIELDS = frozenset({
    "employee_id", "hired_on", "terminated_on", "status", "evidence_ref",
})
ALLOCATION_FIELDS = frozenset({
    "employee_id", "contract_id", "segment_from", "segment_to",
    "approval_status", "approval_ref", "policy_ref",
})


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SettlementCoverageError(f"{label}: nonempty text required")
    item = value.strip()
    if item[0] in ("=", "+", "-", "@", "\t", "\n", "\r"):
        raise SettlementCoverageError(f"{label}: unsafe text")
    return item


def _day(value: Any, label: str) -> date:
    try:
        return _date(value, label)
    except PayrollPeriodError as exc:
        raise SettlementCoverageError(f"{label}: canonical ISO date required") from exc


def _exact(row: Any, expected: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(row, Mapping) or set(row) != expected:
        raise SettlementCoverageError(f"{label}: exact fields required")
    return row


def _list(value: Any, label: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise SettlementCoverageError(f"{label}: list required")
    return tuple(value)


def _intersections(
    contracts: Iterable[Mapping[str, Any]], first: date, last: date,
) -> tuple[dict[str, Mapping[str, Any]], dict[str, set[str]]]:
    """Discover every contract touching the period, rejecting ID ambiguity."""
    active: dict[str, Mapping[str, Any]] = {}
    workers: dict[str, set[str]] = defaultdict(set)
    for row in contracts:
        if not isinstance(row, Mapping):
            raise SettlementCoverageError("contracts: object rows required")
        worker = _text(row.get("employee_id"), "employee_id")
        contract_id = _text(row.get("contract_id"), "contract_id")
        start = _day(row.get("calculation_period_from"), "calculation_period_from")
        end = _day(row.get("calculation_period_to"), "calculation_period_to")
        if start > end:
            raise SettlementCoverageError("contracts: reversed declared calculation period")
        if contract_id in active:
            raise SettlementCoverageError("contracts: duplicate contract_id")
        active[contract_id] = row
        if start <= last and end >= first:
            # A rate denominated in a month must not be divided by seven days.
            try:
                _expected_cycle(row, first, last)
            except PayrollPeriodError as exc:
                raise SettlementCoverageError("contracts: incompatible pay-cycle policy") from exc
            workers[worker].add(contract_id)
    if not workers:
        raise SettlementCoverageError("contracts: no calculation windows intersect requested period")
    return active, workers


def validate_settlement_coverage(
    contracts: Iterable[Mapping[str, Any]],
    *,
    plan: Mapping[str, Any],
    period_from: str,
    period_to: str,
) -> dict[str, Any]:
    """Exact employee-to-contract coverage, with no inferred unpaid absences.

    An employee must be covered *continuously* for every day from the
    intersection of documented employment and requested payroll period.
    A missing segment never means no work, unpaid leave or no wages.
    """
    raw = _exact(plan, PLAN_FIELDS, "settlement_plan")
    if raw["schema_version"] != "0.1":
        raise SettlementCoverageError("settlement_plan: unsupported schema_version")
    try:
        first, last = _period(period_from, period_to)
    except PayrollPeriodError as exc:
        raise SettlementCoverageError("period: invalid payroll period") from exc
    if raw["period_from"] != period_from or raw["period_to"] != period_to:
        raise SettlementCoverageError("settlement_plan: period mismatch")
    snapshot = _text(raw["snapshot_ref"], "snapshot_ref")
    if raw["proration_method"] != "CALENDAR_DAYS":
        raise SettlementCoverageError("proration_method: explicit CALENDAR_DAYS required")
    if raw["rounding_mode"] not in ("DOWN", "HALF_UP"):
        raise SettlementCoverageError("rounding_mode: explicit DOWN or HALF_UP required")
    contracts_by_id, touching = _intersections(contracts, first, last)
    denominator = (last - first).days + 1

    employment: dict[str, dict[str, Any]] = {}
    for item in _list(raw["employment_facts"], "employment_facts"):
        source = _exact(item, EMPLOYMENT_FIELDS, "employment_facts")
        worker = _text(source["employee_id"], "employment_facts.employee_id")
        ref = _text(source["evidence_ref"], "employment_facts.evidence_ref")
        if worker in employment or worker not in touching:
            raise SettlementCoverageError("employment_facts: duplicate or unselected employee")
        if source["status"] != "VERIFIED":
            raise SettlementCoverageError("employment_facts: VERIFIED status required")
        hired = _day(source["hired_on"], "employment_facts.hired_on")
        terminated = (None if source["terminated_on"] is None else
                      _day(source["terminated_on"], "employment_facts.terminated_on"))
        if terminated is not None and terminated < hired:
            raise SettlementCoverageError("employment_facts: termination before hire")
        begin, end = max(first, hired), min(last, terminated or last)
        if begin > end:
            raise SettlementCoverageError("employment_facts: employee outside payroll period")
        employment[worker] = {
            "begin": begin, "end": end, "evidence_ref": ref,
            "hired_on": hired.isoformat(),
            "terminated_on": terminated.isoformat() if terminated else None,
        }
    if set(employment) != set(touching):
        raise SettlementCoverageError("employment_facts: missing employee evidence")

    by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    used: set[str] = set()
    refs: set[str] = set()
    for item in _list(raw["allocations"], "allocations"):
        source = _exact(item, ALLOCATION_FIELDS, "allocations")
        worker = _text(source["employee_id"], "allocations.employee_id")
        contract_id = _text(source["contract_id"], "allocations.contract_id")
        approval_ref = _text(source["approval_ref"], "allocations.approval_ref")
        policy_ref = _text(source["policy_ref"], "allocations.policy_ref")
        if source["approval_status"] != "APPROVED":
            raise SettlementCoverageError("allocations: APPROVED status required")
        if approval_ref in refs:
            raise SettlementCoverageError("allocations: duplicate approval_ref")
        refs.add(approval_ref)
        if worker not in touching or contract_id not in touching[worker]:
            raise SettlementCoverageError("allocations: contract outside worker/period")
        if contract_id in used:
            raise SettlementCoverageError("allocations: contract used more than once")
        used.add(contract_id)
        start = _day(source["segment_from"], "allocations.segment_from")
        end = _day(source["segment_to"], "allocations.segment_to")
        if start > end:
            raise SettlementCoverageError("allocations: reversed segment")
        contract = contracts_by_id[contract_id]
        declared_start = _day(contract["calculation_period_from"], "calculation_period_from")
        declared_end = _day(contract["calculation_period_to"], "calculation_period_to")
        fact = employment[worker]
        if not (first <= start <= end <= last and
                declared_start <= start <= end <= declared_end and
                fact["begin"] <= start <= end <= fact["end"]):
            raise SettlementCoverageError("allocations: outside declared contract/employment boundaries")
        by_worker[worker].append({
            "employee_id": worker, "contract_id": contract_id,
            "segment_from": start.isoformat(), "segment_to": end.isoformat(),
            "days": (end - start).days + 1, "denominator_days": denominator,
            "approval_ref": approval_ref, "policy_ref": policy_ref,
            "employment_ref": fact["evidence_ref"],
        })

    selected: dict[str, tuple[dict[str, Any], ...]] = {}
    for worker, contract_ids in sorted(touching.items()):
        rows = sorted(by_worker[worker], key=lambda item: item["segment_from"])
        if {item["contract_id"] for item in rows} != contract_ids:
            raise SettlementCoverageError("allocations: missing declared overlapping contract")
        expected = employment[worker]["begin"]
        for segment in rows:
            begin = _day(segment["segment_from"], "segment_from")
            if begin != expected:
                raise SettlementCoverageError("allocations: gap or overlap in employed period")
            expected = _day(segment["segment_to"], "segment_to") + timedelta(days=1)
        if expected != employment[worker]["end"] + timedelta(days=1):
            raise SettlementCoverageError("allocations: employed period not fully covered")
        payment_dates = {contracts_by_id[x["contract_id"]].get("payment_date") for x in rows}
        if len(payment_dates) != 1:
            raise SettlementCoverageError("contracts: different payment dates across one payroll cycle")
        selected[worker] = tuple(rows)

    return {
        "schema_version": "0.1",
        "period_from": period_from, "period_to": period_to,
        "snapshot_ref": snapshot, "rounding_mode": raw["rounding_mode"],
        "proration_method": "CALENDAR_DAYS", "denominator_days": denominator,
        "employment": employment, "segments_by_employee": selected,
        "contracts_by_id": contracts_by_id,
        "source_authenticity": "NOT_AUTHENTICATED_BY_THIS_MODULE",
        "earnings_complete": False, "approval_state": "NOT_APPROVED",
    }
