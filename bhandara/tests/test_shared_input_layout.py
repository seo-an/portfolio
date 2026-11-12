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
    InputLayoutError, ROLE_PATHS, choose_path, next_result_dir, period_bounds, read_id_map,
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
            "payroll/compensation.xlsx", "payroll/payroll-input.xlsx",
        )
        for relative in necessary:
            with self.subTest(filename=relative):
                self.assertGreater(choose_path(SAMPLE, relative).stat().st_size, 500)
        self.assertTrue((SAMPLE / "payroll/worktime-result.json").is_file())

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
                "payroll/compensation.xlsx", "payroll/payroll-input.xlsx",
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


if __name__ == "__main__":
    unittest.main()
