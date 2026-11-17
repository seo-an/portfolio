"""Pure PTO entitlement calculations from already-decided Korean attendance flags.

No attendance evaluation, usage, expiry, carryover, balance or payroll logic.
Intermediate quantities are exact rational numbers. Recurring decimals are
truncated to seven places only when serialized, never for later arithmetic.
"""
from __future__ import annotations

from datetime import date, timedelta
from fractions import Fraction
from decimal import Decimal
from typing import Iterable, Mapping, Any

from . import (
    ELIGIBLE, NOT_ELIGIBLE, UNDETERMINED, add_months,
    calculate_anniversary_grants,
)

BASIS_ANNIVERSARY = "입사일 기준"
BASIS_FISCAL = "회계연도 기준"
BASIS_MONTHLY = "1년 미만 기준"
BASES = {BASIS_ANNIVERSARY, BASIS_FISCAL, BASIS_MONTHLY}
CHECK_TYPES = {"월간", "연간"}
FLAGS = {
    ("월간", "개근"): ELIGIBLE,
    ("월간", "미개근"): NOT_ELIGIBLE,
    ("월간", "판정 안됨"): UNDETERMINED,
    ("연간", "80% 충족"): ELIGIBLE,
    ("연간", "80% 미충족"): NOT_ELIGIBLE,
    ("연간", "판정 안됨"): UNDETERMINED,
}
METHODS = {"소정근로일 기준", "달력일 기준", "월수 기준"}


def strict_date(value: Any, field: str) -> date:
    """Accept native Excel dates or strict YYYY-MM-DD; never guess locale."""
    from datetime import datetime
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f"{field}: YYYY-MM-DD 형식이어야 합니다")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field}: 날짜가 올바르지 않습니다") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field}: YYYY-MM-DD 형식이어야 합니다")
    return parsed


def build_flag_index(rows: Iterable[Mapping[str, Any]]) -> dict[tuple, str]:
    """Build an exact-interval lookup; attendance flags are never recalculated."""
    result: dict[tuple, str] = {}
    for row in rows:
        employee_id = str(row.get("employee_id") or "").strip()
        check_type = row.get("check_type")
        flag = row.get("attendance_flag")
        if not employee_id or check_type not in CHECK_TYPES:
            raise ValueError("직원 ID 또는 근태 구분이 올바르지 않습니다")
        if (check_type, flag) not in FLAGS:
            raise ValueError(f"{employee_id}: 근태 플래그가 올바르지 않습니다")
        start = strict_date(row.get("period_start"), "period_start")
        end = strict_date(row.get("period_end"), "period_end")
        if start > end:
            raise ValueError("근태 시작일이 종료일보다 늦습니다")
        key = (employee_id, check_type, start, end)
        if key in result:
            raise ValueError(f"{employee_id}: 중복 근태 판정기간이 있습니다")
        result[key] = FLAGS[(check_type, flag)]
    return result


def _resolver(index: Mapping[tuple, str], employee_id: str, check_type: str):
    def resolve(start: date, end: date) -> str:
        return index.get((employee_id, check_type, start, end), UNDETERMINED)
    return resolve


def _finite_digits(denominator: int) -> int | None:
    twos = fives = 0
    while denominator % 2 == 0:
        twos += 1
        denominator //= 2
    while denominator % 5 == 0:
        fives += 1
        denominator //= 5
    return max(twos, fives) if denominator == 1 else None


def quantity_text(value: Fraction) -> str:
    """Exact finite decimals; nonterminating decimals truncate after 7 digits."""
    if value < 0:
        raise ValueError("발생량은 음수일 수 없습니다")
    digits = _finite_digits(value.denominator)
    if digits is not None:
        scale = 10 ** digits
        scaled = value.numerator * scale // value.denominator
        return format(Decimal(scaled).scaleb(-digits), "f")
    scale = 10 ** 7
    truncated = value.numerator * scale // value.denominator
    whole, decimals = divmod(truncated, scale)
    return f"{whole}.{decimals:07d}"


def round_final(value: Fraction, precision: int) -> str:
    """One ROUND_HALF_UP at the employee/basis summary level only."""
    if type(precision) is not int or precision not in (0, 1):
        raise ValueError("최종 반올림 자릿수는 0 또는 1만 허용합니다")
    if value < 0:
        raise ValueError("발생량은 음수일 수 없습니다")
    scale = 10 ** precision
    scaled, remainder = divmod(value.numerator * scale, value.denominator)
    if remainder * 2 >= value.denominator:
        scaled += 1
    return format(Decimal(scaled).scaleb(-precision), "f")


