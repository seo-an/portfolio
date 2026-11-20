"""Excel/file boundary for the PTO Tool's *optional* usage-allocation flow.

No invocation of Entitlement, Deduction Quantity or Closing: consumes their
explicitly supplied finished Excel results, plus source/validity references.
This runner is independent of Gearbox and Slack.
"""
from __future__ import annotations

import importlib
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal
from fractions import Fraction
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Mapping

from openpyxl import Workbook, load_workbook

from bhandara.common.utils.hashing import sha256_file

_entitlement = importlib.import_module("bhandara.paid-time-off.entitlement.calculation")
_allocation = importlib.import_module("bhandara.paid-time-off.allocation")
_sources = importlib.import_module("bhandara.paid-time-off.source_join")
_expiry = importlib.import_module("bhandara.paid-time-off.expiry-carryover.calculation")

TOOL_ROOT = Path(__file__).resolve().parent
SHARED_ROOT = TOOL_ROOT.parent / "data" / "input"
OUTPUT_ROOT = TOOL_ROOT / "output"


class UsageInputError(ValueError):
    """Invalid or incomplete contract: no apparently final ledger is produced."""


def _input_cell(cell: Any, field: str) -> Any:
    if cell.data_type == "f":
        # No formula evaluation; downstream should see missing/invalid value.
        return None
    value = cell.value
    if isinstance(value, str):
        value = value.strip()
        if value.startswith(("=", "+", "@")):
            return None
        if value.startswith("-") and not re.fullmatch(
                r"-[0-9]+(?:\.[0-9]+)?(?:/[0-9]+)?", value):
            # A negative numeric value or signed exact fraction is safe.
            # Formula-looking content such as '-SUM(...)' is not.
            return None
    return value


def read_rows(
    path: Path, sheet: str, fields: Iterable[str], *, optional_sheet=False
) -> list[dict[str, Any]]:
    """Read only explicitly contracted headers, without formulas or fallback."""
    if not path.is_file() or path.suffix.lower() not in (".xlsx", ".xlsm"):
        raise UsageInputError(f"필수 Excel 파일이 없습니다: {path}")
    book = None
    try:
        book = load_workbook(path, read_only=True, data_only=False)
        if sheet not in book.sheetnames:
            if optional_sheet:
                return []
            raise UsageInputError(f"{path.name}: {sheet} 시트가 없습니다")
        iterator = book[sheet].iter_rows()
        head = next(iterator, None)
        if head is None:
            raise UsageInputError(f"{path.name}/{sheet}: 헤더 없음")
        headers = [x.value.strip() if isinstance(x.value, str)
                   else x.value for x in head]
        fields = tuple(fields)
        present = [item for item in headers if item not in (None, "")]
        if len(present) != len(set(present)):
            raise UsageInputError(f"{path.name}/{sheet}: 중복 헤더")
        missing = [field for field in fields if field not in headers]
        if missing:
            raise UsageInputError(f"{path.name}/{sheet}: 필수 열 누락 {missing}")
        positions = {field: headers.index(field) for field in fields}
        rows = []
        for position, row in enumerate(iterator, start=2):
            if not any(c.value not in (None, "") for c in row):
                continue
            data = {
                field: _input_cell(row[index], field) if index < len(row)
                else None for field, index in positions.items()
            }
            data["_source_row"] = position
            rows.append(data)
        return rows
    except UsageInputError:
        raise
    except Exception as exc:
        raise UsageInputError(f"{path.name}/{sheet}: Excel 읽기 실패") from exc
    finally:
        if book is not None:
            book.close()


def _policy(path: Path) -> dict[str, Any]:
    pairs = read_rows(path, "정책정보", ("항목", "값"))
    result = {}
    for item in pairs:
        name = str(item["항목"] or "").strip()
        if name in result:
            raise UsageInputError(f"{path.name}: 중복 정책정보 {name}")
        result[name] = item["값"]
    return result


