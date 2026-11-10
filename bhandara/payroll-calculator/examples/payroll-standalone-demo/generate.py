#!/usr/bin/env python3
"""Create synthetic Payroll standalone inputs to follow the Worktime CLI demo.

Never uses or generates actual employee identities. Generated files are
intended solely for isolated local contract tests, not payroll approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from openpyxl import Workbook


def _json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _xlsx(path: Path, headers: list[str], rows: list[list]) -> None:
    book = Workbook()
    try:
        sheet = book.active
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        book.save(path)
    finally:
        book.close()


def build_synthetic_payroll(output_dir: str | Path, worktime_result: str | Path) -> Path:
    output = Path(output_dir).expanduser().resolve()
    source = Path(worktime_result).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Worktime result does not exist: {source}")
    # Do not silently reuse a real-work input directory or overwrite artifacts.
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    repo_gearbox = Path(__file__).resolve().parents[4]
    _xlsx(
        output / "compensation.xlsx",
        ["worker_id", "effective_from", "effective_to", "base_salary"],
        [
            ["EP0001", "2026-01-01", None, 3200000],
            ["EP0002", "2026-01-01", None, 2800000],
        ],
    )
    _xlsx(
        output / "payroll-input.xlsx",
        ["worker_id", "pay_item_code", "amount", "quantity",
         "origin_pay_item_code", "origin_from", "origin_to", "note"],
        [["EP0001", "performance_bonus", 100000, None, None, None, None, "synthetic bonus"]],
    )
    _json(output / "employment-facts.json", [
        {"worker_id": worker, "employment_from": "2026-01-01", "employment_to": None}
        for worker in ("EP0001", "EP0002")
    ])
    _json(output / "company-policy.json", {
        "proration": {"base_salary": {"method": "역일수"}},
        "ordinary_wage": {"monthly_basis_hours": 200, "pay_items": {}},
        "worktime_pay": {"base_component_policy": {}},
        "amount_processing": {
            "unit": 10, "method": "절사", "apply_at": "최종지급액",
            "remainder": {
                "handling": "settlement_ledger",
                "transaction_type": "rounding_carry", "settlement_month": 12,
            },
        },
    })
    _json(output / "payroll-config.json", {
        "schema_version": "0.1",
        "payroll_period": "2026-10",
        "expected_worker_ids": ["EP0001", "EP0002"],
        "compensation_path": "compensation.xlsx",
        "payroll_input_path": "payroll-input.xlsx",
        "worktime_result_path": str(source),
        "registry_path": str(repo_gearbox / "registry" / "pay-item-registry.json"),
        "operating_config_path": str(repo_gearbox / "gear" / "payroll-calculator" / "operating-config.json"),
        "company_policy_path": "company-policy.json",
        "legal_policy_path": str(repo_gearbox / "policy" / "payroll" / "2026.json"),
        "employment_facts_path": "employment-facts.json",
        "recurring_pay_item_codes": ["base_salary"],
    })
    return output / "payroll-config.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic Payroll CLI demo")
    parser.add_argument("--worktime-result", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    config = build_synthetic_payroll(args.output_dir, args.worktime_result)
    print(f"Generated synthetic standalone Payroll config: {config}")


if __name__ == "__main__":
    main()
