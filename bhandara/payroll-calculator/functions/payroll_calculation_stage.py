"""Calculate source Payroll Results without finalization or Settlement Ledger effects."""

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


_run_input = _load_sibling("payroll_run_input")
_compensation = _load_sibling("compensation_calculation_adapter")
_payroll_input = _load_sibling("payroll_input_calculation_adapter")
_worktime = _load_sibling("worktime_calculation_adapter")
_compensation_resolver = _load_sibling("compensation_resolver")
_ordinary_wage = _load_sibling("ordinary_wage_resolver")
_absence = _load_sibling("absence_deduction_calculation_adapter")
_weekly_holiday = _load_sibling("weekly_holiday_calculation_adapter")


class PayrollCalculationStageError(ValueError):
    pass


def _build_worktime_hourly_resolver(
    compensation_rows: list[dict[str, Any]],
    registry: Mapping[str, Any],
    company_policy: Mapping[str, Any],
):
    ordinary_policy = company_policy.get("ordinary_wage", {})
    monthly_basis_hours = ordinary_policy.get("monthly_basis_hours")
    if monthly_basis_hours in (None, "", "company_policy_required"):
        raise PayrollCalculationStageError(
            "ordinary_wage.monthly_basis_hours requires explicit company policy"
        )

    def resolve(row: Mapping[str, Any]):
        compensation = _compensation_resolver.resolve_compensation(
            compensation_rows,
            row.get("worker_id"),
            row.get("work_date"),
        )
        monthly = _ordinary_wage.resolve_ordinary_monthly_wage(
            compensation,
            dict(registry),
            dict(company_policy),
        )
        return _ordinary_wage.resolve_ordinary_hourly_wage(
            monthly["ordinary_monthly_wage"],
            monthly_basis_hours,
        )

    return resolve


def run_payroll_calculation_stage(
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
    absence_events: Iterable[dict[str, Any]] = (),
    absence_deduction_inputs: Iterable[Mapping[str, Any]] = (),
    weekly_holiday_inputs: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return calculated source Results only; no finalization or Ledger lifecycle."""
    employment_rows = list(employment_facts)
    prepared = _run_input.build_payroll_run_input(
        payroll_period,
        compensation_path,
        payroll_input_path,
        worktime_rows,
        registry,
        operating_config,
    )

    compensation_results = _compensation.build_prorated_compensation_results(
        prepared["compensation"],
        payroll_period,
        registry,
        company_policy,
        employment_rows,
        pay_item_codes=recurring_pay_item_codes,
        eligibility_facts=eligibility_facts,
    )
    payroll_input_results = _payroll_input.build_payroll_input_results(
        prepared["payroll_input"]["rows"],
        payroll_period,
        registry,
    )

    worktime_results = []
    if prepared["worktime"]["rows"]:
        hourly_resolver = _build_worktime_hourly_resolver(
            prepared["compensation_history"],
            registry,
            company_policy,
        )
        worktime_results = _worktime.build_worktime_payroll_results(
            prepared["worktime"],
            payroll_period,
            registry,
            company_policy,
            legal_policy,
            ordinary_hourly_wage_resolver=hourly_resolver,
        )

    absence_event_rows = list(absence_events)
    absence_results = []
    for item in absence_deduction_inputs:
        worker_id = str(item.get("worker_id", "")).strip()
        if not worker_id:
            raise PayrollCalculationStageError(
                "absence_deduction_inputs requires worker_id"
            )
        absence_results.extend(
            _absence.build_absence_deduction_results(
                absence_events=absence_event_rows,
                worktime_rows=prepared["worktime_history"],
                compensation_rows=prepared["compensation_history"],
                worker_id=worker_id,
                payroll_period=payroll_period,
                scheduled_workdays=item.get("scheduled_workdays"),
                paid_treatment_days=item.get("paid_treatment_days"),
                registry=registry,
            )
        )

    employment_by_worker = {
        str(item.get("worker_id", "")).strip(): item
        for item in employment_rows
    }
    weekly_holiday_resolutions = []
    weekly_holiday_results = []
    for item in weekly_holiday_inputs:
        worker_id = str(item.get("worker_id", "")).strip()
        if not worker_id:
            raise PayrollCalculationStageError(
                "weekly_holiday_inputs requires worker_id"
            )
        employment = employment_by_worker.get(worker_id, {})
        output = _weekly_holiday.build_weekly_holiday_result(
            worker_id=worker_id,
            payroll_period=payroll_period,
            week_start=item.get("week_start"),
            week_end=item.get("week_end"),
            worktime_rows=prepared["worktime_history"],
            absence_events=absence_event_rows,
            weekly_scheduled_hours=item.get("weekly_scheduled_hours"),
            labor_status=item.get("labor_status"),
            pay_basis=item.get("pay_basis"),
            registry=registry,
            ordinary_worker_weekly_prescribed_days=item.get(
                "ordinary_worker_weekly_prescribed_days", 5
            ),
            hourly_rate=item.get("hourly_rate"),
            special_agreement=item.get("special_agreement"),
            employment_from=employment.get("employment_from"),
            employment_to=employment.get("employment_to"),
        )
        weekly_holiday_resolutions.append(output["resolution"])
        if output["payroll_result"] is not None:
            weekly_holiday_results.append(output["payroll_result"])

    source_results = {
        "compensation": compensation_results,
        "worktime": worktime_results,
        "payroll_input": payroll_input_results,
        "absence_deduction": absence_results,
        "weekly_holiday": weekly_holiday_results,
    }
    return {
        "payroll_period": str(payroll_period).strip(),
        "prepared_input": prepared,
        "source_results": source_results,
        "weekly_holiday_resolutions": weekly_holiday_resolutions,
    }