def _verified_entitlement(path: Path, as_of: date) -> list[dict]:
    meta = _policy(path)
    if str(meta.get("산정 기준일")) != as_of.isoformat():
        raise UsageInputError("Entitlement 산정 기준일과 실행 기준일이 다릅니다")
    details = read_rows(path, "발생상세", (
        "employee_id", "basis", "발생구분", "period_start", "period_end",
        "grant_date", "계산결과", "상태", "사유", "grant_id", "반영발생일수",
    ))
    summaries = read_rows(path, "발생요약", (
        "employee_id", "발생연차", "상태",
    ))
    undetermined = {
        str(row["employee_id"]) for row in summaries
        if row["상태"] != "계산 완료"
    }
    totals = defaultdict(Fraction)
    valid = set()
    for item in details:
        normalized = {
            "employee_id": item["employee_id"],
            "basis": item["basis"],
            "grant_type": item["발생구분"],
            "period_start": item["period_start"],
            "period_end": item["period_end"],
            "grant_date": item["grant_date"],
        }
        if not item["grant_id"] or (
            item["grant_id"] != _entitlement.grant_identity(normalized)):
            raise UsageInputError("Entitlement grant_id가 발생 건 정보와 일치하지 않습니다")
        item["reflected_days"] = item.pop("반영발생일수")
        item["status"] = item.pop("상태")
        item["calculation_result"] = item.pop("계산결과")
        item["grant_type"] = item.pop("발생구분")
        if item["status"] == "계산 완료":
            if item["reflected_days"] is None and str(item["employee_id"]) in undetermined:
                # This employee has an unresolved grant; Entitlement correctly
                # withheld all reflected amounts to avoid a false partial right.
                item["status"] = "판정 안됨"
                continue
            if item["reflected_days"] is None:
                raise UsageInputError("완료된 Entitlement 발생 건의 반영발생일수 누락")
            try:
                totals[str(item["employee_id"])] += _sources._quantity(
                    item["reflected_days"], "반영발생일수")
            except ValueError as exc:
                raise UsageInputError(str(exc)) from exc
            valid.add(str(item["employee_id"]))
    for row in summaries:
        employee = str(row["employee_id"])
        if row["상태"] == "계산 완료":
            try:
                summary_days = _sources._quantity(row["발생연차"], "발생연차")
            except ValueError as exc:
                raise UsageInputError(str(exc)) from exc
            if totals[employee] != summary_days:
                raise UsageInputError(f"{employee}: 발생상세 합계와 발생요약 불일치")
        elif employee in valid:
            # Partially undecided grants must not look like a fully final total.
            pass
    return details


def _verified_deduction(path: Path) -> tuple[list[dict], list[dict]]:
    details = read_rows(path, "차감상세", (
        "request_id", "employee_id", "leave_date", "leave_type", "상태",
        "차감일수", "_exact_numerator", "_exact_denominator",
    ))
    calculated, ignored = [], []
    for row in details:
        if row["상태"] != "계산 완료":
            ignored.append({"source": "Deduction Quantity",
                            "row": row["_source_row"], "status": "계산 제외",
                            "reason": "상위 차감 계산에서 제외된 승인 신청",
                            "request_id": row["request_id"],
                            "employee_id": row["employee_id"]})
            continue
        num, den = row["_exact_numerator"], row["_exact_denominator"]
        if (not re.fullmatch(r"[0-9]+", str(num or "")) or
                not re.fullmatch(r"[0-9]+", str(den or ""))):
            raise UsageInputError("Deduction 정확한 분수 열 누락·오류: 새 버전으로 재산출하세요")
        num, den = int(num), int(den)
        if num <= 0 or den <= 0:
            raise UsageInputError("Deduction 정확한 분수의 분자/분모는 양수여야 합니다")
        number = Fraction(num, den)
        if _allocation.quantity_text(number) != str(row["차감일수"]):
            raise UsageInputError("Deduction 표기 수량과 정확한 분수가 다릅니다")
        calculated.append({
            "request_id": row["request_id"],
            "employee_id": row["employee_id"],
            "leave_date": row["leave_date"],
            "leave_type": row["leave_type"],
            "deduction_days": number,
        })
    return calculated, ignored


def _verified_references(path: Path) -> tuple[list[dict], list[dict]]:
    rows = read_rows(path, "발생근거", (
        "grant_id", "employee_id", "grant_date",
        "valid_from", "expires_on", "source_ref",
    ))
    compensation = read_rows(path, "대휴발생", (
        "source_ref", "반영발생일수",
    ), optional_sheet=True)
    return rows, [
        {"source_ref": row["source_ref"],
         "reflected_days": row["반영발생일수"]} for row in compensation
    ]


