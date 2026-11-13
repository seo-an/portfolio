"""Synthetic v2 external-service contracts using Worktime, no extra service XLSX."""
from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook

from bhandara.common.io.input_layout import InputLayoutError, read_id_map


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "bhandara/examples/sample/input"
adapter = importlib.import_module("bhandara.payroll-calculator.contract_adapter")
shared = importlib.import_module("bhandara.payroll-calculator.shared_excel")


class ServiceWorktimeV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bhandara-service-wt-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "input"
        (self.root / "payroll").mkdir(parents=True)
        (self.root / "common").mkdir()
        for name in ("employee.xlsx", "id-map.xlsx"):
            shutil.copy2(SAMPLE / "common" / name, self.root / "common" / name)
        for name in ("payroll-input.xlsx", "company-policy.json"):
            shutil.copy2(SAMPLE / "payroll" / name, self.root / "payroll" / name)
        self._contract_book()
        self.worktime_path = Path(self.temp.name) / "external-worktime.json"
        self._worktime()

    def _contract_book(self):
        legacy = load_workbook(SAMPLE / "payroll/pay-contract.xlsx", read_only=True)
        extras = load_workbook(
            SAMPLE / "payroll/pay-contract-components.xlsx", read_only=True
        )
        try:
            contract_rows = list(legacy.active.values)
            fixed_rows = list(extras.active.values)[1:]
        finally:
            legacy.close()
            extras.close()
        amounts = {}
        for contract_id, code, amount in fixed_rows:
            amounts.setdefault(contract_id, {})[code] = Decimal(str(amount))
        book = Workbook()
        contracts = book.active
        contracts.title = "Contracts"
        contracts.append(
            (*contract_rows[0], "amount_type", "relationship_type",
             "party_id", "worker_id")
        )
        parts = book.create_sheet("Components")
        parts.append(("contract_id", "pay_item_code", "monthly_amount"))
        for record in contract_rows[1:]:
            cid, employee_id, basis, amount = record[:4]
            if basis in {"ANNUAL", "MONTHLY"}:
                monthly = Decimal(str(amount)) / (
                    Decimal("12") if basis == "ANNUAL" else Decimal("1")
                )
                basic = monthly - sum(
                    amounts.get(cid, {}).values(), Decimal("0")
                )
                parts.append((cid, "base_salary", float(basic)))
                for code, value in amounts.get(cid, {}).items():
                    parts.append((cid, code, float(value)))
            contracts.append((
                *record, "TOTAL" if basis in {"ANNUAL", "MONTHLY"} else "RATE",
                "REGULAR_EMPLOYEE", None, None,
            ))
        self._service_specs = [
            ("SVC-H001", None, "HOURLY", 37000, "2026-01-01", None, None,
             "Synthetic Worktime service", "RATE", "INDEPENDENT_SERVICE",
             "PARTY-001", "EXT-W001"),
            ("SVC-D002", None, "DAILY", 230000, "2026-01-01", None, 8,
             "Synthetic Worktime service", "RATE", "CORPORATE_VENDOR",
             "PARTY-002", "EXT-W002"),
            ("SVC-P003", None, "PROJECT", 5000000, "2026-01-01", None, None,
             "No auto-billing without delivery evidence", "TOTAL",
             "CORPORATE_VENDOR", "PARTY-003", None),
        ]
        for row in self._service_specs:
            contracts.append(row)
        try:
            book.save(self.root / "payroll/pay-contract.xlsx")
        finally:
            book.close()

    def _worktime(self):
        data = json.loads(
            (SAMPLE / "payroll/worktime-result.json").read_text(encoding="utf-8")
        )
        data["covered_worker_ids"] = [
            *data["covered_worker_ids"], "EXT-W001", "EXT-W002"
        ]
        data["rows"].extend([
            {"worker_id": "EXT-W001", "work_date": "2026-06-02",
             "ordinary_hours": "8", "worked_hours": "8",
             "validation_flags": []},
            {"worker_id": "EXT-W001", "work_date": "2026-06-03",
             "ordinary_hours": "8", "worked_hours": "14",
             "validation_flags": []},
            {"worker_id": "EXT-W002", "work_date": "2026-06-02",
             "ordinary_hours": "8", "worked_hours": "8",
             "validation_flags": []},
            {"worker_id": "EXT-W002", "work_date": "2026-06-03",
             "ordinary_hours": "8", "worked_hours": "8",
             "validation_flags": []},
        ])
        self.worktime_path.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    def _calculate(self):
        return adapter.build_contract_compensation(
            self.root, "2026-07", read_id_map(self.root),
            worktime_path=self.worktime_path,
            generated_dir=Path(self.temp.name) / "generated",
        )

    def test_v2_contracts_reuse_worktime_and_keep_services_out_of_payroll(self):
        paths = self._calculate()
        audit = json.loads(paths["review_path"].read_text(encoding="utf-8"))
        self.assertEqual(audit["contract_input_layout"], "v2")
        self.assertEqual(audit["employee_count"], 80)
        self.assertEqual(audit["service_worker_count"], 2)
        self.assertEqual(audit["source_hashes"]["service_contracts"],
                         "IN_PAY_CONTRACT_XLSX")
        self.assertEqual(audit["source_hashes"]["service_records"],
                         "WORKTIME_HANDOFF")
        services = {x["service_contract_id"]: x
                    for x in audit["service_contracts"]}
        self.assertEqual(set(services), {"SVC-H001", "SVC-D002", "SVC-P003"})
        self.assertEqual(services["SVC-H001"]["billable_quantity"], "22")
        self.assertEqual(services["SVC-H001"]["estimated_service_amount"], "814000")
        self.assertEqual(services["SVC-D002"]["billable_quantity"], "2")
        self.assertEqual(services["SVC-D002"]["estimated_service_amount"], "460000")
        self.assertEqual(services["SVC-P003"]["reason"],
                         "PROJECT_DELIVERY_EVIDENCE_REQUIRED")
        self.assertIsNone(services["SVC-P003"]["estimated_service_amount"])
        self.assertTrue(all(x["status"] == "REVIEW_REQUIRED" for x in services.values()))
        self.assertTrue(all(x["approved"] is False for x in services.values()))
        self.assertFalse(audit["service_contracts_in_employee_payroll"])
        book = load_workbook(paths["compensation_path"], read_only=True)
        try:
            records = list(book.active.values)
        finally:
            book.close()
        self.assertEqual(len(records) - 1, 80)
        self.assertFalse({"EXT-W001", "EXT-W002"} &
                         {x[0] for x in records[1:]})
        filtered = json.loads(
            paths["worktime_result_path"].read_text(encoding="utf-8")
        )
        self.assertEqual(len(filtered["covered_worker_ids"]), 80)
        self.assertFalse({"EXT-W001", "EXT-W002"} &
                         set(filtered["covered_worker_ids"]))
        self.assertFalse(filtered["coverage_verified"])

    def test_payroll_config_excludes_external_workers(self):
        config = shared.prepare_shared_payroll(
            self.root, "2026-07", worktime_result_path=self.worktime_path,
            generated_dir=Path(self.temp.name) / "configs",
        )
        payload = json.loads(config.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["expected_worker_ids"]), 80)
        self.assertNotIn("EXT-W001", payload["expected_worker_ids"])
        self.assertNotIn("EXT-W002", payload["expected_worker_ids"])
        self.assertEqual(len(json.loads(
            Path(payload["employment_facts_path"]).read_text(encoding="utf-8")
        )), 80)

    def _replace_contract_cell(self, row_number, header, value):
        path = self.root / "payroll/pay-contract.xlsx"
        book = load_workbook(path)
        try:
            sheet = book["Contracts"]
            headers = [x.value for x in sheet[1]]
            sheet.cell(row_number, headers.index(header) + 1).value = value
            book.save(path)
        finally:
            book.close()

    def test_external_service_worker_requires_explicit_worktime_identity(self):
        self._replace_contract_cell(82, "worker_id", None)
        with self.assertRaisesRegex(
            InputLayoutError, "service worker_id required",
        ):
            self._calculate()

    def test_uncovered_service_worker_blocks_entire_run(self):
        self._replace_contract_cell(82, "worker_id", "MISSING-EXT")
        with self.assertRaisesRegex(
            InputLayoutError, "Worktime covered worker IDs do not match",
        ):
            self._calculate()

    def test_duplicate_employee_worktime_identity_is_rejected(self):
        self._replace_contract_cell(82, "worker_id", "EP0001")
        with self.assertRaisesRegex(
            InputLayoutError, "must not duplicate employee payroll worker",
        ):
            self._calculate()

    def test_legacy_service_files_conflict_with_v2_workbook(self):
        bad_file = self.root / "payroll/service-work-records.xlsx"
        bad_file.write_bytes(b"dummy")
        with self.assertRaisesRegex(
            InputLayoutError, "conflict with legacy service-contracts.xlsx",
        ):
            self._calculate()

    def test_same_worker_cannot_have_overlapping_time_based_service_contracts(self):
        path = self.root / "payroll/pay-contract.xlsx"
        book = load_workbook(path)
        try:
            sheet = book["Contracts"]
            duplicated = list(self._service_specs[0])
            duplicated[0] = "SVC-H-DUP"
            sheet.append(duplicated)
            book.save(path)
        finally:
            book.close()
        with self.assertRaisesRegex(
            InputLayoutError, "overlapping Worktime service contracts",
        ):
            self._calculate()

    def test_vendor_can_have_multiple_independent_projects_in_same_period(self):
        path = self.root / "payroll/pay-contract.xlsx"
        book = load_workbook(path)
        try:
            sheet = book["Contracts"]
            extra = list(self._service_specs[2])
            extra[0] = "SVC-P004"
            extra[3] = 2500000
            sheet.append(extra)
            book.save(path)
        finally:
            book.close()
        result = self._calculate()
        report = json.loads(result["review_path"].read_text(encoding="utf-8"))
        projects = [
            x for x in report["service_contracts"]
            if x["pay_basis"] == "PROJECT"
        ]
        self.assertEqual(len(projects), 2)
        self.assertTrue(all(x["estimated_service_amount"] is None for x in projects))

    def test_external_party_cannot_be_encoded_as_employee(self):
        self._replace_contract_cell(82, "employee_id", "E081")
        with self.assertRaisesRegex(
            InputLayoutError, "blank employee_id",
        ):
            self._calculate()


if __name__ == "__main__":
    unittest.main()
