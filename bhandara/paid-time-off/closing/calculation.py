"""Quarterly Closing report from already-calculated PTO Tool results.

No entitlement creation, deduction quantity conversion, grant allocation,
expiry date inference, cash compensation or use-promotion adjudication.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from fractions import Fraction
from typing import Any, Iterable, Mapping

MONTHS = tuple(f"{n}월" for n in range(1, 13))
REPORT_COLUMNS = (
    "employee_id", "name", "발생연차일수", "기초이월잔여일수",
    "대휴발생일수", "총확보휴가일수", "미사용만료일수", *MONTHS,
    "누적사용일수", "마감잔여일수", "마감상태",
)


def as_date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            if len(value.strip()) == 10:
                result = date.fromisoformat(value.strip())
                if result.isoformat() == value.strip():
                    return result
        except ValueError:
            pass
    raise ValueError(f"{field}: YYYY-MM-DD 날짜 오류")


def days(value: Any, field: str, *, allow_negative=False) -> Fraction:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field}: 수량 누락")
    try:
        number = Fraction(str(value).strip())
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError(f"{field}: 수량 오류") from exc
    if not allow_negative and number < 0:
        raise ValueError(f"{field}: 음수 오류")
    return number


def _quarter(closing_id: str) -> tuple[date, int]:
    import importlib
    expiry = importlib.import_module(
        "bhandara.paid-time-off.expiry-carryover.calculation"
    )
    end = expiry.closing_boundary(closing_id)
    return end, (end.month // 3)


def calculate_closing(
    *, closing_id: str,
    source_grants: Iterable[Mapping[str, Any]],
    usage_details: Iterable[Mapping[str, Any]],
    expiry_rows: Iterable[Mapping[str, Any]],
    usage_summaries: Iterable[Mapping[str, Any]],
    name_map: Mapping[str, str],
    previous_rows: Iterable[Mapping[str, Any]] = (),
    previous_closing_id: str | None = None,
    promotion_flags: Mapping[str, bool] | None = None,
    input_issues: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Produce employee-by-employee year-to-date quarter report.

    Previous report is the single authority for earlier quarters' cumulative
    amounts and the January 1 opening balance, never last quarter's closing
    remaining balance. Only incremental rows after previous close are added.
    """
    cutoff, quarter = _quarter(closing_id)
    year_start = date(cutoff.year, 1, 1)
    prev_end = None
    if previous_closing_id:
        prev_end, prev_quarter = _quarter(previous_closing_id)
        if (prev_end.year != cutoff.year or
                prev_quarter != quarter - 1):
            raise ValueError("직전 Closing ID가 바로 앞 분기가 아닙니다")
    elif previous_rows:
        raise ValueError("직전 Closing ID 없이 이전 보고서를 사용할 수 없습니다")
    previous = {}
    for raw in previous_rows:
        eid = str(raw.get("employee_id") or "").strip()
        if not eid or eid in previous:
            raise ValueError("이전 Closing 직원 ID 누락·중복")
        previous[eid] = raw

    issues = []
    affected = set()
    for issue in input_issues:
        eid = str(issue.get("employee_id") or "").strip()
        if eid:
            affected.add(eid)
        else:
            # An issue without owner cannot be scoped: everyone is review.
            affected.add("*")
        issues.append({
            "employee_id": eid or None, "reason": issue.get("reason") or
            "상위 계산 검토 필요", "source": issue.get("source") or "usage",
        })

    sources = defaultdict(lambda: {"연차": Fraction(), "이월": Fraction(),
                                  "대휴": Fraction()})
    outstanding = defaultdict(Fraction)
    carried = defaultdict(list)
    active_ids = set()
    for position, row in enumerate(source_grants, 1):
        eid = str(row.get("employee_id") or "").strip()
        gid = str(row.get("grant_id") or "").strip()
        if not eid or not gid or gid in active_ids:
            raise ValueError(f"발생스냅샷 {position}행: 직원·발생 ID 누락/중복")
        active_ids.add(gid)
        kind = row.get("leave_type")
        if kind not in ("연차", "대휴"):
            affected.add(eid)
            issues.append({"employee_id": eid, "source": "발생스냅샷",
                           "reason": "휴가 유형 오류"})
            continue
        grant_date = as_date(row.get("grant_date"), "grant_date")
        start = as_date(row.get("valid_from"), "valid_from")
        expires = as_date(row.get("expires_on"), "expires_on")
        amount = days(row.get("available_days"), "available_days")
        remain = days(row.get("remaining_days"), "remaining_days")
        if start > expires or start < grant_date or remain > amount:
            affected.add(eid)
            issues.append({"employee_id": eid, "source": "발생스냅샷",
                           "reason": "발생·유효기간 또는 잔여 수량 모순"})
            continue
        source_type = row.get("source_type")
        if source_type not in ("기초인계", "신규연차", "신규대휴"):
            affected.add(eid)
            issues.append({"employee_id": eid, "source": "발생스냅샷",
                           "reason": "발생 출처 구분 누락"})
            continue
        if grant_date > cutoff:
            # Future-dated confirmed grants are not current-year awards yet.
            continue
        if source_type == "기초인계" and prev_end is None:
            sources[eid]["이월"] += amount
        elif source_type == "신규연차" and (
            prev_end is None or grant_date > prev_end
        ):
            sources[eid]["연차"] += amount
        elif source_type == "신규대휴" and (
            prev_end is None or grant_date > prev_end
        ):
            sources[eid]["대휴"] += amount

        # Actual Closing handoff: expired balances become zero and all
        # grant IDs (including exhausted IDs) are retained.
        carried[eid].append({
            "grant_id": gid, "employee_id": eid, "leave_type": kind,
            "grant_date": grant_date.isoformat(),
            "available_days": remain if expires > cutoff else Fraction(),
            "valid_from": start.isoformat(), "expires_on": expires.isoformat(),
            "source_ref": row.get("source_ref"),
        })

    month_usage = defaultdict(lambda: defaultdict(Fraction))
    seen_inherited = set()
    current_shortages = []
    for position, row in enumerate(usage_details, 1):
        eid = str(row.get("employee_id") or "").strip()
        if not eid:
            raise ValueError(f"사용상세 {position}행: 직원 ID 누락")
        status = row.get("처리구분")
        if status not in ("사용", "부족", "예약", "예약부족", "인계부족"):
            affected.add(eid)
            issues.append({"employee_id": eid, "source": "사용상세",
                           "reason": "사용 처리구분 오류"})
            continue
        if status in ("예약", "예약부족"):
            continue
        actual_date = as_date(row.get("leave_date"), "leave_date")
        amount = days(row.get("차감일수"), "차감일수")
        if status == "인계부족":
            key = (str(row.get("request_id")), actual_date)
            if key in seen_inherited:
                raise ValueError("인계 미상계부족 신청 ID·사용일 중복")
            seen_inherited.add(key)
            # This deficit is already carried into opening balance (Q1)
            # or previous Closing net balance (Q2+).
            outstanding[eid] += amount
            current_shortages.append({
                "request_id": row.get("request_id"),
                "employee_id": eid, "leave_type": row.get("leave_type"),
                "leave_date": actual_date.isoformat(),
                "shortage_days": amount,
            })
            continue
        if not year_start <= actual_date <= cutoff:
            if actual_date > cutoff:
                # A past-marked row beyond the cutoff is an invalid contract.
                affected.add(eid)
                issues.append({"employee_id": eid, "source": "사용상세",
                               "reason": "마감 이후 사용이 실사용 처리됨"})
            continue
        if prev_end is None or actual_date > prev_end:
            month_usage[eid][actual_date.month] += amount
        if status == "부족":
            outstanding[eid] += amount
            current_shortages.append({
                "request_id": row.get("request_id"),
                "employee_id": eid, "leave_type": row.get("leave_type"),
                "leave_date": actual_date.isoformat(),
                "shortage_days": amount,
            })

    expired = defaultdict(Fraction)
    for position, row in enumerate(expiry_rows, 1):
        eid = str(row.get("employee_id") or "").strip()
        if not eid:
            raise ValueError(f"만료이월 {position}행: employee_id 누락")
        amount = days(row.get("expiry_days"), "expiry_days")
        expires = as_date(row.get("expires_on"), "expires_on")
        if amount and row.get("status") != "만료":
            affected.add(eid)
            issues.append({"employee_id": eid, "source": "만료이월",
                           "reason": "만료량·판정 불일치"})
            continue
        if amount and prev_end and expires <= prev_end:
            # Previous closing must have included this earlier expiry.
            affected.add(eid)
            issues.append({"employee_id": eid, "source": "만료이월",
                           "reason": "이전 분기 만료량이 재등장"})
            continue
        if amount and not year_start <= expires <= cutoff:
            affected.add(eid)
            issues.append({"employee_id": eid, "source": "만료이월",
                           "reason": "해당 연도 마감 범위 밖의 만료량"})
            continue
        expired[eid] += amount

    prev_parsed = {}
    for eid, row in previous.items():
        values = {}
        for field in ("발생연차일수", "기초이월잔여일수", "대휴발생일수",
                      "미사용만료일수", "누적사용일수", "마감잔여일수"):
            values[field] = days(row.get(field), f"직전 Closing.{field}",
                                 allow_negative=(field == "기초이월잔여일수" or
                                                 field == "마감잔여일수"))
        for month in range(1, prev_end.month + 1):
            values[f"{month}월"] = days(row.get(f"{month}월"),
                                      f"직전 Closing.{month}월")
        if sum((values[f"{i}월"] for i in range(1, prev_end.month + 1)),
               Fraction()) != values["누적사용일수"]:
            raise ValueError("직전 Closing 누적사용일수와 월별 합계 불일치")
        if (values["발생연차일수"] + values["기초이월잔여일수"] +
            values["대휴발생일수"] - values["미사용만료일수"] -
            values["누적사용일수"]) != values["마감잔여일수"]:
            raise ValueError("직전 Closing 수량 관계 불일치")
        prev_parsed[eid] = values

    calculated_net = {}
    for row in usage_summaries:
        eid = str(row.get("employee_id") or "").strip()
        if not eid or eid in calculated_net:
            raise ValueError("사용요약 직원 ID 누락·중복")
        if row.get("잔여일수") is None:
            affected.add(eid)
            calculated_net[eid] = None
        else:
            calculated_net[eid] = days(
                row["잔여일수"], "사용요약.잔여일수", allow_negative=True)

    all_employees = (set(name_map) | set(prev_parsed) | set(sources) |
                     set(month_usage) | set(calculated_net) |
                     set(expired) | set(outstanding))
    report = []
    for eid in sorted(all_employees):
        name = str(name_map.get(eid) or "").strip()
        if not name:
            affected.add(eid)
            issues.append({"employee_id": eid, "source": "직원명부",
                           "reason": "직원명 누락"})
        prev = prev_parsed.get(eid)
        c = (prev["발생연차일수"] if prev else Fraction()) + sources[eid]["연차"]
        d = (prev["기초이월잔여일수"] if prev else
             sources[eid]["이월"] - outstanding[eid] if prev_end is None else
             Fraction())
        e = (prev["대휴발생일수"] if prev else Fraction()) + sources[eid]["대휴"]
        g = (prev["미사용만료일수"] if prev else Fraction()) + expired[eid]
        months = {}
        for month in range(1, 13):
            if month > cutoff.month:
                months[f"{month}월"] = None
            else:
                old = prev.get(f"{month}월", Fraction()) if prev else Fraction()
                months[f"{month}월"] = old + month_usage[eid][month]
        t = sum((value for value in months.values() if value is not None),
                Fraction())
        f = c + d + e
        u = f - g - t
        net = calculated_net.get(eid)
        if net is None or net != u:
            affected.add(eid)
            issues.append({"employee_id": eid, "source": "잔여검산",
                           "reason": ("사용요약 잔여 자료 누락" if net is None else
                                      f"마감 잔여 검산 불일치: {u} != {net}")})
        if "*" in affected or eid in affected:
            status = "자료확인 필요"
        elif outstanding[eid] > 0:
            status = "초과사용"
        elif quarter == 3 and (promotion_flags is None or
                               eid not in promotion_flags):
            status = "자료확인 필요"
            issues.append({"employee_id": eid, "source": "사용촉진",
                           "reason": "3분기 사용촉진 외부 판정자료 미제공"})
        elif quarter == 3 and promotion_flags[eid]:
            status = "사용촉진 검토"
        else:
            status = "정상"
        report.append({
            "employee_id": eid, "name": name or None,
            "발생연차일수": c, "기초이월잔여일수": d,
            "대휴발생일수": e, "총확보휴가일수": f,
            "미사용만료일수": g, **months, "누적사용일수": t,
            "마감잔여일수": None if status == "자료확인 필요" else u,
            "마감상태": status,
        })

    handoff = [row for eid in sorted(carried) for row in carried[eid]]
    return {
        "closing_id": closing_id, "period_end": cutoff.isoformat(),
        "report": report, "carry_rows": handoff,
        "shortage_rows": current_shortages, "issues": issues,
        "ready_for_review": bool(report) and not issues,
    }
