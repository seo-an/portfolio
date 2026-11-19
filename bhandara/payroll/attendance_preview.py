"""P1-5b: connect an authenticated-elsewhere adjustment plan to one Payroll view.

Source agreement is NOT source authenticity or legal wage determination.
No overtime compensation is combined; approved intervals, if supplied, are
only checked for conflicts with the declared leave intervals.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.attendance_reconciliation import reconcile_attendance_adjustments
from bhandara.payroll.input_excel import PayrollInputs
from bhandara.payroll.segmented_settlement import build_segmented_settlement_preview
from bhandara.payroll.settlement_coverage import validate_settlement_coverage
from bhandara.payroll.worktime_bridge import (
    WorktimePayrollBridgeError, _verify_worktime_workbook, review_worktime_facts,
)
from bhandara.worktime.output_excel import read_worktime_xlsx


def build_attendance_adjusted_preview(
    inputs: PayrollInputs,
    worktime_xlsx: str | Path,
    *,
    settlement_plan: Mapping[str, Any],
    attendance_plan: Mapping[str, Any],
    period_from: str,
    period_to: str,
    approved_overtime_segments: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build partial register from confirmed *listed* wage adjustment claims.

    This does not read or write an eighth Excel input, modify Worktime,
    infer a base reduction from working minutes, authenticate ledger records,
    or compute bonuses/overtime beyond P1-5a's original candidate scope.
    """
    path = Path(worktime_xlsx)
    if path.name != "worktime-result.xlsx" or not path.is_file():
        raise WorktimePayrollBridgeError("WORKTIME: worktime-result.xlsx is required")
    coverage = validate_settlement_coverage(
        inputs.for_role("contracts"), plan=settlement_plan,
        period_from=period_from, period_to=period_to,
    )
    source_sha = sha256_file(path)
    _verify_worktime_workbook(path)
    worktime_rows = read_worktime_xlsx(path)
    if sha256_file(path) != source_sha:
        raise WorktimePayrollBridgeError("WORKTIME: workbook modified during read")
    attendance = reconcile_attendance_adjustments(
        coverage, worktime_rows,
        attendance_plan=attendance_plan,
        worktime_sha256=source_sha,
        approved_overtime_segments=approved_overtime_segments,
    )
    worktime_review = review_worktime_facts(
        worktime_rows, employee_ids=coverage["segments_by_employee"],
        period_from=period_from, period_to=period_to,
    )
    preview = build_segmented_settlement_preview(
        inputs, settlement_plan=settlement_plan,
        period_from=period_from, period_to=period_to,
        base_reductions=attendance["base_reductions_by_employee"],
    )
    if sha256_file(path) != source_sha:
        raise WorktimePayrollBridgeError("WORKTIME: workbook modified during preview")
    review = preview["settlement_review"]
    review["paid_leave_verification"] = "LISTED_EVENTS_MATCH_WORKTIME_NOT_AUTHENTICATED"
    review["worktime_integration"] = "FACTS_REVIEWED_NOT_PAYROLL_APPROVAL"
    review["overtime_reconciliation"] = attendance["overtime_overlap_review"]
    preview["attendance_review"] = attendance
    preview["worktime_review"] = worktime_review
    preview["status"] = "PARTIAL_REVIEW_ONLY"
    preview["approval_state"] = "NOT_APPROVED"
    return preview