def _carry_reference(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(
            r"(?:Closing|Opening)-[1-4]\.4-[0-9]{4}", value):
        raise UsageInputError("인계 출처는 Closing-4.4-2025 또는 Opening-4.4-2025 형식")
    return _expiry.closing_boundary(value.replace("Opening-", "Closing-", 1))


def _read_carry(path: Path) -> tuple[list[dict], list[dict], str, date]:
    meta = _policy(path)
    ref = meta.get("참조 ID")
    if meta.get("확정여부") != "확정":
        raise UsageInputError("마감/최초 기초자료가 확정된 상태가 아닙니다")
    end = _carry_reference(ref)
    raw = read_rows(path, "인계자료", (
        "grant_id", "employee_id", "leave_type", "grant_date",
        "available_days", "valid_from", "expires_on", "source_ref",
    ))
    shortage = read_rows(path, "미상계부족", (
        "request_id", "employee_id", "leave_type", "leave_date",
        "shortage_days",
    ), optional_sheet=True)
    return raw, shortage, ref, end


def _positive_shortages(rows: Iterable[Mapping[str, Any]]) -> list[dict]:
    valid = []
    seen: set[tuple[str, date]] = set()
    for row in rows:
        try:
            amount = _sources._quantity(row.get("shortage_days"), "shortage_days")
            if amount <= 0:
                raise ValueError("shortage_days는 양수여야 합니다")
            employee = _sources._identifier(row.get("employee_id"), "employee_id")
            leave_type = _sources._identifier(row.get("leave_type"), "leave_type")
            if leave_type not in ("연차", "대휴"):
                raise ValueError("leave_type 오류")
            request = _sources._identifier(row.get("request_id"), "request_id")
            leave_date = _sources._iso_date(row.get("leave_date"), "leave_date")
            key = (request, leave_date)
            if key in seen:
                raise ValueError("인계 미상계부족 request_id·leave_date 중복")
            seen.add(key)
            valid.append({"request_id": request, "employee_id": employee,
                          "leave_type": leave_type, "leave_date": leave_date,
                          "shortage_days": amount})
        except ValueError as exc:
            raise UsageInputError("인계 미상계부족 입력 오류: " + str(exc)) from exc
    return valid


def _output_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Fraction):
        # Excel is decimal based; only display can truncate nonterminating
        # amounts. Exact fraction stays in in-memory allocation records.
        return Decimal(_allocation.quantity_text(value))
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    if isinstance(value, date):
        return value.isoformat()
    return value


def _sheet(book, title: str, fields: tuple[str, ...], rows: Iterable[Mapping]):
    sheet = book.create_sheet(title)
    sheet.append(fields)
    for row in rows:
        sheet.append([_output_cell(row.get(field)) for field in fields])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    return sheet


def _record_details(allocation: Mapping[str, Any],
                    opening_shortages: list[dict]) -> list[dict]:
    lookup = {g["grant_id"]: g for g in allocation["balances"]}
    entries = []
    for row in allocation["allocations"]:
        grant = lookup.get(row["grant_id"])
        entries.append({
            "employee_id": row["employee_id"], "leave_type": row["leave_type"],
            "grant_id": row["grant_id"],
            "grant_date": grant["grant_date"] if grant else None,
            "반영발생일수": grant["available_days"] if grant else None,
            "valid_from": grant["valid_from"] if grant else None,
            "expires_on": grant["expires_on"] if grant else None,
            "source_ref": grant["source_ref"] if grant else None,
            "request_id": row["request_id"], "leave_date": row["leave_date"],
            "차감일수": row["allocated_days"], "처리구분": row["status"],
            "사유": None,
        })
    for row in opening_shortages:
        entries.append({
            "employee_id": row["employee_id"], "leave_type": row["leave_type"],
            "grant_id": None, "grant_date": None, "반영발생일수": None,
            "valid_from": None, "expires_on": None, "source_ref": None,
            "request_id": row["request_id"], "leave_date": row["leave_date"],
            "차감일수": row["shortage_days"], "처리구분": "인계부족",
            "사유": "외부 확정 상계 전까지 음수 잔여 유지",
        })
    return entries


