"""Public 80-person fixture: fixed paths, Excel/ID mapping, and all three CLIs.

No private Gateway/Gearbox fixtures; all tests use the checked-in sample.
"""
from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from bhandara.common.io.input_layout import (
    InputLayoutError, ROLE_PATHS, choose_path, next_result_dir, period_bounds, read_id_map, hash_file,
)

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "bhandara/examples/sample/input"


def invoke(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "run.py"), *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


class SharedLayoutFixtureTests(unittest.TestCase):
    def test_real_excel_fixtures_are_committed(self):
        self.assertTrue(SAMPLE.is_dir())
        files = list(SAMPLE.rglob("*.xlsx"))
        self.assertGreaterEqual(len(files), 10)
        necessary = (
            "common/employee.xlsx", "common/id-map.xlsx",
            "pto/work-schedule.xlsx", "pto/work-schedule-assignment.xlsx",
            "pto/work-records/2026/2026-07-schedule.xlsx",
            "pto/work-records/2026/2026-07-attendance.xlsx",
            "pto/employee-events.xlsx",
            "worktime/work-schedule.xlsx", "worktime/attendance.xlsx",
            "payroll/pay-contract.xlsx", "payroll/pay-contract-components.xlsx",
            "payroll/service-contracts.xlsx", "payroll/payroll-input.xlsx",
        )
        for relative in necessary:
            with self.subTest(filename=relative):
                self.assertGreater(choose_path(SAMPLE, relative).stat().st_size, 500)
        self.assertTrue((SAMPLE / "payroll/worktime-result.json").is_file())

    def test_contract_examples_cover_all_payment_bases(self):
        contract = SAMPLE / "payroll/pay-contract.xlsx"
        book = load_workbook(contract, read_only=True)
        try:
            rows = list(book.active.values)
        finally:
            book.close()
        self.assertEqual(len(rows) - 1, 80)
        self.assertEqual(
            {row[2] for row in rows[1:]},
            {"ANNUAL", "MONTHLY", "HOURLY", "DAILY"},
        )
        service = load_workbook(
            SAMPLE / "payroll/service-contracts.xlsx", read_only=True
        )
        try:
            self.assertEqual(service.active.max_row - 1, 8)
        finally:
            service.close()

    def test_mapping_is_readable_80_unique_one_to_one(self):
        mapping = read_id_map(SAMPLE)
        self.assertEqual(len(mapping), 80)
        self.assertEqual(mapping["E001"]["worker_id"], "EP0001")
        self.assertEqual(mapping["E080"]["security_id"], "SEC-0080")
        self.assertEqual(len({x["security_id"] for x in mapping.values()}), 80)
        book = load_workbook(SAMPLE / "common/id-map.xlsx", read_only=True)
        try:
            self.assertIn("ID_MAP", book.sheetnames)
            headers = next(book["ID_MAP"].values)
            self.assertIn("payroll_id", headers)
        finally:
            book.close()

    def test_test_case_index_is_separate_from_hr_inputs(self):
        # Case labels explain synthetic scenarios; production calculators do
        # not read the case index or require case columns in source workbooks.
        case_path = SAMPLE.parent / "test-cases.json"
        self.assertTrue(case_path.is_file())
        self.assertFalse(case_path.is_relative_to(SAMPLE))
        cases = json.loads(case_path.read_text(encoding="utf-8"))
        expected_cases = {
            "LOW_ATTENDANCE": "E002",
            "MISSING_RAW_EVENT": "E005",
            "TERMINATED_JUL20": "E007",
            "NIGHT_SHIFT": "E012",
            "TERMINATED_JUL31": "E019",
            "CHILDCARE_REDUCED": "E031",
            "DUPLICATE_RAW_TAG": "E044",
            "FLEXIBLE_REVIEW": "E067",
        }
        self.assertEqual(
            set(cases), set(expected_cases) | {"NORMAL_OR_WORKSYSTEM_REVIEW"}
        )
        for case, ident in expected_cases.items():
            self.assertEqual(cases[case], [ident])
        self.assertEqual(len(cases["NORMAL_OR_WORKSYSTEM_REVIEW"]), 72)
        flattened = [employee for group in cases.values() for employee in group]
        self.assertEqual(len(flattened), 80)
        self.assertEqual(len(set(flattened)), 80)

        book = load_workbook(SAMPLE / "common/employee.xlsx", read_only=True)
        try:
            rows = list(book.active.values)
        finally:
            book.close()
        self.assertEqual(
            rows[0],
            ("employee_id", "hire_date", "termination_date", "work_system"),
        )
        self.assertEqual(len(rows), 81)
        self.assertEqual({row[0] for row in rows[1:]}, set(flattened))
        self.assertEqual(
            {row[0]: row[2] for row in rows[1:] if row[2]},
            {"E007": "2026-07-20", "E019": "2026-07-31"},
        )
        self.assertEqual(len({row[3] for row in rows[1:]}), 6)

        book = load_workbook(SAMPLE / "common/id-map.xlsx", read_only=True)
        try:
            self.assertIn("ID_MAP", book.sheetnames)
            mappings = list(book["ID_MAP"].values)
        finally:
            book.close()
        self.assertEqual(
            mappings[0],
            ("employee_id", "security_id", "worker_id", "payroll_id"),
        )
        self.assertEqual(len(mappings), 81)
        self.assertEqual({row[0] for row in mappings[1:]}, set(flattened))
        self.assertEqual(len({row[1] for row in mappings[1:]}), 80)
        self.assertEqual(len({row[2] for row in mappings[1:]}), 80)
        self.assertEqual(len({row[3] for row in mappings[1:]}), 80)

    def test_committed_worktime_handoff_matches_current_excel_hashes(self):
        # The sample Payroll bridge is intentionally a fixed Worktime handoff.
        # Editing source Excel without refreshing its provenance must fail here.
        handoff = json.loads(
            (SAMPLE / "payroll/worktime-result.json").read_text(encoding="utf-8")
        )
        for role, filename in (
            ("employees", "common/employee.xlsx"),
            ("schedule", "worktime/work-schedule.xlsx"),
            ("attendance", "worktime/attendance.xlsx"),
        ):
            with self.subTest(role=role):
                self.assertEqual(
                    handoff["source_hashes"][role],
                    hash_file(SAMPLE / filename),
                    f"stale Worktime fixture: {role} hash; refresh handoff before merge",
                )

    def test_manifest_files_are_real_default_input_contract(self):
        for module in ("pto", "worktime", "payroll"):
            path = ROOT / "bhandara" / f"{module}-calculator/module.json"
            with self.subTest(module=module):
                content = json.loads(path.read_text(encoding="utf-8"))
                shared = content["shared_excel_input"]
                self.assertEqual(shared["roles"], ROLE_PATHS[module])
                self.assertEqual(
                    shared["common_roles"], ROLE_PATHS["common"]
                )

    def test_no_fuzzy_input_fallback_and_no_path_escape(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            with self.assertRaisesRegex(InputLayoutError, "Missing required input"):
                choose_path(root, "common/employee.xlsx")
            with self.assertRaisesRegex(InputLayoutError, "escapes"):
                choose_path(root, "../other.xlsx")
            with self.assertRaisesRegex(InputLayoutError, "relative"):
                choose_path(root, "/tmp/private.xlsx")
        self.assertEqual(period_bounds("2026-07"), ("2026-07-01", "2026-07-31"))
        for bad in ("2026-13", "2026-7", "2026-00", "202607"):
            with self.subTest(period=bad):
                with self.assertRaises(InputLayoutError):
                    period_bounds(bad)

    def test_default_output_never_overwrites_prior_result(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname) / "input"
            root.mkdir()
            first = next_result_dir(root, "worktime-calculator")
            self.assertEqual(first.name, "worktime-calculator")
            first.mkdir(parents=True)
            other = next_result_dir(root, "worktime-calculator")
            self.assertEqual(other.name, "worktime-calculator-001")
            self.assertFalse(other.exists())

    def test_conflicting_id_map_fails_before_calculation(self):
        with tempfile.TemporaryDirectory(prefix="bhandara-mapping-") as dirname:
            root = Path(dirname)
            (root / "common").mkdir()
            source = SAMPLE / "common/id-map.xlsx"
            shutil.copy2(source, root / "common/id-map.xlsx")
            book = load_workbook(root / "common/id-map.xlsx")
            sheet = book["ID_MAP"]
            sheet["C3"] = sheet["C2"].value  # duplicate worker_id
            book.save(root / "common/id-map.xlsx")
            book.close()
            with self.assertRaisesRegex(InputLayoutError, "duplicated identity"):
                read_id_map(root)

    def test_duplicate_attendance_is_isolated_to_worker_day(self):
        with tempfile.TemporaryDirectory(prefix="bhandara-duplicate-") as dirname:
            root = Path(dirname)
            for relative in (
                "common/id-map.xlsx", "common/employee.xlsx",
                "worktime/work-schedule.xlsx", "worktime/attendance.xlsx",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(SAMPLE / relative, target)
            book = load_workbook(root / "worktime/attendance.xlsx")
            sheet = book.active
            sheet.append([cell.value for cell in sheet[2]])
            book.save(root / "worktime/attendance.xlsx")
            book.close()
            result = invoke(
                "bhandara", "worktime-calculator", "--period", "2026-06",
                "--input-dir", root, "--output-dir", root / "output",
            )
            self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
            output = root / "output" / "worktime-result.json"
            self.assertTrue(output.is_file(), result.stderr)
            reviewed = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(reviewed["status"], "BLOCKED")
            self.assertGreater(len(reviewed["rows"]), 1000)
            report = json.loads(
                (output.parent / "worktime-review.json").read_text(encoding="utf-8")
            )
            self.assertTrue(any(
                issue["code"] == "WORKTIME_DUPLICATE_DAY"
                for issue in report["issues"]
            ))

    def test_payroll_rejects_stale_worktime_handoff(self):
        loader = importlib.import_module("bhandara.payroll-calculator.shared_excel")
        with tempfile.TemporaryDirectory(prefix="bhandara-stale-") as dirname:
            root = Path(dirname)
            for relative in (
                "common/id-map.xlsx", "common/employee.xlsx",
                "worktime/work-schedule.xlsx", "worktime/attendance.xlsx",
                "payroll/pay-contract.xlsx", "payroll/pay-contract-components.xlsx",
            "payroll/service-contracts.xlsx", "payroll/payroll-input.xlsx",
                "payroll/company-policy.json", "payroll/worktime-result.json",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(SAMPLE / relative, target)
            book = load_workbook(root / "worktime/attendance.xlsx")
            sheet = book.active
            sheet["F2"] = "MODIFIED_SOURCE"
            book.save(root / "worktime/attendance.xlsx")
            book.close()
            with self.assertRaisesRegex(InputLayoutError, "Stale Worktime handoff"):
                loader.prepare_shared_payroll(root, "2026-07")


class SharedLayoutThreeModulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="bhandara-shared-e2e-")
        cls.workdir = Path(cls.temp.name)
        cls.runs = {}
        for module, month in (
            ("worktime-calculator", "2026-06"),
            ("pto-calculator", "2026-07"),
            ("payroll-calculator", "2026-07"),
        ):
            output = cls.workdir / module
            response = invoke(
                "bhandara", module, "--period", month,
                "--input-dir", SAMPLE, "--output-dir", output,
            )
            cls.runs[module] = (response, output)
            if response.returncode not in (0, 1, 2):
                raise AssertionError(response.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_auto_configs_are_written_beside_output_not_source(self):
        config_dir = self.workdir / "config"
        self.assertTrue(config_dir.is_dir(), "PTO and Payroll must use writable output-adjacent config")
        generated = list(config_dir.glob("*.json"))
        names = [path.name for path in generated]
        self.assertTrue(any(name.startswith("pto-auto-2026-07-") for name in names), names)
        self.assertTrue(any(name.startswith("payroll-auto-2026-07-") for name in names), names)
        self.assertTrue(any(name.startswith("employment-facts-2026-07-") for name in names), names)
        self.assertFalse(
            (SAMPLE.parent / "config").exists(),
            "public fixture checkout must stay read-only and clean",
        )

    def test_worktime_80_people_from_xlsx_no_manual_json(self):
        run, output = self.runs["worktime-calculator"]
        self.assertEqual(run.returncode, 2, run.stderr + run.stdout)
        self.assertTrue(
            (output / "worktime-result.json").is_file(),
            run.stderr + "\n" + run.stdout,
        )
        data = json.loads((output / "worktime-result.json").read_text())
        self.assertEqual(data["status"], "REVIEW_REQUIRED")
        self.assertEqual(len(data["covered_worker_ids"]), 80)
        self.assertGreater(len(data["rows"]), 1500)
        self.assertFalse(data["finalizable"])
        self.assertIsNone(data["close_receipt"])
        self.assertTrue((output / "normalized-input.json").is_file())
        self.assertTrue((output / "worktime-config.json").is_file())

    def test_pto_80_people_from_xlsx_no_manual_json(self):
        run, output = self.runs["pto-calculator"]
        self.assertEqual(run.returncode, 1, run.stderr + run.stdout)
        data = json.loads((output / "pto-result.json").read_text())
        self.assertEqual(data["status"], "REVIEW_REQUIRED")
        self.assertEqual(len(data["results"]), 80)
        self.assertFalse(data["approved"])
        self.assertFalse(data["finalizable"])

    def test_payroll_80_people_from_xlsx_no_manual_json(self):
        run, output = self.runs["payroll-calculator"]
        self.assertEqual(run.returncode, 2, run.stderr + run.stdout)
        data = json.loads((output / "payroll-calculation.json").read_text())
        self.assertEqual(data["status"], "REVIEW_REQUIRED")
        self.assertEqual(len(data["expected_worker_ids"]), 80)
        self.assertEqual(len(data["composition"]["worker_runs"]), 80)
        self.assertFalse(data["finalizable"])
        self.assertFalse(data["ledger_committed"])
        report_path = output / "contract-basis-review.json"
        self.assertTrue(report_path.is_file(), run.stderr + run.stdout)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["employee_count"], 80)
        self.assertEqual(report["salary_based_worker_count"], 40)
        self.assertEqual(report["time_based_worker_count"], 40)
        self.assertEqual(len(report["service_contracts"]), 8)
        self.assertFalse(report["service_contracts_in_employee_payroll"])
        self.assertTrue(
            all(not worker["approved"] and not worker["finalizable"]
                for worker in report["employees"])
        )
        self.assertTrue(
            (output / "contract-basis-review.xlsx").is_file()
        )
        employees = {row["employee_id"]: row for row in report["employees"]}
        self.assertEqual(
            employees["E001"]["contract_details"][0]["pay_basis"], "ANNUAL"
        )
        self.assertEqual(
            employees["E003"]["contract_details"][0]["pay_basis"], "HOURLY"
        )
        self.assertIn(
            "NONMONTHLY_PREMIUM_NOT_CALCULATED", employees["E003"]["review_codes"]
        )
        self.assertEqual(
            employees["E004"]["contract_details"][0]["pay_basis"], "DAILY"
        )
        self.assertIn(
            "WEEKLY_PAID_HOLIDAY_NOT_RESOLVED", employees["E004"]["review_codes"]
        )


if __name__ == "__main__":
    unittest.main()
