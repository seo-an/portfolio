"""Independent review of worked/rest minutes against an externally reviewed policy.

Does not reconstruct worked hours from device access, create overtime pay items,
accept employee leave, approve a statutory exception or close Worktime.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Mapping

DAY_MIN = 24 * 60
WAIVER_EFFECTIVE = date(2026, 12, 10)
SUPPORTED_ACTORS = {"EMPLOYEE", "EXTERNAL_SERVICE"}
SUPPORTED_SYSTEMS = {"standard"}


class ComplianceInputError(ValueError):
    """Request-level invalid policy or argument."""


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _minutes(value: Any) -> int | None:
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value and value.isascii() and value.isdecimal():
        return int(value)
    return None


def _required_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, Mapping):
        raise ComplianceInputError("policy must be a mapping")
    if policy.get("schema_version") != "0.1":
        raise ComplianceInputError("policy schema_version 0.1 required")
    name = policy.get("policy_ref")
    if not isinstance(name, str) or not name.strip():
        raise ComplianceInputError("policy_ref is required")
    values: dict[str, Any] = {"policy_ref": name}
    for field in ("daily_standard_min", "weekly_standard_min",
                  "weekly_limit_min", "rest_every_work_min",
                  "rest_per_block_min", "break_overrun_tolerance_min"):
        value = _minutes(policy.get(field))
        if value is None:
            raise ComplianceInputError(f"{field} must be a non-negative integer")
        values[field] = value
    if not (0 < values["daily_standard_min"] < values["weekly_standard_min"]
            <= values["weekly_limit_min"] and values["rest_every_work_min"] > 0
            and values["rest_per_block_min"] > 0):
        raise ComplianceInputError("policy limits are inconsistent")
    return values


def _issue(code: str, source: str, row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "code": code, "source": source,
        "employee_id": str(row.get("employee_id") or "").strip(),
        "work_date": str(row.get("work_date") or ""),
        "source_ref": str(row.get("source_ref") or ""),
        "row_number": row.get("_row_number"),
    }


def _daily_index(rows: Iterable[Mapping[str, Any]], begin: date, end: date
                 ) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], list[dict[str, Any]]]:
    if isinstance(rows, (Mapping, str, bytes)):
        raise ComplianceInputError("daily_rows must be row iterable")
    indexed: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    issues = []
    try:
        iterator = iter(rows)
    except TypeError as exc:
        raise ComplianceInputError("daily_rows must be row iterable") from exc
    for row in iterator:
        if not isinstance(row, Mapping):
            raise ComplianceInputError("daily row must be mapping")
        employee = str(row.get("employee_id") or "").strip()
        day = _date(row.get("work_date"))
        if not employee or day is None:
            issues.append(_issue("DAILY_KEY_INVALID", "daily", row))
        elif not begin <= day <= end:
            issues.append(_issue("DAILY_OUTSIDE_PERIOD", "daily", row))
        else:
            indexed[(employee, day.isoformat())].append(dict(row))
    return indexed, issues


def _weekly_index(rows: Iterable[Mapping[str, Any]], begin: date, end: date
                  ) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], list[dict[str, Any]]]:
    if isinstance(rows, (Mapping, str, bytes)):
        raise ComplianceInputError("weekly_coverage must be row iterable")
    indexed: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    issues = []
    try:
        iterator = iter(rows)
    except TypeError as exc:
        raise ComplianceInputError("weekly_coverage must be row iterable") from exc
    for row in iterator:
        if not isinstance(row, Mapping):
            raise ComplianceInputError("weekly_coverage row must be mapping")
        employee = str(row.get("employee_id") or "").strip()
        week = _date(row.get("week_start"))
        if not employee or week is None or week.weekday() != 0:
            issues.append(_issue("WEEKLY_KEY_INVALID", "weekly_coverage", row))
        elif week + timedelta(days=6) < begin or week > end:
            issues.append(_issue("WEEKLY_OUTSIDE_PERIOD", "weekly_coverage", row))
        else:
            indexed[(employee, week.isoformat())].append(dict(row))
    return indexed, issues


def _required_rest(worked: int, day: date, policy: Mapping[str, int],
                   waiver_ref: str, codes: list[str]) -> int:
    required = worked // policy["rest_every_work_min"] * policy["rest_per_block_min"]
    if waiver_ref:
        # In the 2026 amendment, the specifically documented exact-4h
        # request is not a blanket waiver for longer shifts or earlier days.
        if day >= WAIVER_EFFECTIVE and worked == 240:
            required = 0
        else:
            codes.append("BREAK_WAIVER_NOT_APPLICABLE")
    return required


def _rest_deviation(
    required: int | None,
    actual: int | None,
    *,
    verified: bool,
    coverage_complete: bool,
    reason: str | None,
) -> dict[str, Any]:
    """Actual confirmed rest minus minimum required rest, never payroll time."""
    diff = actual - required if verified and actual is not None and required is not None else None
    return {
        "required_min": required,
        "recorded_min": actual,
        "delta_min": diff,
        "direction": ("UNKNOWN" if diff is None else
                      "NEGATIVE" if diff < 0 else
                      "POSITIVE" if diff > 0 else "ZERO"),
        "coverage_complete": coverage_complete,
        "shortfall_confirmable": bool(diff is not None and diff < 0 and coverage_complete),
        "reason": reason,
    }


def _daily_one(employee: str, day: str, data: list[dict[str, Any]],
               policy: Mapping[str, Any]) -> dict[str, Any]:
    codes = []
    if len(data) > 1:
        codes.append("DUPLICATE_DAILY_FACT")
    if len(data) != 1:
        return {
            "employee_id": employee, "work_date": day,
            "status": "REVIEW_REQUIRED", "worked_min": None,
            "rest_min": None, "required_rest_min": None,
            "planned_break_min": None,
            "rest_deviation": _rest_deviation(
                None, None, verified=False, coverage_complete=False, reason=None
            ), "review_codes": sorted(set(codes)),
            "source_ref": None,
        }
    row = data[0]
    actor = str(row.get("actor_type") or "UNKNOWN").upper()
    system = str(row.get("worktime_system") or "UNKNOWN").lower()
    if actor not in SUPPORTED_ACTORS:
        codes.append("ACTOR_TYPE_UNKNOWN")
    elif actor != "EMPLOYEE":
        codes.append("RELATIONSHIP_POLICY_REVIEW")
    if system not in SUPPORTED_SYSTEMS:
        codes.append("WORKTIME_SYSTEM_REVIEW")
    if str(row.get("policy_ref") or "").strip() != policy["policy_ref"]:
        codes.append("POLICY_REF_MISMATCH")
    worked = _minutes(row.get("worked_min"))
    rest = _minutes(row.get("rest_min"))
    planned = _minutes(row.get("planned_break_min"))
    raw_reason = row.get("rest_reason")
    if raw_reason is None or raw_reason == "":
        reason = None
    elif isinstance(raw_reason, str):
        reason = raw_reason.strip() or None
    else:
        reason = None
        codes.append("INVALID_REST_REASON")
    if worked is None:
        codes.append("WORK_MINUTES_INVALID")
    if rest is None:
        codes.append("REST_MINUTES_UNKNOWN")
    if row.get("worked_verified") is not True or not str(row.get("worked_evidence_ref") or "").strip():
        codes.append("WORK_EVIDENCE_UNVERIFIED")
    if row.get("rest_verified") is not True or not str(row.get("rest_evidence_ref") or "").strip():
        codes.append("REST_EVIDENCE_UNVERIFIED")
    if row.get("rest_within_workday_verified") is not True:
        codes.append("REST_PLACEMENT_UNVERIFIED")
    coverage = row.get("rest_coverage_complete")
    if type(coverage) is not bool:
        codes.append("REST_COVERAGE_INVALID")
        coverage = False
    if coverage and not str(row.get("rest_coverage_ref") or "").strip():
        codes.append("REST_COVERAGE_EVIDENCE_MISSING")
        coverage = False
    applicable = actor == "EMPLOYEE" and system == "standard" and (
        str(row.get("policy_ref") or "").strip() == policy["policy_ref"]
    )
    worked_supported = worked is not None and row.get("worked_verified") is True and bool(
        str(row.get("worked_evidence_ref") or "").strip()
    )
    rest_supported = rest is not None and row.get("rest_verified") is True and bool(
        str(row.get("rest_evidence_ref") or "").strip()
    ) and row.get("rest_within_workday_verified") is True

    required = None
    if applicable and worked_supported:
        waiver = str(row.get("four_hour_waiver_ref") or "").strip()
        required = _required_rest(worked, date.fromisoformat(day), policy, waiver, codes)
        if worked > policy["daily_standard_min"]:
            codes.append("DAILY_STANDARD_EXCEEDED_REVIEW")
        if rest_supported:
            if rest < required:
                if coverage:
                    codes.append("REST_SHORTFALL_REVIEW")
                else:
                    codes.append("REST_SHORTFALL_UNDETERMINED")
        else:
            codes.append("REST_SUFFICIENCY_UNDETERMINED")
    if rest_supported and planned is not None and (
        rest > planned + policy["break_overrun_tolerance_min"]
    ):
        # Company/planned break deviation; NOT a statutory upper limit.
        codes.append("COMPANY_BREAK_OVERRUN_REVIEW")
    if worked is not None and rest is not None and worked + rest > DAY_MIN:
        codes.append("TOTAL_SPAN_REVIEW")
    return {
        "employee_id": employee, "work_date": day,
        "status": "PASS" if not codes else "REVIEW_REQUIRED",
        "worked_min": worked, "rest_min": rest,
        "required_rest_min": required,
        "planned_break_min": planned,
        "rest_deviation": _rest_deviation(
            required, rest, verified=rest_supported,
            coverage_complete=coverage, reason=reason,
        ),
        "review_codes": sorted(set(codes)),
        "source_ref": str(row.get("source_ref") or ""),
    }


def _week_key(employee: str, work_date: str) -> tuple[str, str]:
    day = date.fromisoformat(work_date)
    return employee, (day - timedelta(days=day.weekday())).isoformat()


def _weekly_one(key: tuple[str, str], days: list[dict[str, Any]],
                coverage_rows: list[dict[str, Any]],
                begin: date, end: date, policy: Mapping[str, Any]) -> dict[str, Any]:
    employee, week = key
    codes = []
    if len(coverage_rows) > 1:
        codes.append("DUPLICATE_WEEKLY_COVERAGE")
    coverage = coverage_rows[0] if len(coverage_rows) == 1 else {}
    if not days:
        codes.append("WEEK_WITHOUT_DAILY_FACTS")
    week_start = date.fromisoformat(week)
    if week_start < begin or week_start + timedelta(days=6) > end:
        codes.append("WEEK_CROSSES_INPUT_PERIOD")
    covered = coverage.get("coverage_complete") is True and bool(
        str(coverage.get("evidence_ref") or "").strip()
    )
    if not covered:
        codes.append("WEEKLY_COVERAGE_UNVERIFIED")
    exceptions = str(coverage.get("exception_status") or "UNKNOWN").upper()
    if exceptions != "NONE":
        codes.append("WEEKLY_EXCEPTION_REVIEW")
    total = None
    if days and all(
        day["worked_min"] is not None and
        not any(code in day["review_codes"] for code in (
            "WORK_MINUTES_INVALID", "WORK_EVIDENCE_UNVERIFIED",
            "DUPLICATE_DAILY_FACT", "RELATIONSHIP_POLICY_REVIEW",
            "ACTOR_TYPE_UNKNOWN", "WORKTIME_SYSTEM_REVIEW", "POLICY_REF_MISMATCH"
        ))
        for day in days
    ):
        total = sum(day["worked_min"] for day in days)
        if covered and week_start >= begin and week_start + timedelta(days=6) <= end:
            if total > policy["weekly_standard_min"]:
                codes.append("WEEKLY_STANDARD_EXCEEDED_REVIEW")
            if exceptions == "NONE" and total > policy["weekly_limit_min"]:
                codes.append("WEEKLY_LIMIT_EXCEEDED_REVIEW")
    return {
        "employee_id": employee, "week_start": week,
        "week_end": (week_start + timedelta(days=6)).isoformat(),
        "status": "PASS" if not codes else "REVIEW_REQUIRED",
        "total_worked_min": total,
        "coverage_ref": str(coverage.get("evidence_ref") or ""),
        "policy_ref": policy["policy_ref"],
        "review_codes": sorted(set(codes)),
    }


def review_worktime_compliance(
    daily_rows: Iterable[Mapping[str, Any]],
    weekly_coverage: Iterable[Mapping[str, Any]],
    policy: Mapping[str, Any],
    *,
    period_from: str,
    period_to: str,
) -> dict[str, Any]:
    """Return daily/weekly *review findings*, never final legal determinations."""
    begin, end = _date(period_from), _date(period_to)
    if begin is None or end is None or end < begin:
        raise ComplianceInputError("period must be ordered YYYY-MM-DD")
    rules = _required_policy(policy)
    indexed, issues = _daily_index(daily_rows, begin, end)
    weekly, weekly_issues = _weekly_index(weekly_coverage, begin, end)
    issues.extend(weekly_issues)
    daily = [
        _daily_one(employee, day, indexed[(employee, day)], rules)
        for employee, day in sorted(indexed)
    ]
    by_week: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in daily:
        by_week[_week_key(row["employee_id"], row["work_date"])].append(row)
    week_keys = set(by_week) | set(weekly)
    weeks = [
        _weekly_one(key, by_week.get(key, []), weekly.get(key, []), begin, end, rules)
        for key in sorted(week_keys)
    ]
    if not daily and not weeks:
        issues.append({"code": "NO_COMPARABLE_ROWS", "source": "daily",
                       "employee_id": "", "work_date": "", "source_ref": "",
                       "row_number": None})
    return {
        "schema_version": "0.1",
        "module": "worktime-compliance",
        "status": ("PASS" if not issues and daily and weeks
                   and all(row["status"] == "PASS" for row in daily + weeks)
                   else "REVIEW_REQUIRED"),
        "policy_ref": rules["policy_ref"],
        "period_from": begin.isoformat(), "period_to": end.isoformat(),
        "daily": daily, "weekly": weeks, "source_issues": issues,
        "approved": False, "legal_conclusion": False, "payroll_finalizable": False,
        "notice": "확인된 근로·휴게시간과 적용 정책에 대한 검토 결과이며 법 위반·연장근무 승인·급여를 확정하지 않습니다.",
    }
