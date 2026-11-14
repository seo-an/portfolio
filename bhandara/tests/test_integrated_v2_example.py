"""One canonical 80-person workbook sample using current module contracts."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from bhandara.common.io.input_layout import InputLayoutError, read_id_map

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "bhandara/examples/sample/generate.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "bhandara_current_sample_generator", GENERATOR
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IntegratedExampleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bhandara-example-")
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / "sample-80"

    def _generate(self):
        demo = _load_generator().generate(self.destination)
        self.assertEqual(demo, self.destination)
        return demo / "input"

    def test_integrated_demo_is_generated_without_legacy_service_files(self):
        source = self._generate()
        payroll = source / "payroll"
        self.assertFalse((payroll / "pay-contract-components.xlsx").exists())
        self.assertFalse((payroll / "service-contracts.xlsx").exists())
        self.assertFalse((payroll / "service-work-records.xlsx").exists())
        book = load_workbook(payroll / "pay-contract.xlsx", read_only=True)
        try:
            self.assertEqual(book.sheetnames, ["Contracts", "Components"])
            contracts = list(book["Contracts"].values)
            components = list(book["Components"].values)
        finally:
            book.close()
        self.assertEqual(len(contracts) - 1, 83)
        self.assertEqual({r[8] for r in contracts[1:]}, {
            "BASE", "TOTAL", "RATE",
        })
        self.assertEqual(sum(r[9] == "REGULAR_EMPLOYEE" for r in contracts[1:]), 80)
        e6 = next(r for r in contracts if r[1] == "E006")
        self.assertEqual(e6[8], "BASE")
        self.assertEqual(e6[3], 3500000)
        e6_components = {
            code: int(amount)
            for contract_id, code, amount in components[1:]
            if contract_id == e6[0]
        }
        self.assertEqual(e6_components, {
            "base_salary": 3500000,
            "meal_allowance": 100000,
            "position_allowance": 150000,
        })
        employee_ids = read_id_map(source)
        self.assertEqual(len(employee_ids), 80)
        ids = load_workbook(source / "common/id-map.xlsx", read_only=True)
        try:
            self.assertEqual(ids.sheetnames, ["ID_MAP", "EXTERNAL"])
        finally:
            ids.close()
        handoff = json.loads(
            (payroll / "worktime-result.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(handoff["covered_worker_ids"]), 82)
        self.assertEqual(handoff["status"], "REVIEW_REQUIRED")
        self.assertFalse(handoff["finalizable"])
        self.assertIsNone(handoff["close_receipt"])
        meta = json.loads(
            (self.destination / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(meta["schema_version"], "2.0")
        self.assertFalse((self.destination / "worktime-output").exists())
        company_policy = json.loads(
            (payroll / "company-policy.json").read_text(encoding="utf-8")
        )
        taxable = company_policy["taxability_review"]["pay_items"]
        self.assertEqual(taxable["base_salary"]["status"], "TAXABLE")
        self.assertEqual(taxable["meal_allowance"]["status"], "NON_TAXABLE")
        self.assertEqual(taxable["meal_allowance"]["cap_per_worker_period"], 100000)
        self.assertIn("SYNTHETIC", taxable["meal_allowance"]["policy_ref"])
        with self.assertRaises(FileExistsError):
            _load_generator().generate(self.destination)

    def test_v2_pto_workbook_contains_nine_new_usage_cases(self):
        """Verify committed legacy sample stays untouched; recommended v2 is current."""
        source = self._generate()
        event_book = load_workbook(source / "pto/employee-events.xlsx", read_only=True)
        try:
            rows = list(event_book.active.values)
        finally:
            event_book.close()
        expected = {
            "연차": 2, "오전 반차": 3, "오후 반차": 2,
            "조기퇴근": 1, "육아기근로시간단축": 1,
        }
        produced = [row for row in rows[1:] if
                    str(row[0]).startswith("INTEGRATED-V2-PTO-")]
        self.assertEqual(len(produced), 9)
        self.assertEqual({kind: sum(row[2] == kind for row in produced)
                          for kind in expected}, expected)
        self.assertEqual({row[1] for row in produced},
                         {f"E{i:03d}" for i in range(1, 10)})
        self.assertEqual({row[5] for row in produced}, {"APPROVED"})
        self.assertEqual(len(rows) - 1, 11)  # preserve 2 historic review events
        self.assertFalse((ROOT / "bhandara/examples/sample/input/pto" /
                          "employee-events.xlsx").samefile(
                              source / "pto/employee-events.xlsx"))

        attendance = load_workbook(
            source / "pto/work-records/2026/2026-07-attendance.xlsx",
            read_only=True,
        )
        try:
            all_rows = list(attendance.active.values)
        finally:
            attendance.close()
        by_key = {(row[0], str(row[1])): row for row in all_rows[1:]}
        for employee in ("E001", "E002"):
            self.assertNotIn((employee, "2026-07-06"), by_key)
        for employee in ("E003", "E004", "E005"):
            self.assertEqual(str(by_key[(employee, "2026-07-07")][2]), "14:00")
            self.assertEqual(by_key[(employee, "2026-07-07")][4], 0)
        for employee in ("E006", "E007"):
            self.assertEqual(str(by_key[(employee, "2026-07-08")][3]), "13:00")
            self.assertEqual(by_key[(employee, "2026-07-08")][4], 0)
        for employee, day in (("E008", "2026-07-09"),
                              ("E009", "2026-07-10")):
            self.assertEqual(str(by_key[(employee, day)][3]), "16:00")
        manifest = json.loads(
            (self.destination / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["pto_event_scenarios"], 9)
        self.assertEqual(manifest["period_pto"], "2026-07")

    def test_v2_pto_cli_ledger_outputs_usage_and_provisional_balances(self):
        """Run the actual calculator, not just count source workbook rows."""
        import subprocess
        import sys
        source = self._generate()
        destination = Path(self.temp.name) / "pto-reviewed"
        cmd = [sys.executable, str(ROOT / "run.py"), "bhandara",
               "pto-calculator", "--period", "2026-07",
               "--input-dir", str(source), "--output-dir", str(destination)]
        run = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True,
                             check=False, timeout=150)
        self.assertIn(run.returncode, (0, 1, 2), run.stderr + run.stdout)
        result = json.loads(
            (destination / "pto-result.json").read_text(encoding="utf-8"))
        by_emp = {row["employee_id"]: row for row in result["results"]}
        self.assertEqual(len(by_emp), 80)
        for emp in ("E001", "E002"):
            self.assertEqual(by_emp[emp]["ledger"]["known_used_days"], "1")
        for emp in ("E003", "E004", "E005", "E006", "E007"):
            self.assertEqual(
                by_emp[emp]["ledger"]["known_used_days"], "0.5")
        for emp in ("E008", "E009"):
            self.assertEqual(by_emp[emp]["ledger"]["known_used_days"], "0")
            self.assertEqual(len(by_emp[emp]["ledger"]["other_events"]), 1)
        self.assertIsNone(by_emp["E001"]["ledger"]["confirmed_balance_days"])
        self.assertIsNone(by_emp["E001"]["ledger"]["expired_days"])
        book = load_workbook(destination / "pto-result.xlsx", read_only=True)
        try:
            self.assertTrue({"Summary", "Accruals", "Usage", "Balances",
                             "Unresolved", "Review Required", "Run Info"}
                            <= set(book.sheetnames))
            usage = list(book["Usage"].values)
            self.assertEqual(len(usage) - 1, 7)
        finally:
            book.close()

    def test_real_worktime_handoff_feeds_new_payroll_contracts(self):
        from importlib import import_module
        source = self._generate()
        adapter = import_module("bhandara.payroll-calculator.contract_adapter")
        artifacts = adapter.build_contract_compensation(
            source, "2026-07", read_id_map(source),
            worktime_path=source / "payroll/worktime-result.json",
            generated_dir=Path(self.temp.name) / "config",
        )
        report = json.loads(
            artifacts["review_path"].read_text(encoding="utf-8")
        )
        self.assertEqual(report["employee_count"], 80)
        self.assertEqual(report["service_worker_count"], 2)
        self.assertEqual(report["contract_input_layout"], "v2")
        self.assertFalse(report["finalizable"])
        services = {item["service_contract_id"]: item
                    for item in report["service_contracts"]}
        self.assertEqual(
            services["SVC-H001"]["estimated_service_amount"], "814000"
        )
        self.assertEqual(
            services["SVC-D002"]["estimated_service_amount"], "460000"
        )
        self.assertIsNone(
            services["SVC-P003"]["estimated_service_amount"]
        )
        xlsx = load_workbook(artifacts["compensation_path"], read_only=True)
        try:
            rows = list(xlsx.active.values)
        finally:
            xlsx.close()
        self.assertEqual(len(rows) - 1, 80)
        self.assertFalse({"EXT-W001", "EXT-W002"} &
                         {x[0] for x in rows[1:]})

    def test_single_checked_in_sample_is_current_structure(self):
        """The only publicly committed 80-person Excel must match the builder."""
        baseline = ROOT / "bhandara/examples/sample/input"
        self.assertTrue((baseline / "common/employee.xlsx").is_file())
        self.assertFalse((baseline / "payroll/pay-contract-components.xlsx").exists())
        self.assertFalse((baseline / "payroll/service-contracts.xlsx").exists())
        self.assertFalse((baseline / "payroll/service-work-records.xlsx").exists())
        contracts = load_workbook(baseline / "payroll/pay-contract.xlsx",
                                  read_only=True)
        try:
            self.assertEqual(contracts.sheetnames, ["Contracts", "Components"])
            rows = list(contracts["Contracts"].values)
            self.assertEqual(len(rows) - 1, 83)
        finally:
            contracts.close()
        events = load_workbook(baseline / "pto/employee-events.xlsx",
                               read_only=True)
        try:
            source = list(events.active.values)
            self.assertEqual(len(source) - 1, 11)
            synthetic = [row for row in source[1:]
                         if str(row[0]).startswith("INTEGRATED-V2-PTO-")]
            self.assertEqual(len(synthetic), 9)
        finally:
            events.close()



if __name__ == "__main__":
    unittest.main()
