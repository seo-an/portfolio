"""Promote separately calculated weekly-holiday earnings into Payroll Results."""

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


_resolver = _load_sibling("weekly_holiday_resolver")
_result_adapter = _load_sibling("calculated_result_adapter")


class WeeklyHolidayCalculationAdapterError(ValueError):
    pass


def build_weekly_holiday_result(
    *,
    worker_id: str,
    payroll_period: str,
    week_start: Any,
    week_end: Any,
    worktime_rows: list[dict[str, Any]],
    absence_events: list[dict[str, Any]],
    weekly_scheduled_hours: Any,
    labor_status: str,
    pay_basis: str,
    registry: Mapping[str, Any],
    ordinary_worker_weekly_prescribed_days: Any = 5,
    hourly_rate: Any | None = None,
    special_agreement: dict[str, Any] | None = None,
    employment_from: Any | None = None,
    employment_to: Any | None = None,
) -> dict[str, Any]:
    """Resolve one week and return its trace plus an optional Payroll Result."""
    resolved = _resolver.resolve_weekly_holiday(
        worker_id=worker_id,
        week_start=week_start,
        week_end=week_end,
        worktime_rows=worktime_rows,
        absence_events=absence_events,
        weekly_scheduled_hours=weekly_scheduled_hours,
        labor_status=labor_status,
        pay_basis=pay_basis,
        ordinary_worker_weekly_prescribed_days=ordinary_worker_weekly_prescribed_days,
        hourly_rate=hourly_rate,
        special_agreement=special_agreement,
        employment_from=employment_from,
        employment_to=employment_to,
    )

    earning_line = resolved["earning_line"]
    payroll_result = None
    if earning_line is not None:
        payroll_result = _result_adapter.build_payroll_result_from_calculation(
            {**earning_line, "worker_id": str(worker_id).strip()},
            payroll_period,
            registry,
            source="payroll_calculator",
            calculation_trace={"weekly_holiday_resolution": resolved},
        )

    return {
        "resolution": resolved,
        "payroll_result": payroll_result,
    }
