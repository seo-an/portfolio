"""Standalone Payroll file contracts and Worktime handoff selection.

Accepted Worktime sources: an unclosed standalone Worktime result, an explicit
validated row list, or independently approved period-close receipts. Never infer
an approval from calculated values or truncate another source period silently.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Mapping

try:
    from .operating_period_resolver import resolve_source_period
    from .settlement_ledger_xlsx import load_settlement_ledger_rows
    from .worktime_handoff import validate_worktime_handoff
    from .payroll_policy_catalog import resolve_policy_catalog, policy_sha256
except ImportError:
    from operating_period_resolver import resolve_source_period
    from settlement_ledger_xlsx import load_settlement_ledger_rows
    from worktime_handoff import validate_worktime_handoff
    from payroll_policy_catalog import resolve_policy_catalog, policy_sha256


class StandalonePayrollInputError(ValueError):
    pass


REQUIRED_PATHS = (
    "compensation_path", "payroll_input_path", "registry_path",
    "operating_config_path", "legal_policy_path",
    "employment_facts_path",
)


def _path(root: Path, config: Mapping[str, Any], key: str) -> Path:
    name = config.get(key)
    if not isinstance(name, str) or not name.strip():
        raise StandalonePayrollInputError(f"{key} is a required file path")
    file = Path(name).expanduser()
    if not file.is_absolute():
        file = root / file
    file = file.resolve()
    if not file.is_file():
        raise StandalonePayrollInputError(f"{key}: file does not exist: {file}")
    return file


def _read_json(path: Path, expected: type):
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, expected):
        raise StandalonePayrollInputError(
            f"{path.name}: expected JSON {expected.__name__}"
        )
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_worktime_closer():
    path = (Path(__file__).resolve().parents[2]
            / "worktime-calculator" / "functions" / "worktime_close.py")
    spec = importlib.util.spec_from_file_location("standalone_worktime_close", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _worker_ids(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise StandalonePayrollInputError(
            "expected_worker_ids must be a nonempty independent roster"
        )
    if any(not isinstance(x, str) or not x.strip() or x != x.strip() for x in value):
        raise StandalonePayrollInputError("expected_worker_ids requires nonempty canonical strings")
    if len(value) != len(set(value)):
        raise StandalonePayrollInputError("duplicate expected_worker_ids")
    return sorted(value)


def _worktime_input(config: Mapping[str, Any], root: Path, operating: Mapping[str, Any],
                    workers: list[str], period: str) -> dict[str, Any]:
    keys = ["worktime_result_path", "worktime_rows_path", "worktime_closes_path"]
    active = [key for key in keys if config.get(key) is not None]
    if len(active) != 1:
        raise StandalonePayrollInputError(
            "select exactly one worktime_result_path, worktime_rows_path, or worktime_closes_path"
        )
    key = active[0]
    path = _path(root, config, key)
    resolved = resolve_source_period(period, "worktime", dict(operating))
    source_from = resolved["period_from"].isoformat()
    source_to = resolved["period_to"].isoformat()
    data = _read_json(path, dict if key == "worktime_result_path" else list)
    warnings = []
    receipts = []
    if key == "worktime_result_path":
        if data.get("schema_version") != "0.1":
            raise StandalonePayrollInputError("Worktime result schema_version 0.1 required")
        if data.get("status") not in ("CALCULATED_UNCLOSED", "REVIEW_REQUIRED"):
            raise StandalonePayrollInputError(
                f"Worktime result status cannot be calculated safely: {data.get('status')}"
            )
        if data.get("close_receipt") is not None:
            raise StandalonePayrollInputError("Worktime calculation result must not carry close receipt")
        rows = data.get("rows")
        if not isinstance(rows, list):
            raise StandalonePayrollInputError("Worktime result.rows must be a list")
        for row in rows:
            if not isinstance(row, dict):
                raise StandalonePayrollInputError("Worktime result row must be an object")
        warnings.append({
            "code": "WORKTIME_UNCLOSED", "severity": "ACTION_REQUIRED",
            "message": "Worktime calculation lacks independent period-close approval",
            "worker_id": None,
        })
        if (data.get("period_from") != source_from or
                data.get("period_to") != source_to or
                data.get("coverage_verified") is not True):
            warnings.append({
                "code": "WORKTIME_COVERAGE_UNVERIFIED", "severity": "ACTION_REQUIRED",
                "message": f"Worktime period coverage not verified for {source_from}..{source_to}",
                "worker_id": None,
            })
        for row in rows:
            for flag in row.get("validation_flags", []):
                if not isinstance(flag, Mapping):
                    raise StandalonePayrollInputError("Worktime flags must be objects")
                warnings.append({
                    "code": str(flag.get("code", "WORKTIME_REVIEW")),
                    "severity": "ACTION_REQUIRED",
                    "message": str(flag.get("message", "Worktime requires review")),
                    "worker_id": str(row.get("worker_id", "")),
                    "work_date": row.get("work_date"),
                })
    elif key == "worktime_rows_path":
        rows = data
        warnings.append({
            "code": "WORKTIME_ROWS_UNCLOSED", "severity": "ACTION_REQUIRED",
            "message": "Explicit Worktime rows are not verified period-close receipts",
            "worker_id": None,
        })
    else:
        receipts = data
        closer = _load_worktime_closer()
        rows = closer.select_closed_worktime(
            receipts,
            period_from=source_from,
            period_to=source_to,
            required_worker_ids=workers,
        )

    checked = validate_worktime_handoff(rows)
    keys_seen = set()
    for row in checked:
        worker_id = str(row["worker_id"]).strip()
        day = str(row["work_date"])
        if worker_id not in workers:
            raise StandalonePayrollInputError(
                f"Worktime worker absent from independent roster: {worker_id}"
            )
        if not source_from <= day <= source_to:
            raise StandalonePayrollInputError(
                f"Worktime row outside resolved source period: {worker_id}/{day}"
            )
        item_key = (worker_id, day)
        if item_key in keys_seen:
            raise StandalonePayrollInputError(f"duplicate Worktime row: {item_key}")
        keys_seen.add(item_key)
        if any(str(flag.get("severity", "")).upper() in ("REVIEW", "ERROR")
               for flag in row["validation_flags"] if isinstance(flag, Mapping)) and key == "worktime_closes_path":
            raise StandalonePayrollInputError("closed Worktime receipts cannot contain REVIEW/ERROR flags")
    return {
        "mode": "CLOSED" if receipts else "UNCLOSED",
        "rows": checked,
        "warnings": warnings,
        "path": path,
        "source_period": {"period_from": source_from, "period_to": source_to},
        "receipt_hashes": [item.get("receipt_hash") for item in receipts],
    }


def _selected_policy(config: Mapping[str, Any], root: Path,
                     scenario_id: str | None, scenario_source: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    catalog_provided = config.get("policy_catalog_path") is not None
    legacy_provided = config.get("company_policy_path") is not None
    if catalog_provided == legacy_provided:
        raise StandalonePayrollInputError(
            "select exactly one policy_catalog_path or company_policy_path"
        )
    config_choice = config.get("scenario_id")
    if config_choice is not None and (
        not isinstance(config_choice, str) or not config_choice.strip()
    ):
        raise StandalonePayrollInputError("config scenario_id must be a nonempty string")
    chosen = scenario_id if scenario_id is not None else config_choice
    if chosen is not None and (not isinstance(chosen, str) or not chosen.strip()):
        raise StandalonePayrollInputError("scenario_id must be a nonempty string")
    if catalog_provided:
        path = _path(root, config, "policy_catalog_path")
        resolved = resolve_policy_catalog(_read_json(path, dict), chosen)
        selection = dict(resolved["selection"])
        selection["selection_source"] = (
            scenario_source if scenario_id is not None
            else "config" if config_choice is not None else "catalog_default"
        )
        return resolved["policy"], selection, path
    if chosen is not None:
        raise StandalonePayrollInputError(
            "scenario_id requires policy_catalog_path; legacy company_policy_path has no scenarios"
        )
    path = _path(root, config, "company_policy_path")
    policy = _read_json(path, dict)
    return policy, {
        "catalog_id": None, "scenario_id": None,
        "profile_id": None, "scenario_kind": "legacy",
        "selection_source": "legacy_single_policy",
        "policy_sha256": policy_sha256(policy),
        "changes_from_default": [], "inheritance": [],
        "default_scenario_id": None,
    }, path


def load_standalone_inputs(config_path: str | Path, *, scenario_id: str | None = None,
                           scenario_source: str = "cli") -> dict[str, Any]:
    """Read source documents once, keep all input fingerprints and worker scope."""
    config_file = Path(config_path).resolve()
    config = _read_json(config_file, dict)
    if config.get("schema_version") != "0.1":
        raise StandalonePayrollInputError("config schema_version must be 0.1")
    period = config.get("payroll_period")
    if not isinstance(period, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise StandalonePayrollInputError("payroll_period must be YYYY-MM")
    workers = _worker_ids(config.get("expected_worker_ids"))
    root = config_file.parent
    paths = {key: _path(root, config, key) for key in REQUIRED_PATHS}
    company_policy, policy_selection, policy_path = _selected_policy(config, root, scenario_id, scenario_source)
    paths["selected_policy_source"] = policy_path
    loaded = {
        key.replace("_path", ""): _read_json(paths[key], dict)
        for key in ("registry_path", "operating_config_path", "legal_policy_path")
    }
    loaded["company_policy"] = company_policy
    facts = _read_json(paths["employment_facts_path"], list)
    if any(not isinstance(item, dict) or not isinstance(item.get("worker_id"), str)
           for item in facts):
        raise StandalonePayrollInputError("employment facts must be worker_id objects")
    fact_ids = [item["worker_id"] for item in facts]
    if sorted(fact_ids) != workers:
        raise StandalonePayrollInputError(
            f"expected roster/employment facts mismatch: missing={sorted(set(workers)-set(fact_ids))}, "
            f"unexpected={sorted(set(fact_ids)-set(workers))}, duplicate={len(fact_ids)!=len(set(fact_ids))}"
        )
    codes = config.get("recurring_pay_item_codes")
    if not isinstance(codes, list) or not codes or any(
        not isinstance(code, str) or not code.strip() for code in codes
    ) or len(codes) != len(set(codes)):
        raise StandalonePayrollInputError("recurring_pay_item_codes must be a unique nonempty list")
    worktime = _worktime_input(config, root, loaded["operating_config"], workers, period)
    paths["worktime_source"] = worktime["path"]
    optional = {}
    for param in ("eligibility_facts", "absence_events", "absence_deduction_inputs",
                  "weekly_holiday_inputs", "historical_rerun_results"):
        file_key = param + "_path"
        if config.get(file_key) is not None:
            paths[file_key] = _path(root, config, file_key)
            optional[param] = _read_json(paths[file_key], list)
        else:
            optional[param] = []
    if config.get("settlement_ledger_path") is not None:
        paths["settlement_ledger_path"] = _path(root, config, "settlement_ledger_path")
        ledger = load_settlement_ledger_rows(paths["settlement_ledger_path"])
    else:
        ledger = []
    return {
        "config_path": config_file,
        "payroll_period": period,
        "expected_worker_ids": workers,
        "compensation_path": paths["compensation_path"],
        "payroll_input_path": paths["payroll_input_path"],
        "registry": loaded["registry"],
        "operating_config": loaded["operating_config"],
        "company_policy": loaded["company_policy"],
        "policy_selection": policy_selection,
        "legal_policy": loaded["legal_policy"],
        "employment_facts": facts,
        "recurring_pay_item_codes": codes,
        "worktime": worktime,
        "settlement_ledger_rows": ledger,
        "ledger_supplied": "settlement_ledger_path" in paths,
        "optional": optional,
        "source_hashes": {
            "config": _sha256(config_file),
            **{key: _sha256(value) for key, value in paths.items()},
        },
    }
