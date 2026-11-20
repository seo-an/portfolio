"""JSON-configured public Worktime Tool: selected Modules and one factual Excel.

Schedule, Attendance Verification and Compliance retain independent domain
contracts. This Tool only joins explicit inputs/results by selected steps.
"""
from __future__ import annotations

from datetime import date, datetime
from importlib import import_module
import json
from pathlib import Path
import re
import sys
from typing import Any

from bhandara.common.runtime.workspace import ensure_tool_workspace
from zoneinfo import ZoneInfo

from bhandara.common.io.input_layout import read_sheet, as_day, InputLayoutError
from bhandara.worktime.access_source import verify_attendance_xlsx
from bhandara.worktime.schedule.mapping import read_schedule_mapping, for_attendance_verification
from bhandara.worktime.output import build_worktime_result
from bhandara.worktime.output_excel import write_worktime_xlsx


STEPS = ("schedule", "attendance-verification", "worktime-compliance", "output")
FILES = frozenset((
    "schedule", "attendance", "access_events", "verified_work",
    "attendance_facts", "attendance_verification_result", "compliance_result",
))
LEDGER_FIELDS = ("employee_id", "work_date", "clock_in", "clock_out", "break_min")
DAILY_FIELDS = (
    "employee_id", "work_date", "actor_type", "worktime_system",
    "policy_ref", "worked_min", "worked_verified", "worked_evidence_ref",
    "rest_min", "rest_verified", "rest_evidence_ref",
    "rest_within_workday_verified", "rest_coverage_complete",
    "rest_coverage_ref",
)
WEEKLY_FIELDS = ("employee_id", "week_start", "coverage_complete",
                 "evidence_ref", "exception_status")
LEAVE_FIELDS = ("employee_id", "work_date", "attendance_type",
                "leave_type", "leave_request_id")


class WorktimeToolError(ValueError):
    """Tool config/execution boundary error, not a HR/payroll conclusion."""


def _path(value: Any, field: str, base: Path) -> Path:
    if type(value) is not str or not value.strip():
        raise WorktimeToolError(f"{field}: explicit non-empty path required")
    raw = Path(value).expanduser()
    return (raw if raw.is_absolute() else base / raw).resolve()


