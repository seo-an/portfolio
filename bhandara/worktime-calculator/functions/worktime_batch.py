"""Standalone Worktime batch calculation from canonical source-mapping results.

This is a pure, side-effect-free orchestration boundary. Existing Worktime
calculation rules remain owned by worktime_source_adapter/worktime_daily.
Failures are recorded per employee/day; unrelated valid days still calculate.
A computed Worktime Result is NEVER a closed/approved Worktime period.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping

try:
    from .worktime_source_adapter import calculate_from_monthly_records
except ImportError:
    from worktime_source_adapter import calculate_from_monthly_records


class WorktimeBatchError(ValueError):
    pass


def _date(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise WorktimeBatchError(f"{field}: YYYY-MM-DD required")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise WorktimeBatchError(f"{field}: YYYY-MM-DD required") from exc
    if result.isoformat() != value:
        raise WorktimeBatchError(f"{field}: canonical YYYY-MM-DD required")
    return value


def _identity(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _issue(code: str, message: str, *, severity: str = "ERROR",
           source: str = "", row_number: int | None = None,
           employee_id: str = "", worker_id: str = "",
           work_date: str = "") -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "source": source,
        "row_number": row_number,
        "employee_id": employee_id,
        "worker_id": worker_id,
        "work_date": work_date,
    }


def _sources(bundle: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    names = config.get("source_names", {})
    if not isinstance(names, Mapping):
        raise WorktimeBatchError("source_names must be a mapping")
    available = bundle.get("sources")
    if not isinstance(available, Mapping):
        raise WorktimeBatchError("normalized bundle.sources is required")
    result = {}
    for key in ("employees", "schedule", "attendance"):
        name = names.get(key, key)
        if not isinstance(name, str) or not name or name not in available:
            raise WorktimeBatchError(f"normalized bundle missing source: {key} ({name})")
        item = available[name]
        if not isinstance(item, Mapping) or not isinstance(item.get("rows"), list):
            raise WorktimeBatchError(f"{name}: canonical rows list required")
        if not isinstance(item.get("lineage"), list):
            raise WorktimeBatchError(f"{name}: source lineage list required")
        result[key] = {"name": name, **item}
    if len({s["name"] for s in result.values()}) != 3:
        raise WorktimeBatchError("employee, schedule and attendance sources must be distinct")
    return result


def _accepted_with_lineage(source: Mapping[str, Any], issues: list[dict[str, Any]]):
    accepted = [entry for entry in source["lineage"]
                if isinstance(entry, Mapping) and entry.get("status") == "ACCEPTED"]
    rows = source["rows"]
    if len(accepted) != len(rows):
        raise WorktimeBatchError(f"{source['name']}: canonical row/lineage count mismatch")
    for row, entry in zip(rows, accepted):
        if not isinstance(row, Mapping):
            raise WorktimeBatchError(f"{source['name']}: canonical row must be an object")
        yield row, entry.get("row_number")


def _upstream_issues(bundle: Mapping[str, Any],
                     sources: Mapping[str, Mapping[str, Any]],
                     source_review: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    issues = []
    if source_review is not None:
        if (not isinstance(source_review, Mapping) or
                source_review.get("batch_id") != bundle.get("batch_id")):
            raise WorktimeBatchError("source review batch_id does not match normalized input")
        for value in source_review.get("issues", []):
            if not isinstance(value, Mapping):
                raise WorktimeBatchError("source review issues must be objects")
            issues.append(_issue(
                str(value.get("code", "SOURCE_REVIEW")),
                str(value.get("message", "Upstream mapping review required")),
                severity=str(value.get("severity", "ERROR")),
                source=str(value.get("source", "")),
                row_number=value.get("row_number"),
            ))
    for item in sources.values():
        for entry in item["lineage"]:
            if entry.get("status") != "REJECTED":
                continue
            issues.append(_issue(
                "SOURCE_ROW_REJECTED",
                "Canonical source excluded this row: " +
                ", ".join(str(x) for x in entry.get("issue_codes", [])),
                source=str(item["name"]),
                row_number=entry.get("row_number"),
            ))
    if bundle.get("status") != "READY_FOR_CALCULATION":
        issues.append(_issue(
            "UPSTREAM_NORMALIZATION_BLOCKED",
            "Source mapping was not clean; calculation may cover only part of the input",
            source="source_mapping",
        ))
    return issues


def _read_roster(source: Mapping[str, Any], issues: list[dict[str, Any]]) -> dict[str, str]:
    roster: dict[str, str] = {}
    worker_ids: set[str] = set()
    for row, line in _accepted_with_lineage(source, issues):
        employee_id = _identity(row.get("employee_id"))
        worker_id = _identity(row.get("worker_id"))
        if not employee_id or not worker_id or employee_id in roster or worker_id in worker_ids:
            issues.append(_issue(
                "ROSTER_ID_INVALID", "unique employee_id and worker_id required",
                source=source["name"], row_number=line,
                employee_id=employee_id, worker_id=worker_id,
            ))
            continue
        roster[employee_id] = worker_id
        worker_ids.add(worker_id)
    if not roster:
        issues.append(_issue(
            "ROSTER_EMPTY", "No valid workers in independently supplied employee roster",
            source=source["name"],
        ))
    return roster


def _index_source(source: Mapping[str, Any], roster: Mapping[str, str],
                  start: str, end: str,
                  issues: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row, line in _accepted_with_lineage(source, issues):
        employee_id = _identity(row.get("employee_id"))
        day = row.get("work_date")
        if not employee_id or not isinstance(day, str):
            issues.append(_issue(
                "WORKTIME_SOURCE_KEY_INVALID", "employee_id and work_date are required",
                source=source["name"], row_number=line, employee_id=employee_id,
            ))
            continue
        try:
            _date(day, "work_date")
        except WorktimeBatchError:
            issues.append(_issue(
                "WORKTIME_DATE_INVALID", "canonical work_date required",
                source=source["name"], row_number=line, employee_id=employee_id,
            ))
            continue
        if not start <= day <= end:
            issues.append(_issue(
                "WORKTIME_OUTSIDE_PERIOD", "date is outside requested Worktime period",
                source=source["name"], row_number=line,
                employee_id=employee_id, work_date=day,
            ))
            continue
        if employee_id not in roster:
            issues.append(_issue(
                "WORKTIME_UNKNOWN_EMPLOYEE", "employee absent from independent roster",
                source=source["name"], row_number=line,
                employee_id=employee_id, work_date=day,
            ))
            continue
        if row.get("worker_id") != roster[employee_id]:
            issues.append(_issue(
                "WORKTIME_WORKER_ID_CONFLICT", "canonical worker ID disagrees with roster",
                source=source["name"], row_number=line,
                employee_id=employee_id, worker_id=roster[employee_id],
                work_date=day,
            ))
            continue
        key = (employee_id, day)
        if key in result:
            issues.append(_issue(
                "WORKTIME_DUPLICATE_DAY", "duplicate employee/day canonical source",
                source=source["name"], row_number=line,
                employee_id=employee_id, worker_id=roster[employee_id],
                work_date=day,
            ))
            # Invalidates this key, including the earlier entry.
            result[key]["duplicate"] = True
            continue
        result[key] = {"row": dict(row), "row_number": line, "duplicate": False}
    return result


def _approval_index(config: Mapping[str, Any],
                    issues: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    source = config.get("approvals", [])
    if not isinstance(source, list):
        raise WorktimeBatchError("approvals must be a list of employee/date objects")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for index, row in enumerate(source, start=1):
        if not isinstance(row, Mapping):
            raise WorktimeBatchError(f"approvals[{index}] must be an object")
        employee_id = _identity(row.get("employee_id"))
        day = row.get("work_date")
        if not employee_id:
            raise WorktimeBatchError(f"approvals[{index}].employee_id required")
        _date(day, f"approvals[{index}].work_date")
        key = (employee_id, day)
        if key in result:
            raise WorktimeBatchError(f"duplicate approvals for {employee_id}/{day}")
        result[key] = {k: v for k, v in row.items()
                       if k not in ("employee_id", "work_date")}
    return result


def _assignments(config: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    value = config.get("worktime_assignments")
    if not isinstance(value, Mapping):
        raise WorktimeBatchError("worktime_assignments must be an employee_id keyed mapping")
    if any(not isinstance(key, str) or not isinstance(item, Mapping)
           for key, item in value.items()):
        raise WorktimeBatchError("worktime_assignments must contain employee mappings")
    return dict(value)


def calculate_worktime_batch(
    bundle: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    source_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate independently on each scheduled employee/day.

    Issue and result records are retained even when other days fail. The
    adapter's factual results and REVIEW flags remain unchanged.
    """
    if not isinstance(bundle, Mapping) or bundle.get("schema_version") != "0.1":
        raise WorktimeBatchError("normalized bundle schema_version 0.1 required")
    if not isinstance(config, Mapping) or config.get("schema_version") != "0.1":
        raise WorktimeBatchError("worktime config schema_version 0.1 required")
    start = _date(config.get("period_from"), "period_from")
    end = _date(config.get("period_to"), "period_to")
    if end < start:
        raise WorktimeBatchError("period_to precedes period_from")
    sources = _sources(bundle, config)
    issues = _upstream_issues(bundle, sources, source_review)
    roster = _read_roster(sources["employees"], issues)
    schedule = _index_source(sources["schedule"], roster, start, end, issues)
    attendance = _index_source(sources["attendance"], roster, start, end, issues)
    approvals = _approval_index(config, issues)
    assignments = _assignments(config)
    rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    coverage = {worker_id: 0 for worker_id in roster.values()}
    for key in sorted(set(attendance) - set(schedule)):
        employee_id, day = key
        issues.append(_issue(
            "ATTENDANCE_WITHOUT_SCHEDULE",
            "Attendance has no matching scheduled employee/date",
            source=sources["attendance"]["name"],
            row_number=attendance[key]["row_number"],
            employee_id=employee_id, worker_id=roster[employee_id], work_date=day,
        ))
        records.append({"employee_id": employee_id, "worker_id": roster[employee_id],
                        "work_date": day, "status": "ERROR", "issue_codes": ["ATTENDANCE_WITHOUT_SCHEDULE"],
                        "schedule_row_number": None,
                        "attendance_row_number": attendance[key]["row_number"]})
    for key in sorted(schedule):
        employee_id, day = key
        worker_id = roster[employee_id]
        coverage[worker_id] += 1
        sched = schedule[key]
        observed = attendance.get(key)
        record = {
            "employee_id": employee_id, "worker_id": worker_id, "work_date": day,
            "schedule_row_number": sched["row_number"],
            "attendance_row_number": observed["row_number"] if observed else None,
            "status": "", "issue_codes": [],
        }
        if sched["duplicate"] or (observed and observed["duplicate"]):
            record["status"] = "ERROR"
            record["issue_codes"].append("WORKTIME_DUPLICATE_DAY")
        elif observed is None and str(sched["row"].get("day_type", "")).upper() in ("OFF", "HOLIDAY"):
            record["status"] = "SKIPPED"
            record["issue_codes"].append("UNWORKED_OFF_OR_HOLIDAY")
        else:
            try:
                result = calculate_from_monthly_records(
                    [sched["row"]],
                    [observed["row"]] if observed else [],
                    worker_ids={employee_id: worker_id},
                    worktime_assignments={employee_id: assignments.get(employee_id, {})},
                    approvals={key: approvals.get(key, {})},
                )
            except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
                record["status"] = "ERROR"
                record["issue_codes"].append("WORKTIME_CALCULATION_FAILED")
                issues.append(_issue(
                    "WORKTIME_CALCULATION_FAILED",
                    f"Worktime adapter rejected employee/day: {type(exc).__name__}: {exc}",
                    source=sources["schedule"]["name"],
                    row_number=sched["row_number"],
                    employee_id=employee_id, worker_id=worker_id, work_date=day,
                ))
            else:
                if len(result["rows"]) != 1:
                    raise WorktimeBatchError("single-day Worktime adapter returned unexpected row count")
                calculated = result["rows"][0]
                rows.append(calculated)
                flags = calculated["validation_flags"]
                record["status"] = "REVIEW" if flags else "CALCULATED"
                record["issue_codes"].extend(str(flag["code"]) for flag in flags)
                for flag in flags:
                    issues.append(_issue(
                        str(flag["code"]), str(flag.get("message", "Worktime review required")),
                        severity="REVIEW", source=sources["attendance"]["name"],
                        row_number=observed["row_number"] if observed else None,
                        employee_id=employee_id, worker_id=worker_id, work_date=day,
                    ))
        records.append(record)
    for worker_id, count in sorted(coverage.items()):
        if count == 0:
            issues.append(_issue(
                "WORKER_WITHOUT_SCHEDULE",
                "Employee appears in roster but has no scheduled days in the requested period; verify coverage",
                severity="REVIEW", source=sources["employees"]["name"], worker_id=worker_id,
            ))
    for key in sorted(set(approvals) - set(schedule)):
        employee_id, day = key
        issues.append(_issue(
            "UNMATCHED_APPROVAL",
            "Approval refers to employee/date absent from scheduled source",
            severity="REVIEW", source="approvals",
            employee_id=employee_id, worker_id=roster.get(employee_id, ""), work_date=day,
        ))
    issues.sort(key=lambda item: (item["source"], item["row_number"] or 0,
                                  item["employee_id"], item["work_date"], item["code"]))
    if any(item["severity"] == "ERROR" for item in issues):
        status = "BLOCKED"
    elif any(item["severity"] == "REVIEW" for item in issues):
        status = "REVIEW_REQUIRED"
    else:
        status = "CALCULATED_UNCLOSED"
    return {
        "schema_version": "0.1",
        "status": status,
        "finalizable": False,
        "period_from": start,
        "period_to": end,
        "source_batch_id": bundle.get("batch_id"),
        "source_hashes": {value["name"]: value.get("source_sha256", "")
                          for value in sources.values()},
        "covered_worker_ids": sorted(roster.values()),
        "rows": sorted(rows, key=lambda row: (row["worker_id"], row["work_date"])),
        "candidate_expected_keys": [
            {"worker_id": row["worker_id"], "work_date": row["work_date"]}
            for row in sorted(rows, key=lambda row: (row["worker_id"], row["work_date"]))
        ],
        "records": sorted(records, key=lambda row: (row["worker_id"], row["work_date"])),
        "issues": issues,
        "coverage_verified": False,
        "close_receipt": None,
    }
