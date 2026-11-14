"""Standalone Payroll contract-basis tests; only synthetic public Excel input."""
from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from bhandara.common.io.input_layout import InputLayoutError, read_id_map

ROOT = Path(__file__).resolve().parents[2]
from bhandara.tests._seed_fixture import SEED_INPUT
INPUT = SEED_INPUT
adapter = importlib.import_module("bhandara.payroll-calculator.contract_adapter")


def source_rows(filename: Path) -> list[dict]:
    book = load_workbook(filename, read_only=True, data_only=True)
    try:
        records = list(book.active.values)
    finally:
        book.close()
    return [dict(zip(records[0], row)) for row in records[1:]]


class ContractBasisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bhandara-contract-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def run_contract(self, root: Path = INPUT):
        return adapter.build_contract_compensation(
            root, "2026-07", read_id_map(INPUT),
            worktime_path=INPUT / "payroll/worktime-result.json",
            generated_dir=self.directory / "generated",
        )

    def test_annual_monthly_hourly_daily_calculations_from_real_sample(self):
        paths = self.run_contract()
        records = {r["worker_id"]: r for r in
                   source_rows(paths["compensation_path"])}
        # ANNUAL: 37,200,000/12. MONTHLY: 2,900,000.
        self.assertEqual(Decimal(str(records["EP0001"]["base_salary"])), Decimal("3100000"))
        self.assertEqual(Decimal(str(records["EP0002"]["base_salary"])), Decimal("2900000"))
        # HOURLY: 13,450 x 176 ordinary hours in June.
        self.assertEqual(Decimal(str(records["EP0003"]["base_salary"])), Decimal("2367200"))
        # DAILY: 136,000 x 22 qualifying days.
        self.assertEqual(Decimal(str(records["EP0004"]["base_salary"])), Decimal("2992000"))
        # MONTHLY E006 contains position 150,000 + meal 100,000.
        self.assertEqual(Decimal(str(records["EP0006"]["base_salary"])), Decimal("3250000"))
        self.assertEqual(Decimal(str(records["EP0006"]["position_allowance"])), Decimal("150000"))
        self.assertEqual(Decimal(str(records["EP0006"]["meal_allowance"])), Decimal("100000"))
        self.assertNotIn("compensation.xlsx", paths["compensation_path"].name)

    def test_time_based_premiums_not_falsely_calculated(self):
        paths = self.run_contract()
        result = json.loads(paths["review_path"].read_text(encoding="utf-8"))
        self.assertFalse(result["finalizable"])
        self.assertFalse(result["time_based_premiums_calculated"])
        by_id = {r["employee_id"]: r for r in result["employees"]}
        self.assertIn(
            "ANNUAL_12_EQUAL_INSTALLMENTS_ASSUMED",
            by_id["E001"]["review_codes"],
        )
        self.assertEqual(result["employee_count"], 80)
        self.assertEqual(result["salary_based_worker_count"], 40)
        self.assertEqual(result["time_based_worker_count"], 40)
        self.assertEqual(len(result["service_contracts"]), 8)
        self.assertEqual(
            {entry["pay_basis"] for entry in result["service_contracts"]},
            {"HOURLY", "DAILY"},
        )
        self.assertTrue(all(
            record["status"] == "REVIEW_REQUIRED"
            for record in result["service_contracts"]
        ))
        services = {
            item["service_contract_id"]: item
            for item in result["service_contracts"]
        }
        self.assertEqual(services["SVC-001"]["billable_quantity"], "3")
        self.assertEqual(
            services["SVC-001"]["estimated_service_amount"], "690000"
        )
        self.assertEqual(services["SVC-002"]["billable_quantity"], "22")
        self.assertEqual(
            services["SVC-002"]["estimated_service_amount"], "814000"
        )
        self.assertFalse(any(item["approved"] for item in services.values()))
        filtered = json.loads(
            paths["worktime_result_path"].read_text(encoding="utf-8")
        )
        self.assertFalse(filtered["coverage_verified"])
        self.assertIsNone(filtered["close_receipt"])
        self.assertTrue(all(
            row["worker_id"] in paths["salary_workers"]
            for row in filtered["rows"]
        ))

    def test_missing_optional_service_file_is_accepted(self):
        root = self.directory / "input"
        (root / "payroll").mkdir(parents=True)
        for name in ("pay-contract.xlsx", "pay-contract-components.xlsx"):
            shutil.copy2(INPUT / "payroll" / name, root / "payroll" / name)
        result = adapter.build_contract_compensation(
            root, "2026-07", read_id_map(INPUT),
            worktime_path=INPUT / "payroll/worktime-result.json",
            generated_dir=self.directory / "config",
        )
        audit = json.loads(result["review_path"].read_text(encoding="utf-8"))
        self.assertEqual(audit["service_contracts"], [])
        self.assertFalse(audit["service_contracts_in_employee_payroll"])

    def test_contract_overlap_is_rejected_before_payroll(self):
        original = INPUT / "payroll/pay-contract.xlsx"
        patched = self.directory / "pay-contract.xlsx"
        shutil.copy2(original, patched)
        book = load_workbook(patched)
        sheet = book.active
        source = list(sheet[2])
        inserted = [cell.value for cell in source]
        inserted[0] = "CTR-DUPLICATE"
        inserted[4] = "2026-06-15"
        sheet.append(inserted)
        book.save(patched)
        book.close()
        with self.assertRaisesRegex(InputLayoutError, "overlapping contracts"):
            adapter._load_employee_contracts(patched, read_id_map(INPUT), "2026-07")

    def test_duplicate_contract_components_are_rejected(self):
        root = self.directory / "input"
        (root / "payroll").mkdir(parents=True)
        for name in ("pay-contract.xlsx", "pay-contract-components.xlsx"):
            shutil.copy2(INPUT / "payroll" / name, root / "payroll" / name)
        book = load_workbook(root / "payroll/pay-contract-components.xlsx")
        sheet = book.active
        sheet.append(["CTR-0006", "position_allowance", 7000000])
        # First ensure duplicated pay-item is caught, not silently summed.
        book.save(root / "payroll/pay-contract-components.xlsx")
        book.close()
        with self.assertRaisesRegex(InputLayoutError, "duplicate contract/item"):
            adapter.build_contract_compensation(
                root, "2026-07", read_id_map(INPUT),
                worktime_path=INPUT / "payroll/worktime-result.json",
                generated_dir=self.directory / "config",
            )


    def test_contract_components_exceeding_total_are_rejected(self):
        root = self.directory / "input"
        (root / "payroll").mkdir(parents=True)
        for name in ("pay-contract.xlsx", "pay-contract-components.xlsx"):
            shutil.copy2(INPUT / "payroll" / name, root / "payroll" / name)
        book = load_workbook(root / "payroll/pay-contract-components.xlsx")
        book.active["C2"] = 99999999
        book.save(root / "payroll/pay-contract-components.xlsx")
        book.close()
        with self.assertRaisesRegex(InputLayoutError, "fixed components exceed gross"):
            adapter.build_contract_compensation(
                root, "2026-07", read_id_map(INPUT),
                worktime_path=INPUT / "payroll/worktime-result.json",
                generated_dir=self.directory / "config",
            )

    def test_service_records_cannot_duplicate_evidence(self):
        root = self.directory / "input"
        (root / "payroll").mkdir(parents=True)
        for name in (
            "pay-contract.xlsx", "pay-contract-components.xlsx",
            "service-contracts.xlsx", "service-work-records.xlsx",
        ):
            shutil.copy2(INPUT / "payroll" / name, root / "payroll" / name)
        book = load_workbook(root / "payroll/service-work-records.xlsx")
        sheet = book.active
        sheet.append([cell.value for cell in sheet[2]])
        book.save(root / "payroll/service-work-records.xlsx")
        book.close()
        with self.assertRaisesRegex(InputLayoutError, "duplicate source evidence"):
            adapter.build_contract_compensation(
                root, "2026-07", read_id_map(INPUT),
                worktime_path=INPUT / "payroll/worktime-result.json",
                generated_dir=self.directory / "config",
            )

if __name__ == "__main__":
    unittest.main()
