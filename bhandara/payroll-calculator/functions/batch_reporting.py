"""Human- and machine-readable payroll input audit reports.

Reports never contain source cell values, only provenance and actionable
findings. Raw normalized facts are exported separately with local-only access.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from openpyxl import Workbook


class BatchReportError(ValueError):
    pass


def summarize_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    sources = bundle.get("source_results", {})
    issues = list(bundle.get("issues", []))
    return {
        "schema_version": bundle.get("schema_version"),
        "payroll_period": bundle.get("payroll_period"),
        "batch_id": bundle.get("batch_id"),
        "status": bundle.get("status"),
        "finalizable": False,
        "sources": [
            {
                "source": name,
                "source_file": result.get("source_file"),
                "source_sha256": result.get("source_sha256"),
                "total_rows": result.get("total_rows"),
                "accepted_rows": result.get("accepted_rows"),
                "rejected_rows": result.get("rejected_rows"),
            }
            for name, result in sorted(sources.items())
        ],
        "stages": list(bundle.get("stages", [])),
        "issue_count": len(issues),
        "error_count": sum(1 for item in issues if item.get("severity") == "ERROR"),
        "review_count": sum(1 for item in issues if item.get("severity") == "REVIEW"),
        "issues": issues,
    }


def _safe_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value  # Guard spreadsheet formula injection.
    return value


def write_batch_report_xlsx(path: str | Path, report: Mapping[str, Any]) -> None:
    target = Path(path)
    if target.exists():
        raise BatchReportError(f"report file exists: {target}")
    book = Workbook()
    try:
        overview = book.active
        overview.title = "Run Summary"
        overview.append(["field", "value"])
        for name in ("payroll_period", "batch_id", "status", "finalizable",
                     "issue_count", "error_count", "review_count"):
            overview.append([name, _safe_cell(report.get(name))])
        stages = book.create_sheet("Stages")
        stages.append(["stage", "status", "input_count", "output_count"])
        for item in report.get("stages", []):
            stages.append([_safe_cell(item.get(key)) for key in
                           ("stage", "status", "input_count", "output_count")])
        sources = book.create_sheet("Sources")
        names = ("source", "source_file", "source_sha256", "total_rows",
                 "accepted_rows", "rejected_rows")
        sources.append(names)
        for item in report.get("sources", []):
            sources.append([_safe_cell(item.get(key)) for key in names])
        issues = book.create_sheet("Review Required")
        issue_fields = ("severity", "code", "source", "row_number",
                        "field", "message")
        issues.append(issue_fields)
        for item in report.get("issues", []):
            issues.append([_safe_cell(item.get(key)) for key in issue_fields])
        for sheet in book:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
        book.save(target)
        os.chmod(target, 0o600)
    finally:
        book.close()


def write_batch_outputs(
    output_dir: str | Path,
    bundle: Mapping[str, Any],
) -> dict[str, str]:
    """Write normalized facts + audit JSON/XLSX without overwriting older runs."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "normalized": root / "normalized-input.json",
        "report_json": root / "review-report.json",
        "report_xlsx": root / "review-report.xlsx",
    }
    if any(path.exists() for path in paths.values()):
        raise BatchReportError("output files already exist; choose a new output directory")
    report = summarize_bundle(bundle)
    # Never treat this report as proof that payroll was calculated or finalized.
    normalized = {
        "schema_version": bundle.get("schema_version"),
        "payroll_period": bundle.get("payroll_period"),
        "batch_id": bundle.get("batch_id"),
        "status": bundle.get("status"),
        "sources": {
            key: {
                "rows": result.get("rows", []),
                "lineage": result.get("lineage", []),
                "source_file": result.get("source_file"),
                "source_sha256": result.get("source_sha256"),
            }
            for key, result in bundle.get("source_results", {}).items()
        },
    }
    try:
        for label, payload in (("normalized", normalized), ("report_json", report)):
            path = paths[label]
            with path.open("x", encoding="utf-8") as handle:
                os.chmod(path, 0o600)
                json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
                handle.write("\n")
        write_batch_report_xlsx(paths["report_xlsx"], report)
    except Exception:
        for path in paths.values():
            # This call exclusively owns newly created paths (prechecked above).
            path.unlink(missing_ok=True)
        raise
    return {key: str(value) for key, value in paths.items()}
