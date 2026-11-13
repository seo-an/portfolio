#!/usr/bin/env python3
"""Create the recommended, fully synthetic Bhandara v2 integrated sample.

Legacy 80-person XLSX inputs remain committed as regression baselines. This
command creates fresh, v2-ready real Excel inputs and an actual Worktime handoff
in a NEW destination. Nothing is written to the Git source checkout.

The Worktime module is used only by this example generator. Production modules
remain independent and exchange the documented JSON handoff.
"""
from __future__ import annotations

import argparse
import importlib
import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[3]
LEGACY_INPUT = ROOT / "bhandara/examples/sample/input"

EXTERNAL_WORKERS = (
    ("EXT-W001", "SEC-EXT-001"),
    ("EXT-W002", "SEC-EXT-002"),
)
EXTERNAL_WORKTIME = (
    ("EXT-W001", "2026-06-02", "09:00", "18:00", 60),
    ("EXT-W001", "2026-06-03", "08:00", "23:00", 60),
    ("EXT-W002", "2026-06-02", "09:00", "18:00", 60),
    ("EXT-W002", "2026-06-03", "09:00", "18:00", 60),
)
SERVICE_CONTRACTS = (
    ("SVC-H001", None, "HOURLY", 37000, "2026-01-01", None, None,
     "Synthetic hourly independent service, not payroll", "RATE",
     "INDEPENDENT_SERVICE", "PARTY-001", "EXT-W001"),
    ("SVC-D002", None, "DAILY", 230000, "2026-01-01", None, 8,
     "Synthetic daily vendor, not payroll", "RATE",
     "CORPORATE_VENDOR", "PARTY-002", "EXT-W002"),
    ("SVC-P003", None, "PROJECT", 5000000, "2026-01-01", None, None,
     "Project settlement requires evidence", "TOTAL",
     "CORPORATE_VENDOR", "PARTY-003", None),
)


def _install_external_mapping(input_dir: Path) -> None:
    path = input_dir / "common/id-map.xlsx"
    book = load_workbook(path)
    try:
        if "EXTERNAL" in book.sheetnames:
            raise ValueError("unexpected existing EXTERNAL sheet in legacy input")
        sheet = book.create_sheet("EXTERNAL")
        sheet.append(("worker_id", "security_id"))
        for identity in EXTERNAL_WORKERS:
            sheet.append(identity)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        book.save(path)
    finally:
        book.close()


def _extend_worktime(input_dir: Path) -> None:
    for filename in ("work-schedule.xlsx", "attendance.xlsx"):
        path = input_dir / "worktime" / filename
        book = load_workbook(path)
        try:
            sheet = book.active
            headers = [cell.value for cell in sheet[1]]
            if "worker_id" in headers:
                raise ValueError(f"unexpected worker_id column in legacy {filename}")
            sheet.cell(1, len(headers) + 1, "worker_id")
            for worker_id, day, start, end, pause in EXTERNAL_WORKTIME:
                row = {
                    "employee_id": None, "worker_id": worker_id,
                    "work_date": day, "break_min": pause,
                }
                if filename == "work-schedule.xlsx":
                    row.update(
                        day_type="WORK", scheduled_start=start,
                        scheduled_end=end, scheduled_work_hours=14 if
                        (worker_id, day) == ("EXT-W001", "2026-06-03") else 8,
                        note="SYNTHETIC_EXTERNAL_SCHEDULE",
                    )
                else:
                    row.update(
                        clock_in=start, clock_out=end,
                        source="SYNTHETIC_CONFIRMED_CLOCK_PAIR",
                        note="REVIEW_ONLY_NO_APPROVAL",
                    )
                sheet.append([row.get(header) for header in (*headers, "worker_id")])
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            book.save(path)
        finally:
            book.close()


def _monthly_components(legacy_components: Path) -> dict[str, dict[str, Decimal]]:
    book = load_workbook(legacy_components, read_only=True, data_only=True)
    try:
        rows = list(book.active.values)
    finally:
        book.close()
    components: dict[str, dict[str, Decimal]] = {}
    for contract_id, code, amount in rows[1:]:
        components.setdefault(str(contract_id), {})[str(code)] = Decimal(str(amount))
    return components


