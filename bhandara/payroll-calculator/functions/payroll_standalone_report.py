"""Human review artifacts for a standalone Payroll calculation.

Artifacts are never finalized payroll records or proof of actual approvals.
A failure to load or calculate still produces independent review JSON/XLSX.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from openpyxl import Workbook

try:
    from .payroll_output_xlsx import write_payroll_output_xlsx
except ImportError:
    from payroll_output_xlsx import write_payroll_output_xlsx


class StandalonePayrollReportError(ValueError):
    pass


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    return value


def make_report(result: Mapping[str, Any] | None, *,
                error: Exception | None = None) -> dict[str, Any]:
    if result is None:
        if error is None:
            raise StandalonePayrollReportError("result or error required")
        return {
            "schema_version": "0.1",
            "status": "BLOCKED",
            "finalizable": False,
            "ledger_committed": False,
            "payroll_period": None,
            "worktime_mode": "UNAVAILABLE",
            "source_hashes": {},
            "expected_workers": [],
            "actual_workers": [],
            "issue_count": 1,
            "issues": [{
                "code": "PAYROLL_CALCULATION_FAILED",
                "severity": "ERROR",
                "worker_id": None,
                "message": f"{type(error).__name__}: {error}",
            }],
            "notice": "No payroll amounts were calculated; check input contract and source data.",
        }
    runs = result["composition"]["worker_runs"]
    missing = sorted(set(result["expected_worker_ids"]) - set(runs))
    return {
        "schema_version": result["schema_version"],
        "status": result["status"],
        "finalizable": False,
        "ledger_committed": False,
        "payroll_period": result["payroll_period"],
        "worktime_mode": result["worktime_mode"],
        "policy_selection": result.get("policy_selection"),
        "worktime_source_period": result["worktime_source_period"],
        "worktime_receipt_hashes": result["worktime_receipt_hashes"],
        "source_hashes": result["source_hashes"],
        "expected_workers": result["expected_worker_ids"],
        "actual_workers": sorted(runs),
        "calculated_worker_count": len(runs),
        "worker_statuses": [{
            "worker_id": worker_id,
            "can_auto_finalize": False,
            "has_calculation": run["final_payroll"] is not None,
            "has_error": run["validation_summary"]["has_error"],
            "requires_action": True,
            "validation_codes": [str(item.get("code", ""))
                                 for item in run["validations"]],
        } for worker_id, run in sorted(runs.items())] + [{
            "worker_id": worker_id,
            "can_auto_finalize": False,
            "has_calculation": False,
            "has_error": True,
            "requires_action": True,
            "validation_codes": ["MISSING_PAYROLL_RESULT"],
        } for worker_id in missing],
        "ledger_write_request_count": (
            len(result["ledger_write_requests"]) + len(result["final_ledger_requests"])
        ),
        "issue_count": len(result["issues"]),
        "issues": result["issues"],
        "notice": (
            "REVIEW ONLY. Payroll amounts are provisional; tax/insurance and "
            "approvals are not finalized, and no Settlement Ledger was modified."
        ),
    }


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dict, list)):
        value = json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True)
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def write_review_xlsx(path: Path, report: Mapping[str, Any]) -> None:
    if path.exists():
        raise StandalonePayrollReportError(f"review workbook exists: {path}")
    book = Workbook()
    try:
        summary = book.active
        summary.title = "Run Summary"
        summary.append(["field", "value"])
        for name in ("status", "payroll_period", "finalizable",
                     "ledger_committed", "worktime_mode",
                     "calculated_worker_count", "issue_count", "notice"):
            summary.append([name, _cell(report.get(name))])
        workers = book.create_sheet("Worker Coverage")
        worker_fields = ("worker_id", "has_calculation", "requires_action",
                         "has_error", "validation_codes")
        workers.append(worker_fields)
        for item in report.get("worker_statuses", []):
            workers.append([_cell(item.get(name)) for name in worker_fields])
        issues = book.create_sheet("Review Required")
        issue_fields = ("severity", "code", "worker_id", "work_date", "message")
        issues.append(issue_fields)
        for item in report.get("issues", []):
            issues.append([_cell(item.get(name)) for name in issue_fields])
        for sheet in book:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
        book.save(path)
        os.chmod(path, 0o600)
    finally:
        book.close()


def write_standalone_outputs(output_dir: str | Path,
                             result: Mapping[str, Any] | None, *,
                             error: Exception | None = None) -> dict[str, str]:
    """Create new private directory; never overwrite, never write ledger."""
    root = Path(output_dir)
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    report = make_report(result, error=error)
    paths = {
        "review_json": root / "payroll-review.json",
        "review_xlsx": root / "payroll-review.xlsx",
    }
    if result is not None:
        paths["policy_resolution_json"] = root / "policy-resolution.json"
        paths["calculation_json"] = root / "payroll-calculation.json"
        paths["calculation_xlsx"] = root / "payroll-calculation.xlsx"
    try:
        payloads = [("review_json", report)]
        if result is not None:
            payloads.append(("policy_resolution_json", {
                "schema_version": "0.1",
                "payroll_period": result["payroll_period"],
                "selection": result.get("policy_selection"),
                "resolved_company_policy": result.get("resolved_company_policy"),
                "finalizable": False,
            }))
            payloads.append(("calculation_json", {
                "schema_version": "0.1",
                "payroll_period": result["payroll_period"],
                "status": result["status"],
                "finalizable": False,
                "ledger_committed": False,
                "worktime_mode": result["worktime_mode"],
                "policy_selection": result.get("policy_selection"),
                "expected_worker_ids": result["expected_worker_ids"],
                "composition": result["composition"],
                "ledger_write_requests": result["ledger_write_requests"],
                "final_ledger_requests": result["final_ledger_requests"],
            }))
        for label, payload in payloads:
            with paths[label].open("x", encoding="utf-8") as handle:
                os.chmod(paths[label], 0o600)
                json.dump(_jsonable(payload), handle, ensure_ascii=False,
                          indent=2, sort_keys=True, allow_nan=False)
                handle.write("\n")
        write_review_xlsx(paths["review_xlsx"], report)
        if result is not None:
            write_payroll_output_xlsx(
                paths["calculation_xlsx"],
                result["composition"],
            )
            os.chmod(paths["calculation_xlsx"], 0o600)
    except Exception:
        for file in paths.values():
            file.unlink(missing_ok=True)
        root.rmdir()
        raise
    return {name: str(path) for name, path in paths.items()}
