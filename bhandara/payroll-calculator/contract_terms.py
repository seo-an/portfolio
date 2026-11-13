"""Resolve contract facts against explicitly listed monthly pay components.

An agreement amount is evidence, not a permission to invent a base salary.
Payroll always receives additive pay items; contract-type interpretation is
limited to the reconciliation step. This module does not decide tax policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping


class ContractTermsError(ValueError):
    """Missing or inconsistent contract-level pay facts."""


@dataclass(frozen=True)
class MonthlyTerms:
    base_salary: Decimal
    allowances: dict[str, Decimal]
    monthly_paid_total: Decimal
    monthly_contract_reference: Decimal
    amount_type: str


def resolve_monthly_terms(
    *,
    contract_id: str,
    pay_basis: str,
    contract_amount: Decimal,
    amount_type: str,
    components: Mapping[str, Decimal],
) -> MonthlyTerms:
    """Make additive pay items and validate the stated amount (no guessing).

    BASE: contract amount is base pay; additional items increase the total.
    TOTAL: contract amount is all-inclusive; base_salary must be a stated
           component, and all listed components must sum to the amount.
    """
    if pay_basis not in {"ANNUAL", "MONTHLY"}:
        raise ContractTermsError(
            f"{contract_id}: monthly terms require ANNUAL or MONTHLY"
        )
    if amount_type not in {"BASE", "TOTAL"}:
        raise ContractTermsError(
            f"{contract_id}: amount_type must be BASE or TOTAL for {pay_basis}"
        )
    reference = (
        contract_amount / Decimal("12") if pay_basis == "ANNUAL"
        else contract_amount
    )
    base_line = components.get("base_salary")
    allowances = {key: amount for key, amount in components.items()
                  if key != "base_salary"}

    if amount_type == "BASE":
        if base_line is not None and base_line != reference:
            raise ContractTermsError(
                f"{contract_id}: explicit base_salary differs from BASE contract amount"
            )
        base = reference
    else:
        if base_line is None:
            raise ContractTermsError(
                f"{contract_id}: TOTAL requires an explicit base_salary component"
            )
        base = base_line

    if base <= 0 or any(value < 0 for value in allowances.values()):
        raise ContractTermsError(f"{contract_id}: pay components must be nonnegative with positive base")

    total = base + sum(allowances.values(), Decimal("0"))
    if amount_type == "TOTAL" and total != reference:
        raise ContractTermsError(
            f"{contract_id}: TOTAL components do not reconcile to contract amount"
        )
    return MonthlyTerms(
        base_salary=base,
        allowances=allowances,
        monthly_paid_total=total,
        monthly_contract_reference=reference,
        amount_type=amount_type,
    )
