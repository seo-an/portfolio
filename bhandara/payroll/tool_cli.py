"""JSON-only standalone Payroll Tool CLI (P3-1).

The already merged Payroll calculation Flow is reused verbatim. Every
external data/approval source is an explicit JSON file reference, not a
second calculation implementation. Input and output directories are never
overwritten or treated as approval to pay.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from bhandara.common.runtime.workspace import ensure_tool_workspace
from zoneinfo import ZoneInfo

from bhandara.common.io.input_layout import period_bounds
from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.contract_scoped_overtime import build_contract_scoped_overtime_preview
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.output_excel import write_payroll_result_xlsx


STEPS = ("review", "output")
INPUT_FILES = frozenset((
    "worktime", "employee", "pto_usage", "pto_deduction", "pto_closing",
))
REQUIRED_SOURCES = frozenset((
    "settlement_plan", "attendance_plan", "verified_work",
    "approved_segments", "evidence_registry", "rate_policy", "rollup_policy",
))
OPTIONAL_SOURCES = frozenset((
    "pto_claims", "pto_wage_plan", "insurance_assessment_plan",
    "withholding_plan", "industrial_assessment_plan",
))
SOURCE_NAMES = REQUIRED_SOURCES | OPTIONAL_SOURCES
ROOT_KEYS = frozenset((
    "schema_version", "tool", "run_id", "payroll_period", "steps",
    "input_root", "output_root", "files", "source_files",
))
OBJECT_SOURCES = (
    REQUIRED_SOURCES - {"verified_work", "approved_segments"}
) | (OPTIONAL_SOURCES - {"pto_claims"})
LIST_SOURCES = {"verified_work", "approved_segments", "pto_claims"}


class PayrollToolError(ValueError):
    """Invalid configuration or unverified source; no payroll artifact emitted."""


def _path(value: Any, field: str, *, root: Path) -> Path:
    if type(value) is not str or not value.strip():
        raise PayrollToolError(f"{field}: explicit nonempty relative or absolute path required")
    item = Path(value).expanduser()
    return (item if item.is_absolute() else root / item).resolve()


def _read_json(path: Path, field: str) -> Any:
    if not path.is_file():
        raise PayrollToolError(f"{field}: missing JSON source")
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream, parse_float=str)
    except (OSError, ValueError, UnicodeError) as exc:
        raise PayrollToolError(f"{field}: malformed JSON") from exc


def _config(file: str | Path) -> dict[str, Any]:
    path = Path(file).expanduser().resolve()
    data = _read_json(path, "config")
    if not isinstance(data, dict) or set(data) != ROOT_KEYS:
        raise PayrollToolError("config: exact Payroll Tool keys required")
    if (data["tool"], data["schema_version"]) != ("payroll", "1.0"):
        raise PayrollToolError("config: tool/schema_version must be payroll/1.0")
    steps = data["steps"]
    if (not isinstance(steps, list) or not steps
            or any(step not in STEPS for step in steps)
            or len(steps) != len(set(steps))
            or steps != [step for step in STEPS if step in steps]):
        raise PayrollToolError("steps: review/output once in order")
    try:
        start, end = period_bounds(data["payroll_period"])
    except (ValueError, TypeError) as exc:
        raise PayrollToolError("payroll_period: YYYY-MM required") from exc
    run_id = data["run_id"]
    if run_id == "auto":
        run_id = datetime.now(ZoneInfo("Asia/Seoul")).strftime("payroll-%Y%m%d-%H%M%S-%f")
    if type(run_id) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", run_id):
        raise PayrollToolError("run_id: auto or 1-64 safe characters required")
    input_root = _path(data["input_root"], "input_root", root=path.parent)
    output_root = _path(data["output_root"], "output_root", root=path.parent)
    if (input_root == output_root or output_root.is_relative_to(input_root)
            or input_root.is_relative_to(output_root)):
        raise PayrollToolError("input/output: output must be outside input")
    if not input_root.is_dir():
        raise PayrollToolError("input_root: missing directory")
    if not isinstance(data["files"], dict) or set(data["files"]) - INPUT_FILES:
        raise PayrollToolError("files: unknown input file role")
    if "worktime" not in data["files"]:
        raise PayrollToolError("files.worktime: required")
    if (not isinstance(data["source_files"], dict)
            or set(data["source_files"]) - SOURCE_NAMES
            or not REQUIRED_SOURCES <= set(data["source_files"])):
        raise PayrollToolError("source_files: missing or unknown verification source")
    files = {
        name: _path(value, f"files.{name}", root=input_root)
        for name, value in data["files"].items()
    }
    sources = {
        name: _path(value, f"source_files.{name}", root=input_root)
        for name, value in data["source_files"].items()
    }
    if files["worktime"].name != "worktime-result.xlsx":
        raise PayrollToolError("files.worktime: worktime-result.xlsx required")
    for name, target in {**files, **sources}.items():
        if not target.is_file():
            raise PayrollToolError(f"input file missing: {name}")
        if target.is_relative_to(output_root):
            raise PayrollToolError(f"source: {name} must not point into output")
    present_pto = {"pto_usage", "pto_deduction"} & set(files)
    if present_pto and not (
        {"pto_usage", "pto_deduction"} <= set(files) and
        "pto_claims" in sources
    ):
        raise PayrollToolError("PTO: usage/deduction/claims must be provided together")
    if "pto_closing" in files and not present_pto:
        raise PayrollToolError("PTO: confirmed Closing requires usage and deduction")
    if "pto_wage_plan" in sources and not present_pto:
        raise PayrollToolError("PTO wage: source PTO workbooks required")
    if "industrial_assessment_plan" in sources and "employee" not in files:
        raise PayrollToolError("employer industrial: common employee file required")
    return {
        "run_id": run_id, "period_from": start, "period_to": end,
        "steps": steps, "input_root": input_root, "output_root": output_root,
        "files": files, "source_files": sources,
    }


def _load_sources(paths: Mapping[str, Path]) -> dict[str, Any]:
    result = {}
    for name, path in paths.items():
        value = _read_json(path, f"source_files.{name}")
        if name in LIST_SOURCES:
            if not isinstance(value, list):
                raise PayrollToolError(f"source_files.{name}: JSON list required")
        elif name in OBJECT_SOURCES:
            if not isinstance(value, dict):
                raise PayrollToolError(f"source_files.{name}: JSON object required")
        else:
            raise PayrollToolError("source: unsupported type")
        result[name] = value
    return result


def _source_digest_snapshot(config: Mapping[str, Any]) -> dict[str, str]:
    """Reject source rewrites during computation; report only short role names."""
    watched = {}
    for name, target in config["files"].items():
        watched[f"files.{name}"] = sha256_file(target)
    for name, target in config["source_files"].items():
        watched[f"source_files.{name}"] = sha256_file(target)
    # Every selected Payroll contract workbook is the same strict 7-role set.
    contract = json.loads(
        (Path(__file__).with_name("input-files.json")).read_text(encoding="utf-8")
    )
    for name, detail in contract["workbooks"].items():
        file = config["input_root"] / contract["input_directory"] / detail["filename"]
        if not file.is_file():
            raise PayrollToolError(f"payroll input missing: {name}")
        watched[f"payroll.{name}"] = sha256_file(file)
    return watched


def _verify_unchanged(config: Mapping[str, Any], previous: Mapping[str, str]) -> None:
    if _source_digest_snapshot(config) != previous:
        raise PayrollToolError("input source changed during calculation; rerun with a new ID")


def _review_summary(result: Mapping[str, Any], config: Mapping[str, Any],
                    digests: Mapping[str, str]) -> dict[str, Any]:
    register = result["payroll_register"]
    keys = {column["key"] for column in register["columns"]}
    return {
        "schema_version": "0.1",
        "tool": "payroll",
        "period_from": config["period_from"],
        "period_to": config["period_to"],
        "run_id": config["run_id"],
        "approval_state": "NOT_APPROVED",
        "status": "PARTIAL_REVIEW_ONLY",
        "employee_count": len(register["rows"]),
        "review_requests": result["review_requests"],
        "review_flags": register["review_flags"],
        "totals_are_provisional": register["totals_are_provisional"],
        "company_cost": {
            "scope": register.get("employer_cost_scope"),
            "complete": register.get("employer_cost_complete"),
            "known_amount_total_won": (
                sum(row["known_company_outlay"] for row in register["rows"])
                if "known_company_outlay" in keys else None
            ),
        },
        "source_sha256_by_role": dict(sorted(digests.items())),
    }


def execute(config_path: str | Path) -> dict[str, str]:
    """Calculate exactly once; use named JSON sources and output only selected artifacts."""
    ensure_tool_workspace("payroll")
    cfg = _config(config_path)
    snapshot = _source_digest_snapshot(cfg)
    sources = _load_sources(cfg["source_files"])
    inputs = read_payroll_inputs(cfg["input_root"])
    files = cfg["files"]
    pto_sources = None
    if "pto_usage" in files:
        pto_sources = {
            "usage_file": files["pto_usage"],
            "deduction_file": files["pto_deduction"],
            "closing_file": files.get("pto_closing"),
            "pto_claims": sources["pto_claims"],
        }
    result = build_contract_scoped_overtime_preview(
        inputs, files["worktime"],
        settlement_plan=sources["settlement_plan"],
        attendance_plan=sources["attendance_plan"],
        period_from=cfg["period_from"], period_to=cfg["period_to"],
        verified_work=sources["verified_work"],
        approved_segments=sources["approved_segments"],
        evidence_registry=sources["evidence_registry"],
        rate_policy=sources["rate_policy"],
        rollup_policy=sources["rollup_policy"],
        pto_sources=pto_sources,
        pto_wage_plan=sources.get("pto_wage_plan"),
        insurance_assessment_plan=sources.get("insurance_assessment_plan"),
        withholding_plan=sources.get("withholding_plan"),
        industrial_assessment_plan=sources.get("industrial_assessment_plan"),
        employee_xlsx=files.get("employee"),
    )
    _verify_unchanged(cfg, snapshot)
    report = _review_summary(result, cfg, snapshot)

    run_dir = cfg["output_root"] / cfg["run_id"]
    # No output directory is created until every input has passed review.
    if run_dir.exists():
        raise PayrollToolError("run_id already exists; output overwrite forbidden")
    cfg["output_root"].mkdir(parents=True, exist_ok=True)
    try:
        run_dir.mkdir(exist_ok=False)
        artifact_paths: dict[str, str] = {}
        if "review" in cfg["steps"]:
            file = run_dir / "payroll-review.json"
            with file.open("x", encoding="utf-8") as out:
                json.dump(report, out, indent=2, ensure_ascii=False)
                out.write("\n")
            artifact_paths["review"] = str(file)
        if "output" in cfg["steps"]:
            file = write_payroll_result_xlsx(
                result["payroll_register"], run_dir / "payroll-result.xlsx"
            )
            artifact_paths["output"] = str(file)
        return artifact_paths
    except BaseException:
        # Remove only files we created in this NEW run folder; never touch
        # user input or a previously completed run.
        if run_dir.is_dir():
            for filename in ("payroll-review.json", "payroll-result.xlsx"):
                artifact = run_dir / filename
                if artifact.is_file():
                    artifact.unlink()
            run_dir.rmdir()
        raise


def main(config_path: str | Path) -> int:
    try:
        files = execute(config_path)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"PAYROLL_TOOL_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "tool": "payroll", "approval_state": "NOT_APPROVED",
        "artifacts": files,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JSON-driven Payroll review Tool")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    raise SystemExit(main(args.config))