def prorated_quantity(
    *,
    base_days: str | int | Decimal,
    numerator: int,
    denominator: int,
    method: str = "소정근로일 기준",
) -> Fraction:
    """Explicit external day/month counts; no implicit calendar/attendance guess."""
    if method not in METHODS:
        raise ValueError("비례연차 산정방식이 올바르지 않습니다")
    if type(numerator) is not int or type(denominator) is not int:
        raise ValueError("비례연차 분자·분모는 정수여야 합니다")
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        raise ValueError("비례연차 분자·분모가 올바르지 않습니다")
    try:
        base = Fraction(str(base_days))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("기준 발생일수가 올바르지 않습니다") from exc
    if base <= 0:
        raise ValueError("기준 발생일수는 양수여야 합니다")
    return base * Fraction(numerator, denominator)


def _make_event(
    employee_id: str, basis: str, grant_type: str,
    grant_date: date, start: date, end: date,
    status: str, raw: Fraction | None, reason: str = "",
) -> tuple[dict[str, Any], Fraction | None]:
    detail = {
        "employee_id": employee_id,
        "basis": basis,
        "grant_type": grant_type,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "grant_date": grant_date.isoformat(),
        "calculation_result": quantity_text(raw) if raw is not None else None,
        "status": status,
        "reason": reason,
    }
    return detail, raw


def _first_fiscal_boundary(hire_date: date, fiscal_year_start: str) -> date:
    try:
        month, day = map(int, fiscal_year_start.split("-"))
        year_start = date(hire_date.year, month, day)
        if not (len(fiscal_year_start) == 5 and fiscal_year_start[2] == "-"):
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise ValueError("회계연도 시작일은 MM-DD 형식이어야 합니다") from exc
    # A hire before the fiscal boundary in the same calendar year reaches
    # that boundary first; on/after it reaches next year's boundary.
    if hire_date < year_start:
        return year_start
    return date(hire_date.year + 1, month, day)



def completed_service_years(hire_date: date, grant_date: date) -> int:
    """Completed years measured from the real hire anniversary, not fiscal years."""
    years = grant_date.year - hire_date.year
    if years <= 0:
        return 0
    return years - int(add_months(hire_date, years * 12) > grant_date)


def _fiscal_regular_grants(
    *,
    employee_id: str,
    hire_date: date,
    start: date,
    boundary: date,
    annual,
    monthly,
) -> list[tuple[dict[str, Any], Fraction | None]]:
    """Annual fiscal grant or the monthly-completion fallback for <80% attendance.

    The first eleven monthly first-year entitlements must never be counted a
    second time as a fiscal-year <80% fallback.
    """
    end = boundary - timedelta(days=1)
    status = annual(start, end)
    if status == ELIGIBLE:
        from . import annual_days_for_service_year
        service_year = completed_service_years(hire_date, boundary)
        if service_year < 1:
            return [_make_event(
                employee_id, BASIS_FISCAL, "회계연도 정기 발생",
                boundary, start, end, "판정 안됨", None,
                "연간 부여 시점의 근속기간 확인 필요",
            )]
        return [_make_event(
            employee_id, BASIS_FISCAL, "회계연도 정기 발생",
            boundary, start, end, "계산 완료",
            Fraction(annual_days_for_service_year(service_year)),
        )]
    if status == UNDETERMINED:
        return [_make_event(
            employee_id, BASIS_FISCAL, "회계연도 정기 발생",
            boundary, start, end, "판정 안됨", None,
            "직전 회계연도의 연간 근태 판정 누락·미확정",
        )]

    # Annual attendance below 80%: use prior-period monthly attendance flags.
    # For first-year monthly rights (months 1..11), do not re-award them.
    first_year_monthly_cutoff = add_months(hire_date, 11)
    entries: list[tuple[dict[str, Any], Fraction | None]] = []
    for offset in range(12):
        month_start = add_months(start, offset)
        month_end = add_months(start, offset + 1) - timedelta(days=1)
        if month_end < first_year_monthly_cutoff:
            continue
        if month_start < first_year_monthly_cutoff <= month_end:
            entries.append(_make_event(
                employee_id, BASIS_FISCAL, "80% 미달 월별 발생",
                boundary, month_start, month_end, "판정 안됨", None,
                "첫해 월별 발생기간과 회계연도 월간기간이 겹침",
            ))
            continue
        monthly_status = monthly(month_start, month_end)
        if monthly_status == NOT_ELIGIBLE:
            continue
        entries.append(_make_event(
            employee_id, BASIS_FISCAL, "80% 미달 월별 발생",
            boundary, month_start, month_end,
            "계산 완료" if monthly_status == ELIGIBLE else "판정 안됨",
            Fraction(1) if monthly_status == ELIGIBLE else None,
            "월간 근태 판정 누락·미확정" if monthly_status == UNDETERMINED else "",
        ))
    return entries


