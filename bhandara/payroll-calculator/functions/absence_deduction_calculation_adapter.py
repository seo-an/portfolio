"""Promote effective absence deductions into Payroll Results."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Mapping


def _load_sibling(module_name: str):
    path = Path(__file__).with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_effective = _load_sibling("effective_absence_deduction")
_result_adapter = _load_sibling("calculated_result_adapter")


class AbsenceDeductionCalculationAdapterError(ValueError):
    pass


def build_absence_deduction_results(
    *,
    absence_events: list[dict[str, Any]],
    worktime_rows: list[dict[str, Any]],
    compensation_rows: list[dict[str, Any]],
    worker_id: str,
    payroll_period: str,
    scheduled_workdays: Any,
    paid_treatment_days: Any,
    registry: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Calculate explicit absence events and promote each deduction line."""
    worker = str(worker_id).strip()
    if not worker:
        raise AbsenceDeductionCalculationAdapterError(
            "worker_id must not be empty"
        )

    lines = _effective.build_effective_absence_deduction_lines(
        events=absence_events,
        worktime_rows=worktime_rows,
        compensation_rows=compensation_rows,
        worker_id=worker,
        payroll_period=payroll_period,
        scheduled_workdays=scheduled_workdays,
        paid_treatment_days=paid_treatment_days,
    )

    results = []
    for line in lines:
        results.append(
            _result_adapter.build_payroll_result_from_calculation(
                {**line, "worker_id": worker},
                payroll_period,
                registry,
                source="payroll_calculator",
            )
        )
    return results