def _employee_summary(
    allocation: Mapping[str, Any], opening_shortages: list[dict],
    *, as_of: date, close_of_period: bool = False
) -> list[dict]:
    carry = defaultdict(Fraction)
    for row in opening_shortages:
        carry[row["employee_id"]] += row["shortage_days"]
    groups = set(allocation["blocked_groups"])
    employees = (
        {g["employee_id"] for g in allocation["balances"]} |
        {row["employee_id"] for row in allocation["allocations"]} |
        {row["employee_id"] for row in opening_shortages} |
        {item["employee_id"] for item in allocation["summary"]}
    )
    result = []
    for employee in sorted(employees):
        blocked = any(key[0] == employee for key in groups)
        sources = [g for g in allocation["balances"] if g["employee_id"] == employee]
        new_and_open = sum((
            g["available_days"] for g in sources
            if _sources._iso_date(g["grant_date"], "grant_date") <= as_of
        ), Fraction())
        used = sum((
            row["allocated_days"] for row in allocation["allocations"]
            if row["employee_id"] == employee and
            row["status"] in ("사용", "부족")
        ), Fraction())
        available = sum((
            g["remaining_days"] for g in sources
            if (_sources._iso_date(g["valid_from"], "valid_from") <= as_of and
                (_sources._iso_date(g["expires_on"], "expires_on") > as_of if
                 close_of_period else
                 _sources._iso_date(g["expires_on"], "expires_on") >= as_of))
        ), Fraction())
        shortage = sum((
            v for (eid, kind), v in allocation["shortages"].items()
            if eid == employee
        ), Fraction())
        result.append({
            "employee_id": employee,
            "발생일수": None if blocked else new_and_open,
            "사용일수": None if blocked else used,
            "잔여일수": None if blocked else available - shortage - carry[employee],
        })
    return result


def make_usage_workbook(
    summary: list[dict], details: list[dict], expiry_result: dict | None,
    issues: list[dict], metadata: dict[str, Any],
    source_snapshot: list[dict] | None = None,
) -> bytes:
    book = Workbook()
    try:
        book.remove(book.active)
        _sheet(book, "사용요약",
               ("employee_id", "발생일수", "사용일수", "잔여일수"), summary)
        _sheet(book, "사용상세",
               ("employee_id", "leave_type", "grant_id", "grant_date",
                "반영발생일수", "valid_from", "expires_on", "source_ref",
                "request_id", "leave_date", "차감일수", "처리구분", "사유"),
               details)
        if expiry_result is not None:
            _sheet(book, "만료이월",
                   ("grant_id", "employee_id", "leave_type", "source_ref",
                    "valid_from", "expires_on", "remaining_days",
                    "expiry_days", "carryover_days", "status",
                    "compensation_review"), expiry_result["entries"])
        if issues:
            _sheet(book, "검토사항",
                   ("source", "row", "employee_id", "leave_type",
                    "grant_id", "request_id", "status", "reason"), issues)
        if source_snapshot is not None:
            keys = ("grant_id", "employee_id", "leave_type", "grant_date",
                    "valid_from", "expires_on", "source_ref", "source_type",
                    "available_days", "remaining_days")
            # Handoff facts are NOT a second business ledger. Exact rational
            # values are stored as text "numerator/denominator" to avoid the
            # 7-decimal visual truncation used in the human-facing workbook.
            entries = []
            for record in source_snapshot:
                entries.append({
                    key: str(record[key]) if isinstance(record.get(key), Fraction)
                    else record.get(key) for key in keys
                })
            hidden = _sheet(book, "_발생자료", keys, entries)
            hidden.sheet_state = "hidden"
        _sheet(book, "정책정보", ("항목", "값"),
               [{"항목": k, "값": v} for k, v in metadata.items()])
        stream = BytesIO()
        book.save(stream)
        return stream.getvalue()
    finally:
        book.close()


