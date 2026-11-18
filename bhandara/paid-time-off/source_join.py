"""Pure PTO Tool grant-source relational joins (no Excel/file I/O).

Current entitlements provide IDs and reflected days; a shared reference
register supplies validity. Compensation quantity is keyed only by source_ref.
An earlier confirmed Closing snapshot is authoritative for older grants,
including zero balances, so reruns cannot accidentally resurrect spent grants.
"""
from __future__ import annotations

from datetime import date
from fractions import Fraction
from typing import Any, Iterable, Mapping


def _identifier(value: Any, name: str) -> str:
    if value is None or isinstance(value, bool) or not str(value).strip():
        raise ValueError(f"{name} 누락")
    return str(value).strip()


def _iso_date(value: Any, name: str) -> date:
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    if not isinstance(value, str) or len(value.strip()) != 10:
        raise ValueError(f"{name}: YYYY-MM-DD 형식 필요")
    try:
        result = date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{name}: 날짜 오류") from exc
    if result.isoformat() != value.strip():
        raise ValueError(f"{name}: YYYY-MM-DD 형식 필요")
    return result


def _quantity(value: Any, name: str) -> Fraction:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} 누락")
    try:
        # The already-reflected days in input are decimal, not raw 7-digit
        # display from a repeating fraction.
        result = Fraction(str(value).strip())
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError(f"{name}: 수량 오류") from exc
    if result < 0:
        raise ValueError(f"{name}: 음수 불가")
    return result


def _index(
    rows: Iterable[Mapping[str, Any]], *, key: str, label: str
) -> dict[str, Mapping[str, Any]]:
    result = {}
    for row in rows:
        name = _identifier(row.get(key), f"{label}.{key}")
        if name in result:
            raise ValueError(f"{label}: 중복 {key}={name}")
        result[name] = row
    return result


