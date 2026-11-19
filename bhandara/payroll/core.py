"""Pure, review-only payroll foundations for contract, fixed allowances and bonuses.

Rows are dictionaries from independently verified Excel readers. No IO, approvals,
insurance calculation, overtime inference or net-pay finalization occurs here.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Iterable, Mapping


class PayrollCoreError(ValueError):
    """An ambiguous or inconsistent payroll fact blocks calculation."""


def _value(row: Mapping[str, Any], field: str) -> str:
    raw = row.get(field)
    if raw is None or str(raw).strip() == "":
        raise PayrollCoreError(f"{field}: explicit value required")
    return str(raw).strip()


def _number(value: Any, field: str, *, whole_won: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None or str(value).strip() == "":
        raise PayrollCoreError(f"{field}: numeric value required")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PayrollCoreError(f"{field}: invalid decimal") from exc
    if not number.is_finite() or number < 0:
        raise PayrollCoreError(f"{field}: nonnegative finite number required")
    if whole_won and number != number.to_integral_value():
        raise PayrollCoreError(f"{field}: whole KRW required")
    return number


def _cycle_amount(contract: Mapping[str, Any]) -> Decimal:
    basis = _value(contract, "pay_basis")
    amount = _number(contract.get("contract_amount"), "contract_amount", whole_won=True)
    if basis == "ANNUAL":
        installments = _number(contract.get("installments_per_year"), "installments_per_year", whole_won=True)
        if installments == 0:
            raise PayrollCoreError("installments_per_year: cannot be zero")
        cycle = amount / installments
        if cycle != cycle.to_integral_value():
            raise PayrollCoreError("annual installment is fractional KRW; explicit rounding policy required")
        return cycle
    if basis in {"MONTHLY", "WEEKLY"}:
        return amount
    raise PayrollCoreError(f"pay_basis: unsupported {basis}")


def resolve_contract_pay(contracts: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Resolve exactly one selected contract per employee for an explicit pay cycle.

    Temporal selection belongs to the caller; overlapping/old rows must never be
    silently selected by this function. BASE means allowances are additional;
    TOTAL requires an independently declared base to avoid reverse inference.
    """
    resolved: dict[str, dict[str, Any]] = {}
    selected_contract_ids: set[str] = set()
    for row in contracts:
        worker = _value(row, "employee_id")
        contract_id = _value(row, "contract_id")
        if worker in resolved:
            raise PayrollCoreError(f"{worker}: multiple selected contracts")
        if contract_id in selected_contract_ids:
            raise PayrollCoreError(f"{contract_id}: duplicate contract_id")
        selected_contract_ids.add(contract_id)
        cycle = _cycle_amount(row)
        kind = _value(row, "amount_type")
        if kind not in {"BASE", "TOTAL"}:
            raise PayrollCoreError(f"{worker}: amount_type must be BASE or TOTAL")
        declared = row.get("declared_base_amount")
        if kind == "TOTAL" and declared in (None, ""):
            raise PayrollCoreError(f"{worker}: TOTAL needs declared_base_amount")
        base = (cycle if declared in (None, "") else
                _number(declared, "declared_base_amount", whole_won=True))
        if kind == "BASE" and base != cycle:
            raise PayrollCoreError(f"{worker}: BASE declared base conflicts with contract")
        daily = _number(row.get("daily_base_rate"), "daily_base_rate", whole_won=True)
        if daily <= 0:
            raise PayrollCoreError(f"{worker}: daily base must be positive")
        resolved[worker] = {
            "employee_id": worker, "contract_id": contract_id,
            "pay_basis": _value(row, "pay_basis"), "amount_type": kind,
            "contract_cycle_amount": cycle, "base_pay": base,
            "daily_base_rate": daily,
            "deduction_code": _value(row, "deduction_code"),
            "payment_date": _value(row, "payment_date"),
            "calculation_period_from": _value(row, "calculation_period_from"),
            "calculation_period_to": _value(row, "calculation_period_to"),
        }
    if not resolved:
        raise PayrollCoreError("at least one selected contract is required")
    return resolved


