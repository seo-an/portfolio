"""Explicit standalone Excel adapter for the paid-time-off Closing Module.

Reads finished usage/allocation results; never recalculates entitlement,
deduction, expiry or decides statutory use-promotion.
"""
from __future__ import annotations

import importlib
import re
from datetime import date
from decimal import Decimal
from fractions import Fraction
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from bhandara.common.utils.hashing import sha256_file

_closing = importlib.import_module("bhandara.paid-time-off.closing.calculation")
_usage = importlib.import_module("bhandara.paid-time-off.runner_usage")
_expiry = importlib.import_module("bhandara.paid-time-off.expiry-carryover.calculation")

DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "output"


class ClosingInputError(ValueError):
    pass


def _month_and_quarter(closing_id: str) -> tuple[date, int]:
    cutoff = _expiry.closing_boundary(closing_id)
    return cutoff, cutoff.month // 3


def _roster(file: Path) -> dict[str, str]:
    """Read the same existing common/employee.xlsx 재직자·퇴사자 sheets."""
    mapping = {}
    for name in ("재직자", "퇴사자"):
        try:
            rows = _usage.read_rows(file, name, ("employee_id", "name"))
        except _usage.UsageInputError as exc:
            if "필수 열 누락" not in str(exc):
                raise
            rows = _usage.read_rows(file, name, ("employee_id",))
        for row in rows:
            identifier = str(row.get("employee_id") or "").strip()
            if not identifier or identifier in mapping:
                raise ClosingInputError(f"직원명부 직원 ID 누락/중복: {identifier}")
            mapping[identifier] = str(row.get("name") or "").strip()
    return mapping


def _promotion(file: Path | None) -> dict[str, bool] | None:
    if file is None:
        return None
    rows = _usage.read_rows(file, "검토결과", ("employee_id", "review_required"))
    results = {}
    for row in rows:
        eid = str(row.get("employee_id") or "").strip()
        flag = row.get("review_required")
        if not eid or eid in results:
            raise ClosingInputError("사용촉진 검토자료의 직원 ID 누락·중복")
        if flag in (True, 1, "Y", "TRUE"):
            results[eid] = True
        elif flag in (False, 0, "N", "FALSE"):
            results[eid] = False
        else:
            raise ClosingInputError(f"{eid}: review_required는 Y/N입니다")
    return results


def _usage_inputs(file: Path, closing_id: str) -> tuple[dict, dict]:
    policy = _usage._policy(file)
    end = _expiry.closing_boundary(closing_id)
    if policy.get("마감 판정 ID") != closing_id:
        raise ClosingInputError("사용내역 Excel의 Closing ID가 다릅니다")
    if policy.get("실행 기준일") != end.isoformat():
        raise ClosingInputError("사용내역 산정 기준일과 Closing 마감일이 다릅니다")
    sources = _usage.read_rows(file, "_발생자료", (
        "grant_id", "employee_id", "leave_type", "grant_date",
        "valid_from", "expires_on", "source_ref", "source_type",
        "available_days", "remaining_days",
    ))
    details = _usage.read_rows(file, "사용상세", (
        "employee_id", "leave_type", "grant_id", "request_id", "leave_date",
        "차감일수", "처리구분",
    ))
    expiry = _usage.read_rows(file, "만료이월", (
        "employee_id", "expires_on", "expiry_days", "status",
    ))
    summary = _usage.read_rows(file, "사용요약", (
        "employee_id", "잔여일수",
    ))
    issues = _usage.read_rows(file, "검토사항", (
        "employee_id", "source", "reason",
    ), optional_sheet=True)
    return policy, {
        "source_grants": sources, "usage_details": details,
        "expiry_rows": expiry, "usage_summaries": summary,
        "input_issues": issues,
    }