def combine_grant_sources(
    entitlement_rows: Iterable[Mapping[str, Any]],
    reference_rows: Iterable[Mapping[str, Any]],
    compensation_rows: Iterable[Mapping[str, Any]],
    *,
    carry_rows: Iterable[Mapping[str, Any]] = (),
    closing_end: date | None = None,
) -> dict[str, Any]:
    """Build grant objects for allocation without extra raw/grant ledgers.

    Reference rows: grant_id,valid_from,expires_on; for compensation additionally
    source_ref,employee_id,grant_date. Compensation rows contain only source_ref,
    reflected_days. Carry rows are confirmed full grant snapshots including
    zero-balance IDs. Entitlement rows contain stable grant_id and reflected_days.
    """
    references = _index(reference_rows, key="grant_id", label="발생근거")
    by_source = {}
    duplicate_sources = set()
    for row in references.values():
        source = str(row.get("source_ref") or "").strip()
        if source:
            if source in by_source:
                duplicate_sources.add(source)
            else:
                by_source[source] = row
    compensation = _index(compensation_rows, key="source_ref", label="대휴발생")
    if duplicate_sources & set(compensation):
        raise ValueError(f"대휴 발생근거 source_ref 중복: {sorted(duplicate_sources & set(compensation))}")
    carried = _index(carry_rows, key="grant_id", label="Closing 인계")
    results: dict[str, dict] = {}
    issues: list[dict] = []
    end = _iso_date(closing_end, "closing_end") if closing_end else None

    for identifier, row in carried.items():
        try:
            grant_date = _iso_date(row.get("grant_date"), "grant_date")
            expiry = _iso_date(row.get("expires_on"), "expires_on")
            start = _iso_date(row.get("valid_from"), "valid_from")
            amount = _quantity(row.get("available_days"), "인계 잔여일수")
            if end is None:
                raise ValueError("Closing 기준일 없이 인계 데이터가 제공됨")
            if grant_date > end:
                raise ValueError("마감일 이후 발생분을 과거 Closing에서 인계할 수 없습니다")
            if start > expiry:
                raise ValueError("유효기간 시작·종료 역전")
            if expiry <= end and amount:
                raise ValueError("이미 만료된 권리의 잔여가 Closing에서 인계되었습니다")
            employee = _identifier(row.get("employee_id"), "employee_id")
            leave_type = _identifier(row.get("leave_type"), "leave_type")
            source = _identifier(row.get("source_ref"), "source_ref")
            results[identifier] = {
                "grant_id": identifier, "employee_id": employee,
                "leave_type": leave_type, "grant_date": grant_date.isoformat(),
                "available_days": amount, "valid_from": start.isoformat(),
                "expires_on": expiry.isoformat(), "source_ref": source,
                "source_type": "기초인계",
            }
        except ValueError as exc:
            issues.append({"source": "인계자료", "grant_id": identifier,
                           "status": "계산 제외", "reason": str(exc),
                           "employee_id": row.get("employee_id"),
                           "leave_type": row.get("leave_type")})
            # Do not forget the invalid ID; later entitlement must not
            # reintroduce the same historical grant.
            results[identifier] = {
                "grant_id": identifier, "employee_id": row.get("employee_id"),
                "leave_type": row.get("leave_type"),
                "grant_date": row.get("grant_date"), "available_days": None,
                "valid_from": row.get("valid_from"),
                "expires_on": row.get("expires_on"),
                "source_ref": row.get("source_ref"),
                "source_type": "기초인계",
            }

    for index, row in enumerate(entitlement_rows, 1):
        employee = str(row.get("employee_id") or "").strip()
        identifier = str(row.get("grant_id") or "").strip()
        if not identifier:
            issues.append({"source": "Entitlement", "row": index,
                           "employee_id": employee, "leave_type": "연차",
                           "status": "계산 제외", "reason": "grant_id 누락"})
            continue
        if identifier in results:
            before = results[identifier]
            if before.get("employee_id") != employee or (
                before.get("grant_date") != row.get("grant_date")) or (
                before.get("leave_type") != "연차"):
                raise ValueError(f"Closing과 Entitlement의 발생 ID 불일치: {identifier}")
            continue
        grant_date = _iso_date(row.get("grant_date"), "grant_date")
        if end and grant_date <= end:
            # A missing zero-balance ID in Closing would resurrect consumed
            # rights, so fail the whole join instead of guessing.
            raise ValueError(f"Closing에 과거 발생 건 누락: {identifier}")
        ref = references.get(identifier)
        if ref:
            if ref.get("employee_id") not in (None, "", employee):
                raise ValueError(f"발생근거 직원 ID 불일치: {identifier}")
            if ref.get("grant_date") not in (None, "", row.get("grant_date")):
                raise ValueError(f"발생근거 발생일 불일치: {identifier}")
        else:
            issues.append({"source": "Entitlement", "row": index,
                           "employee_id": employee, "leave_type": "연차",
                           "status": "계산 제외",
                           "reason": f"발생근거에서 grant_id={identifier} 유효기간 누락"})
        results[identifier] = {
            "grant_id": identifier, "employee_id": employee,
            "leave_type": "연차", "grant_date": grant_date.isoformat(),
            "available_days": (row.get("reflected_days") if
                               row.get("status") == "계산 완료" else None),
            "valid_from": ref.get("valid_from") if ref else None,
            "expires_on": ref.get("expires_on") if ref else None,
            "source_ref": (str(ref.get("source_ref")).strip()
                           if ref and ref.get("source_ref") else
                           "Entitlement:" + identifier),
            "source_type": "신규연차",
        }

    for index, (source, row) in enumerate(compensation.items(), 1):
        ref = by_source.get(source)
        if not ref:
            issues.append({"source": "대휴발생", "row": index,
                           "status": "계산 제외",
                           "reason": f"발생근거에 source_ref={source} 없음"})
            continue
        identifier = _identifier(ref.get("grant_id"), "grant_id")
        if identifier in results:
            before = results[identifier]
            if before.get("leave_type") != "대휴" or (
                before.get("source_ref") != source):
                raise ValueError(f"대휴 발생 ID 충돌: {identifier}")
            continue
        grant_date = _iso_date(ref.get("grant_date"), "grant_date")
        if end and grant_date <= end:
            raise ValueError(f"Closing에 과거 대휴 발생 건 누락: {identifier}")
        results[identifier] = {
            "grant_id": identifier,
            "employee_id": ref.get("employee_id"),
            "leave_type": "대휴", "grant_date": grant_date.isoformat(),
            "available_days": row.get("reflected_days"),
            "valid_from": ref.get("valid_from"),
            "expires_on": ref.get("expires_on"),
            "source_ref": source, "source_type": "신규대휴",
        }
    # A missing compensation quantity does not silently create an additional
    # grant; an unused reference row is merely metadata, not an issued right.
    return {"grants": list(results.values()), "issues": issues}
