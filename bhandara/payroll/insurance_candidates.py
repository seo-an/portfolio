"""P2-1 employee insurance *candidates* from externally assessed bases.

Rates are read from the existing DEDUCTION MAP workbook. Assessment bases,
applicability decisions, reference snapshots and rounding are explicitly
provided by an external policy. This does NOT determine Korean legal rates,
insurance caps, eligibility, wage-taxability, or final payroll approval.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Iterable

from bhandara.common.io.input_layout import InputLayoutError, read_sheet

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


# Four statutory social insurance registration fields in common/employee.xlsx.
# Long-term care is a health-insurance-linked employee deduction and must
# NOT be misrepresented as the fourth statutory social insurance.
COMMON_INSURANCE_COLUMNS = {
    "national_pension": "national_pension_acquired_on",
    "health_insurance": "health_insurance_acquired_on",
    "employment_insurance": "employment_insurance_acquired_on",
    "industrial_accident": "industrial_accident_acquired_on",
}
CONTRIBUTION_KINDS = ("national_pension", "health_insurance", "employment_insurance")


def _employee_status(value: Any, column: str, *, period_to: str) -> dict[str, Any]:
    """Interpret date=enrolled, blank=explicit exclusion, 미가입=unregistered."""
    if value is None or value == "":
        return {"state": "EXCLUDED", "acquired_on": None}
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {"state": "EXCLUDED", "acquired_on": None}
        if raw == "미가입":
            return {"state": "NOT_ENROLLED", "acquired_on": None}
        try:
            acquired = date.fromisoformat(raw)
        except ValueError as exc:
            raise InsuranceCandidateError(
                f"common employee: {column} must be ISO acquisition date, blank, or 미가입"
            ) from exc
        if acquired.isoformat() != raw:
            raise InsuranceCandidateError(
                f"common employee: {column} must use YYYY-MM-DD"
            )
    elif isinstance(value, datetime):
        if value.time().isoformat() != "00:00:00":
            raise InsuranceCandidateError(
                f"common employee: {column} must not contain time"
            )
        acquired = value.date()
    elif isinstance(value, date):
        acquired = value
    else:
        raise InsuranceCandidateError(
            f"common employee: {column} must be a date, blank, or 미가입"
        )
    return {
        "state": "ENROLLED" if acquired.isoformat() <= period_to else "NOT_YET_ACQUIRED",
        "acquired_on": acquired.isoformat(),
    }


def read_employee_insurance_status(
    employee_xlsx: str | Path,
    *,
    employee_ids: Iterable[str],
    period_to: str,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Read canonical common/employee.xlsx only; no new Payroll input workbook.

    The caller supplies the exact verified contract roster. Missing *columns*
    are errors. Explicit blank *cells* mean EXCLUDED and require no review.
    """
    path = Path(employee_xlsx)
    if path.name != "employee.xlsx":
        raise InsuranceCandidateError("common employee: expected employee.xlsx")
    wanted = set(employee_ids)
    required = ("employee_id", *COMMON_INSURANCE_COLUMNS.values())
    seen: dict[str, dict[str, dict[str, Any]]] = {}
    try:
        # Common staff roster has active and terminated employee sheets.
        for sheet in ("재직자", "퇴사자"):
            for row in read_sheet(path, required, sheet_name=sheet):
                worker = row["employee_id"]
                if not isinstance(worker, str) or not worker.strip():
                    raise InsuranceCandidateError(
                        "common employee: employee_id must be nonempty Excel text"
                    )
                worker = worker.strip()
                if worker not in wanted:
                    continue
                if worker in seen:
                    raise InsuranceCandidateError(
                        "common employee: duplicate selected employee across sheets"
                    )
                seen[worker] = {
                    kind: _employee_status(
                        row[column], column, period_to=period_to,
                    ) for kind, column in COMMON_INSURANCE_COLUMNS.items()
                }
    except (InputLayoutError, OSError) as exc:
        raise InsuranceCandidateError("common employee: invalid employee workbook") from exc
    if set(seen) != wanted:
        raise InsuranceCandidateError("common employee: missing selected payroll employee")
    return seen


