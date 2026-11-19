"""Connect verified Payroll Excel rows, pure Core and the dynamic review-only Output.

The adapter MUST NOT claim complete earnings, complete deductions or net pay.
P1/P2 own overtime/leave adjustments, insurance/tax and eligibility evidence.
"""
from __future__ import annotations

from typing import Any, Mapping, Iterable

from bhandara.payroll.contract_period import select_contracts_for_period
from bhandara.payroll.core import (
    allocate_performance_bonus, resolve_contract_pay, resolve_fixed_allowances,
)
from bhandara.payroll.input_excel import PayrollInputs
from bhandara.payroll.output import build_payroll_register


class PayrollPreviewError(ValueError):
    """Required source roles or a human-readable pay item label is missing."""


PREVIEW_ROLES = frozenset({
    "contracts", "allowance_assignments", "fixed_allowance_map",
    "bonus_budget", "bonus_allocation",
})


def _require_roles(inputs: PayrollInputs) -> None:
    missing = PREVIEW_ROLES - inputs.rows.keys()
    if missing:
        raise PayrollPreviewError(
            "review preview requires every earnings input role: " + ", ".join(sorted(missing))
        )


def _names_for_ids(rows: tuple[Mapping[str, Any], ...], *,
                   id_field: str, label_field: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in rows:
        identifier, label = row.get(id_field), row.get(label_field)
        if not isinstance(identifier, str) or not identifier.strip():
            raise PayrollPreviewError(f"{id_field}: verified text ID required")
        if not isinstance(label, str) or not label.strip():
            raise PayrollPreviewError(f"{label_field}: explicit label required")
        if identifier in names and names[identifier] != label:
            raise PayrollPreviewError(f"{label_field}: inconsistent label for same ID")
        names[identifier] = label
    return names


def _as_items(items: list[Mapping[str, Any]], names: Mapping[str, str], *,
              id_field: str) -> list[dict[str, Any]]:
    results = []
    for item in items:
        item_id = item[id_field]
        if item_id not in names:
            raise PayrollPreviewError(f"{id_field}: missing mapped display name")
        results.append({
            "item_id": item_id, "label": names[item_id], "amount": item["amount"],
        })
    return results


def build_payroll_review_register(
    inputs: PayrollInputs,
    *,
    period_from: str,
    period_to: str,
    overtime_candidates: Mapping[str, Iterable[Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Produce the final *layout*, but with intentionally incomplete pay totals.

    Required five role files can be empty except CONTRACTS; an empty earnings
    file means explicitly 'none' for that file, not a missing calculation.
    A period must match exactly one already-declared cycle per selected worker.
    This adapter does not accept independent completion flags from a caller.
    """
    _require_roles(inputs)
    selected = select_contracts_for_period(
        inputs.for_role("contracts"), period_from=period_from, period_to=period_to,
    )
    contracts = resolve_contract_pay(selected)
    selected_ids = {contract["contract_id"] for contract in contracts.values()}
    # Historical rows remain in the verified source but are not inherited by a
    # renewed contract. Unknown contract IDs are rejected by the Reader join.
    current_assignments = [
        row for row in inputs.for_role("allowance_assignments")
        if row["contract_id"] in selected_ids
    ]
    fixed = resolve_fixed_allowances(
        contracts, inputs.for_role("fixed_allowance_map"), current_assignments,
    )
    bonuses = allocate_performance_bonus(
        contracts, inputs.for_role("bonus_budget"), inputs.for_role("bonus_allocation"),
    )
    allowance_names = _names_for_ids(
        inputs.for_role("fixed_allowance_map"),
        id_field="allowance_id", label_field="allowance_name",
    )
    bonus_names = _names_for_ids(
        inputs.for_role("bonus_budget"), id_field="bonus_id", label_field="bonus_name",
    )

    if overtime_candidates is not None and set(overtime_candidates) - set(contracts):
        raise PayrollPreviewError("overtime_candidates: unknown selected employee")
    rows: list[dict[str, Any]] = []
    for worker in sorted(contracts):
        rows.append({
            "employee_id": worker,
            "base_pay": contracts[worker]["base_pay"],
            "fixed_allowances": _as_items(
                fixed[worker], allowance_names, id_field="allowance_id",
            ),
            "performance_bonuses": _as_items(
                bonuses[worker], bonus_names, id_field="bonus_id",
            ),
            # Calculated candidate items do NOT imply complete/approved overtime.
            "overtime_allowances": list((overtime_candidates or {}).get(worker, ())),
            "deductions": [],  # insurance/tax rates are NOT monetary deductions
            "earnings_complete": False,
            "deductions_complete": False,
        })
    return build_payroll_register(rows)