def _config(source: str | Path) -> dict[str, Any]:
    path = Path(source).resolve()
    if not path.is_file():
        raise WorktimeToolError(f"설정 JSON 없음: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorktimeToolError("설정 JSON을 읽을 수 없습니다") from exc
    if not isinstance(doc, dict) or doc.get("tool") != "worktime" or doc.get("schema_version") != "1.0":
        raise WorktimeToolError("tool/schema_version must be worktime/1.0")
    steps = doc.get("steps")
    if (not isinstance(steps, list) or not steps
            or any(type(step) is not str or step not in STEPS for step in steps)
            or len(set(steps)) != len(steps)):
        raise WorktimeToolError(f"steps must be unique names from {STEPS}")
    for prerequisite in ("attendance-verification", "worktime-compliance"):
        if prerequisite in steps and "output" in steps and steps.index("output") < steps.index(prerequisite):
            raise WorktimeToolError(f"steps: {prerequisite} must precede output")
    first, last = doc.get("period_from"), doc.get("period_to")
    try:
        f, t = date.fromisoformat(first), date.fromisoformat(last)
    except (TypeError, ValueError) as exc:
        raise WorktimeToolError("period_from/period_to must be YYYY-MM-DD") from exc
    if f > t or (first, last) != (f.isoformat(), t.isoformat()):
        raise WorktimeToolError("period_from/period_to must be canonical ordered dates")
    run_id = doc.get("run_id")
    if run_id == "auto":
        run_id = datetime.now(ZoneInfo("Asia/Seoul")).strftime("worktime-%Y%m%d-%H%M%S-%f")
    if type(run_id) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", run_id):
        raise WorktimeToolError("run_id must be auto or 1..64 letters/digits/-/_")
    input_root = _path(doc.get("input_root"), "input_root", path.parent)
    output_root = _path(doc.get("output_root"), "output_root", path.parent)
    if (input_root == output_root or output_root.is_relative_to(input_root)
            or input_root.is_relative_to(output_root)):
        raise WorktimeToolError("input/output roots must not contain one another")
    files = doc.get("files", {})
    if not isinstance(files, dict) or set(files) - FILES:
        raise WorktimeToolError(f"files permits only {sorted(FILES)}")
    paths = {key: _path(v, f"files.{key}", input_root) for key, v in files.items()}
    for key, location in paths.items():
        if not location.is_file():
            raise WorktimeToolError(f"files.{key}: missing input {location.name}")
    required = set()
    if set(steps) & {"schedule", "attendance-verification", "output"}:
        required.add("schedule")
    if set(steps) & {"schedule", "attendance-verification"}:
        required.add("attendance")
    if "attendance-verification" in steps:
        required.add("access_events")
    if "worktime-compliance" in steps:
        required.add("verified_work")
        if not isinstance(doc.get("policy"), dict):
            raise WorktimeToolError("worktime-compliance requires policy JSON object")
    if "output" in steps:
        if "attendance-verification" not in steps:
            required.add("attendance_verification_result")
        if "worktime-compliance" not in steps:
            required.add("compliance_result")
    missing = required - set(paths)
    if missing:
        raise WorktimeToolError(f"missing explicit input file keys: {sorted(missing)}")
    return {
        **doc, "run_id": run_id, "steps": steps, "input_root": input_root,
        "output_root": output_root, "files": paths,
    }


def _rows(path: Path, fields: tuple[str, ...], sheet: str,
          *, date_field: str = "work_date") -> list[dict[str, Any]]:
    try:
        values = read_sheet(path, fields, sheet_name=sheet)
    except (InputLayoutError, OSError) as exc:
        raise WorktimeToolError(f"{path.name}/{sheet}: {exc}") from exc
    for item in values:
        item[date_field] = as_day(item.get(date_field), date_field)
        item["source_ref"] = f"{path.name}:{sheet}"
    return values


def _safe_json_write(payload: dict[str, Any], output: Path) -> Path:
    if output.exists():
        raise WorktimeToolError(f"result already exists: {output.name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    # The pure Module result is kept for audit/reuse, not mixed into WORKTIME.
    with output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")
    return output


def _read_module_result(path: Path, *, name: str, config: dict[str, Any]) -> dict[str, Any]:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorktimeToolError(f"{path.name}: invalid JSON result") from exc
    if (not isinstance(result, dict) or result.get("module") != name
            or (result.get("period_from"), result.get("period_to")) !=
               (config["period_from"], config["period_to"])):
        raise WorktimeToolError(f"{path.name}: module or period mismatch")
    return result


def execute(config_path: str | Path) -> dict[str, str]:
    """Execute exactly the JSON-selected stages. No implicit Module invocation."""
    ensure_tool_workspace("worktime")
    config = _config(config_path)
    paths = config["files"]
    if (config["output_root"] / config["run_id"]).exists():
        raise WorktimeToolError("run_id already exists; output overwrite forbidden")
    output = config["output_root"] / config["run_id"]
    from_date, to_date = config["period_from"], config["period_to"]
    steps = config["steps"]
    schedule_rows = None
    ledger_rows = None
    verification = None
    compliance = None
    result_files: dict[str, str] = {}
    for step in steps:
        if step in ("schedule", "attendance-verification", "output") and schedule_rows is None:
            schedule_rows = read_schedule_mapping(paths["schedule"],
                                                  period_from=from_date, period_to=to_date)
        if step in ("schedule", "attendance-verification") and ledger_rows is None:
            ledger_rows = _rows(paths["attendance"], LEDGER_FIELDS, "Attendance")
        if step == "schedule":
            module = import_module("bhandara.worktime.schedule")
            report = module.reconcile_schedule(schedule_rows, ledger_rows,
                                               period_from=from_date, period_to=to_date)
            artifact = _safe_json_write(report, output / "schedule-result.json")
        elif step == "attendance-verification":
            report = verify_attendance_xlsx(
                ledger_rows, paths["access_events"], period_from=from_date,
                period_to=to_date,
                schedule_rows=for_attendance_verification(schedule_rows),
            )
            verification = report
            artifact = _safe_json_write(report, output / "attendance-verification-result.json")
        elif step == "worktime-compliance":
            module = import_module("bhandara.worktime.worktime-compliance")
            data = _rows(paths["verified_work"], DAILY_FIELDS, "DAILY")
            weekly = _rows(paths["verified_work"], WEEKLY_FIELDS,
                           "WEEKLY COVERAGE", date_field="week_start")
            report = module.review_worktime_compliance(
                data, weekly, config["policy"],
                period_from=from_date, period_to=to_date,
            )
            compliance = report
            artifact = _safe_json_write(report, output / "worktime-compliance-result.json")
        else:  # output: only join known existing Module results
            if verification is None:
                verification = _read_module_result(
                    paths["attendance_verification_result"],
                    name="attendance-verification", config=config)
            if compliance is None:
                compliance = _read_module_result(
                    paths["compliance_result"], name="worktime-compliance", config=config)
            external = (_rows(paths["attendance_facts"], LEAVE_FIELDS,
                              "ATTENDANCE FACTS")
                        if "attendance_facts" in paths else [])
            result = build_worktime_result(
                schedule_rows, verification, compliance,
                period_from=from_date, period_to=to_date,
                attendance_facts=external,
            )
            output.mkdir(parents=True, exist_ok=True)
            artifact = write_worktime_xlsx(result, output / "worktime-result.xlsx")
        result_files[step] = str(artifact)
    return result_files


def main(config_path: str | Path) -> int:
    try:
        results = execute(config_path)
    except (WorktimeToolError, ValueError, OSError, TypeError, KeyError) as exc:
        print(f"WORKTIME_TOOL_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"tool": "worktime", "artifacts": results},
                     indent=2, ensure_ascii=False))
    return 0
