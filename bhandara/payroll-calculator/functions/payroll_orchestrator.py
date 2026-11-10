"""Compose Payroll Calculator modules for one worker and payroll period."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

try:
    from .amount_processing import process_final_amount
    from .effective_absence_deduction import build_effective_absence_deduction_lines
    from .payroll_aggregator import aggregate_earnings
    from .payroll_policy_resolver import resolve_payroll_policy
    from .proration import build_prorated_recurring_item
    from .rounding_settlement import build_rounding_settlement_batch
    from .settlement_ledger import resolve_period_adjustments
    from .weekly_holiday_resolver import resolve_weekly_holiday
except ImportError:
    from amount_processing import process_final_amount
    from effective_absence_deduction import build_effective_absence_deduction_lines
    from payroll_aggregator import aggregate_earnings
    from payroll_policy_resolver import resolve_payroll_policy
    from proration import build_prorated_recurring_item
    from rounding_settlement import build_rounding_settlement_batch
    from settlement_ledger import resolve_period_adjustments
    from weekly_holiday_resolver import resolve_weekly_holiday


def _period_month(payroll_period: str) -> int:
    parts = str(payroll_period).split("-")
    if len(parts) < 2:
        raise ValueError("payroll_period must start with YYYY-MM")
    month = int(parts[1])
    if month < 1 or month > 12:
        raise ValueError("payroll_period month must be 01..12")
    return month


def calculate_worker_payroll(
    worker_id: str,
    payroll_period: str,
    recurring_items: list[dict[str, Any]],
    worktime_items: list[dict[str, Any]],
    variable_items: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    policy: dict[str, Any] | None = None,
    policy_history: list[dict[str, Any]] | None = None,
    settlement_date: str | None = None,
    compensation_rows: list[dict[str, Any]] | None = None,
    registry: dict[str, Any] | None = None,
    employment_from: Any | None = None,
    employment_to: Any | None = None,
    absence_events: list[dict[str, Any]] | None = None,
    worktime_rows: list[dict[str, Any]] | None = None,
    scheduled_workdays: Any | None = None,
    paid_treatment_days: Any | None = None,
    weekly_holiday_requests: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    policy_warnings: list[dict[str, Any]] = []
    if policy_history is not None:
        if not settlement_date:
            raise ValueError("settlement_date is required when policy_history is provided")
        resolved = resolve_payroll_policy(policy_history, settlement_date)
        policy = resolved["policy"]
        policy_warnings = resolved["warnings"]
    if policy is None:
        raise ValueError("policy or policy_history is required")

    resolved_recurring_items = recurring_items
    if compensation_rows is not None:
        if recurring_items:
            raise ValueError(
                "recurring_items and compensation_rows cannot be provided together"
            )
        if registry is None:
            raise ValueError("registry is required when compensation_rows is provided")
        resolved_recurring_items = [
            build_prorated_recurring_item(
                compensation_rows,
                worker_id,
                payroll_period,
                "base_salary",
                registry,
                policy,
                employment_from=employment_from,
                employment_to=employment_to,
            )
        ]

    deduction_items: list[dict[str, Any]] = []
    if absence_events:
        if compensation_rows is None:
            raise ValueError("compensation_rows is required when absence_events are provided")
        if worktime_rows is None:
            raise ValueError("worktime_rows is required when absence_events are provided")
        if scheduled_workdays is None or paid_treatment_days is None:
            raise ValueError(
                "scheduled_workdays and paid_treatment_days are required "
                "when absence_events are provided"
            )
        deduction_items = build_effective_absence_deduction_lines(
            absence_events,
            worktime_rows,
            compensation_rows,
            worker_id,
            payroll_period,
            scheduled_workdays,
            paid_treatment_days,
        )

    weekly_holiday_results: list[dict[str, Any]] = []
    weekly_holiday_items: list[dict[str, Any]] = []
    for request in weekly_holiday_requests or []:
        result = resolve_weekly_holiday(
            worker_id=worker_id,
            week_start=request["week_start"],
            week_end=request["week_end"],
            worktime_rows=worktime_rows or [],
            absence_events=absence_events or [],
            weekly_scheduled_hours=request["weekly_scheduled_hours"],
            labor_status=request["labor_status"],
            pay_basis=request["pay_basis"],
            ordinary_worker_weekly_prescribed_days=request.get(
                "ordinary_worker_weekly_prescribed_days", 5
            ),
            hourly_rate=request.get("hourly_rate"),
            special_agreement=request.get("special_agreement"),
            employment_from=employment_from,
            employment_to=employment_to,
        )
        weekly_holiday_results.append(result)
        if result["earning_line"] is not None:
            weekly_holiday_items.append(result["earning_line"])

    resolved_variable_items = [*variable_items, *weekly_holiday_items]

    period_adjustments = resolve_period_adjustments(ledger_rows, worker_id, payroll_period)
    settlement_adjustment = period_adjustments["settlement_adjustment"]
    ledger_write_requests: list[dict[str, Any]] = []

    remainder_policy = policy.get("amount_processing", {}).get("remainder", {})
    settlement_month = int(remainder_policy.get("settlement_month", 0) or 0)
    rounding_batch = None

    if settlement_month and _period_month(payroll_period) == settlement_month:
        batch_id = f"RS-{payroll_period[:4]}-{worker_id}"
        rounding_batch = build_rounding_settlement_batch(
            ledger_rows, worker_id, payroll_period, batch_id
        )
        ledger_write_requests.extend(rounding_batch["settlement_transactions"])

    aggregated = aggregate_earnings(
        resolved_recurring_items,
        worktime_items,
        resolved_variable_items,
        settlement_adjustment=settlement_adjustment,
        deduction_items=deduction_items,
    )
    processed = process_final_amount(
        worker_id,
        payroll_period,
        aggregated["calculated_payable_before_amount_processing"],
        policy,
    )
    if processed["ledger_transaction_request"] is not None:
        ledger_write_requests.append(processed["ledger_transaction_request"])

    rounding_settlement_payable = (
        rounding_batch["settlement_amount"] if rounding_batch is not None else Decimal("0")
    )
    total_payable_amount = processed["payable_amount"] + rounding_settlement_payable

    return {
        "worker_id": worker_id,
        "payroll_period": payroll_period,
        "settlement_date": settlement_date,
        "policy_id": policy.get("policy_id"),
        "policy_warnings": policy_warnings,
        "period_settlement": period_adjustments,
        "rounding_settlement_batch": rounding_batch,
        "aggregation": aggregated,
        "resolved_recurring_items": resolved_recurring_items,
        "resolved_deduction_items": deduction_items,
        "resolved_weekly_holiday_results": weekly_holiday_results,
        "resolved_weekly_holiday_items": weekly_holiday_items,
        "amount_processing": processed,
        "regular_payable_amount": processed["payable_amount"],
        "rounding_settlement_payable": rounding_settlement_payable,
        "payable_amount": total_payable_amount,
        "ledger_write_requests": ledger_write_requests,
    }
