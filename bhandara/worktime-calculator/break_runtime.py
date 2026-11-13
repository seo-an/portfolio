"""Optional Worktime entrypoint for already-normalized CAPS access evidence.

The original migrated 10 source files remain byte-identical for Golden parity.
A missing access_events source uses the original CLI unchanged. With access
facts present, the review is performed before any output is published.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .break_review import BreakReviewError, analyze_access_breaks, write_break_review
from .functions.worktime_batch import WorktimeBatchError, calculate_worktime_batch
from .functions.worktime_report import WorktimeReportError, write_worktime_outputs


def _read_json(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise BreakReviewError("Worktime input must be an object")
    return payload


def _augment_reviews(result: dict, break_analysis: dict) -> None:
    """Do not let a reviewed break become an unreviewed overall Worktime run."""
    for row in break_analysis["rows"]:
        if row["status"] == "PASS_VERIFIED":
            continue
        code = ("BREAK_SHORTFALL_DETECTED" if row["status"] == "SHORTFALL_DETECTED"
                else "BREAK_EVIDENCE_REVIEW_REQUIRED")
        result["issues"].append({
            "code": code, "severity": "REVIEW",
            "message": "Normalized access/rest evidence requires human review",
            "source": "access_events", "row_number": None,
            "employee_id": "", "worker_id": row["worker_id"],
            "work_date": row["work_date"],
        })
    if break_analysis.get("normalization_issue_count", 0):
        result["issues"].append({
            "code": "CAPS_UPSTREAM_NORMALIZATION_REVIEW", "severity": "REVIEW",
            "message": "CAPS mapping contained rejected/uncertain source rows",
            "source": "access_events", "row_number": None,
            "employee_id": "", "worker_id": "", "work_date": "",
        })
    if result["status"] == "CALCULATED_UNCLOSED" and (
        break_analysis["status"] != "PASS_VERIFIED"
    ):
        result["status"] = "REVIEW_REQUIRED"


def calculate_with_break_evidence(normalized_path: str | Path,
                                  config_path: str | Path,
                                  output_dir: str | Path) -> int:
    """Use existing CLI unless an explicitly normalized access source exists."""
    from importlib import import_module

    try:
        source = _read_json(normalized_path)
        if "access_events" not in source.get("sources", {}):
            old_cli = import_module("bhandara.worktime-calculator.run")
            return old_cli.main([
                "calculate", "--normalized", str(normalized_path),
                "--config", str(config_path), "--output-dir", str(output_dir),
            ])
        config = _read_json(config_path)
        review_path = Path(normalized_path).resolve().with_name("review-report.json")
        review = _read_json(review_path) if review_path.is_file() else None
        result = calculate_worktime_batch(source, config, source_review=review)
        break_analysis = analyze_access_breaks(source, config, result)
        _augment_reviews(result, break_analysis)
        original = write_worktime_outputs(output_dir, result)
        write_break_review(output_dir, break_analysis)
    except (WorktimeBatchError, WorktimeReportError, BreakReviewError,
            OSError, ValueError, TypeError, KeyError) as exc:
        print(f"WORKTIME_BREAK_INVALID: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print("BREAK_COMPLIANCE: " + break_analysis["status"] + " (not approved)")
    print("BREAK_COMPLIANCE_ARTIFACT: " + str(Path(output_dir) / "break-compliance.json"))
    for key, path in original.items():
        print(f"{key}: {path}")
    return 0 if result["status"] == "CALCULATED_UNCLOSED" else 2
