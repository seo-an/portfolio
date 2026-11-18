"""Optional handoff from the vendor-independent access-events.xlsx v0.2.

The candidate worksheet is unconfirmed evidence only. Unmapped/rejected raw
vendor records remain visible and prevent a misleading clean detection run.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from bhandara.worktime.access_source import read_access_events_xlsx
from .calculation import detect_attendance


def detect_attendance_xlsx(
    schedule_rows: Iterable[Mapping[str, Any]],
    attendance_rows: Iterable[Mapping[str, Any]],
    workbook_path: str | Path,
    *,
    period_from: str,
    period_to: str,
    verified_work_intervals: Iterable[Mapping[str, Any]] = (),
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Read the *common* workbook; never consume raw vendor-specific columns."""
    normalized = read_access_events_xlsx(workbook_path)
    report = detect_attendance(
        schedule_rows, attendance_rows,
        period_from=period_from, period_to=period_to,
        candidate_rows=normalized["attendance_candidates"],
        verified_work_intervals=verified_work_intervals,
        policy=policy,
    )
    actionable = [
        finding for finding in normalized["source_reviews"]
        if finding["status"] != "EXCLUDED"
    ]
    for finding in actionable:
        report["source_issues"].append({
            "source": "access_normalization",
            "code": "NORMALIZATION_" + finding["status"],
            "employee_id": "",
            "work_date": "",
            "source_ref": finding["source_ref"],
            "row_number": finding["source_row_number"],
            "detail": finding["issue_codes"],
        })
    if actionable:
        report["status"] = "REVIEW_REQUIRED"
    report["normalized_source"] = {
        "schema_version": normalized["schema_version"],
        "source_vendor": normalized["metadata"]["source_vendor"],
        "source_sha256": normalized["metadata"]["source_sha256"],
        "unresolved_count": len(actionable),
        "excluded_count": len(normalized["source_reviews"]) - len(actionable),
    }
    return report