def _create_v2_contracts(input_dir: Path) -> None:
    path = input_dir / "payroll/pay-contract.xlsx"
    components_path = input_dir / "payroll/pay-contract-components.xlsx"
    old_items = _monthly_components(components_path)
    book = load_workbook(path)
    try:
        source = book.active
        previous = list(source.values)
        original_headers = [cell.value for cell in source[1]]
        if "amount_type" in original_headers:
            raise ValueError("expected original 80-person legacy contract input")
        source.title = "Contracts"
        source.delete_rows(1, source.max_row)
        source.append((
            *original_headers, "amount_type", "relationship_type",
            "party_id", "worker_id",
        ))
        items = book.create_sheet("Components")
        items.append(("contract_id", "pay_item_code", "monthly_amount"))
        for old in previous[1:]:
            cid, employee_id, pay_basis, contract_amount = old[:4]
            # v2 explicitly distinguishes contract base from included total.
            kind = "TOTAL" if pay_basis in {"ANNUAL", "MONTHLY"} else "RATE"
            if employee_id == "E006":
                kind = "BASE"
            if pay_basis in {"ANNUAL", "MONTHLY"}:
                monthly = Decimal(str(contract_amount)) / (
                    Decimal("12") if pay_basis == "ANNUAL" else Decimal("1")
                )
                allowances = old_items.get(cid, {})
                base = monthly if kind == "BASE" else (
                    monthly - sum(allowances.values(), Decimal("0"))
                )
                items.append((cid, "base_salary", int(base)))
                for code, amount in sorted(allowances.items()):
                    items.append((cid, code, int(amount)))
            source.append((
                *old, kind, "REGULAR_EMPLOYEE", None, None,
            ))
        for row in SERVICE_CONTRACTS:
            source.append(row)
        source.freeze_panes = "A2"
        source.auto_filter.ref = source.dimensions
        items.freeze_panes = "A2"
        items.auto_filter.ref = items.dimensions
        book.save(path)
    finally:
        book.close()
    components_path.unlink()
    for name in ("service-contracts.xlsx", "service-work-records.xlsx"):
        (input_dir / "payroll" / name).unlink()


def _create_worktime_handoff(input_dir: Path, working_dir: Path) -> None:
    module = importlib.import_module("bhandara.worktime-calculator.shared_excel")
    target = working_dir / "worktime-output"
    result_code = module.run_shared_excel(input_dir, "2026-06", target)
    if result_code not in (0, 2):
        raise RuntimeError("Worktime generation failed")
    result = json.loads((target / "worktime-result.json").read_text(encoding="utf-8"))
    expected = {f"EP{i:04d}" for i in range(1, 81)}
    expected.update(worker for worker, _ in EXTERNAL_WORKERS)
    if set(result["covered_worker_ids"]) != expected:
        raise RuntimeError("unexpected Worktime roster")
    if result["finalizable"] or result["coverage_verified"]:
        raise RuntimeError("Worktime sample must remain unclosed")
    shutil.copy2(
        target / "worktime-result.json",
        input_dir / "payroll/worktime-result.json",
    )


def generate(destination: Path) -> Path:
    """Generate all public v2 Excel/JSON sample inputs without overwrites."""
    target = destination.resolve()
    if target.exists():
        raise FileExistsError(f"refusing to overwrite destination: {target}")
    if target == ROOT or target.is_relative_to(ROOT):
        raise ValueError("create the sample outside the Git repository")
    with tempfile.TemporaryDirectory(prefix="bhandara-v2-generator-") as tmp:
        stage = Path(tmp)
        input_dir = stage / "input"
        shutil.copytree(LEGACY_INPUT, input_dir)
        _install_external_mapping(input_dir)
        _extend_worktime(input_dir)
        _create_v2_contracts(input_dir)
        _create_worktime_handoff(input_dir, stage)
        manifest = {
            "schema_version": "2.0",
            "fixture": "INTEGRATED_SYNTHETIC_DEMO",
            "period_worktime": "2026-06",
            "period_payroll": "2026-07",
            "employee_count": 80,
            "external_time_workers": 2,
            "service_contracts": 3,
            "contract_layout": "payroll/pay-contract.xlsx: Contracts+Components",
            "worktime_handoff": "payroll/worktime-result.json",
            "approved": False,
            "finalizable": False,
            "note": "Synthetic only; no employment, vendor billing or tax approval",
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic only at the directory level: destination must be nonexistent.
        shutil.move(str(stage), str(target))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    generated = generate(args.output_dir)
    print(f"INTEGRATED_SAMPLE=READY {generated}")
    print("EMPLOYEES=80 EXTERNAL_WORKERS=2 LEGACY_SERVICE_XLSX=NONE")
    print("PAYROLL_REVIEW_ONLY=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
