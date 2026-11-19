"""P1-1: Review-only bridge from Worktime's factual XLSX into Payroll.

Neither deltas nor actual-minus-scheduled minutes are payable overtime.
This bridge never determines approval, wages, leave eligibility or net pay.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import BadZipFile
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from typing import Any, Iterable, Mapping

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.contract_period import select_contracts_for_period
from bhandara.payroll.input_excel import PayrollInputs
from bhandara.payroll.review_adapter import build_payroll_review_register
from bhandara.worktime.output import OUTPUT_FIELDS
from bhandara.worktime.output_excel import read_worktime_xlsx


class WorktimePayrollBridgeError(ValueError):
    """Worktime evidence cannot safely be attached to a Payroll review period."""


def _period_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise WorktimePayrollBridgeError(f"{field}: YYYY-MM-DD string required")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise WorktimePayrollBridgeError(f"{field}: invalid date") from exc
    if parsed.isoformat() != value:
        raise WorktimePayrollBridgeError(f"{field}: canonical YYYY-MM-DD required")
    return parsed


def _minute(value: Any, field: str, *, signed: bool) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise WorktimePayrollBridgeError(f"{field}: numeric minutes or null required")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise WorktimePayrollBridgeError(f"{field}: invalid number") from exc
    if not number.is_finite():
        raise WorktimePayrollBridgeError(f"{field}: finite number required")
    if not signed and (number < 0 or number != number.to_integral_value()):
        raise WorktimePayrollBridgeError(f"{field}: nonnegative integer or null required")
    return number


def _text(value: Any, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise WorktimePayrollBridgeError(f"{field}: text required")
    value = value.strip()
    if not value:
        if optional:
            return None
        raise WorktimePayrollBridgeError(f"{field}: nonempty text required")
    if value[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        raise WorktimePayrollBridgeError(f"{field}: unsafe cell text")
    return value


def review_worktime_facts(
    rows: Iterable[Mapping[str, Any]],
    *,
    employee_ids: Iterable[str],
    period_from: str,
    period_to: str,
) -> dict[str, Any]:
    """Validate Worktime row facts and flag potential follow-up only.

    No payroll-grade work interval, effective policy, verified leave interval
    or employer approval is available from the ten-column source.
    """
    start = _period_date(period_from, "period_from")
    end = _period_date(period_to, "period_to")
    if start > end:
        raise WorktimePayrollBridgeError("period_from: after period_to")
    ids = tuple(employee_ids)
    if not ids or any(not isinstance(i, str) or not i.strip() for i in ids):
        raise WorktimePayrollBridgeError("employee_ids: explicit text IDs required")
    if len(set(ids)) != len(ids):
        raise WorktimePayrollBridgeError("employee_ids: duplicate ID")

    permitted = set(ids)
    seen: set[tuple[str, str]] = set()
    reviewed: list[dict[str, Any]] = []
    covered: set[str] = set()
    for source in rows:
        if not isinstance(source, Mapping) or set(source) != set(OUTPUT_FIELDS):
            raise WorktimePayrollBridgeError("WORKTIME: exact ten-column fact row required")
        employee = _text(source["employee_id"], "employee_id")
        work_day = _period_date(source["work_date"], "work_date")
        if employee not in permitted:
            raise WorktimePayrollBridgeError("WORKTIME: employee outside selected Payroll contracts")
        if not start <= work_day <= end:
            raise WorktimePayrollBridgeError("WORKTIME: date outside selected Payroll calculation period")
        key = (employee, work_day.isoformat())
        if key in seen:
            raise WorktimePayrollBridgeError("WORKTIME: duplicate employee/date")
        seen.add(key)
        covered.add(employee)

        _text(source["schedule_id"], "schedule_id", optional=True)
        _text(source["attendance_type"], "attendance_type", optional=True)
        leave_type = _text(source["leave_type"], "leave_type", optional=True)
        leave_id = _text(source["leave_request_id"], "leave_request_id", optional=True)
        scheduled = _minute(source["scheduled_min"], "scheduled_min", signed=False)
        actual = _minute(source["actual_min"], "actual_min", signed=False)
        early = _minute(source["clock_in_delta_min"], "clock_in_delta_min", signed=True)
        late = _minute(source["clock_out_delta_min"], "clock_out_delta_min", signed=True)

        hints: list[str] = []
        if scheduled is None:
            hints.append("SCHEDULE_UNVERIFIED")
        if actual is None:
            hints.append("ACTUAL_UNVERIFIED")
        if scheduled is not None and actual is not None:
            if scheduled == 0 and actual > 0:
                hints.append("WORK_ON_SCHEDULED_OFF")
            elif actual > scheduled:
                hints.append("ACTUAL_ABOVE_SCHEDULED")
        if early is not None and early > 0:
            hints.append("CLOCK_IN_EARLIER")
        if late is not None and late > 0:
            hints.append("CLOCK_OUT_LATER")
        if early is not None and early < 0:
            hints.append("CLOCK_IN_LATER")
        if late is not None and late < 0:
            hints.append("CLOCK_OUT_EARLIER")
        if leave_type is not None or leave_id is not None:
            hints.append("LEAVE_SOURCE_REVIEW")
        if actual == 0 and ((early is not None and early > 0) or (late is not None and late > 0)):
            hints.append("VERIFY_CLOCK_VS_WORK_MINUTES")

        reviewed.append({
            "employee_id": employee,
            "work_date": work_day.isoformat(),
            "review_codes": hints,
            "payment_decision": "NOT_ASSESSED",
        })

    reviewed.sort(key=lambda r: (r["employee_id"], r["work_date"]))
    return {
        "schema_version": "0.1",
        "contract": "WORKTIME_FACT_REVIEW_NOT_PAYROLL_APPROVAL",
        "period_from": period_from,
        "period_to": period_to,
        "rows": reviewed,
        "employees_without_worktime_rows": sorted(permitted - covered),
        "payable_minutes_calculated": False,
        "earnings_complete": False,
        "approval_state": "NOT_APPROVED",
    }


def _verify_worktime_workbook(path: Path) -> None:
    """Check exact one-sheet structure and text IDs before upstream coercion."""
    try:
        book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
        try:
            if book.sheetnames != ["WORKTIME"]:
                raise WorktimePayrollBridgeError(
                    "WORKTIME: expected exactly one sheet named WORKTIME"
                )
            for row in book["WORKTIME"].iter_rows(min_row=2, min_col=1, max_col=1):
                value = row[0].value
                if value is not None and (not isinstance(value, str) or not value.strip()):
                    raise WorktimePayrollBridgeError(
                        "WORKTIME: employee_id must be Excel text (leading zeros preserved)"
                    )
        finally:
            book.close()
    except WorktimePayrollBridgeError:
        raise
    except (OSError, ValueError, BadZipFile, InvalidFileException) as exc:
        raise WorktimePayrollBridgeError("WORKTIME: cannot inspect source workbook") from exc


def build_payroll_worktime_review(
    inputs: PayrollInputs,
    worktime_xlsx: str | Path,
    *,
    period_from: str,
    period_to: str,
) -> dict[str, Any]:
    """Compose a partial Payroll register + factual Worktime review, no extra XLSX.

    The requested period and selected workers must match both components.
    Source fingerprint checks detect a workbook mutation during inspection.
    """
    register = build_payroll_review_register(
        inputs, period_from=period_from, period_to=period_to,
    )
    contracts = select_contracts_for_period(
        inputs.for_role("contracts"), period_from=period_from, period_to=period_to,
    )
    path = Path(worktime_xlsx)
    if path.name != "worktime-result.xlsx":
        raise WorktimePayrollBridgeError("WORKTIME: fixed source filename worktime-result.xlsx required")
    if not path.is_file():
        raise WorktimePayrollBridgeError("WORKTIME: source file missing")
    before = sha256_file(path)
    _verify_worktime_workbook(path)
    rows = read_worktime_xlsx(path)
    if before != sha256_file(path):
        raise WorktimePayrollBridgeError("WORKTIME: source modified during read")
    review = review_worktime_facts(
        rows, employee_ids=(r["employee_id"] for r in contracts),
        period_from=period_from, period_to=period_to,
    )
    return {
        "payroll_register": register,
        "worktime_review": review,
        "status": "PARTIAL_REVIEW_ONLY",
        "approval_state": "NOT_APPROVED",
    }
