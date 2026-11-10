"""Recalculate one historical Payroll run and build later retroactive Results."""

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


_calculation_stage = _load_sibling("payroll_calculation_stage")
_comparison = _load_sibling("historical_result_comparison")


class HistoricalRerunOrchestratorError(ValueError):
    pass


def _flatten_source_results(
    source_results: Mapping[str, Iterable[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    if not isinstance(source_results, Mapping):
        raise HistoricalRerunOrchestratorError(
            "calculation stage source_results must be a mapping"
        )
    flattened = []
    for results in source_results.values():
        flattened.extend(dict(result) for result in results)
    return flattened


def run_historical_payroll_rerun(
    historical_payroll_period: str,
    settlement_payroll_period: str,
    historical_results: Iterable[Mapping[str, Any]],
    compensation_path: str | Path,
    payroll_input_path: str | Path,
    worktime_rows: list[dict[str, Any]],
    registry: Mapping[str, Any],
    historical_operating_config: Mapping[str, Any],
    historical_company_policy: Mapping[str, Any],
    historical_legal_policy: Mapping[str, Any],
    employment_facts: Iterable[Mapping[str, Any]],
    *,
    recurring_pay_item_codes: Iterable[str],
    eligibility_facts: Iterable[Mapping[str, Any]] = (),
    absence_events: Iterable[dict[str, Any]] = (),
    absence_deduction_inputs: Iterable[Mapping[str, Any]] = (),
    weekly_holiday_inputs: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Rerun historical source calculations and emit settlement-period retro Results.

    Historical Payroll Results are comparison baselines only. They are never
    passed into the calculation stage.
    """
    employment_rows = list(employment_facts)
    stage = _calculation_stage.run_payroll_calculation_stage(
        historical_payroll_period,
        compensation_path,
        payroll_input_path,
        worktime_rows,
        registry,
        historical_operating_config,
        historical_company_policy,
        historical_legal_policy,
        employment_rows,
        recurring_pay_item_codes=recurring_pay_item_codes,
        eligibility_facts=eligibility_facts,
        absence_events=absence_events,
        absence_deduction_inputs=absence_deduction_inputs,
        weekly_holiday_inputs=weekly_holiday_inputs,
    )
    recalculated_results = _flatten_source_results(stage["source_results"])
    employment_to_by_worker = {
        str(row.get("worker_id", "")).strip(): row.get("employment_to")
        for row in employment_rows
        if str(row.get("worker_id", "")).strip()
    }
    retroactive_results = _comparison.build_historical_retroactive_results(
        historical_results,
        recalculated_results,
        historical_payroll_period,
        settlement_payroll_period,
        registry,
        employment_to_by_worker=employment_to_by_worker,
    )
    return {
        "historical_payroll_period": str(historical_payroll_period).strip(),
        "settlement_payroll_period": str(settlement_payroll_period).strip(),
        "recalculation": stage,
        "recalculated_results": recalculated_results,
        "retroactive_results": retroactive_results,
    }
