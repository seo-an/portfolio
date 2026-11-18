"""Standalone, explicitly invoked PTO entitlement Excel boundary.

This is NOT the legacy PTO runner, a general Tool dispatcher or Gearbox hook.
All business arithmetic stays inside entitlement; this file owns workbook I/O.
"""
from __future__ import annotations

import importlib
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook

from bhandara.common.utils.hashing import sha256_file

_entitlement = importlib.import_module("bhandara.paid-time-off.entitlement.calculation")

SHARED_INPUT_ROOT = Path(__file__).resolve().parents[1] / "data" / "input"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "output"
EMPLOYEE_RELATIVE = Path("common") / "employee.xlsx"
ATTENDANCE_RELATIVE = Path("paid-time-off") / "attendance-result.xlsx"
PRORATION_RELATIVE = Path("paid-time-off") / "proration.xlsx"

EMPLOYEE_COLUMNS = ("employee_id", "hire_date", "termination_date")
ATTENDANCE_COLUMNS = ("employee_id", "period_start", "period_end",
                      "check_type", "attendance_flag")
PRORATION_COLUMNS = ("employee_id", "period_start", "period_end",
                     "method", "numerator", "denominator")


class EntitlementInputError(ValueError):
    pass


def _cell(value: Any, *, column: str) -> Any:
    if isinstance(value, str):
        value = value.strip()
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        # Source formulas are never evaluated or treated as recorded facts.
        raise EntitlementInputError(f"{column}: 수식·위험한 문자열은 허용하지 않습니다")
    return value


