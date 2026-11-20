"""Contract tests for seven fixed one-sheet Payroll input workbooks.

These tests validate the published *schema*, not Excel reader/Tool CLI behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "payroll" / "input-files.json"

EXPECTED_FILES = {
    "contracts": "pay-contract.xlsx",
    "allowance_assignments": "allowance-assignments.xlsx",
    "fixed_allowance_map": "fixed-allowance-map.xlsx",
    "deduction_map": "deduction-map.xlsx",
    "overtime_rules": "overtime-rules.xlsx",
    "bonus_budget": "bonus-budget.xlsx",
    "bonus_allocation": "bonus-allocation.xlsx",
}


class PayrollInputFilesContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.files = cls.data["workbooks"]

    def test_input_location_is_explicit(self):
        self.assertEqual(self.data["input_directory"], "payroll")

    def test_fixed_filename_roles(self):
        self.assertEqual(self.data["tool"], "payroll")
        self.assertEqual(self.data["schema_version"], "1.1")
        self.assertEqual(self.data["input_directory"], "payroll")
        self.assertEqual({role: row["filename"] for role, row in self.files.items()},
                         EXPECTED_FILES)

    def test_filename_sheet_uniqueness_and_single_sheet(self):
        filenames = [row["filename"] for row in self.files.values()]
        sheetnames = [row["sheet"] for row in self.files.values()]
        self.assertEqual(len(set(filenames)), len(filenames))
        self.assertEqual(len(set(sheetnames)), len(sheetnames))
        for row in self.files.values():
            self.assertTrue(row["filename"].endswith(".xlsx"))
            self.assertTrue(row["sheet"])
            self.assertIsInstance(row["columns"], list)
            self.assertEqual(len(row["columns"]), len(set(row["columns"])))

    def test_worktime_minutes_not_duplicated_in_contracts(self):
        columns = self.files["contracts"]["columns"]
        self.assertNotIn("standard_day_minutes", columns)
        self.assertIn("daily_base_rate", columns)
        self.assertIn("deduction_code", columns)

    def test_allowance_assignments_join_only_by_contract(self):
        self.assertEqual(self.files["allowance_assignments"]["columns"],
                         ["contract_id", "allowance_id", "level"])
        self.assertIn("employee_id", self.files["contracts"]["columns"])

    def test_display_names_live_in_existing_mapping_roles(self):
        self.assertIn("allowance_name", self.files["fixed_allowance_map"]["columns"])
        self.assertIn("bonus_name", self.files["bonus_budget"]["columns"])
        self.assertEqual(len(self.files), 7)

    def test_deduction_rates_are_policy_mapping(self):
        columns = self.files["deduction_map"]["columns"]
        self.assertEqual(columns[:5],
                         ["deduction_code", "national_pension", "health_insurance",
                          "longterm_care", "employment_insurance"])
        self.assertNotIn("employee_id", columns)


if __name__ == "__main__":
    unittest.main()