def _previous(
    path: Path | None, closing_id: str, carry_ref: str | None,
) -> tuple[list[dict], str | None]:
    _, quarter = _month_and_quarter(closing_id)
    previous = f"Closing-{quarter - 1}.4-{closing_id[-4:]}" if quarter > 1 else None
    if carry_ref and re.fullmatch(r"Closing-[1-4]\.4-[0-9]{4}", carry_ref):
        carry_date = _expiry.closing_boundary(carry_ref)
        current_date = _expiry.closing_boundary(closing_id)
        if carry_date.year == current_date.year and carry_ref != previous:
            raise ClosingInputError("직전 분기 이외 Closing 인계값: 분기 누락")
        if carry_date.year == current_date.year and path is None:
            raise ClosingInputError("같은 해 이전 분기 Closing 사용 시 그 마감보고서가 필요합니다")
    if path is None:
        return [], None
    if previous is None:
        raise ClosingInputError("1분기에는 같은 해 이전 분기 Closing이 없습니다")
    policy = _usage._policy(path)
    if policy.get("참조 ID") != previous or policy.get("확정여부") != "확정":
        raise ClosingInputError("직전 분기 Closing ID·확정상태 불일치")
    if carry_ref != previous:
        raise ClosingInputError("사용내역의 기초 Closing과 전분기 Closing 파일이 다릅니다")
    headers = (
        "employee_id", "발생연차일수", "기초이월잔여일수",
        "대휴발생일수", "미사용만료일수", *_closing.MONTHS,
        "누적사용일수", "마감잔여일수",
    )
    return _usage.read_rows(path, "_수량정본", headers), previous


def _display(value: Any):
    if value is None:
        return None
    if isinstance(value, Fraction):
        # Human Excel display only. Exact ratios stay on hidden handoff sheets.
        import importlib
        precision = importlib.import_module(
            "bhandara.paid-time-off.allocation"
        )
        return float(Decimal(precision.quantity_text(value)))
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _write_sheet(book, title: str, columns: tuple[str, ...],
                 rows: list[Mapping], *, hidden=False, exact=False):
    sheet = book.create_sheet(title)
    sheet.append(columns)
    for item in rows:
        sheet.append([
            (str(item.get(key)) if isinstance(item.get(key), Fraction) else
             _display(item.get(key)) if not exact else item.get(key))
            for key in columns
        ])
    sheet.freeze_panes = "C2" if title == "마감보고" else "A2"
    sheet.auto_filter.ref = sheet.dimensions
    if hidden:
        sheet.sheet_state = "hidden"
    return sheet


def _style_report(sheet, count: int):
    colors = ("203354", "175E63", "35617F", "263E5A")
    for col in range(1, 23):
        cell = sheet.cell(1, col)
        group = 0 if col <= 2 else 1 if col <= 7 else 2 if col <= 19 else 3
        cell.fill = PatternFill("solid", fgColor=colors[group])
        cell.font = Font(name="맑은 고딕", bold=True, color="FFFFFF", size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)
        width = (16 if col in (1, 2) else 19 if col in (3, 4, 5, 6, 7, 20, 21)
                 else 23 if col == 22 else 9)
        sheet.column_dimensions[get_column_letter(col)].width = width
    sheet.row_dimensions[1].height = 34
    for n in range(2, count + 2):
        sheet.row_dimensions[n].height = 23
        for col in range(1, 23):
            cell = sheet.cell(n, col)
            cell.alignment = Alignment(
                horizontal="center" if col in (1, 2, 22) else "right",
                vertical="center"
            )
            cell.font = Font(name="맑은 고딕", size=10,
                             color="263546")
            if n % 2 == 0:
                cell.fill = PatternFill("solid", fgColor="F2F5F8")
            if 3 <= col <= 21:
                # Actual stored value is negative. Only visual style uses (3).
                cell.number_format = '#,##0.####;[Red](#,##0.####);0'
        status = sheet.cell(n, 22)
        if status.value == "자료확인 필요":
            status.fill = PatternFill("solid", fgColor="FFF1CF")
        elif status.value == "초과사용":
            status.fill = PatternFill("solid", fgColor="FCE2DF")
        elif status.value == "사용촉진 검토":
            status.fill = PatternFill("solid", fgColor="E6F0FF")


