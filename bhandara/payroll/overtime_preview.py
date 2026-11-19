"""P1-2 orchestration: candidate amounts on the existing partial Payroll layout.

P1-1 Worktime source verification and P0 period selection are reused.
No extra Excel files, CLI, approval, or deduction amounts are created.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.contract_period import select_contracts_for_period
from bhandara.payroll.core import resolve_contract_pay
from bhandara.payroll.input_excel import PayrollInputs
from bhandara.payroll.overtime_candidates import calculate_overtime_candidates
from bhandara.payroll.review_adapter import build_payroll_review_register
from bhandara.payroll.worktime_bridge import build_payroll_worktime_review
from bhandara.worktime.output_excel import read_worktime_xlsx


def build_overtime_candidate_preview(
    inputs: PayrollInputs,
    worktime_xlsx: str | Path,
    *,
    period_from: str,
    period_to: str,
    verified_work: Iterable[Mapping[str, Any]],
    approved_segments: Iterable[Mapping[str, Any]],
    rate_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute evidenced *candidate* components, without claiming wages complete."""
    path = Path(worktime_xlsx)
    # The P1 bridge enforces the fixed basename, single sheet, text IDs,
    # duplicate/date/worker constraints and file integrity.
    bridge = build_payroll_worktime_review(
        inputs, path, period_from=period_from, period_to=period_to,
    )
    source_hash = sha256_file(path)
    rows = read_worktime_xlsx(path)
    if source_hash != sha256_file(path):
        raise ValueError("WORKTIME: source changed during overtime candidate composition")
    selected = select_contracts_for_period(
        inputs.for_role("contracts"), period_from=period_from, period_to=period_to,
    )
    contracts = resolve_contract_pay(selected)
    overtime_rules = inputs.for_role("overtime_rules")
    candidate = calculate_overtime_candidates(
        contracts, rows, overtime_rules,
        verified_work=verified_work, approved_segments=approved_segments,
        policy=rate_policy,
    )
    by_employee: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidate["rows"]:
        by_employee[item["employee_id"]].append({
            "item_id": item["item_id"], "label": item["label"],
            "amount": item["amount"],
        })
    register = build_payroll_review_register(
        inputs, period_from=period_from, period_to=period_to,
        overtime_candidates=by_employee,
    )
    return {
        "payroll_register": register,
        "worktime_review": bridge["worktime_review"],
        "overtime_candidate_review": candidate,
        "status": "PARTIAL_REVIEW_ONLY",
        "approval_state": "NOT_APPROVED",
    }
