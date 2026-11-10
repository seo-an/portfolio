"""Current operational Payroll entrypoint from source inputs to Final Payroll."""

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
_composition = _load_sibling("payroll_operational_composition")
_ledger_lifecycle = _load_sibling("settlement_ledger_lifecycle")

class PayrollOperationalEntrypointError(ValueError):
    pass


def run_operational_payroll(
    payroll_period: str,
    compensation_path: str | Path,
    payroll_input_path: str | Path,
    worktime_rows: list[dict[str, Any]],
    registry: Mapping[str, Any],
    operating_config: Mapping[str, Any],
    company_policy: Mapping[str, Any],
    legal_policy: Mapping[str, Any],
    employment_facts: Iterable[Mapping[str, Any]],
    *,
    recurring_pay_item_codes: Iterable[str],
    eligibility_facts: Iterable[Mapping[str, Any]] = (),
    validations_by_worker: Mapping[str, list[dict[str, Any]]] | None = None,
    settlement_adjustments_by_worker: Mapping[str, Any] | None = None,
    settlement_ledger_rows: Iterable[dict[str, Any]] = (),
    rounding_settlement_workers: Iterable[str] = (),
    settlement_batch_ids_by_worker: Mapping[str, str] | None = None,
    absence_events: Iterable[dict[str, Any]] = (),
    absence_deduction_inputs: Iterable[Mapping[str, Any]] = (),
    weekly_holiday_inputs: Iterable[Mapping[str, Any]] = (),
    historical_rerun_results: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Run the current source-contract path without using the legacy orchestrator."""
    stage = _calculation_stage.run_payroll_calculation_stage(
        payroll_period,
        compensation_path,
        payroll_input_path,
        worktime_rows,
        registry,
        operating_config,
        company_policy,
        legal_policy,
        employment_facts,
        recurring_pay_item_codes=recurring_pay_item_codes,
        eligibility_facts=eligibility_facts,
        absence_events=absence_events,
        absence_deduction_inputs=absence_deduction_inputs,
        weekly_holiday_inputs=weekly_holiday_inputs,
    )
    prepared = stage["prepared_input"]
    compensation_results = stage["source_results"]["compensation"]
    worktime_results = stage["source_results"]["worktime"]
    payroll_input_results = stage["source_results"]["payroll_input"]
    absence_results = stage["source_results"]["absence_deduction"]
    weekly_holiday_results = stage["source_results"]["weekly_holiday"]
    weekly_holiday_resolutions = stage["weekly_holiday_resolutions"]

    retroactive_results = [dict(item) for item in historical_rerun_results]
    for item in retroactive_results:
        if str(item.get("payroll_period", "")).strip() != str(payroll_period).strip():
            raise PayrollOperationalEntrypointError(
                "historical rerun result payroll_period must match current payroll_period"
            )
        if str(item.get("source", "")).strip() != "historical_rerun":
            raise PayrollOperationalEntrypointError(
                "historical rerun result source must be historical_rerun"
            )

    all_results = (
        compensation_results
        + worktime_results
        + payroll_input_results
        + absence_results
        + weekly_holiday_results
        + retroactive_results
    )
    result_workers = sorted({str(item["worker_id"]).strip() for item in all_results})
    ledger_rows = list(settlement_ledger_rows)
    rounding_workers = {str(worker).strip() for worker in rounding_settlement_workers}
    batch_ids = settlement_batch_ids_by_worker or {}
    ledger_settlements = {}
    ledger_adjustments = {}
    ledger_write_requests = []
    for worker_id in result_workers:
        settle_rounding = worker_id in rounding_workers
        settlement = _ledger_lifecycle.prepare_worker_settlement(
            ledger_rows,
            worker_id,
            payroll_period,
            settle_rounding_carry=settle_rounding,
            settlement_batch_id=batch_ids.get(worker_id),
        )
        ledger_settlements[worker_id] = settlement
        ledger_adjustments[worker_id] = settlement["settlement_adjustment"]
        ledger_write_requests.extend(settlement["ledger_write_requests"])

    explicit_adjustments = settlement_adjustments_by_worker or {}
    overlap = set(explicit_adjustments) & set(ledger_adjustments)
    if overlap and any(ledger_adjustments[worker] != 0 for worker in overlap):
        raise PayrollOperationalEntrypointError(
            "explicit settlement adjustment conflicts with Settlement Ledger for: "
            + ", ".join(sorted(overlap))
        )
    combined_adjustments = dict(ledger_adjustments)
    combined_adjustments.update(explicit_adjustments)

    source_groups = {
        "compensation": compensation_results,
        "worktime": worktime_results,
        "payroll_input": payroll_input_results,
    }
    if absence_results:
        source_groups["absence_deduction"] = absence_results
    if weekly_holiday_results:
        source_groups["weekly_holiday"] = weekly_holiday_results
    if retroactive_results:
        source_groups["historical_rerun"] = retroactive_results

    composed = _composition.run_payroll_composition(
        source_groups,
        payroll_period,
        dict(company_policy),
        validations_by_worker=validations_by_worker,
        settlement_adjustments_by_worker=combined_adjustments,
    )
    return {
        "payroll_period": str(payroll_period).strip(),
        "prepared_input": prepared,
        "source_results": {
            "compensation": compensation_results,
            "worktime": worktime_results,
            "payroll_input": payroll_input_results,
            "absence_deduction": absence_results,
            "weekly_holiday": weekly_holiday_results,
            "historical_rerun": retroactive_results,
        },
        "weekly_holiday_resolutions": weekly_holiday_resolutions,
        "composition": composed,
        "ledger_settlements": ledger_settlements,
        "ledger_write_requests": ledger_write_requests,
        "final_ledger_requests": [
            run["final_payroll"]["ledger_transaction_request"]
            for run in composed["worker_runs"].values()
            if run["final_payroll"] is not None
            and run["final_payroll"]["ledger_transaction_request"] is not None
        ],
    }
