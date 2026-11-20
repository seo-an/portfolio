"""JSON-driven public Paid Time Off Tool dispatcher.

One JSON document holds all execution choices and paths. Individual runners
remain independent, while this Tool explicitly wires selected results.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from zoneinfo import ZoneInfo
from importlib import import_module
import json
from pathlib import Path
import re
import sys
from typing import Any

from bhandara.common.runtime.workspace import ensure_tool_workspace

STAGES = ("entitlement", "deduction-quantity", "usage-ledger", "closing")
FILE_KEYS = frozenset((
    "employee", "attendance", "proration", "approved_leave", "grant_references",
    "carry_in", "previous_closing", "promotion", "entitlement_result",
    "deduction_result", "usage_result",
))


class ToolConfigError(ValueError):
    """Invalid user-supplied Tool config; no implicit path or stage selection."""


def _require_path(value: Any, field: str, base: Path) -> Path:
    if type(value) is not str or not value.strip():
        raise ToolConfigError(f"{field}: non-empty path required")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def _read_config(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        raise ToolConfigError(f"설정 JSON 없음: {config_path}")
    try:
        doc = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ToolConfigError("설정 JSON을 읽을 수 없습니다") from exc
    if not isinstance(doc, dict) or doc.get("tool") != "paid-time-off" or doc.get("schema_version") != "1.0":
        raise ToolConfigError("tool/schema_version must be paid-time-off/1.0")
    steps = doc.get("steps")
    if (not isinstance(steps, list) or not steps
            or any(type(item) is not str or item not in STAGES for item in steps)
            or len(steps) != len(set(steps))):
        raise ToolConfigError(f"steps must select unique stages from {STAGES}")
    for later, prior in (("usage-ledger", "entitlement"),
                          ("usage-ledger", "deduction-quantity"),
                          ("closing", "usage-ledger")):
        if later in steps and prior in steps and steps.index(later) < steps.index(prior):
            raise ToolConfigError(f"steps: {prior} must run before {later}")
    policy = doc.get("policy_id")
    run_id = doc.get("run_id")
    if type(policy) is not str or not policy.strip():
        raise ToolConfigError("policy_id required")
    if run_id == "auto":
        run_id = datetime.now(ZoneInfo("Asia/Seoul")).strftime("pto-%Y%m%d-%H%M%S-%f")
    if type(run_id) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", run_id):
        raise ToolConfigError("run_id must be auto or 1..64 letters/digits/-/_")
    try:
        day = date.fromisoformat(doc["as_of_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolConfigError("as_of_date must be YYYY-MM-DD") from exc
    if day.isoformat() != doc["as_of_date"]:
        raise ToolConfigError("as_of_date must be canonical")
    input_root = _require_path(doc.get("input_root"), "input_root", config_path.parent)
    output_root = _require_path(doc.get("output_root"), "output_root", config_path.parent)
    if (input_root == output_root or output_root.is_relative_to(input_root)
            or input_root.is_relative_to(output_root)):
        raise ToolConfigError("input/output roots must not contain one another")
    raw_files = doc.get("files", {})
    if not isinstance(raw_files, dict) or set(raw_files) - FILE_KEYS:
        raise ToolConfigError(f"files permits only {sorted(FILE_KEYS)}")
    resolved = {key: _require_path(value, f"files.{key}", input_root)
                for key, value in raw_files.items()}
    for key, path in resolved.items():
        if not path.is_file():
            raise ToolConfigError(f"files.{key}: missing input {path.name}")
    if "usage-ledger" in steps and not resolved.get("grant_references"):
        raise ToolConfigError("usage-ledger requires files.grant_references")
    for stage, key, producer in (
        ("usage-ledger", "entitlement_result", "entitlement"),
        ("usage-ledger", "deduction_result", "deduction-quantity"),
        ("closing", "usage_result", "usage-ledger"),
    ):
        if stage in steps and producer not in steps and key not in resolved:
            raise ToolConfigError(f"{stage}: select {producer} or provide files.{key}")
    if "closing" in steps and not doc.get("closing_id"):
        raise ToolConfigError("closing requires closing_id")
    if "closing" in steps and "usage-ledger" in steps and not doc.get("closing_id"):
        raise ToolConfigError("usage-ledger requires closing_id for closing")
    return {
        **doc, "run_id": run_id, "steps": steps, "as_of_date": day,
        "input_root": input_root, "output_root": output_root, "files": resolved,
    }


def _run_entitlement(config: dict[str, Any]) -> Path:
    module = import_module("bhandara.paid-time-off.runner")
    files = config["files"]
    result = module.run_entitlement(
        as_of_date=config["as_of_date"],
        basis=config.get("basis", "입사일 기준"),
        policy_id=config["policy_id"], run_id=config["run_id"],
        input_root=config["input_root"], output_root=config["output_root"],
        employee_file=files.get("employee"), attendance_file=files.get("attendance"),
        proration_file=files.get("proration"),
        rounding_digits=config.get("rounding_digits", 1),
        fiscal_year_start=config.get("fiscal_year_start", "01-01"),
        proration_method=config.get("proration_method", "소정근로일 기준"),
    )
    return Path(result["path"])


def _run_deduction(config: dict[str, Any]) -> Path:
    module = import_module("bhandara.paid-time-off.runner")
    result = module.run_deduction_quantity(
        policy_id=config["policy_id"], run_id=config["run_id"],
        input_root=config["input_root"], output_root=config["output_root"],
        approved_file=config["files"].get("approved_leave"),
        standard_daily_hours=config.get("standard_daily_hours", 8),
    )
    return Path(result["path"])


def _required_file(config: dict[str, Any], results: dict[str, Path], name: str,
                   producer: str) -> Path:
    value = results.get(producer) or config["files"].get(name)
    if value is None:
        raise ToolConfigError(f"missing {name} (produce {producer} first)")
    return value


def _run_usage(config: dict[str, Any], results: dict[str, Path]) -> Path:
    module = import_module("bhandara.paid-time-off.runner_usage")
    files = config["files"]
    result = module.run_usage_ledger(
        as_of_date=config["as_of_date"], policy_id=config["policy_id"],
        run_id=config["run_id"],
        entitlement_file=_required_file(config, results, "entitlement_result", "entitlement"),
        deduction_file=_required_file(config, results, "deduction_result", "deduction-quantity"),
        reference_file=files["grant_references"],
        carry_in_file=files.get("carry_in"),
        closing_id=config.get("closing_id"),
        output_root=config["output_root"],
    )
    return Path(result["path"])


def _run_closing(config: dict[str, Any], results: dict[str, Path]) -> Path:
    module = import_module("bhandara.paid-time-off.runner_closing")
    files = config["files"]
    result = module.run_closing(
        closing_id=config["closing_id"], policy_id=config["policy_id"],
        run_id=config["run_id"],
        usage_file=_required_file(config, results, "usage_result", "usage-ledger"),
        employee_file=files.get("employee", config["input_root"] / "common/employee.xlsx"),
        previous_closing_file=files.get("previous_closing"),
        promotion_file=files.get("promotion"), output_root=config["output_root"],
    )
    return Path(result["path"])


def execute(config_path: str | Path) -> dict[str, str]:
    """Run exactly the ordered JSON steps; never invoke unspecified modules."""
    ensure_tool_workspace("paid-time-off")
    config = _read_config(Path(config_path).resolve())
    if (config["output_root"] / config["run_id"]).exists():
        raise ToolConfigError("run_id already exists; output overwrite forbidden")
    result: dict[str, Path] = {}
    for stage in config["steps"]:
        if stage == "entitlement":
            result[stage] = _run_entitlement(config)
        elif stage == "deduction-quantity":
            result[stage] = _run_deduction(config)
        elif stage == "usage-ledger":
            result[stage] = _run_usage(config, result)
        elif stage == "closing":
            result[stage] = _run_closing(config, result)
    return {stage: str(path) for stage, path in result.items()}


def main(config_path: str | Path) -> int:
    try:
        outputs = execute(config_path)
    except (ToolConfigError, ValueError, OSError, TypeError, KeyError) as exc:
        print(f"PTO_TOOL_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"tool": "paid-time-off", "artifacts": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JSON-driven Paid Time Off Tool")
    parser.add_argument("--config", required=True)
    params = parser.parse_args()
    raise SystemExit(main(params.config))
