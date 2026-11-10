"""Compose Payroll Results, ledger adjustments, and final amount processing."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Iterable, Mapping


def _load_sibling(module_name: str):
    path = Path(__file__).with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_totals = _load_sibling("payroll_totals")
_amount_processing = _load_sibling("amount_processing")


def finalize_worker_payroll(
    results: Iterable[Mapping[str, Any]],
    worker_id: Any,
    payroll_period: Any,
    policy: dict[str, Any],
    *,
    settlement_adjustment: Any = 0,
) -> dict[str, Any]:
    """Aggregate calculation-stage results, then apply final amount policy once."""
    totals = _totals.aggregate_payroll_results(
        results,
        worker_id,
        payroll_period,
        settlement_adjustment=settlement_adjustment,
    )
    amount_result = _amount_processing.process_final_amount(
        totals["worker_id"],
        totals["payroll_period"],
        totals["calculated_net_amount"],
        policy,
    )
    return {
        "worker_id": totals["worker_id"],
        "payroll_period": totals["payroll_period"],
        "totals": totals,
        "amount_processing": amount_result,
        "calculated_net_amount": totals["calculated_net_amount"],
        "payable_amount": amount_result["payable_amount"],
        "rounding_remainder": amount_result["rounding_remainder"],
        "ledger_transaction_request": amount_result["ledger_transaction_request"],
    }
