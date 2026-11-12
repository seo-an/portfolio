"""Independent Payroll Excel entrypoint on the shared Bhandara input root.

The Payroll engine remains read-only and review-only. Its Worktime JSON is an
explicit file handoff, not a hidden dependency on an installed Worktime module.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from bhandara.common.io.input_layout import (
    InputLayoutError, as_day, read_id_map, read_sheet, role,
    write_auto_config,
)


def _check_workers(root: Path, ids: Mapping[str, Mapping[str, str]],
                   overrides: Mapping | None) -> tuple[Path, Path]:
    compensation = role(root, "payroll", "compensation", overrides)
    payroll_input = role(root, "payroll", "payroll_input", overrides)
    allowed = {item["worker_id"] for item in ids.values()}

    compensation_rows = read_sheet(
        compensation, ("worker_id", "effective_from", "effective_to", "base_salary"))
    if not compensation_rows:
        raise InputLayoutError("compensation.xlsx is empty")
    seen: set[str] = set()
    for row in compensation_rows:
        ident = str(row["worker_id"] or "").strip()
        if ident not in allowed:
            raise InputLayoutError(
                f"compensation.xlsx row {row['_row_number']}: unmapped worker_id {ident}"
            )
        seen.add(ident)
    if seen != allowed:
        raise InputLayoutError(
            f"compensation.xlsx missing workers: {sorted(allowed - seen)[:10]}"
        )
    for row in read_sheet(
        payroll_input, ("worker_id", "pay_item_code", "amount", "quantity",
                        "origin_pay_item_code", "origin_from", "origin_to", "note")
    ):
        ident = str(row["worker_id"] or "").strip()
        if ident not in allowed:
            raise InputLayoutError(
                f"payroll-input.xlsx row {row['_row_number']}: unmapped worker_id {ident}"
            )
    return compensation, payroll_input


def _employment_facts(root: Path, identities: Mapping[str, Mapping[str, str]],
                      overrides: Mapping | None) -> list[dict[str, Any]]:
    employee_sheet = role(root, "common", "employees", overrides)
    rows = read_sheet(employee_sheet, ("employee_id", "hire_date", "termination_date"))
    if {str(row["employee_id"]).strip() for row in rows} != set(identities):
        raise InputLayoutError("employee.xlsx and id-map.xlsx roster mismatch")
    return [
        {
            "worker_id": identities[str(row["employee_id"]).strip()]["worker_id"],
            "employment_from": as_day(row["hire_date"], "hire_date"),
            "employment_to": (
                as_day(row["termination_date"], "termination_date")
                if row.get("termination_date") else None
            ),
        }
        for row in rows
    ]


def prepare_shared_payroll(root: Path, period: str, *,
                           overrides: Mapping | None = None,
                           worktime_result_path: Path | None = None) -> Path:
    """Validate Excel mapping and derive a traceable config, no user JSON editing."""
    from bhandara.common.io.input_layout import period_bounds

    period_bounds(period)
    root = root.resolve()
    identities = read_id_map(root, overrides=overrides)
    compensation, payroll_input = _check_workers(root, identities, overrides)
    company_policy = role(root, "payroll", "company_policy", overrides)
    # No implicit lookup for "latest" Worktime results, which may be stale.
    handoff = (
        Path(worktime_result_path).resolve()
        if worktime_result_path is not None
        else role(root, "payroll", "worktime_result", overrides)
    )
    if not handoff.is_file():
        raise InputLayoutError(f"Worktime result handoff missing: {handoff}")
    with handoff.open("r", encoding="utf-8") as source:
        worktime_result = json.load(source)
    if not isinstance(worktime_result, dict):
        raise InputLayoutError("Worktime handoff must be a JSON object")
    covered = set(worktime_result.get("covered_worker_ids") or [])
    expected = {item["worker_id"] for item in identities.values()}
    if covered and covered != expected:
        raise InputLayoutError(
            "Worktime handoff worker roster differs from current id-map.xlsx"
        )
    # Verify a default Worktime handoff against the current shared Excel.
    # An explicit --worktime-result can come from a separate standalone run.
    if worktime_result_path is None:
        from bhandara.common.io.input_layout import hash_file
        fingerprints = worktime_result.get("source_hashes") or {}
        for key, filename in (
            ("employees", "common/employee.xlsx"),
            ("schedule", "worktime/work-schedule.xlsx"),
            ("attendance", "worktime/attendance.xlsx"),
        ):
            if (root / filename).is_file():
                expected_sha = hash_file(root / filename)
                if fingerprints.get(key) != expected_sha:
                    raise InputLayoutError(
                        f"Stale Worktime handoff: {key} Excel changed. "
                        "Recalculate Worktime and specify --worktime-result."
                    )
    module_root = Path(__file__).resolve().parent
    config_root = root.parent / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    facts_path = config_root / f"employment-facts-{period}.json"
    facts = _employment_facts(root, identities, overrides)
    if facts_path.exists():
        if json.loads(facts_path.read_text(encoding="utf-8")) != facts:
            raise InputLayoutError(f"employment facts differ from existing {facts_path}")
    else:
        facts_path.write_text(
            json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    config = {
        "schema_version": "0.1",
        "payroll_period": period,
        "expected_worker_ids": sorted(
            item["worker_id"] for item in identities.values()
        ),
        "compensation_path": str(compensation),
        "payroll_input_path": str(payroll_input),
        "worktime_result_path": str(handoff),
        "registry_path": str(module_root / "resources/pay-item-registry.json"),
        "operating_config_path": str(module_root / "operating-config.json"),
        "company_policy_path": str(company_policy),
        "legal_policy_path": str(module_root / "resources/policy/2026.json"),
        "employment_facts_path": str(facts_path),
        "recurring_pay_item_codes": ["base_salary"],
    }
    return write_auto_config(root, f"payroll-auto-{period}.json", config)
