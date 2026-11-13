"""Worktime-only bridge: shared Excel -> canonical source bundle.

This adapter is independent of Payroll, PTO and any cloud/agent environment.
Security-reader events are evidence, not automatically approved attendance.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from bhandara.common.io.input_layout import (
    InputLayoutError, as_clock, as_day, hash_file,
    read_id_map, read_sheet, role,
)
from .external_identity import load_external_workers, resolve_worktime_actor


def _lineage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"status": "ACCEPTED", "row_number": row["_row_number"], "issue_codes": []}
        for row in rows
    ]


def _unique(rows: list[dict[str, Any]], name: str, keys: tuple[str, ...]) -> None:
    observed: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(str(row.get(k) or "").strip() for k in keys)
        if not all(key):
            raise InputLayoutError(f"{name} row {row['_row_number']}: empty key")
        if key in observed:
            raise InputLayoutError(f"{name} row {row['_row_number']}: duplicate {key}")
        observed.add(key)


def _source(name: str, path: Path, rows: list[dict[str, Any]],
            projected: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != len(projected):
        raise InputLayoutError(f"{name}: source row loss detected")
    return {
        "rows": projected,
        "source_sha256": hash_file(path),
        "lineage": _lineage(rows),
    }


def _employee_source(input_root: Path, identities: Mapping[str, Mapping[str, str]],
                     external: Mapping[str, Mapping[str, Any]],
                     overrides: Mapping | None):
    path = role(input_root, "common", "employees", overrides)
    rows = read_sheet(path, ("employee_id", "hire_date", "termination_date", "work_system"))
    _unique(rows, "employees", ("employee_id",))
    employees = {str(x["employee_id"]).strip() for x in rows}
    if employees != set(identities):
        missing = sorted(employees - set(identities))
        unknown = sorted(set(identities) - employees)
        raise InputLayoutError(
            f"id-map.xlsx / employee.xlsx mismatch: unmapped={missing[:10]}, "
            f"no_employee={unknown[:10]}"
        )
    result = [
        {"employee_id": str(x["employee_id"]).strip(),
         "worker_id": identities[str(x["employee_id"]).strip()]["worker_id"]}
        for x in rows
    ]
    source = _source("employees", path, rows, result)
    # The core Worktime batch still calls this the "employees" source, but
    # these additional entries are declared external Worktime participants,
    # NOT employee records, and never written to common/employee.xlsx.
    for worker in external.values():
        source["rows"].append({
            "employee_id": worker["worker_id"],
            "worker_id": worker["worker_id"],
            "actor_type": "EXTERNAL_SERVICE",
        })
        source["lineage"].append({
            "status": "ACCEPTED",
            "row_number": worker["_row_number"],
            "source_sheet": "id-map.xlsx:EXTERNAL",
            "issue_codes": [],
        })
    return source


def _schedule_source(input_root: Path, identities: Mapping,
                     external: Mapping[str, Mapping[str, Any]],
                     overrides: Mapping | None):
    path = role(input_root, "worktime", "schedule", overrides)
    rows = read_sheet(
        path, ("employee_id", "work_date", "day_type",
               "scheduled_start", "scheduled_end", "break_min"))
    output = []
    for x in rows:
        employee_id, worker_id = resolve_worktime_actor(
            x, identities, external, filename=path.name,
        )
        output.append({
            "employee_id": employee_id,
            "worker_id": worker_id,
            "work_date": as_day(x["work_date"], "work_date"),
            "day_type": str(x["day_type"] or "").strip().upper(),
            "scheduled_start": as_clock(x["scheduled_start"], "scheduled_start"),
            "scheduled_end": as_clock(x["scheduled_end"], "scheduled_end"),
            "break_min": x["break_min"] or 0,
            "scheduled_work_hours": x.get("scheduled_work_hours"),
        })
    # Preserve duplicated employee/date rows as evidence. The existing
    # Worktime batch engine flags only the conflicting day and continues
    # computing independent employee/days instead of blocking the whole file.
    return _source("schedule", path, rows, output)


def _attendance_source(input_root: Path, identities: Mapping,
                       external: Mapping[str, Mapping[str, Any]],
                       overrides: Mapping | None):
    path = role(input_root, "worktime", "attendance", overrides)
    rows = read_sheet(path, ("employee_id", "work_date", "clock_in", "clock_out",
                             "break_min"))
    output = []
    for x in rows:
        employee_id, worker_id = resolve_worktime_actor(
            x, identities, external, filename=path.name,
        )
        output.append({
            "employee_id": employee_id,
            "worker_id": worker_id,
            "work_date": as_day(x["work_date"], "work_date"),
            "clock_in": as_clock(x["clock_in"], "clock_in"),
            "clock_out": as_clock(x["clock_out"], "clock_out"),
            "break_min": x["break_min"] or 0,
            "source": str(x.get("source") or "").strip(),
        })
    # Duplicate attendance is not silently dropped or globally rejected;
    # the existing per-day engine records both row sources for review.
    return _source("attendance", path, rows, output)


def read_shared_worktime(input_root: Path, period: str, *,
                         overrides: Mapping | None = None) -> tuple[dict, dict]:
    """Return in-memory normalized source + conservative review-only settings."""
    from bhandara.common.io.input_layout import period_bounds

    start, end = period_bounds(period)
    identities = read_id_map(input_root, overrides=overrides)
    id_map_path = role(input_root, "common", "identity", overrides)
    external = load_external_workers(id_map_path, identities)
    sources = {
        "employees": _employee_source(input_root, identities, external, overrides),
        "schedule": _schedule_source(input_root, identities, external, overrides),
        "attendance": _attendance_source(input_root, identities, external, overrides),
    }
    for name, source in sources.items():
        if not source["rows"]:
            raise InputLayoutError(f"{name}: source has no usable rows")
    digest = hashlib.sha256()
    for item in sources.values():
        digest.update(item["source_sha256"].encode())
    identity_sha = hash_file(id_map_path)
    # Both ID_MAP and the optional EXTERNAL mapping are source evidence.
    digest.update(identity_sha.encode())
    bundle = {
        "schema_version": "0.1",
        "status": "READY_FOR_CALCULATION",
        "batch_id": "shared-worktime-" + digest.hexdigest()[:16],
        "sources": sources,
        "identity_map_sha256": identity_sha,
        "external_worker_ids": sorted(external),
    }
    assignments = {
        employee_id: {
            "worktime_system": "standard",
            "rule_ref": "labor_standard_50_53",
        }
        for employee_id in identities
    }
    # If not standard, the old Worktime algorithm must be reviewed, not
    # automatically assigned a statutory approved flex-time arrangement.
    employee_rows = read_sheet(
        role(input_root, "common", "employees", overrides),
        ("employee_id", "work_system"))
    for row in employee_rows:
        work_system = str(row.get("work_system") or "").strip().upper()
        if work_system != "FIXED":
            assignments[str(row["employee_id"])] = {
                "worktime_system": "non_standard_review",
                "rule_ref": "MANUAL_REVIEW",
            }
    for worker_id in external:
        # Worktime computes observed time only. Never infer that external
        # services are employees subject to standard wage settlement.
        assignments[worker_id] = {
            "worktime_system": "non_standard_review",
            "rule_ref": "EXTERNAL_SERVICE_HOURS_REVIEW_ONLY",
        }
    config = {
        "schema_version": "0.1", "period_from": start, "period_to": end,
        "worktime_assignments": assignments,
        "approvals": [],  # Never manufacture real approvals for raw Excel facts.
    }
    return bundle, config


def run_shared_excel(input_root: str | Path, period: str,
                     output_dir: str | Path, *,
                     overrides: dict | None = None) -> int:
    """Run the untouched legacy Worktime engine with a new Excel adapter."""
    from .functions.worktime_batch import calculate_worktime_batch
    from .functions.worktime_report import write_worktime_outputs
    import json

    normalized, config = read_shared_worktime(
        Path(input_root), period, overrides=overrides
    )
    target = Path(output_dir)
    # The original Worktime reporter intentionally requires a NEW output
    # directory. Never pre-create it: that would break its safety contract.
    if target.exists():
        raise InputLayoutError(
            f"output directory already exists: {target}; choose a new path"
        )
    result = calculate_worktime_batch(normalized, config)
    result["source_hashes"]["identity_map"] = normalized["identity_map_sha256"]
    output = write_worktime_outputs(target, result)
    for name, payload in (
        ("normalized-input.json", normalized),
        ("worktime-config.json", config),
    ):
        (target / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    print(f"Worktime shared Excel: {result['status']} ({len(result['rows'])} daily rows)")
    for key, filepath in output.items():
        print(f"{key}: {filepath}")
    return 0 if result["status"] == "CALCULATED_UNCLOSED" else 2
