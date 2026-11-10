"""Run the current Payroll Result pipeline without owning source calculations."""

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


_final = _load_sibling("final_payroll")
_validation = _load_sibling("payroll_validation")


class PayrollRunError(RuntimeError):
    pass


def run_worker_payroll(
    results: Iterable[Mapping[str, Any]],
    worker_id: Any,
    payroll_period: Any,
    policy: dict[str, Any],
    *,
    validations: list[dict[str, Any]] | None = None,
    settlement_adjustment: Any = 0,
) -> dict[str, Any]:
    """Validate one worker run, then finalize already-calculated Payroll Results."""
    result_list = list(results)
    validation_list = list(validations or [])

    for result in result_list:
        embedded = result.get("validations", [])
        if embedded:
            if not isinstance(embedded, list):
                raise PayrollRunError("result.validations must be a list")
            validation_list.extend(embedded)

    summary = _validation.summarize_validations(validation_list)
    if not summary["can_calculate"]:
        return {
            "worker_id": str(worker_id).strip(),
            "payroll_period": str(payroll_period).strip(),
            "results": result_list,
            "validations": validation_list,
            "validation_summary": summary,
            "final_payroll": None,
            "can_auto_finalize": False,
        }

    final = _final.finalize_worker_payroll(
        result_list,
        worker_id,
        payroll_period,
        policy,
        settlement_adjustment=settlement_adjustment,
    )
    return {
        "worker_id": final["worker_id"],
        "payroll_period": final["payroll_period"],
        "results": result_list,
        "validations": validation_list,
        "validation_summary": summary,
        "final_payroll": final,
        "can_auto_finalize": summary["can_auto_finalize"],
    }
