"""P2-1 employee insurance *candidates* from externally assessed bases.

Rates are read from the existing DEDUCTION MAP workbook. Assessment bases,
applicability decisions, reference snapshots and rounding are explicitly
provided by an external policy. This does NOT determine Korean legal rates,
insurance caps, eligibility, wage-taxability, or final payroll approval.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Any, Mapping, Iterable

from bhandara.payroll.core import resolve_deduction_mapping


class InsuranceCandidateError(ValueError):
    """Unverified/missing assessment basis or insurance policy; no partial result."""


PLAN_FIELDS = frozenset({
    "schema_version", "period_from", "period_to", "policy_ref",
    "rounding_mode", "longterm_care_base_mode", "assessments",
})
ASSESSMENT_FIELDS = frozenset({
    "employee_id", "national_pension_basis_won",
    "health_insurance_basis_won", "employment_insurance_basis_won",
    "national_pension_applicable", "health_insurance_applicable",
    "longterm_care_applicable", "employment_insurance_applicable",
    "assessment_ref", "applicability_ref", "approval_status",
    "not_pre_deducted",
})
ROUNDING = {"DOWN": ROUND_DOWN, "HALF_UP": ROUND_HALF_UP}
LONGTERM_CARE_BASE_MODE = "ROUNDED_HEALTH_PREMIUM"
ITEMS = (
    ("national_pension", "INS_NATIONAL_PENSION", "국민연금"),
    ("health_insurance", "INS_HEALTH_INSURANCE", "건강보험"),
    ("longterm_care", "INS_LONGTERM_CARE", "장기요양보험"),
    ("employment_insurance", "INS_EMPLOYMENT_INSURANCE", "고용보험"),
)
BASIS = {
    "national_pension": "national_pension_basis_won",
    "health_insurance": "health_insurance_basis_won",
    "employment_insurance": "employment_insurance_basis_won",
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InsuranceCandidateError(f"{field}: nonempty text required")
    value = value.strip()
    if value[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        raise InsuranceCandidateError(f"{field}: unsafe text")
    return value


def _won(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise InsuranceCandidateError(f"{field}: nonnegative integer KRW required")
    return value


def _round(amount: Decimal, mode: str) -> int:
    return int(amount.to_integral_value(rounding=ROUNDING[mode]))


def _contract_code(
    coverage: Mapping[str, Any], worker: str, from_date: str, to_date: str,
) -> str:
    codes = set()
    for segment in coverage["segments_by_employee"][worker]:
        if segment["segment_from"] < from_date or segment["segment_to"] > to_date:
            raise InsuranceCandidateError("contract: assessment period outside payroll period")
        contract_id = segment["contract_id"]
        code = _text(
            coverage["contracts_by_id"][contract_id].get("deduction_code"),
            "deduction_code",
        )
        codes.add(code)
    if len(codes) != 1:
        raise InsuranceCandidateError(
            "contract: multiple insurance deduction codes in one period; explicit split policy required"
        )
    return next(iter(codes))


def calculate_insurance_candidates(
    coverage: Mapping[str, Any],
    deduction_map: Iterable[Mapping[str, Any]],
    *,
    assessment_plan: Mapping[str, Any],
    period_from: str,
    period_to: str,
) -> dict[str, Any]:
    """Produce four separately assessed employee-share insurance candidates.

    The external assessment bases must already account for any statutory
    assessment ceilings/floors, eligibility, partial-month rules and taxable
    base choices. This function does NOT infer those values from payroll pay.
    """
    if not isinstance(assessment_plan, Mapping) or set(assessment_plan) != PLAN_FIELDS:
        raise InsuranceCandidateError("assessment_plan: exact fields required")
    if assessment_plan["schema_version"] != "0.1":
        raise InsuranceCandidateError("assessment_plan: unsupported schema")
    if ((assessment_plan["period_from"], assessment_plan["period_to"])
            != (period_from, period_to)
            or (coverage["period_from"], coverage["period_to"]) != (period_from, period_to)):
        raise InsuranceCandidateError("assessment_plan: period mismatch")
    policy_ref = _text(assessment_plan["policy_ref"], "assessment_plan.policy_ref")
    mode = assessment_plan["rounding_mode"]
    if mode not in ROUNDING:
        raise InsuranceCandidateError("assessment_plan: explicit DOWN/HALF_UP rounding required")
    if assessment_plan["longterm_care_base_mode"] != LONGTERM_CARE_BASE_MODE:
        raise InsuranceCandidateError(
            "assessment_plan: rounded health premium basis must be explicitly selected"
        )
    assessments = assessment_plan["assessments"]
    if not isinstance(assessments, (list, tuple)):
        raise InsuranceCandidateError("assessment_plan.assessments: list required")

    # Reuse the confirmed existing deduction_code -> employee-share rate Core;
    # never create an additional policy workbook or hardcode nominal rates.
    workers = coverage["segments_by_employee"]
    codes = {
        worker: _contract_code(coverage, worker, period_from, period_to)
        for worker in workers
    }
    mapping = tuple(deduction_map)
    rows_by_code = {}
    for row in mapping:
        code = _text(row.get("deduction_code"), "deduction_map.deduction_code")
        if code in rows_by_code:
            raise InsuranceCandidateError("deduction_map: duplicate deduction_code")
        rows_by_code[code] = row
    for code in set(codes.values()):
        if code not in rows_by_code:
            raise InsuranceCandidateError("deduction_map: no policy for selected contract")
        row = rows_by_code[code]
        if (not isinstance(row.get("effective_from"), str)
                or not isinstance(row.get("effective_to"), str)
                or row["effective_from"] > period_from
                or row["effective_to"] < period_to):
            raise InsuranceCandidateError(
                "deduction_map: approved policy does not cover full payroll period"
            )
        _text(row.get("source_ref"), "deduction_map.source_ref")
    rates = resolve_deduction_mapping(
        {worker: {"deduction_code": code} for worker, code in codes.items()},
        mapping,
    )

    given: dict[str, Mapping[str, Any]] = {}
    for record in assessments:
        if not isinstance(record, Mapping) or set(record) != ASSESSMENT_FIELDS:
            raise InsuranceCandidateError("assessment: exact fields required")
        worker = _text(record["employee_id"], "assessment.employee_id")
        if worker not in workers or worker in given:
            raise InsuranceCandidateError("assessment: duplicate or unknown employee")
        if record["approval_status"] != "APPROVED":
            raise InsuranceCandidateError("assessment: externally approved assessment required")
        if record["not_pre_deducted"] is not True:
            raise InsuranceCandidateError("assessment: pre-deducted insurance cannot be charged again")
        _text(record["assessment_ref"], "assessment_ref")
        _text(record["applicability_ref"], "applicability_ref")
        for field in BASIS.values():
            _won(record[field], field)
        for field in (
            "national_pension_applicable", "health_insurance_applicable",
            "longterm_care_applicable", "employment_insurance_applicable",
        ):
            if type(record[field]) is not bool:
                raise InsuranceCandidateError(f"{field}: explicit boolean required")
        if (record["longterm_care_applicable"]
                and not record["health_insurance_applicable"]):
            raise InsuranceCandidateError("longterm_care: health insurance must be applicable")
        given[worker] = record
    if set(given) != set(workers):
        raise InsuranceCandidateError("assessments: all selected employees required; do not assume zero")

    items_by_employee = {}
    audits = []
    for worker in sorted(workers):
        record = given[worker]
        policy = rates[worker]
        r = policy["rates"]
        pension = _round(
            Decimal(record["national_pension_basis_won"]) * r["national_pension"], mode
        ) if record["national_pension_applicable"] else 0
        health = _round(
            Decimal(record["health_insurance_basis_won"]) * r["health_insurance"], mode
        ) if record["health_insurance_applicable"] else 0
        care = _round(
            Decimal(health) * r["longterm_care"], mode
        ) if record["longterm_care_applicable"] else 0
        employment = _round(
            Decimal(record["employment_insurance_basis_won"]) * r["employment_insurance"], mode
        ) if record["employment_insurance_applicable"] else 0
        amount_by_key = {
            "national_pension": pension,
            "health_insurance": health,
            "longterm_care": care,
            "employment_insurance": employment,
        }
        items_by_employee[worker] = [
            {"item_id": item_id, "label": label, "amount": amount_by_key[key]}
            for key, item_id, label in ITEMS
        ]
        audits.append({
            "employee_id": worker, "deduction_code": codes[worker],
            "rate_source_ref": policy["source_ref"],
            "assessment_ref": record["assessment_ref"],
            "applicability_ref": record["applicability_ref"],
            "basis_by_kind_won": {
                kind: record[field] for kind, field in BASIS.items()
            },
            "rates": {kind: str(value) for kind, value in r.items()},
            "applicable_by_kind": {
                kind: record[kind + "_applicable"] for kind in r
            },
            "candidate_by_kind_won": amount_by_key,
            "candidate_total_won": sum(amount_by_key.values()),
        })
    return {
        "schema_version": "0.1",
        "period_from": period_from, "period_to": period_to,
        "policy_ref": policy_ref,
        "rounding_mode": mode,
        "longterm_care_base_mode": LONGTERM_CARE_BASE_MODE,
        "items_by_employee": items_by_employee,
        "employees": audits,
        "assessment_bases": "EXTERNAL_VERIFIED_CLAIM_NOT_AUTHENTICATED",
        "tax_withholding": "NOT_ASSESSED",
        "deductions_complete": False,
        "approval_state": "NOT_APPROVED",
    }
