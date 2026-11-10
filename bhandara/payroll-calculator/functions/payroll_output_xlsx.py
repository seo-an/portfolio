"""Write human-reviewable Payroll output XLSX from operational composition."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from openpyxl import Workbook


class PayrollOutputXlsxError(ValueError):
    pass


SUMMARY_HEADERS = [
    "worker_id", "payroll_period", "status", "can_auto_finalize",
    "pay_total", "deduction_total", "settlement_total", "settlement_adjustment",
    "calculated_net_amount", "payable_amount", "rounding_remainder",
]
DETAIL_HEADERS = [
    "worker_id", "payroll_period", "pay_item_code", "item_type", "direction",
    "calculated_amount", "source", "origin_pay_item_code", "origin_from",
    "origin_to", "calculation_trace",
]
VALIDATION_HEADERS = [
    "worker_id", "payroll_period", "code", "severity", "message", "action",
    "context",
]


def _cell(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
    return value if value is not None else ""


def _status(run: Mapping[str, Any]) -> str:
    summary = run["validation_summary"]
    if summary["has_error"]:
        return "ERROR"
    if summary["requires_action"]:
        return "ACTION_REQUIRED"
    if not run["can_auto_finalize"]:
        return "REVIEW"
    return "FINALIZABLE"


def write_payroll_output_xlsx(
    path: str | Path,
    composition: Mapping[str, Any],
) -> None:
    worker_runs = composition.get("worker_runs")
    if not isinstance(worker_runs, Mapping):
        raise PayrollOutputXlsxError("composition.worker_runs must be a mapping")

    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Summary"
    detail_sheet = workbook.create_sheet("Calculation Detail")
    validation_sheet = workbook.create_sheet("Validation")
    summary_sheet.append(SUMMARY_HEADERS)
    detail_sheet.append(DETAIL_HEADERS)
    validation_sheet.append(VALIDATION_HEADERS)

    for worker_id in sorted(worker_runs):
        run = worker_runs[worker_id]
        final = run.get("final_payroll")
        totals = final["totals"] if final is not None else {}
        summary_sheet.append([
            _cell(run.get("worker_id")),
            _cell(run.get("payroll_period")),
            _status(run),
            bool(run.get("can_auto_finalize")),
            _cell(totals.get("pay_total")),
            _cell(totals.get("deduction_total")),
            _cell(totals.get("settlement_total")),
            _cell(totals.get("settlement_adjustment")),
            _cell(final.get("calculated_net_amount") if final else None),
            _cell(final.get("payable_amount") if final else None),
            _cell(final.get("rounding_remainder") if final else None),
        ])

        for result in run.get("results", []):
            detail_sheet.append([
                _cell(result.get("worker_id")),
                _cell(result.get("payroll_period")),
                _cell(result.get("pay_item_code")),
                _cell(result.get("item_type")),
                _cell(result.get("direction")),
                _cell(result.get("calculated_amount")),
                _cell(result.get("source")),
                _cell(result.get("origin_pay_item_code")),
                _cell(result.get("origin_from")),
                _cell(result.get("origin_to")),
                _cell(result.get("calculation_trace", {})),
            ])

        for validation in run.get("validations", []):
            validation_sheet.append([
                _cell(run.get("worker_id")),
                _cell(run.get("payroll_period")),
                _cell(validation.get("code")),
                _cell(validation.get("severity")),
                _cell(validation.get("message")),
                _cell(validation.get("action")),
                _cell(validation.get("context", {})),
            ])

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(target)
    workbook.close()
