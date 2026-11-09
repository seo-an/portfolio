"""Synthetic PTO integration gates (no Hermes, private fixtures or credentials)."""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "bhandara/pto-calculator/examples/generate_demo.py"


def invoke(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *map(str, args)], cwd=ROOT,
                          capture_output=True, text=True, check=False)


class PTOStandaloneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        result = invoke(GENERATOR, "--output-dir", self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.inputs = self.root / "input"
        self.config = self.root / "config.json"
        self.output = self.root / "results"

    def run_pto(self):
        return invoke(ROOT / "run.py", "bhandara", "pto-calculator",
                      "--config", self.config, "--input-dir", self.inputs,
                      "--output-dir", self.output)

    def result_json(self, filename="pto-result.json"):
        return json.loads((self.output / filename).read_text(encoding="utf-8"))

    def test_pure_core_calculations_unchanged(self):
        core = importlib.import_module("bhandara.pto-calculator.src.core")
        self.assertEqual(core.annual_days_for_service_year(1), 15)
        self.assertEqual(core.annual_days_for_service_year(3), 16)
        self.assertEqual(core.annual_days_for_service_year(21), 25)
        grants = core.anniversary_grants(date(2025, 1, 1), date(2026, 1, 1))
        self.assertEqual(len(grants), 12)
        self.assertEqual(sum(x["raw_days"] for x in grants), Decimal("26"))

    def test_demo_runs_with_local_excel_and_no_approval(self):
        response = self.run_pto()
        self.assertIn(response.returncode, (0, 1), response.stderr + response.stdout)
        value = self.result_json()
        self.assertEqual(value["schema_version"], "1.0")
        self.assertEqual(value["module_id"], "pto-calculator")
        self.assertFalse(value["approved"])
        self.assertFalse(value["finalizable"])
        self.assertEqual(len(value["results"]), 2)
        self.assertEqual({x["employee_id"] for x in value["results"]}, {"E001", "E005"})
        self.assertEqual(len(value["source_hashes"]), 5)
        self.assertTrue((self.output / "pto-result.xlsx").is_file())
        self.assertTrue((self.output / "pto-review.json").is_file())
        receipt = json.loads((self.output / "pto-run.json").read_text())
        self.assertFalse(receipt["approved"])
        self.assertFalse(receipt["finalizable"])
        self.assertEqual(len(receipt["output_sha256"]), 3)

    def test_second_run_uses_coordinated_suffix(self):
        first = self.run_pto()
        self.assertIn(first.returncode, (0, 1), first.stderr + first.stdout)
        second = self.run_pto()
        self.assertIn(second.returncode, (0, 1), second.stderr + second.stdout)
        for name in ("pto-result", "pto-review", "pto-run"):
            self.assertTrue((self.output / f"{name}(1).json").is_file())
        self.assertTrue((self.output / "pto-result(1).xlsx").is_file())
        self.assertTrue((self.output / "pto-result.json").is_file())

    def test_bad_employee_does_not_erase_other_employee(self):
        path = self.inputs / "employee.xlsx"
        book = load_workbook(path)
        sheet = book.active
        sheet["B2"] = "not-a-date"
        book.save(path)
        book.close()
        result = self.run_pto()
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        payload = self.result_json()
        self.assertEqual(payload["status"], "ERROR")
        self.assertTrue(any(x["employee_id"] == "E005" for x in payload["results"]))
        self.assertFalse(any(x["employee_id"] == "E001" for x in payload["results"]))
        review = json.loads((self.output / "pto-review.json").read_text())
        self.assertTrue(any(x["code"] == "INVALID_DATE" and x["row_number"] == 2
                            for x in review["findings"]))

    def test_extra_headers_do_not_require_manual_excel_cleanup(self):
        path = self.inputs / "employee.xlsx"
        book = load_workbook(path)
        book.active["E1"] = "unused_custom_column"
        book.active["E2"] = "ignore"
        book.active["E3"] = "also-ignore"
        book.save(path)
        book.close()
        response = self.run_pto()
        self.assertIn(response.returncode, (0, 1), response.stderr + response.stdout)

    def test_required_header_absent_fails_without_writing_results(self):
        path = self.inputs / "employee.xlsx"
        book = load_workbook(path)
        book.active["B1"] = "incorrect_header"
        book.save(path)
        book.close()
        response = self.run_pto()
        self.assertEqual(response.returncode, 2)
        self.assertIn("PTO_INVALID", response.stderr)
        self.assertFalse((self.output / "pto-result.json").exists())

    def test_formula_is_not_interpreted_as_verified_hire_date(self):
        path = self.inputs / "employee.xlsx"
        book = load_workbook(path)
        book.active["B2"] = "=TODAY()"
        book.save(path)
        book.close()
        response = self.run_pto()
        self.assertEqual(response.returncode, 2)
        review = json.loads((self.output / "pto-review.json").read_text())
        codes = {x["code"] for x in review["findings"]}
        self.assertIn("FORMULA_UNSUPPORTED", codes)
        self.assertIn("E005", {x["employee_id"] for x in self.result_json()["results"]})

    def test_wrong_config_schema_refused(self):
        config = json.loads(self.config.read_text())
        config["schema_version"] = "9.9"
        self.config.write_text(json.dumps(config))
        response = self.run_pto()
        self.assertEqual(response.returncode, 2)
        self.assertFalse((self.output / "pto-result.json").exists())

    def test_source_path_cannot_escape_input_root(self):
        config = json.loads(self.config.read_text())
        config["files"]["employees"] = "../../employee.xlsx"
        self.config.write_text(json.dumps(config))
        response = self.run_pto()
        self.assertEqual(response.returncode, 2)
        self.assertFalse((self.output / "pto-result.json").exists())

    def test_module_never_imports_private_gearbox(self):
        source = ROOT / "bhandara" / "pto-calculator" / "src"
        self.assertTrue((source / "engine.py").is_file())
        for path in source.glob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("from gearbox.", content)
            self.assertNotIn("import gearbox.", content)


if __name__ == "__main__":
    unittest.main()