def review_employee_insurance_status(
    employee_status: Mapping[str, Mapping[str, Mapping[str, Any]]] | None,
    *,
    employee_ids: Iterable[str],
    insurance_review: Mapping[str, Any] | None,
) -> dict[str, list[str]]:
    """Build ONLY insurance review reasons, not allowance/earnings warnings.

    Explicitly excluded employees are not errors or zero-assessment guesses.
    미가입 is a recorded non-enrolment requiring administrative confirmation,
    not an implied social-insurance deduction. Acquisition date doesn't
    determine statutory first-month or partial-month charges.
    """
    employees = tuple(employee_ids)
    if employee_status is None:
        return {worker: ["INSURANCE_COMMON_STATUS_UNVERIFIED"] for worker in employees}
    if set(employee_status) != set(employees):
        raise InsuranceCandidateError("common employee: status roster mismatch")
    verified = (
        {row["employee_id"]: row for row in insurance_review["employees"]}
        if insurance_review is not None else {}
    )
    result = {}
    for worker in employees:
        state = employee_status[worker]
        if set(state) != set(COMMON_INSURANCE_COLUMNS):
            raise InsuranceCandidateError("common employee: incomplete insurance fields")
        reasons: list[str] = []
        for kind, record in state.items():
            if record["state"] == "NOT_ENROLLED":
                reasons.append(f"INSURANCE_NOT_ENROLLED:{kind}")
            elif record["state"] == "ENROLLED" and kind in CONTRIBUTION_KINDS:
                if worker not in verified:
                    reasons.append(f"INSURANCE_PREMIUM_UNVERIFIED:{kind}")
            elif record["state"] not in ("EXCLUDED", "NOT_YET_ACQUIRED", "ENROLLED"):
                raise InsuranceCandidateError("common employee: unsupported state")
        result[worker] = reasons
    return result


def check_insurance_assessment_against_employee_status(
    employee_status: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    insurance_review: Mapping[str, Any],
) -> None:
    """Fail closed if an insurance premium is assigned to an excluded worker."""
    for worker in insurance_review["employees"]:
        employee_id = worker["employee_id"]
        states = employee_status[employee_id]
        for kind in CONTRIBUTION_KINDS:
            state = states[kind]["state"]
            if state != "ENROLLED" and (
                worker["applicable_by_kind"][kind]
                or worker["candidate_by_kind_won"][kind]
            ):
                raise InsuranceCandidateError(
                    f"common employee: {kind} must not deduct when {state}"
                )
        health_state = states["health_insurance"]["state"]
        if health_state != "ENROLLED" and (
            worker["applicable_by_kind"]["longterm_care"]
            or worker["candidate_by_kind_won"]["longterm_care"]
        ):
            raise InsuranceCandidateError(
                "common employee: longterm_care must not deduct without enrolled health insurance"
            )


def apply_common_insurance_applicability(
    assessment_plan: Mapping[str, Any],
    employee_status: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Use common employee acquisition data; do not re-enter enrollment in Payroll.

    The employee-specific assessment base is still externally approved. An
    acquisition date only determines enrolled status as of the period end,
    NOT a statutory first-month premium or partial-month fraction.

    Legacy *_applicable keys are accepted for compatibility but checked
    against the canonical common status. Health-linked care may have an
    explicitly approved exception with applicable=False.
    """
    if not isinstance(assessment_plan, Mapping):
        raise InsuranceCandidateError("assessment_plan: mapping required")
    selected = assessment_plan.get("assessments")
    if not isinstance(selected, (list, tuple)):
        raise InsuranceCandidateError("assessment_plan.assessments: list required")
    normalized = []
    for record in selected:
        if not isinstance(record, Mapping):
            raise InsuranceCandidateError("assessment: object required")
        worker = _text(record.get("employee_id"), "assessment.employee_id")
        if worker not in employee_status:
            raise InsuranceCandidateError("common employee: insurance assessment has unknown employee")
        updated = dict(record)
        states = employee_status[worker]
        for kind in CONTRIBUTION_KINDS:
            key = kind + "_applicable"
            active = states[kind]["state"] == "ENROLLED"
            if key in updated and updated[key] is not active:
                raise InsuranceCandidateError(
                    f"common employee: {kind} applicability conflicts with acquisition status"
                )
            updated[key] = active
        health_enrolled = states["health_insurance"]["state"] == "ENROLLED"
        care = updated.get("longterm_care_applicable", health_enrolled)
        if type(care) is not bool or (care and not health_enrolled):
            raise InsuranceCandidateError(
                "common employee: longterm care requires enrolled health insurance"
            )
        # Exceptions to long-term care require an explicit outside assessment
        # and applicability reference; no age-based eligibility inference.
        updated["longterm_care_applicable"] = care
        normalized.append(updated)
    return {**assessment_plan, "assessments": normalized}


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
