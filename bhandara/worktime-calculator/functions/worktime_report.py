"""Unfinalized Worktime calculation artifacts and independent review workbook."""
from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from openpyxl import Workbook


class WorktimeReportError(ValueError):
    pass


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def build_review(result: Mapping[str, Any]) -> dict[str, Any]:
    records = result["records"]
    issues = result["issues"]
    return {
        "schema_version": result["schema_version"],
        "status": result["status"],
        "finalizable": False,
        "period_from": result["period_from"],
        "period_to": result["period_to"],
        "source_batch_id": result["source_batch_id"],
        "source_hashes": result["source_hashes"],
        "covered_worker_ids": result["covered_worker_ids"],
        "coverage_verified": False,
        "calculated_rows": len(result["rows"]),
        "record_counts": {
            key: sum(row["status"] == key for row in records)
            for key in ("CALCULATED", "REVIEW", "ERROR", "SKIPPED")
        },
        "error_count": sum(x["severity"] == "ERROR" for x in issues),
        "review_count": sum(x["severity"] == "REVIEW" for x in issues),
        "records": records,
        "issues": issues,
        "notice": (
            "Calculation only; NOT a Worktime close receipt. Candidate expected keys "
            "cannot replace independently approved schedule/roster coverage. "
            "No payroll or payment has been finalized."
        ),
    }


def _excel(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dict, list)):
        value = json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True)
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def write_review_xlsx(path: str | Path, result: Mapping[str, Any]) -> None:
    target = Path(path)
    if target.exists():
        raise WorktimeReportError(f"output already exists: {target}")
    review = build_review(result)
    wb = Workbook()
    try:
        summary = wb.active
        summary.title = "Summary"
        summary.append(["field", "value"])
        for key in ("status", "period_from", "period_to", "source_batch_id",
                    "coverage_verified", "calculated_rows", "error_count",
                    "review_count", "notice"):
            summary.append([key, _excel(review.get(key))])
        worktime = wb.create_sheet("Daily Worktime")
        hour_fields = ("scheduled_hours", "worked_hours", "ordinary_hours",
                       "overtime_hours", "night_hours",
                       "holiday_work_hours_within_8", "holiday_work_hours_over_8",
                       "absence_hours")
        columns = ("worker_id", "work_date", *hour_fields,
                   "late_minutes", "early_leave_minutes", "approval_ref",
                   "validation_flags")
        worktime.append(columns)
        for value in result["rows"]:
            worktime.append([_excel(value.get(column)) for column in columns])
        records = wb.create_sheet("Processing")
        record_fields = ("worker_id", "employee_id", "work_date", "status",
                         "schedule_row_number", "attendance_row_number", "issue_codes")
        records.append(record_fields)
        for value in result["records"]:
            records.append([_excel(value.get(column)) for column in record_fields])
        review_sheet = wb.create_sheet("Review Required")
        fields = ("severity", "code", "worker_id", "employee_id", "work_date",
                  "source", "row_number", "message")
        review_sheet.append(fields)
        for value in result["issues"]:
            review_sheet.append([_excel(value.get(column)) for column in fields])
        for sheet in wb.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
        wb.save(target)
        os.chmod(target, 0o600)
    finally:
        wb.close()


def write_worktime_outputs(directory: str | Path, result: Mapping[str, Any]) -> dict[str, str]:
    """Write all outputs in a *new* private directory, never overwrite any run."""
    root = Path(directory)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    names = {
        "worktime_result": root / "worktime-result.json",
        "review_json": root / "worktime-review.json",
        "review_xlsx": root / "worktime-review.xlsx",
    }
    worktime = {
        "schema_version": result["schema_version"],
        "status": result["status"],
        "finalizable": False,
        "period_from": result["period_from"],
        "period_to": result["period_to"],
        "source_batch_id": result["source_batch_id"],
        "source_hashes": result["source_hashes"],
        "covered_worker_ids": result["covered_worker_ids"],
        "rows": result["rows"],
        "candidate_expected_keys": result["candidate_expected_keys"],
        "coverage_verified": False,
        "close_receipt": None,
    }
    try:
        for key, payload in (
            ("worktime_result", worktime),
            ("review_json", build_review(result)),
        ):
            with names[key].open("x", encoding="utf-8") as handle:
                os.chmod(names[key], 0o600)
                json.dump(_jsonable(payload), handle, ensure_ascii=False,
                          indent=2, sort_keys=True, allow_nan=False)
                handle.write("\n")
        write_review_xlsx(names["review_xlsx"], result)
    except Exception:
        for file in names.values():
            file.unlink(missing_ok=True)
        root.rmdir()
        raise
    return {key: str(path) for key, path in names.items()}
