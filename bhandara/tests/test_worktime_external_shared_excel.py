"""End-to-end synthetic external workers in the existing Worktime Excel files.

Never modifies committed 80-person samples or real HR data. External parties
are mapped in the EXTERNAL sheet of the existing common/id-map.xlsx and never
become employees, PTO records, or salary-payroll workers.
"""
from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook, Workbook

from bhandara.common.io.input_layout import (
    InputLayoutError, hash_file, read_id_map,
)


ROOT = Path(__file__).resolve().parents[2]
from bhandara.tests._seed_fixture import SEED_INPUT
SAMPLE = SEED_INPUT
worktime = importlib.import_module("bhandara.worktime-calculator.shared_excel")
payroll = importlib.import_module("bhandara.payroll-calculator.contract_adapter")
configurator = importlib.import_module("bhandara.payroll-calculator.shared_excel")


class ExternalWorktimeExcelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bhandara-external-wt-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "input"
        for folder in ("common", "worktime"):
            (self.root / folder).mkdir(parents=True)
        for folder, filename in (
            ("common", "employee.xlsx"), ("common", "id-map.xlsx"),
            ("worktime", "work-schedule.xlsx"),
            ("worktime", "attendance.xlsx"),
        ):
            shutil.copy2(
                SAMPLE / folder / filename, self.root / folder / filename
            )
        self._add_external_mapping()
        self._add_external_worktime_rows()

    def _add_external_mapping(self):
        path = self.root / "common/id-map.xlsx"
        book = load_workbook(path)
        try:
            self.assertEqual(len(book["ID_MAP"]["A"]), 81)
            external = book.create_sheet("EXTERNAL")
            external.append(("worker_id", "security_id"))
            external.append(("EXT-W001", "SEC-EXT-001"))
            external.append(("EXT-W002", "SEC-EXT-002"))
            book.save(path)
        finally:
            book.close()

    def _add_external_worktime_rows(self):
        fixtures = (
            ("EXT-W001", "2026-06-02", "09:00", "18:00", 60, 8),
            ("EXT-W001", "2026-06-03", "08:00", "23:00", 60, 14),
            ("EXT-W002", "2026-06-02", "09:00", "18:00", 60, 8),
            ("EXT-W002", "2026-06-03", "09:00", "18:00", 60, 8),
        )
        for filename in ("work-schedule.xlsx", "attendance.xlsx"):
            path = self.root / "worktime" / filename
            book = load_workbook(path)
            try:
                sheet = book.active
                headers = [x.value for x in sheet[1]]
                self.assertIn("employee_id", headers)
                self.assertNotIn("worker_id", headers)
                col = len(headers) + 1
                sheet.cell(1, col).value = "worker_id"
                for worker, day, arrival, departure, pause, hours in fixtures:
                    values = {
                        "employee_id": None,
                        "worker_id": worker,
                        "work_date": day,
                        "break_min": pause,
                    }
                    if filename == "work-schedule.xlsx":
                        values.update({
                            "day_type": "WORK",
                            "scheduled_start": arrival,
                            "scheduled_end": departure,
                            "scheduled_work_hours": hours,
                            "note": "Synthetic external Worktime evidence",
                        })
                    else:
                        values.update({
                            "clock_in": arrival,
                            "clock_out": departure,
                            "source": "SYNTHETIC_SECURITY_READER",
                            "note": "Unapproved external attendance",
                        })
                    sheet.append([values.get(name) for name in (*headers, "worker_id")])
                book.save(path)
            finally:
                book.close()

    def _replace_cell(self, filename, sheet_name, row, col, value):
        path = self.root / filename
        book = load_workbook(path)
        try:
            book[sheet_name].cell(row, col).value = value
            book.save(path)
        finally:
            book.close()

    def _worktime_output(self):
        output = self.base / "worktime-results"
        code = worktime.run_shared_excel(self.root, "2026-06", output)
        self.assertIn(code, {0, 2})
        return output / "worktime-result.json"

    def test_legacy_employee_mapping_stays_employee_only(self):
        employees = read_id_map(self.root)
        self.assertEqual(len(employees), 80)
        self.assertEqual(employees["E001"]["worker_id"], "EP0001")
        self.assertFalse(any(k.startswith("EXT") for k in employees))
        bundle, config = worktime.read_shared_worktime(self.root, "2026-06")
        self.assertEqual(bundle["external_worker_ids"], ["EXT-W001", "EXT-W002"])
        self.assertEqual(len(bundle["sources"]["employees"]["rows"]), 82)
        self.assertEqual(len(bundle["sources"]["employees"]["lineage"]), 82)
        self.assertEqual(
            config["worktime_assignments"]["EXT-W001"]["rule_ref"],
            "EXTERNAL_SERVICE_HOURS_REVIEW_ONLY",
        )
        self.assertEqual(bundle["identity_map_sha256"], hash_file(
            self.root / "common/id-map.xlsx"
        ))

    def test_worktime_excel_to_json_is_employee_plus_external(self):
        path = self._worktime_output()
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertEqual(len(report["covered_worker_ids"]), 82)
        self.assertIn("EXT-W001", report["covered_worker_ids"])
        self.assertIn("EXT-W002", report["covered_worker_ids"])
        self.assertEqual(
            report["source_hashes"]["identity_map"],
            hash_file(self.root / "common/id-map.xlsx"),
        )
        rows = {(x["worker_id"], x["work_date"]): x for x in report["rows"]}
        self.assertEqual(
            Decimal(str(rows[("EXT-W001", "2026-06-02")]["worked_hours"])),
            Decimal("8"),
        )
        self.assertEqual(
            Decimal(str(rows[("EXT-W001", "2026-06-03")]["worked_hours"])),
            Decimal("14"),
        )
        self.assertEqual(
            Decimal(str(rows[("EXT-W002", "2026-06-03")]["worked_hours"])),
            Decimal("8"),
        )
        self.assertFalse(report["coverage_verified"])
        self.assertIsNone(report["close_receipt"])

    def _make_unified_payroll(self):
        (self.root / "payroll").mkdir(exist_ok=True)
        for filename in ("payroll-input.xlsx", "company-policy.json"):
            shutil.copy2(
                SAMPLE / "payroll" / filename, self.root / "payroll" / filename
            )
        original = load_workbook(
            SAMPLE / "payroll/pay-contract.xlsx", read_only=True
        )
        fixed = load_workbook(
            SAMPLE / "payroll/pay-contract-components.xlsx", read_only=True
        )
        try:
            old_contracts = list(original.active.values)
            old_components = list(fixed.active.values)[1:]
        finally:
            original.close()
            fixed.close()
        components_by_id: dict[str, dict[str, Decimal]] = {}
        for cid, code, amount in old_components:
            components_by_id.setdefault(cid, {})[code] = Decimal(str(amount))
        wb = Workbook()
        contracts = wb.active
        contracts.title = "Contracts"
        contracts.append((
            *old_contracts[0], "amount_type", "relationship_type",
            "party_id", "worker_id",
        ))
        comps = wb.create_sheet("Components")
        comps.append(("contract_id", "pay_item_code", "monthly_amount"))
        for old in old_contracts[1:]:
            cid, employee_id, basis, amount = old[:4]
            if basis in {"ANNUAL", "MONTHLY"}:
                monthly = Decimal(str(amount)) / (
                    Decimal("12") if basis == "ANNUAL" else Decimal("1")
                )
                allowances = components_by_id.get(cid, {})
                basic = monthly - sum(allowances.values(), Decimal("0"))
                comps.append((cid, "base_salary", float(basic)))
                for code, value in allowances.items():
                    comps.append((cid, code, float(value)))
            contracts.append((
                *old,
                "TOTAL" if basis in {"ANNUAL", "MONTHLY"} else "RATE",
                "REGULAR_EMPLOYEE", None, None,
            ))
        contracts.append((
            "SVC-H001", None, "HOURLY", 37000, "2026-01-01",
            None, None, "Hourly independent service; review only",
            "RATE", "INDEPENDENT_SERVICE", "PARTY-001", "EXT-W001",
        ))
        contracts.append((
            "SVC-D002", None, "DAILY", 230000, "2026-01-01",
            None, 8, "Daily outside vendor; review only",
            "RATE", "CORPORATE_VENDOR", "PARTY-002", "EXT-W002",
        ))
        contracts.append((
            "SVC-P003", None, "PROJECT", 5000000, "2026-01-01",
            None, None, "Unverified project delivery",
            "TOTAL", "CORPORATE_VENDOR", "PARTY-003", None,
        ))
        try:
            wb.save(self.root / "payroll/pay-contract.xlsx")
        finally:
            wb.close()

    def test_actual_worktime_result_feeds_unified_payroll_without_service_excel(self):
        handoff = self._worktime_output()
        self._make_unified_payroll()
        artifacts = payroll.build_contract_compensation(
            self.root, "2026-07", read_id_map(self.root),
            worktime_path=handoff,
            generated_dir=self.base / "payroll-generated",
        )
        report = json.loads(
            artifacts["review_path"].read_text(encoding="utf-8")
        )
        self.assertEqual(report["employee_count"], 80)
        self.assertEqual(report["service_worker_count"], 2)
        services = {x["service_contract_id"]: x
                    for x in report["service_contracts"]}
        self.assertEqual(
            services["SVC-H001"]["estimated_service_amount"], "814000"
        )
        self.assertEqual(
            services["SVC-D002"]["estimated_service_amount"], "460000"
        )
        self.assertIsNone(
            services["SVC-P003"]["estimated_service_amount"]
        )
        self.assertEqual(
            {x["source_kind"] for x in services.values()},
            {"WORKTIME_UNCLOSED", "PROJECT_CONTRACT"},
        )
        self.assertTrue(all(x["approved"] is False for x in services.values()))
        self.assertFalse(report["finalizable"])
        self.assertFalse(report["service_contracts_in_employee_payroll"])
        book = load_workbook(artifacts["compensation_path"], read_only=True)
        try:
            rows = list(book.active.values)
        finally:
            book.close()
        self.assertEqual(len(rows) - 1, 80)
        self.assertFalse(
            {"EXT-W001", "EXT-W002"} & {x[0] for x in rows[1:]}
        )
        config = configurator.prepare_shared_payroll(
            self.root, "2026-07", worktime_result_path=handoff,
            generated_dir=self.base / "payroll-config",
        )
        data = json.loads(config.read_text(encoding="utf-8"))
        self.assertEqual(len(data["expected_worker_ids"]), 80)
        self.assertFalse(
            {"EXT-W001", "EXT-W002"} & set(data["expected_worker_ids"])
        )

    def test_missing_external_mapping_is_rejected(self):
        path = self.root / "common/id-map.xlsx"
        book = load_workbook(path)
        try:
            del book["EXTERNAL"]
            book.save(path)
        finally:
            book.close()
        with self.assertRaisesRegex(
            InputLayoutError, "not in id-map.xlsx EXTERNAL",
        ):
            worktime.read_shared_worktime(self.root, "2026-06")

    def test_unknown_external_schedule_worker_is_rejected(self):
        filename = "worktime/work-schedule.xlsx"
        path = self.root / filename
        wb = load_workbook(path)
        try:
            sheet = wb.active
            header = [c.value for c in sheet[1]]
            sheet.cell(sheet.max_row - 3, header.index("worker_id") + 1).value = "UNKNOWN"
            wb.save(path)
        finally:
            wb.close()
        with self.assertRaisesRegex(
            InputLayoutError, "external worker_id not in",
        ):
            worktime.read_shared_worktime(self.root, "2026-06")

    def test_external_and_employee_column_cannot_be_filled_together(self):
        path = self.root / "worktime/attendance.xlsx"
        book = load_workbook(path)
        try:
            sheet = book.active
            headers = [c.value for c in sheet[1]]
            row_number = sheet.max_row
            sheet.cell(row_number, headers.index("employee_id") + 1).value = "E001"
            book.save(path)
        finally:
            book.close()
        with self.assertRaisesRegex(
            InputLayoutError, "exactly one of employee_id",
        ):
            worktime.read_shared_worktime(self.root, "2026-06")

    def test_external_worker_cannot_reuse_employee_identity_or_security(self):
        self._replace_cell(
            "common/id-map.xlsx", "EXTERNAL", 2, 1, "EP0001"
        )
        with self.assertRaisesRegex(
            InputLayoutError, "collides with employee identity",
        ):
            worktime.read_shared_worktime(self.root, "2026-06")
        self._replace_cell(
            "common/id-map.xlsx", "EXTERNAL", 2, 1, "EXT-W001"
        )
        self._replace_cell(
            "common/id-map.xlsx", "EXTERNAL", 2, 2, "SEC-0001"
        )
        with self.assertRaisesRegex(
            InputLayoutError, "duplicate security_id",
        ):
            worktime.read_shared_worktime(self.root, "2026-06")

    def test_identity_map_change_updates_batch_lineage(self):
        first, _ = worktime.read_shared_worktime(self.root, "2026-06")
        self._replace_cell(
            "common/id-map.xlsx", "EXTERNAL", 2, 2, "SEC-EXT-MODIFIED"
        )
        second, _ = worktime.read_shared_worktime(self.root, "2026-06")
        self.assertNotEqual(first["batch_id"], second["batch_id"])
        self.assertNotEqual(
            first["identity_map_sha256"], second["identity_map_sha256"]
        )


if __name__ == "__main__":
    unittest.main()
