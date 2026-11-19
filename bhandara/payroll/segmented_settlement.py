"""P1-5a: policy-declared calendar-day salary and allowance proration preview.

Contracts retain their *full-cycle* pay rates; an independently supplied plan
allocates the employee's days to those rates. Segment calculations are
aggregated BEFORE a single employee/item/period rounding. This is not legal
entitlement review, leave accounting, or payment authorization.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from bhandara.payroll.core import (
    resolve_contract_pay, resolve_fixed_allowances, allocate_performance_bonus,
)
from bhandara.payroll.input_excel import PayrollInputs
from bhandara.payroll.output import build_payroll_register
from bhandara.payroll.review_adapter import _require_roles, _names_for_ids, _as_items
from bhandara.payroll.settlement_coverage import validate_settlement_coverage


class SettlementPreviewError(ValueError):
    """An allowance or salary allocation cannot be safely aggregated."""


ROUNDING = {"DOWN": ROUND_DOWN, "HALF_UP": ROUND_HALF_UP}


def _rounded(value: Decimal, mode: str) -> int:
    return int(value.to_integral_value(rounding=ROUNDING[mode]))


def _aggregate_contract_components(
    worker: str,
    segments: Iterable[Mapping[str, Any]],
    *,
    contract_rows: Mapping[str, Mapping[str, Any]],
    allowances: tuple[Mapping[str, Any], ...],
    assignments: tuple[Mapping[str, Any], ...],
) -> tuple[Decimal, dict[str, Decimal], list[dict[str, Any]]]:
    base = Decimal(0)
    fixed_totals: dict[str, Decimal] = defaultdict(Decimal)
    classifications: dict[str, tuple[str, str]] = {}
    audit: list[dict[str, Any]] = []
    for segment in segments:
        contract_id = segment["contract_id"]
        rate = resolve_contract_pay([contract_rows[contract_id]])[worker]
        current_assignment = [
            row for row in assignments if row["contract_id"] == contract_id
        ]
        fixed = resolve_fixed_allowances(
            {worker: rate}, allowances, current_assignment,
        )[worker]
        portion = Decimal(segment["days"]) / Decimal(segment["denominator_days"])
        base_component = rate["base_pay"] * portion
        base += base_component
        for item in fixed:
            code = item["allowance_id"]
            classification = (item["payroll_taxability"], item["taxability_policy_ref"])
            previous = classifications.get(code)
            if previous is not None and previous != classification:
                raise SettlementPreviewError(
                    "fixed allowance: taxability classification changed across segments"
                )
            classifications[code] = classification
            fixed_totals[code] += item["amount"] * portion
        audit.append({
            **segment,
            "unrounded_base_component": str(base_component),
            "fixed_allowance_ids": sorted(x["allowance_id"] for x in fixed),
        })
    return base, fixed_totals, audit


def _build_segmented_components(
    inputs: PayrollInputs,
    *,
    coverage: Mapping[str, Any],
    period_from: str,
    period_to: str,
    base_reductions: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Return reviewed employee items without prematurely rendering Output.

    The integrated Payroll flow can attach other vetted components first,
    then build the dynamic one-sheet register exactly once. The public
    P1-5a preview below retains its existing input/output contract.
    """
    _require_roles(inputs)
    allowance_rows = inputs.for_role("fixed_allowance_map")
    allowance_assignments = inputs.for_role("allowance_assignments")
    names = _names_for_ids(
        allowance_rows, id_field="allowance_id", label_field="allowance_name",
    )
    bonus_names = _names_for_ids(
        inputs.for_role("bonus_budget"), id_field="bonus_id", label_field="bonus_name",
    )
    workers = coverage["segments_by_employee"]
    if base_reductions is not None:
        if not isinstance(base_reductions, Mapping) or set(base_reductions) - set(workers):
            raise SettlementPreviewError("base_reductions: unknown worker or invalid mapping")
        if any(type(amount) is not int or amount < 0 for amount in base_reductions.values()):
            raise SettlementPreviewError("base_reductions: nonnegative integer KRW required")
    # This existing Bonus Core uses only the worker keys, not a contract rate.
    # Bonuses remain once per employee and are NOT prorated by calendar days.
    bonuses = allocate_performance_bonus(
        {worker: {} for worker in workers},
        inputs.for_role("bonus_budget"), inputs.for_role("bonus_allocation"),
    )
    rows: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for worker, segments in sorted(workers.items()):
        base, fixed, contract_audit = _aggregate_contract_components(
            worker, segments,
            contract_rows=coverage["contracts_by_id"],
            allowances=allowance_rows,
            assignments=allowance_assignments,
        )
        base_before_adjustment = _rounded(base, coverage["rounding_mode"])
        reduction = (base_reductions or {}).get(worker, 0)
        if reduction > base_before_adjustment:
            raise SettlementPreviewError("base_reductions: reduction exceeds candidate base")
        employee_base = base_before_adjustment - reduction
        employee_fixed = [
            {"item_id": code, "label": names[code],
             "amount": _rounded(amount, coverage["rounding_mode"])}
            for code, amount in sorted(fixed.items())
        ]
        rows.append({
            "employee_id": worker,
            "base_pay": employee_base,
            "fixed_allowances": employee_fixed,
            "performance_bonuses": _as_items(
                bonuses[worker], bonus_names, id_field="bonus_id",
            ),
            "overtime_allowances": [],  # not assessed here, NOT proven zero
            "deductions": [],          # not assessed here, NOT proven zero
            "earnings_complete": False,
            "deductions_complete": False,
        })
        audits.append({
            "employee_id": worker,
            "employment_evidence_ref": coverage["employment"][worker]["evidence_ref"],
            "hired_on": coverage["employment"][worker]["hired_on"],
            "terminated_on": coverage["employment"][worker]["terminated_on"],
            "base_pay_candidate": employee_base,
            "base_before_attendance_adjustment": base_before_adjustment,
            "base_reduction_candidate": reduction if base_reductions is not None else None,
            "fixed_allowance_candidates": employee_fixed,
            "segments": contract_audit,
            "leave_settlement": "NOT_ASSESSED",
            "overtime_reconciliation": "NOT_ASSESSED",
        })
    return {
        "payroll_rows": rows,
        "settlement_review": {
            "schema_version": "0.1",
            "period_from": period_from,
            "period_to": period_to,
            "snapshot_ref": coverage["snapshot_ref"],
            "proration_method": coverage["proration_method"],
            "rounding_mode": coverage["rounding_mode"],
            "denominator_days": coverage["denominator_days"],
            "source_authenticity": coverage["source_authenticity"],
            "employees": audits,
            "employment_coverage": "DECLARED_COVERAGE_MATCHED",
            "paid_leave_verification": "NOT_ASSESSED",
            "unpaid_leave_adjustments": (
                "LISTED_BASE_REDUCTIONS_AS_CANDIDATES"
                if base_reductions is not None else "NOT_ASSESSED"
            ),
            "earnings_complete": False,
            "deductions_complete": False,
            "approval_state": "NOT_APPROVED",
        },
        "status": "PARTIAL_REVIEW_ONLY",
        "approval_state": "NOT_APPROVED",
    }


def build_segmented_settlement_preview(
    inputs: PayrollInputs,
    *,
    settlement_plan: Mapping[str, Any],
    period_from: str,
    period_to: str,
    base_reductions: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Preserve the published P1-5a partial register and status contract."""
    coverage = validate_settlement_coverage(
        inputs.for_role("contracts"), plan=settlement_plan,
        period_from=period_from, period_to=period_to,
    )
    components = _build_segmented_components(
        inputs, coverage=coverage,
        period_from=period_from, period_to=period_to,
        base_reductions=base_reductions,
    )
    return {
        "payroll_register": build_payroll_register(components["payroll_rows"]),
        **{key: value for key, value in components.items() if key != "payroll_rows"},
    }
