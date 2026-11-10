"""Convert matched historical Payroll Results into a retroactive Payroll Result."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from typing import Any, Mapping


class RetroactiveResultError(RuntimeError):
    """Raised when historical payroll results cannot be compared safely."""

    def __init__(self, message: str) -> None:
        super().__init__(f"❌ [payroll-calculator] Retroactive result failed: {message}")


def _load_sibling(module_name: str):
    path = Path(__file__).with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_retroactive = _load_sibling("retroactive_settlement")
_payroll_result = _load_sibling("payroll_result")
_validation = _load_sibling("payroll_validation")


def _origin_period(result: Mapping[str, Any]) -> tuple[Any, Any]:
    origin_from = result.get("origin_from")
    origin_to = result.get("origin_to")
    if origin_from is not None or origin_to is not None:
        if origin_from is None or origin_to is None:
            raise RetroactiveResultError(
                "historical result origin_from and origin_to must be paired"
            )
        return origin_from, origin_to

    payroll_period = str(result.get("payroll_period", "")).strip()
    try:
        year_text, month_text = payroll_period.split("-", 1)
        year = int(year_text)
        month = int(month_text)
        start = date(year, month, 1)
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        end = date.fromordinal(next_month.toordinal() - 1)
        return start, end
    except (TypeError, ValueError):
        raise RetroactiveResultError(
            f"historical payroll_period must use YYYY-MM: {payroll_period!r}"
        ) from None


def build_retroactive_payroll_result(
    original_result: Mapping[str, Any],
    recalculated_result: Mapping[str, Any],
    settlement_payroll_period: Any,
    registry: Mapping[str, Any],
    *,
    employment_to: Any = None,
) -> dict[str, Any] | None:
    """Compare two matched historical results and emit a later settlement result."""
    original_worker = str(original_result.get("worker_id", "")).strip()
    recalculated_worker = str(recalculated_result.get("worker_id", "")).strip()
    if not original_worker or original_worker != recalculated_worker:
        raise RetroactiveResultError("historical results must belong to the same worker")

    original_item = str(original_result.get("pay_item_code", "")).strip()
    recalculated_item = str(recalculated_result.get("pay_item_code", "")).strip()
    if not original_item or original_item != recalculated_item:
        raise RetroactiveResultError(
            "historical results must use the same pay_item_code"
        )

    original_from, original_to = _origin_period(original_result)
    recalculated_from, recalculated_to = _origin_period(recalculated_result)
    if (original_from, original_to) != (recalculated_from, recalculated_to):
        raise RetroactiveResultError(
            "historical results must use the same origin period"
        )

    settlement = _retroactive.build_retroactive_settlement(
        original_item,
        original_from,
        original_to,
        original_result.get("calculated_amount"),
        recalculated_result.get("calculated_amount"),
    )
    if settlement["direction"] == "none":
        return None

    result = _payroll_result.build_payroll_result(
        original_worker,
        settlement_payroll_period,
        settlement["settlement_pay_item_code"],
        settlement["settlement_amount"],
        registry,
        origin_pay_item_code=settlement["origin_pay_item_code"],
        origin_from=settlement["origin_from"],
        origin_to=settlement["origin_to"],
        source="historical_rerun",
        calculation_trace={
            "original_result": original_result,
            "recalculated_result": recalculated_result,
            "difference": settlement["difference"],
        },
    )

    validations = []
    settlement_period_start, _ = _origin_period({
        "payroll_period": settlement_payroll_period,
        "origin_from": None,
        "origin_to": None,
    })
    if (
        settlement["direction"] == "deduction"
        and employment_to is not None
        and _retroactive._date(employment_to, "employment_to") < settlement_period_start
    ):
        validations.append(_validation.build_validation(
            "POST_TERMINATION_RECOVERY_REQUIRED",
            _validation.ACTION_REQUIRED,
            "퇴직 후 과거 급여의 과지급 차액은 자동 공제하지 않고 별도 회수 절차를 확인해야 합니다.",
            action="퇴직자 회수 가능 여부와 회수 절차를 확인한 뒤 수동으로 처리합니다.",
            context={
                "employment_to": employment_to,
                "origin_pay_item_code": settlement["origin_pay_item_code"],
                "origin_from": settlement["origin_from"],
                "origin_to": settlement["origin_to"],
                "settlement_amount": settlement["settlement_amount"],
            },
        ))

    result["validations"] = validations
    result["validation_summary"] = _validation.summarize_validations(validations)
    return result