def make_closing_workbook(result: Mapping, metadata: Mapping) -> bytes:
    book = Workbook()
    try:
        book.remove(book.active)
        report = _write_sheet(book, "마감보고",
                              _closing.REPORT_COLUMNS, result["report"])
        _style_report(report, len(result["report"]))
        # This sheet is for downstream exact values, not a second HR ledger.
        exact_fields = (
            "employee_id", "발생연차일수", "기초이월잔여일수",
            "대휴발생일수", "미사용만료일수", *_closing.MONTHS,
            "누적사용일수", "마감잔여일수",
        )
        _write_sheet(book, "_수량정본", exact_fields, result["report"],
                     hidden=True, exact=True)
        _write_sheet(book, "인계자료", (
            "grant_id", "employee_id", "leave_type", "grant_date",
            "available_days", "valid_from", "expires_on", "source_ref",
        ), result["carry_rows"], hidden=True, exact=True)
        _write_sheet(book, "미상계부족", (
            "request_id", "employee_id", "leave_type", "leave_date",
            "shortage_days",
        ), result["shortage_rows"], hidden=True, exact=True)
        if result["issues"]:
            _write_sheet(book, "검토사항", ("employee_id", "source", "reason"),
                         result["issues"])
        _write_sheet(book, "정책정보", ("항목", "값"),
                     [{"항목": key, "값": value}
                      for key, value in metadata.items()])
        stream = BytesIO()
        book.save(stream)
        return stream.getvalue()
    finally:
        book.close()


def run_closing(
    *, closing_id: str, policy_id: str, run_id: str,
    usage_file: Path, employee_file: Path,
    previous_closing_file: Path | None = None,
    promotion_file: Path | None = None,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    """Write reviewable quarter closing; never silently approve the report."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(run_id)):
        raise ClosingInputError("run_id 형식 오류")
    if not isinstance(policy_id, str) or not policy_id.strip():
        raise ClosingInputError("policy_id가 필요합니다")
    end, quarter = _month_and_quarter(closing_id)
    paths = [Path(usage_file), Path(employee_file)]
    if previous_closing_file:
        paths.append(Path(previous_closing_file))
    if promotion_file:
        paths.append(Path(promotion_file))
    if len(set(p.resolve() for p in paths)) != len(paths):
        raise ClosingInputError("입력 파일을 서로 다르게 지정해야 합니다")
    policy, facts = _usage_inputs(paths[0], closing_id)
    prev_rows, previous_ref = _previous(
        Path(previous_closing_file) if previous_closing_file else None,
        closing_id, policy.get("참조 Closing/기초")
    )
    names = _roster(paths[1])
    flags = _promotion(Path(promotion_file) if promotion_file else None)
    result = _closing.calculate_closing(
        closing_id=closing_id, name_map=names,
        previous_rows=prev_rows, previous_closing_id=previous_ref,
        promotion_flags=flags, **facts,
    )
    metadata = {
        "참조 ID": closing_id, "확정여부": "미확정",
        "정책 ID": policy_id, "run_id": run_id,
        "마감 기준일": end.isoformat(),
        "분기": quarter,
        "연초 기초이월 고정": "예",
        "미도래 월": "공란",
        "직전 Closing": previous_ref or "없음",
        "사용내역 SHA256": sha256_file(paths[0]),
        "직원명부 SHA256": sha256_file(paths[1]),
        "이전 Closing SHA256": (
            sha256_file(Path(previous_closing_file)) if previous_closing_file
            else "없음"),
        "사용촉진 자료 SHA256": (
            sha256_file(Path(promotion_file)) if promotion_file
            else "없음"),
        "검토 필요 건수": len(result["issues"]),
        "수당 청구권/지급 확정": "아니요",
        "외부 승인 없이 확정": "하지 않음",
    }
    target = Path(output_root) / run_id / "closing-result.xlsx"
    if target.exists():
        raise ClosingInputError("동일 run_id 결과가 이미 있습니다. 덮어쓰지 않습니다")
    payload = make_closing_workbook(result, metadata)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(payload)
    return {
        "path": str(target.resolve()), "report": result["report"],
        "issues": result["issues"], "policy": metadata,
        "carry_rows": result["carry_rows"],
        "shortage_rows": result["shortage_rows"],
    }