def run_usage_ledger(
    *, as_of_date: date, policy_id: str, run_id: str,
    entitlement_file: Path, deduction_file: Path, reference_file: Path,
    carry_in_file: Path | None = None, closing_id: str | None = None,
    output_root: Path = OUTPUT_ROOT,
) -> dict[str, Any]:
    """Combine supplied result files only; never auto-execute other modules.

    If closing_id is supplied, as_of_date must equal that quarter boundary.
    Opening/previous Closing is derived from the confirmed carry-in's ref.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(run_id)):
        raise UsageInputError("run_id는 영문·숫자·하이픈·밑줄만 허용합니다")
    if not isinstance(policy_id, str) or not policy_id.strip():
        raise UsageInputError("policy_id가 필요합니다")
    as_of = _sources._iso_date(as_of_date, "as_of_date")
    if closing_id is not None and _expiry.closing_boundary(closing_id) != as_of:
        raise UsageInputError("closing_id 마감일과 실행 기준일이 다릅니다")
    paths = [Path(entitlement_file), Path(deduction_file),
             Path(reference_file)]
    if carry_in_file is not None:
        paths.append(Path(carry_in_file))
    if len({p.resolve() for p in paths}) != len(paths):
        raise UsageInputError("서로 다른 입력 원본 파일이 필요합니다")
    entitlement = _verified_entitlement(paths[0], as_of)
    deduction, deduction_issues = _verified_deduction(paths[1])
    references, compensation = _verified_references(paths[2])
    carry_rows, opening_shortage, carry_ref, carry_end = [], [], None, None
    if carry_in_file is not None:
        carry_rows, raw_shortage, carry_ref, carry_end = _read_carry(
            Path(carry_in_file))
        if carry_end >= as_of:
            raise UsageInputError("인계 마감일은 실행 기준일 이전이어야 합니다")
        opening_shortage = _positive_shortages(raw_shortage)
    combined = _sources.combine_grant_sources(
        entitlement, references, compensation,
        carry_rows=carry_rows, closing_end=carry_end)
    if carry_end:
        # Old approved requests are already included in the confirmed snapshot.
        deduction = [
            row for row in deduction
            if _sources._iso_date(row["leave_date"], "leave_date") > carry_end
        ]
    calculated = _allocation.allocate_usage(
        combined["grants"], deduction, as_of_date=as_of)
    issues = combined["issues"] + deduction_issues + calculated["issues"]
    summary = _employee_summary(
        calculated, opening_shortage, as_of=as_of,
        close_of_period=bool(closing_id))
    details = _record_details(calculated, opening_shortage)
    expiry_result = None
    if closing_id:
        expiry_result = _expiry.evaluate_expiry_carryover(
            calculated["balances"], closing_id=closing_id,
            balance_as_of=as_of)
        issues.extend(expiry_result["errors"])
    source_types = {
        row["grant_id"]: row.get("source_type")
        for row in combined["grants"]
    }
    source_snapshot = [
        {**row, "source_type": source_types.get(row["grant_id"])}
        for row in calculated["balances"]
    ]
    metadata = {
        "정책 ID": policy_id, "run_id": run_id,
        "실행 기준일": as_of.isoformat(), "참조 Closing/기초": carry_ref or "없음",
        "마감 판정 ID": closing_id or "없음",
        "Entitlement SHA256": sha256_file(paths[0]),
        "Deduction SHA256": sha256_file(paths[1]),
        "발생근거 SHA256": sha256_file(paths[2]),
        "기초인계 SHA256": sha256_file(paths[3]) if carry_in_file else "없음",
        "계산 상태": "검토 필요" if issues else "계산 완료",
        "승인·상계·수당 지급 확정": "아니요",
        "미상계 부족분 자동 상계": "하지 않음",
        "정확도": "분수 단위 계산, Excel 소수 무한 반복은 7자리 절사 표기",
        "과거 인계 전 승인 신청": "기초 잔여에 반영되어 재차감하지 않음",
    }
    payload = make_usage_workbook(summary, details, expiry_result,
                                  issues, metadata, source_snapshot)
    destination = Path(output_root) / run_id / "usage-ledger-result.xlsx"
    if destination.exists():
        raise UsageInputError("동일 run_id의 결과가 이미 있습니다. 덮어쓰지 않습니다")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(payload)
    return {
        "path": str(destination.resolve()), "summaries": summary,
        "details": details, "expiry": expiry_result,
        "issues": issues, "policy": metadata,
        "source_snapshot": source_snapshot,
    }
