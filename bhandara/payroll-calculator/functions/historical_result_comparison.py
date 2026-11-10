"""Aggregate historical Payroll Results into safe retroactive comparisons."""

from __future__ import annotations

import importlib.util
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping


def _load_sibling(module_name: str):
    path = Path(__file__).with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_retroactive_result = _load_sibling("retroactive_result")


class HistoricalResultComparisonError(ValueError):
    pass


def _amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise HistoricalResultComparisonError(
            "calculated_amount must be decimal-compatible"
        ) from exc
    if not amount.is_finite() or amount < 0:
        raise HistoricalResultComparisonError(
            "calculated_amount must be finite and non-negative"
        )
    return amount


def _period_bounds(payroll_period: Any) -> tuple[date, date]:
    period = str(payroll_period).strip()
    try:
        year_text, month_text = period.split("-", 1)
        year = int(year_text)
        month = int(month_text)
        start = date(year, month, 1)
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return start, date.fromordinal(next_month.toordinal() - 1)
    except (TypeError, ValueError):
        raise HistoricalResultComparisonError(
            f"payroll_period must use YYYY-MM: {period!r}"
        ) from None


def _origin_key(result: Mapping[str, Any]) -> tuple[Any, Any] | None:
    origin_from = result.get("origin_from")
    origin_to = result.get("origin_to")
    if origin_from in (None, "") and origin_to in (None, ""):
        return None
    if origin_from in (None, "") or origin_to in (None, ""):
        raise HistoricalResultComparisonError(
            "origin_from and origin_to must be paired"
        )
    return origin_from, origin_to


def _aggregate(
    results: Iterable[Mapping[str, Any]],
    historical_payroll_period: str,
) -> dict[tuple[str, str, tuple[Any, Any] | None], Decimal]:
    aggregated = {}
    for result in results:
        worker_id = str(result.get("worker_id", "")).strip()
        pay_item_code = str(result.get("pay_item_code", "")).strip()
        payroll_period = str(result.get("payroll_period", "")).strip()
        if not worker_id or not pay_item_code:
            raise HistoricalResultComparisonError(
                "historical result requires worker_id and pay_item_code"
            )
        if payroll_period != historical_payroll_period:
            raise HistoricalResultComparisonError(
                f"mixed historical payroll_period is not allowed: "
                f"{payroll_period!r} != {historical_payroll_period!r}"
            )
        key = (worker_id, pay_item_code, _origin_key(result))
        aggregated[key] = aggregated.get(key, Decimal("0")) + _amount(
            result.get("calculated_amount")
        )
    return aggregated


def _synthetic_result(
    key: tuple[str, str, tuple[Any, Any] | None],
    amount: Decimal,
    payroll_period: str,
) -> dict[str, Any]:
    worker_id, pay_item_code, origin = key
    origin_from = origin[0] if origin is not None else None
    origin_to = origin[1] if origin is not None else None
    return {
        "worker_id": worker_id,
        "payroll_period": payroll_period,
        "pay_item_code": pay_item_code,
        "calculated_amount": amount,
        "origin_from": origin_from,
        "origin_to": origin_to,
    }


def build_historical_retroactive_results(
    original_results: Iterable[Mapping[str, Any]],
    recalculated_results: Iterable[Mapping[str, Any]],
    historical_payroll_period: Any,
    settlement_payroll_period: Any,
    registry: Mapping[str, Any],
    *,
    employment_to_by_worker: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Compare aggregate historical run amounts and emit later retro Results."""
    historical_period = str(historical_payroll_period).strip()
    _period_bounds(historical_period)
    original = _aggregate(original_results, historical_period)
    recalculated = _aggregate(recalculated_results, historical_period)
    employment_to = employment_to_by_worker or {}

    outputs = []
    for key in sorted(set(original) | set(recalculated), key=str):
        original_result = _synthetic_result(
            key, original.get(key, Decimal("0")), historical_period
        )
        recalculated_result = _synthetic_result(
            key, recalculated.get(key, Decimal("0")), historical_period
        )
        result = _retroactive_result.build_retroactive_payroll_result(
            original_result,
            recalculated_result,
            settlement_payroll_period,
            registry,
            employment_to=employment_to.get(key[0]),
        )
        if result is not None:
            outputs.append(result)
    return outputs
