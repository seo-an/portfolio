"""Compose supported Worktime premium calculations into Payroll Results."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable, Mapping


def _load_sibling(module_name: str):
    path = Path(__file__).with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_mapper = _load_sibling("worktime_pay_item_mapper")
_premium = _load_sibling("premium_calculator")
_pay_policy = _load_sibling("worktime_pay_policy")
_calculator = _load_sibling("worktime_pay_calculator")
_result_adapter = _load_sibling("calculated_result_adapter")


class WorktimeCalculationAdapterError(ValueError):
    pass


def build_worktime_payroll_results(
    prepared_worktime: Mapping[str, Any],
    payroll_period: str,
    registry: Mapping[str, Any],
    company_policy: Mapping[str, Any],
    legal_policy: Mapping[str, Any],
    ordinary_hourly_wage_by_worker: Mapping[str, Any] | None = None,
    *,
    ordinary_hourly_wage_resolver: Callable[[Mapping[str, Any]], Any] | None = None,
) -> list[dict[str, Any]]:
    """Calculate only the premium items already supported by Payroll."""
    rows = prepared_worktime.get("rows")
    operating_period = prepared_worktime.get("period")
    if not isinstance(rows, list):
        raise WorktimeCalculationAdapterError("prepared_worktime.rows must be a list")
    if not isinstance(operating_period, Mapping):
        raise WorktimeCalculationAdapterError("prepared_worktime.period must be a mapping")

    results = []
    for row in rows:
        worker_id = str(row.get("worker_id", "")).strip()
        if ordinary_hourly_wage_resolver is not None:
            hourly = ordinary_hourly_wage_resolver(row)
        else:
            wages = ordinary_hourly_wage_by_worker or {}
            if worker_id not in wages:
                raise WorktimeCalculationAdapterError(
                    f"{worker_id}: ordinary hourly wage is required"
                )
            hourly = wages[worker_id]

        for mapped in _mapper.map_worktime_pay_items(row, dict(registry)):
            code = mapped["pay_item_code"]
            if code not in {"overtime_pay", "night_pay", "holiday_work_pay"}:
                continue

            premium = _premium.calculate_premium_item(
                mapped, hourly, dict(legal_policy)
            )
            base_policy = _pay_policy.resolve_base_component_policy(
                code, dict(company_policy), dict(legal_policy)
            )
            calculated = _calculator.calculate_worktime_pay_total(
                premium, base_policy
            )
            results.append(
                _result_adapter.build_payroll_result_from_calculation(
                    calculated,
                    payroll_period,
                    registry,
                    source="worktime",
                    operating_period=operating_period,
                )
            )
    return results
