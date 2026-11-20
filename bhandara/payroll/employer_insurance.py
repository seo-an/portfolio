"""Employer-only industrial accident premium, separate from worker deductions.

This module is an administrative company-cost candidate. It never inserts
industrial-accident insurance into employee gross pay, deductions or net pay.
An external policy must supply the assessed remuneration, total approved
business/workplace premium rate and rounding choice.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from typing import Any, Mapping

from bhandara.payroll.insurance_candidates import COMMON_INSURANCE_COLUMNS


class EmployerInsuranceError(ValueError):
    """Industrial insurance assessment cannot be safely reconciled."""


PLAN_KEYS = frozenset({
    "schema_version", "period_from", "period_to", "policy_ref",
    "rounding_mode", "assessments",
})
ASSESSMENT_KEYS = frozenset({
    "employee_id", "basis_won", "approved_total_rate",
    "assessment_ref", "rate_ref", "approval_status",
    "not_pre_included",
})
ROUNDINGS = {"DOWN": ROUND_DOWN, "HALF_UP": ROUND_HALF_UP}
INDUSTRIAL_ID = "EMPLOYER_INDUSTRIAL_ACCIDENT"


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EmployerInsuranceError(f"{name}: nonempty text required")
    clean = value.strip()
    if clean[0] in "=+-@\r\n\t":
        raise EmployerInsuranceError(f"{name}: unsafe text")
    return clean


def _basis(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise EmployerInsuranceError("industrial accident: nonnegative integer assessed remuneration required")
    return value


def _rate(value: Any) -> Decimal:
    if isinstance(value, (bool, float)) or value is None:
        raise EmployerInsuranceError("industrial accident: exact approved rate string required")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise EmployerInsuranceError("industrial accident: invalid rate") from exc
    if not result.is_finite() or not (Decimal(0) <= result <= Decimal(1)):
        raise EmployerInsuranceError("industrial accident: rate must be within 0..1")
    return result


def calculate_employer_industrial_insurance(
    employee_status: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    plan: Mapping[str, Any],
    period_from: str,
    period_to: str,
) -> dict[str, Any]:
    """One employer premium per enrolled worker, with source references.

    Blank (EXCLUDED) and 미가입 (NOT_ENROLLED) are zero employer cost,
    independently of the worker-share deductions. A valid registration date
    by itself does not determine chargeable remuneration or legal premium.
    """
    if not isinstance(plan, Mapping) or set(plan) != PLAN_KEYS:
        raise EmployerInsuranceError("employer plan: exact fields required")
    if plan["schema_version"] != "0.1":
        raise EmployerInsuranceError("employer plan: unsupported schema")
    if (plan["period_from"], plan["period_to"]) != (period_from, period_to):
        raise EmployerInsuranceError("employer plan: payroll period mismatch")
    _text(plan["policy_ref"], "employer plan.policy_ref")
    rounding = plan["rounding_mode"]
    if rounding not in ROUNDINGS:
        raise EmployerInsuranceError("employer plan: explicit rounding mode required")
    source = plan["assessments"]
    if not isinstance(source, (list, tuple)):
        raise EmployerInsuranceError("employer plan: assessment list required")
    active = {
        employee for employee, kinds in employee_status.items()
        if kinds["industrial_accident"]["state"] == "ENROLLED"
    }
    submitted = {}
    for row in source:
        if not isinstance(row, Mapping) or set(row) != ASSESSMENT_KEYS:
            raise EmployerInsuranceError("industrial assessment: exact fields required")
        employee = _text(row["employee_id"], "industrial assessment.employee_id")
        if employee not in active or employee in submitted:
            raise EmployerInsuranceError("industrial assessment: duplicate or non-enrolled worker")
        if row["approval_status"] != "APPROVED" or row["not_pre_included"] is not True:
            raise EmployerInsuranceError("industrial assessment: approval and no-duplicate-cost required")
        _text(row["assessment_ref"], "industrial assessment.assessment_ref")
        _text(row["rate_ref"], "industrial assessment.rate_ref")
        submitted[employee] = row
    if set(submitted) != active:
        raise EmployerInsuranceError("industrial assessment: all enrolled workers required")

    amounts = {}
    audits = []
    employer_review_flags = {}
    for employee in sorted(employee_status):
        state = employee_status[employee]["industrial_accident"]
        # A recorded 미가입 is an HR/employer compliance question, not a
        # worker insurance deduction or payroll payment review.
        employer_review_flags[employee] = (
            ["EMPLOYER_INDUSTRIAL_NOT_ENROLLED"]
            if state["state"] == "NOT_ENROLLED" else []
        )
        amount = 0
        if employee in active:
            row = submitted[employee]
            amount = int(
                (Decimal(_basis(row["basis_won"])) * _rate(row["approved_total_rate"]))
                .to_integral_value(rounding=ROUNDINGS[rounding])
            )
            audits.append({
                "employee_id": employee, "state": state["state"],
                "basis_won": row["basis_won"],
                "approved_total_rate": str(_rate(row["approved_total_rate"])),
                "rate_ref": row["rate_ref"],
                "assessment_ref": row["assessment_ref"],
                "candidate_won": amount,
            })
        else:
            audits.append({
                "employee_id": employee, "state": state["state"],
                "candidate_won": 0,
            })
        amounts[employee] = amount
    return {
        "schema_version": "0.1",
        "policy_ref": plan["policy_ref"],
        "period_from": period_from, "period_to": period_to,
        "premium_kind": "INDUSTRIAL_ACCIDENT_EMPLOYER_ONLY",
        "amounts_by_employee": amounts,
        "employees": audits,
        "employer_review_flags": employer_review_flags,
        "total_candidate_won": sum(amounts.values()),
        "source_authenticity": "EXTERNAL_REFERENCE_NOT_AUTHENTICATED",
        "employer_cost_complete": False,
        "worker_deduction": False,
        "approval_state": "NOT_APPROVED",
    }
