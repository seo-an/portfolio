#!/usr/bin/env python3
"""Generate the one canonical 80-person Bhandara sample with current layouts.

A private deterministic seed is created in a temporary directory and then
upgraded to the current integrated input contracts. No stale checked-in Excel
files or parallel legacy/v2 sample trees are used as generator inputs.

The Worktime module is used only by this example generator. Production modules
remain independent and exchange the documented JSON handoff.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[3]
SEED_GENERATOR = ROOT / "bhandara/examples/sample/_seed.py"

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


def _add_synthetic_taxability_policy(input_dir: Path) -> None:
    """Demonstrate the NEW review buckets without asserting legal eligibility."""
    path = input_dir / "payroll/company-policy.json"
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["taxability_review"] = {
        "schema_version": "1.0",
        "pay_items": {
            "base_salary": {
                "status": "TAXABLE",
                "policy_ref": "SYNTHETIC_DEMO_BASE_NO_LEGAL_ASSERTION",
            },
            "meal_allowance": {
                "status": "NON_TAXABLE",
                "policy_ref": "SYNTHETIC_DEMO_MEAL_NO_LEGAL_ASSERTION",
                "cap_per_worker_period": 100000,
            },
            "position_allowance": {
                "status": "REVIEW",
            },
        },
    }
    path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# v0.2 PTO usage examples are separate from the immutable legacy 80-person
# regression fixture. All nine events are synthetic and unapproved for payroll.
PTO_USAGE_CASES = (
    ("E001", "연차", "DAY", "2026-07-06", None),
    ("E002", "연차", "DAY", "2026-07-06", None),
    ("E003", "오전 반차", "HALF_DAY", "2026-07-07", None),
    ("E004", "오전 반차", "HALF_DAY", "2026-07-07", None),
    ("E005", "오전 반차", "HALF_DAY", "2026-07-07", None),
    ("E006", "오후 반차", "HALF_DAY", "2026-07-08", None),
    ("E007", "오후 반차", "HALF_DAY", "2026-07-08", None),
    ("E008", "조기퇴근", "HOURS", "2026-07-09", None),
    ("E009", "육아기근로시간단축", "HOURS", "2026-07-10", 2),
)


def _apply_pto_usage_scenarios(input_dir: Path) -> None:
    """Add the nine approved synthetic PTO events to the recommended v2 sample.

    Keep the original E031 pregnancy and E044 sick-leave review events. Leave
    use must agree with presence evidence: full leave has no punch; AM/PM half
    retains only actually worked half; early departure/reduced hours retain
    observed partial hours rather than claiming full attendance.
    """
    event_path = input_dir / "pto/employee-events.xlsx"
    attendance_path = input_dir / "pto/work-records/2026/2026-07-attendance.xlsx"
    event_book = load_workbook(event_path)
    try:
        sheet = event_book.active
        expected = ("request_id", "employee_id", "event_type",
                    "event_date", "unit", "status", "note", "reduced_hours")
        if tuple(cell.value for cell in sheet[1]) != expected:
            raise ValueError("unexpected PTO event input layout")
        existing = {str(row[0]) for row in list(sheet.values)[1:]}
        for index, (employee, label, unit, date, reduced) in enumerate(
            PTO_USAGE_CASES, 1
        ):
            request_id = f"INTEGRATED-V2-PTO-{index:02d}"
            if request_id in existing:
                raise ValueError("duplicate PTO fixture event")
            sheet.append((
                request_id, employee, label, date, unit,
                "APPROVED", "SYNTHETIC_REVIEW_ONLY", reduced,
            ))
        book = event_book
        book.save(event_path)
    finally:
        event_book.close()

    attendance_book = load_workbook(attendance_path)
    try:
        sheet = attendance_book.active
        columns = tuple(cell.value for cell in sheet[1])
        if columns[:6] != ("employee_id", "work_date", "clock_in",
                           "clock_out", "break_min", "source"):
            raise ValueError("unexpected PTO attendance input layout")
        cases = {(employee, day): label for employee, label, _, day, _ in PTO_USAGE_CASES}
        seen = set()
        for row in range(sheet.max_row, 1, -1):
            ident = sheet.cell(row, 1).value
            day = str(sheet.cell(row, 2).value)
            label = cases.get((ident, day))
            if label is None:
                continue
            if (ident, day) in seen:
                raise ValueError("duplicate PTO fixture attendance day")
            seen.add((ident, day))
            if label == "연차":
                sheet.delete_rows(row)
            elif label == "오전 반차":
                sheet.cell(row, 3, "14:00")
                sheet.cell(row, 4, "18:00")
                sheet.cell(row, 5, 0)
            elif label == "오후 반차":
                sheet.cell(row, 3, "09:00")
                sheet.cell(row, 4, "13:00")
                sheet.cell(row, 5, 0)
            elif label == "조기퇴근":
                sheet.cell(row, 4, "16:00")
                sheet.cell(row, 5, 60)
            else:  # 육아기근로시간단축
                sheet.cell(row, 4, "16:00")
                sheet.cell(row, 5, 60)
        if len(seen) != len(PTO_USAGE_CASES):
            raise ValueError("missing dated workday in PTO synthetic fixture")
        sheet.auto_filter.ref = sheet.dimensions
        attendance_book.save(attendance_path)
    finally:
        attendance_book.close()


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
        payload = stage / "sample"
        input_dir = payload / "input"
        spec = importlib.util.spec_from_file_location(
            "bhandara_sample_seed", SEED_GENERATOR
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("sample seed generator unavailable")
        seed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed)
        seed_root = stage / "seed"
        seed.build_shared_input(seed_root)
        shutil.copytree(seed_root / "input", input_dir)
        shutil.copy2(seed_root / "test-cases.json", payload / "test-cases.json")
        _install_external_mapping(input_dir)
        _extend_worktime(input_dir)
        _create_v2_contracts(input_dir)
        _add_synthetic_taxability_policy(input_dir)
        _apply_pto_usage_scenarios(input_dir)
        _create_worktime_handoff(input_dir, stage)
        manifest = {
            "schema_version": "2.0",
            "fixture": "CURRENT_80_PERSON_SYNTHETIC_SAMPLE",
            "period_worktime": "2026-06",
            "period_pto": "2026-07",
            "pto_event_scenarios": len(PTO_USAGE_CASES),
            "pto_scope": "known_usage_provisional_balance_no_expiry_or_approval",
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
        (payload / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic only at the directory level: destination must be nonexistent.
        shutil.move(str(payload), str(target))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    generated = generate(args.output_dir)
    print(f"SAMPLE_80=READY {generated}")
    print("EMPLOYEES=80 EXTERNAL_WORKERS=2 CURRENT_CONTRACT_LAYOUT=Contracts+Components")
    print("PAYROLL_REVIEW_ONLY=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