def _read_rows(path: Path, sheet_name: str,
               required: tuple[str, ...],
               *, allow_blank: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    if not path.is_file() or path.suffix.lower() not in (".xlsx", ".xlsm"):
        raise EntitlementInputError(f"필수 Excel 파일이 없습니다: {path.name}")
    try:
        book = load_workbook(path, read_only=True, data_only=False)
    except Exception as exc:
        raise EntitlementInputError(f"Excel 열기 실패: {path.name}") from exc
    try:
        if sheet_name not in book.sheetnames:
            raise EntitlementInputError(f"{path.name}: '{sheet_name}' 시트가 없습니다")
        sheet = book[sheet_name]
        iterator = sheet.iter_rows()
        first = next(iterator, None)
        if first is None:
            raise EntitlementInputError(f"{sheet_name}: 헤더 행이 없습니다")
        headers = [cell.value for cell in first]
        if len([x for x in headers if x in required]) != len(required):
            raise EntitlementInputError(f"{sheet_name}: 필수 헤더가 없습니다")
        if len(set(h for h in headers if h in required)) != len(required):
            raise EntitlementInputError(f"{sheet_name}: 중복 헤더가 있습니다")
        positions = {name: headers.index(name) for name in required}
        # Preserve optional employee columns from a shared roster when present.
        optional = ("work_system", "termination_date", "base_days")
        for name in optional:
            if name in headers and name not in positions:
                positions[name] = headers.index(name)
        results = []
        for row_number, cells in enumerate(iterator, start=2):
            if not any(cell.value is not None and cell.value != "" for cell in cells):
                continue
            for name, index in positions.items():
                if index < len(cells) and cells[index].data_type == "f":
                    raise EntitlementInputError(
                        f"{sheet_name} {row_number}행 {name}: Excel 수식 입력 불가"
                    )
            values = {name: _cell(cells[i].value if i < len(cells) else None,
                                  column=name) for name, i in positions.items()}
            for name in required:
                if name in allow_blank:
                    continue
                if values[name] is None or values[name] == "":
                    raise EntitlementInputError(
                        f"{sheet_name} {row_number}행: {name} 값이 없습니다"
                    )
            results.append(values)
        return results
    finally:
        book.close()


def read_employee_roster(path: Path) -> list[dict[str, Any]]:
    """One common employee.xlsx; separate 재직자 and 퇴사자 sheets."""
    output = []
    seen: set[str] = set()
    for name in ("재직자", "퇴사자"):
        for row in _read_rows(path, name, ("employee_id", "hire_date")):
            identifier = str(row["employee_id"]).strip()
            if identifier in seen:
                raise EntitlementInputError(f"직원 ID 중복: {identifier}")
            seen.add(identifier)
            record = {
                "employee_id": identifier,
                "hire_date": _entitlement.strict_date(row["hire_date"], "hire_date"),
                "termination_date": (
                    _entitlement.strict_date(row["termination_date"], "termination_date")
                    if row.get("termination_date") else None
                ),
            }
            if name == "퇴사자" and record["termination_date"] is None:
                raise EntitlementInputError(f"{identifier}: 퇴사자 시트에 퇴사일이 없습니다")
            output.append(record)
    return output


def _read_attendance(path: Path) -> list[dict[str, Any]]:
    rows = _read_rows(path, "근태결과", ATTENDANCE_COLUMNS,
                      allow_blank=("attendance_flag",))
    for row in rows:
        if row["attendance_flag"] is None or row["attendance_flag"] == "":
            row["attendance_flag"] = "판정 안됨"
    return rows


def _read_proration(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data: dict[str, dict[str, Any]] = {}
    for row in _read_rows(path, "비례자료", PRORATION_COLUMNS):
        employee_id = str(row["employee_id"])
        if employee_id in data:
            raise EntitlementInputError(f"{employee_id}: 비례자료가 중복되었습니다")
        for name in ("numerator", "denominator"):
            value = row[name]
            if type(value) is int:
                continue
            if type(value) is float and value.is_integer():
                row[name] = int(value)
                continue
            raise EntitlementInputError(f"{employee_id}: {name}는 정수여야 합니다")
        data[employee_id] = row
    return data


def _safe_text(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _append_table(sheet, headers: tuple[str, ...], rows: list[dict], keys: tuple[str, ...]):
    sheet.append(headers)
    for row in rows:
        sheet.append([_safe_text(row.get(key)) for key in keys])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


def make_entitlement_workbook(
    summaries: list[dict], details: list[dict], metadata: dict[str, Any],
) -> bytes:
    """Workbook contains two parallel result sheets and one final policy sheet."""
    book = Workbook()
    try:
        summary = book.active
        summary.title = "발생요약"
        _append_table(
            summary,
            ("employee_id", "basis", "계산결과", "발생연차", "상태"),
            summaries,
            ("employee_id", "basis", "calculation_result", "granted_days", "status"),
        )
        detail = book.create_sheet("발생상세")
        _append_table(
            detail,
            ("employee_id", "basis", "발생구분", "period_start", "period_end",
             "grant_date", "계산결과", "상태", "사유"),
            details,
            ("employee_id", "basis", "grant_type", "period_start", "period_end",
             "grant_date", "calculation_result", "status", "reason"),
        )
        policy = book.create_sheet("정책정보")
        _append_table(
            policy, ("항목", "값"),
            [{"name": key, "value": value} for key, value in metadata.items()],
            ("name", "value"),
        )
        stream = BytesIO()
        book.save(stream)
        return stream.getvalue()
    finally:
        book.close()


def run_entitlement(
    *,
    as_of_date: date,
    basis: str,
    policy_id: str,
    run_id: str,
    input_root: Path = SHARED_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    employee_file: Path | None = None,
    attendance_file: Path | None = None,
    proration_file: Path | None = None,
    rounding_digits: int = 1,
    fiscal_year_start: str = "01-01",
    proration_method: str = "소정근로일 기준",
) -> dict[str, Any]:
    """Explicit local invocation. Never falls back from invalid explicit paths."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", run_id):
        raise EntitlementInputError("run_id는 영문·숫자·하이픈·밑줄만 허용합니다")
    if not isinstance(policy_id, str) or not policy_id.strip():
        raise EntitlementInputError("policy_id가 필요합니다")
    input_root = Path(input_root)
    employee_path = Path(employee_file) if employee_file is not None else input_root / EMPLOYEE_RELATIVE
    attendance_path = Path(attendance_file) if attendance_file is not None else input_root / ATTENDANCE_RELATIVE
    proration_path = Path(proration_file) if proration_file is not None else input_root / PRORATION_RELATIVE
    roster = read_employee_roster(employee_path)
    attendance = _read_attendance(attendance_path)
    index = _entitlement.build_flag_index(attendance)
    if basis == "회계연도 기준" and proration_file is not None and not proration_path.is_file():
        raise EntitlementInputError("명시적으로 전달한 비례자료 파일이 없습니다")
    proration = _read_proration(proration_path) if basis == "회계연도 기준" else {}
    summaries, details = [], []
    for person in roster:
        summary, events = _entitlement.calculate_employee(
            **person, as_of_date=as_of_date, basis=basis, flag_index=index,
            rounding_digits=rounding_digits, fiscal_year_start=fiscal_year_start,
            proration_method=proration_method,
            proration_facts=proration.get(person["employee_id"]),
        )
        summaries.append(summary)
        details.extend(events)
    metadata = {
        "정책 ID": policy_id,
        "산정 기준일": _entitlement.strict_date(as_of_date, "as_of_date").isoformat(),
        "산정 기간 시작일": date(_entitlement.strict_date(as_of_date, "as_of_date").year, 1, 1).isoformat(),
        "산정 기간 종료일": _entitlement.strict_date(as_of_date, "as_of_date").isoformat(),
        "산정 기준": basis,
        "비례연차 방식": proration_method,
        "최종 반올림 자릿수": rounding_digits,
        "중간 계산": "반올림 없음, 무한소수 기록 7자리 절사",
        "직원정보 파일": employee_path.name,
        "직원정보 SHA256": sha256_file(employee_path),
        "근태 결과 파일": attendance_path.name,
        "근태 결과 SHA256": sha256_file(attendance_path),
        "비례자료 파일": proration_path.name if proration_path.is_file() else "없음",
        "비례자료 SHA256": sha256_file(proration_path) if proration_path.is_file() else "없음",
        "사용·이월·만료 포함": "아니요",
        "확정·승인": "아니요",
    }
    payload = make_entitlement_workbook(summaries, details, metadata)
    destination = Path(output_root) / run_id / "entitlement-result.xlsx"
    if destination.exists():
        raise EntitlementInputError("동일 run_id 결과가 이미 있습니다. 덮어쓰지 않습니다")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create to prevent accidental overwrite across concurrent runs.
    with destination.open("xb") as stream:
        stream.write(payload)
    return {"path": str(destination.resolve()), "summaries": summaries,
            "details": details, "policy": metadata}


# Separate, standalone Excel boundary for the deduction-quantity Module.
# The combined PTO usage ledger and closing reports are NOT created here.
_deduction = importlib.import_module(
    "bhandara.paid-time-off.deduction-quantity.calculation")
APPROVED_LEAVE_RELATIVE = Path("paid-time-off") / "approved-leave.xlsx"
APPROVED_LEAVE_COLUMNS = _deduction.INPUT_COLUMNS


def _read_approved_leave(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Read approved rows without aborting the workbook for row-level errors.

    A missing column is propagated as blank values to each source row. Duplicate
    *headers*, or an unreadable workbook, are structural errors and cannot be
    interpreted unambiguously.
    """
    if not path.is_file() or path.suffix.lower() not in (".xlsx", ".xlsm"):
        raise EntitlementInputError(f"승인휴가 Excel 파일이 없습니다: {path.name}")
    try:
        book = load_workbook(path, read_only=True, data_only=False)
    except Exception as exc:
        raise EntitlementInputError(f"승인휴가 Excel 열기 실패: {path.name}") from exc
    try:
        if "승인휴가" not in book.sheetnames:
            raise EntitlementInputError("approved-leave.xlsx: '승인휴가' 시트가 없습니다")
        iterator = book["승인휴가"].iter_rows()
        first = next(iterator, None)
        if first is None:
            raise EntitlementInputError("승인휴가: 헤더 행이 없습니다")
        headers = [
            cell.value.strip() if isinstance(cell.value, str) else cell.value
            for cell in first
        ]
        for name in APPROVED_LEAVE_COLUMNS:
            if headers.count(name) > 1:
                raise EntitlementInputError(f"승인휴가: {name} 헤더가 중복됐습니다")
        positions = {
            name: headers.index(name)
            for name in APPROVED_LEAVE_COLUMNS if name in headers
        }
        missing = [name for name in APPROVED_LEAVE_COLUMNS if name not in headers]
        data = []
        for row_number, cells in enumerate(iterator, start=2):
            if not any(c.value is not None and c.value != "" for c in cells):
                continue
            values = {
                name: cells[index].value if index < len(cells) else None
                for name, index in positions.items()
            }
            errors = [
                f"{name}: Excel 수식 입력 불가"
                for name, index in positions.items()
                if index < len(cells) and cells[index].data_type == "f"
            ]
            values.update({
                "_excel_row": row_number,
                "_source_errors": errors,
            })
            data.append(values)
        return data, missing
    finally:
        book.close()


def make_deduction_workbook(
    summaries: list[dict], details: list[dict], metadata: dict[str, Any],
) -> bytes:
    """Deduction-only workbook; no grant balance, allocation, or closing."""
    book = Workbook()
    try:
        summary = book.active
        summary.title = "차감요약"
        _append_table(
            summary,
            ("employee_id", "차감일수", "계산 건수", "제외 건수", "상태"),
            summaries,
            ("employee_id", "deduction_days", "valid_rows", "excluded_rows",
             "status"),
        )
        detail = book.create_sheet("차감상세")
        _append_table(
            detail,
            ("원본행", "request_id", "employee_id", "leave_date",
             "leave_type", "사용시간", "차감일수", "상태", "사유"),
            details,
            ("excel_row", "request_id", "employee_id", "leave_date",
             "leave_type", "duration_hours", "deduction_days", "status",
             "reason"),
        )
        policy = book.create_sheet("정책정보")
        _append_table(
            policy, ("항목", "값"),
            [{"name": key, "value": value} for key, value in metadata.items()],
            ("name", "value"),
        )
        stream = BytesIO()
        book.save(stream)
        return stream.getvalue()
    finally:
        book.close()


def run_deduction_quantity(
    *,
    policy_id: str,
    run_id: str,
    input_root: Path = SHARED_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    approved_file: Path | None = None,
    standard_daily_hours: Any = 8,
) -> dict[str, Any]:
    """Independent approved-leave quantity calculation; not ledger posting.

    Every supplied row is externally approved (including future leave).
    No implicit date filtering, leave-grant selection, or approval decisions.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", run_id):
        raise EntitlementInputError("run_id는 영문·숫자·하이픈·밑줄만 허용합니다")
    if not isinstance(policy_id, str) or not policy_id.strip():
        raise EntitlementInputError("policy_id가 필요합니다")
    path = (Path(approved_file) if approved_file is not None
            else Path(input_root) / APPROVED_LEAVE_RELATIVE)
    rows, missing_headers = _read_approved_leave(path)
    calculated = _deduction.calculate_approved_rows(
        rows, standard_daily_hours=standard_daily_hours)
    metadata = {
        "정책 ID": policy_id,
        "입력 파일": path.name,
        "입력 SHA256": sha256_file(path),
        "입력 시트": "승인휴가",
        "1일 기준시간": calculated["standard_daily_hours"],
        "기준시간 출처": ("기본값 8시간" if standard_daily_hours == 8
                     else "호출 시 지정값"),
        "대상": "외부 승인 완료 건 전체(미래 사용일 포함)",
        "누락 헤더": ", ".join(missing_headers) if missing_headers else "없음",
        "계산 건수": calculated["calculated_rows"],
        "제외 건수": calculated["excluded_rows"],
        "정밀도": "중간 반올림 없음; 무한소수만 표시 7자리 절사",
        "발생·잔여·만료·이월·마감 포함": "아니요",
        "승인·취소 판정": "외부 시스템",
    }
    payload = make_deduction_workbook(
        calculated["summaries"], calculated["details"], metadata)
    destination = Path(output_root) / run_id / "deduction-quantity-result.xlsx"
    if destination.exists():
        raise EntitlementInputError("동일 run_id 결과가 이미 있습니다. 덮어쓰지 않습니다")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(payload)
    return {
        "path": str(destination.resolve()),
        "summaries": calculated["summaries"],
        "details": calculated["details"],
        "policy": metadata,
    }