def resolve_fixed_allowances(
    contracts: Mapping[str, Mapping[str, Any]],
    mapping: Iterable[Mapping[str, Any]],
    assignments: Iterable[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Resolve contract_id to employee once, then join allowance ID + level.

    A negotiated contract gets a *new* contract_id and its own allowance
    assignments. Never silently inherit old-contract rows.
    """
    rate_map: dict[tuple[str, str], dict[str, Any]] = {}
    for row in mapping:
        key = (_value(row, "allowance_id"), _value(row, "level"))
        if key in rate_map:
            raise PayrollCoreError(f"allowance mapping duplicated: {key}")
        tax = _value(row, "payroll_taxability")
        if tax not in {"TAXABLE", "NON_TAXABLE", "REVIEW"}:
            raise PayrollCoreError(f"{key}: invalid payday taxability")
        rate_map[key] = {"amount": _number(row.get("amount"), "allowance amount", whole_won=True),
                         "payroll_taxability": tax,
                         "taxability_policy_ref": str(row.get("taxability_policy_ref") or "").strip()}
    out: dict[str, list[dict[str, Any]]] = {worker: [] for worker in contracts}
    contract_to_worker: dict[str, str] = {}
    for worker, contract in contracts.items():
        contract_id = _value(contract, "contract_id")
        if contract_id in contract_to_worker:
            raise PayrollCoreError(f"{contract_id}: duplicate selected contract_id")
        contract_to_worker[contract_id] = worker
    seen: set[tuple[str, str]] = set()
    for row in assignments:
        contract_id = _value(row, "contract_id")
        worker = contract_to_worker.get(contract_id)
        if worker is None:
            raise PayrollCoreError(f"{contract_id}: allowance refers to unknown or expired contract")
        key = (_value(row, "allowance_id"), _value(row, "level"))
        if key not in rate_map:
            raise PayrollCoreError(f"{contract_id}: allowance map missing {key}")
        assignment_key = (contract_id, key[0])
        if assignment_key in seen:
            raise PayrollCoreError(f"{contract_id}: duplicated allowance id {key[0]}")
        seen.add(assignment_key)
        entry = rate_map[key]
        out[worker].append({"allowance_id": key[0], "level": key[1], **entry})
    for worker, contract in contracts.items():
        fixed = sum((a["amount"] for a in out[worker]), Decimal(0))
        if contract["amount_type"] == "TOTAL" and contract["base_pay"] + fixed != contract["contract_cycle_amount"]:
            raise PayrollCoreError(f"{worker}: TOTAL base + fixed allowances != contract amount")
    return out



DEDUCTION_RATE_FIELDS = (
    "national_pension",
    "health_insurance",
    "longterm_care",
    "employment_insurance",
)


def resolve_deduction_mapping(
    contracts: Mapping[str, Mapping[str, Any]],
    mapping: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Join an insurance deduction policy by contract.deduction_code.

    The four employee-share rates are decimal fractions (e.g. 4.75% = 0.0475).
    This only resolves policy *rates*. It intentionally does not multiply them
    by base salary: each insurance uses its own verified assessment basis, and
    long-term care is based on the health insurance premium.
    """
    policies: dict[str, dict[str, Any]] = {}
    for row in mapping:
        policy_id = _value(row, "deduction_code")
        if policy_id in policies:
            raise PayrollCoreError(f"{policy_id}: duplicated deduction policy")
        rates: dict[str, Decimal] = {}
        for field in DEDUCTION_RATE_FIELDS:
            rate = _number(row.get(field), f"{policy_id}.{field}")
            if rate > 1:
                raise PayrollCoreError(f"{policy_id}.{field}: rate must be 0..1")
            rates[field] = rate
        policies[policy_id] = {
            "deduction_code": policy_id,
            "rates": rates,
            "source_ref": str(row.get("source_ref") or "").strip(),
        }
    resolved: dict[str, dict[str, Any]] = {}
    for worker, contract in contracts.items():
        code = _value(contract, "deduction_code")
        if code not in policies:
            raise PayrollCoreError(f"{worker}: unknown deduction_code {code}")
        resolved[worker] = policies[code].copy()
    return resolved


def allocate_performance_bonus(
    contracts: Mapping[str, Any],
    budgets: Iterable[Mapping[str, Any]],
    assignments: Iterable[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Allocate each team/project budget exactly, with deterministic KRW remainders."""
    budget_map: dict[str, tuple[int, str, str]] = {}
    for row in budgets:
        bonus_id = _value(row, "bonus_id")
        if bonus_id in budget_map:
            raise PayrollCoreError(f"{bonus_id}: duplicate budget")
        team, project = str(row.get("team_id") or "").strip(), str(row.get("project_id") or "").strip()
        if bool(team) == bool(project):
            raise PayrollCoreError(f"{bonus_id}: exactly one of team_id/project_id")
        amount = int(_number(row.get("budget_amount"), "budget_amount", whole_won=True))
        budget_map[bonus_id] = (amount, "TEAM" if team else "PROJECT", team or project)
    shares: dict[str, list[tuple[str, Decimal]]] = defaultdict(list)
    dedupe: set[tuple[str, str]] = set()
    for row in assignments:
        bonus_id, worker = _value(row, "bonus_id"), _value(row, "employee_id")
        if bonus_id not in budget_map or worker not in contracts:
            raise PayrollCoreError(f"{bonus_id}/{worker}: missing budget or contract")
        if (bonus_id, worker) in dedupe:
            raise PayrollCoreError(f"{bonus_id}/{worker}: duplicated bonus allocation")
        dedupe.add((bonus_id, worker))
        ratio = _number(row.get("allocation_ratio"), "allocation_ratio")
        if ratio > 1:
            raise PayrollCoreError(f"{bonus_id}/{worker}: ratio must be 0..1")
        shares[bonus_id].append((worker, ratio))
    out: dict[str, list[dict[str, Any]]] = {worker: [] for worker in contracts}
    for bonus_id, (budget, scope, target) in budget_map.items():
        ratios = shares[bonus_id]
        if sum((ratio for _, ratio in ratios), Decimal(0)) != 1:
            raise PayrollCoreError(f"{bonus_id}: allocation ratios must sum to exactly 1")
        raw = [(worker, Decimal(budget) * ratio, ratio) for worker, ratio in ratios]
        integer = {worker: int(amount.to_integral_value(rounding=ROUND_DOWN)) for worker, amount, _ in raw}
        missing = budget - sum(integer.values())
        ranked = sorted(raw, key=lambda item: (-(item[1] - int(item[1])), item[0]))
        for worker, _, _ in ranked[:missing]:
            integer[worker] += 1
        for worker, _, ratio in raw:
            out[worker].append({"bonus_id": bonus_id, "scope": scope,
                                "target_id": target, "allocation_ratio": ratio,
                                "amount": Decimal(integer[worker])})
    return out


def build_partial_payroll(
    contracts: Mapping[str, Mapping[str, Any]],
    allowances: Mapping[str, list[Mapping[str, Any]]],
    bonuses: Mapping[str, list[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Preview only: do not present as net pay or a final payroll register."""
    rows = []
    for worker in sorted(contracts):
        contract = contracts[worker]
        fixed = sum((a["amount"] for a in allowances.get(worker, [])), Decimal(0))
        bonus = sum((a["amount"] for a in bonuses.get(worker, [])), Decimal(0))
        base = contract["base_pay"]
        rows.append({"employee_id": worker, "base_pay": base,
                     "fixed_allowance_pay": fixed, "performance_bonus": bonus,
                     "partial_gross_pay": base + fixed + bonus,
                     "status": "PARTIAL_REVIEW_ONLY",
                     "not_calculated": ["OVERTIME_PAY", "DEDUCTIONS", "NET_PAY"]})
    return rows