def calculate_employee(
    *,
    employee_id: str,
    hire_date: date,
    as_of_date: date,
    basis: str,
    flag_index: Mapping[tuple, str],
    termination_date: date | None = None,
    rounding_digits: int = 1,
    fiscal_year_start: str = "01-01",
    proration_method: str = "소정근로일 기준",
    proration_facts: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return one employee summary + dated details, with no rounding of events.

    as_of_date is the cutoff of its calendar-year calculation window:
    01-01 through as_of_date. Previous years may supply attendance evidence but
    their entitlement amounts are never added to this year's summary.
    Fiscal mode uses first proration, then regular prior-fiscal-year grants.
    """
    if not employee_id or not isinstance(employee_id, str):
        raise ValueError("employee_id가 필요합니다")
    if basis not in BASES:
        raise ValueError("basis가 올바르지 않습니다")
    if type(rounding_digits) is not int or rounding_digits not in (0, 1):
        raise ValueError("최종 반올림 자릿수는 0 또는 1만 허용합니다")
    hire = strict_date(hire_date, "hire_date")
    as_of = strict_date(as_of_date, "as_of_date")
    terminated = strict_date(termination_date, "termination_date") if termination_date else None
    if terminated and terminated < hire:
        raise ValueError("퇴사일이 입사일보다 빠릅니다")
    effective_as_of = min(as_of, terminated) if terminated else as_of
    calculation_start = date(as_of.year, 1, 1)
    results: list[tuple[dict[str, Any], Fraction | None]] = []
    monthly = _resolver(flag_index, employee_id, "월간")
    annual = _resolver(flag_index, employee_id, "연간")

    if basis in (BASIS_ANNIVERSARY, BASIS_MONTHLY):
        # Historical periods are evaluated only to locate anniversary grants.
        # They do not enter this calendar year's output or uncertainty status.
        grants = calculate_anniversary_grants(
            hire_date=hire, as_of_date=effective_as_of,
            monthly_eligibility=monthly, annual_eligibility=annual,
        )
        for grant in grants:
            if not calculation_start <= grant["grant_date"] <= effective_as_of:
                continue
            if basis == BASIS_MONTHLY and grant["grant_type"] != "monthly":
                continue
            raw = (Fraction(grant["raw_days"])
                   if grant["raw_days"] is not None else None)
            status = "계산 완료" if raw is not None else "판정 안됨"
            results.append(_make_event(
                employee_id, basis,
                {"monthly": "월별 발생", "annual": "연간 발생",
                 "monthly_under_80": "80% 미달 월별 발생"}[grant["grant_type"]],
                grant["grant_date"], grant["period_start"], grant["period_end"],
                status, raw, "근태 판정 누락·미확정" if raw is None else "",
            ))
    else:
        first_boundary = _first_fiscal_boundary(hire, fiscal_year_start)
        boundary = first_boundary
        previous_boundary = hire
        while boundary <= effective_as_of:
            # Fiscal grants from older calendar years are not recalculated or
            # added to this year's report. In particular, historical first-year
            # proration evidence is NOT required for later regular-year runs.
            if boundary >= calculation_start:
                start, end = previous_boundary, boundary - timedelta(days=1)
                if boundary == first_boundary:
                    flag = annual(start, end)
                    if flag != ELIGIBLE:
                        results.append(_make_event(
                            employee_id, basis, "최초 회계연도 비례",
                            boundary, start, end, "판정 안됨", None,
                            "해당기간 근태 판정 누락·미확정 또는 요건 미충족",
                        ))
                    elif proration_facts is None:
                        results.append(_make_event(
                            employee_id, basis, "최초 회계연도 비례",
                            boundary, start, end, "판정 안됨", None,
                            "비례 산정용 소정근로일·달력일·월수 집계 누락",
                        ))
                    else:
                        fact_start = strict_date(proration_facts.get("period_start"), "period_start")
                        fact_end = strict_date(proration_facts.get("period_end"), "period_end")
                        if (fact_start, fact_end) != (start, end):
                            raise ValueError("비례 산정기간이 근속기간과 일치하지 않습니다")
                        if proration_facts.get("method") != proration_method:
                            raise ValueError("비례 산정방식이 입력 집계와 다릅니다")
                        raw = prorated_quantity(
                            base_days=proration_facts.get("base_days", 15),
                            numerator=proration_facts.get("numerator"),
                            denominator=proration_facts.get("denominator"),
                            method=proration_method,
                        )
                        results.append(_make_event(
                            employee_id, basis, "최초 회계연도 비례",
                            boundary, start, end, "계산 완료", raw,
                        ))
                else:
                    results.extend(_fiscal_regular_grants(
                        employee_id=employee_id, hire_date=hire,
                        start=start, boundary=boundary,
                        annual=annual, monthly=monthly,
                    ))
            previous_boundary = boundary
            boundary = date(boundary.year + 1, boundary.month, boundary.day)
    unresolved = any(raw is None for _, raw in results)
    total = sum((raw for _, raw in results if raw is not None), Fraction(0))
    summary = {
        "employee_id": employee_id,
        "basis": basis,
        "calculation_result": None if unresolved else quantity_text(total),
        "granted_days": None if unresolved else round_final(total, rounding_digits),
        "status": "판정 안됨" if unresolved else "계산 완료",
    }
    return summary, [row for row, _raw in results]
