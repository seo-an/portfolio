"""PTO v3 pure-module migration tests (no employee source data)."""
from __future__ import annotations

import ast
import importlib
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path


def module(name: str):
    return importlib.import_module(f"bhandara.paid-time-off.{name}")


class EligibilityIndependentTests(unittest.TestCase):
    def setUp(self):
        self.api = module("eligibility")

    def test_monthly_present_and_absent(self):
        calc = self.api.evaluate_monthly_full_attendance
        good = calc(denominator_included_days=20, not_present_days=0,
                    coverage_complete=True, source_status="FINAL")
        bad = calc(denominator_included_days=20, not_present_days=1,
                   coverage_complete=True, source_status="FINAL")
        self.assertEqual(good["eligibility"], "ELIGIBLE")
        self.assertEqual(bad["eligibility"], "NOT_ELIGIBLE")
        self.assertFalse(good["approved"])

    def test_annual_exact_boundary_and_below(self):
        calc = self.api.evaluate_annual_attendance_80
        args = {"denominator_included_days": 100, "coverage_complete": True,
                "source_status": "FINAL"}
        good = calc(attendance_credited_days=80, **args)
        bad = calc(attendance_credited_days=79, **args)
        self.assertEqual(good["eligibility"], "ELIGIBLE")
        self.assertEqual(good["attendance_rate"], "0.8")
        self.assertEqual(bad["eligibility"], "NOT_ELIGIBLE")

    def test_missing_coverage_and_zero_denominator_not_eligible(self):
        calc = self.api.evaluate_monthly_full_attendance
        for complete, days in ((False, 20), (True, 0)):
            result = calc(denominator_included_days=days, not_present_days=0,
                          coverage_complete=complete, source_status="FINAL")
            self.assertEqual(result["eligibility"], "UNDETERMINED")
            self.assertTrue(result["review_codes"])

    def test_non_final_source_not_promoted_to_eligible(self):
        result = self.api.evaluate_annual_attendance_80(
            denominator_included_days=20, attendance_credited_days=20,
            coverage_complete=True, source_status="REVIEW_REQUIRED")
        self.assertEqual(result["eligibility"], "UNDETERMINED")

    def test_invalid_denominator_and_credit_fail_closed(self):
        with self.assertRaises(ValueError):
            self.api.evaluate_annual_attendance_80(
                denominator_included_days=10, attendance_credited_days=11,
                coverage_complete=True, source_status="FINAL")
        with self.assertRaises(ValueError):
            self.api.evaluate_monthly_full_attendance(
                denominator_included_days=-2, not_present_days=0,
                coverage_complete=True, source_status="FINAL")


class EntitlementIndependentTests(unittest.TestCase):
    def setUp(self):
        self.api = module("entitlement")

    def test_legacy_anniversary_11_monthly_plus_15_annual(self):
        rows = self.api.calculate_anniversary_grants(
            hire_date=date(2025, 1, 1), as_of_date=date(2026, 1, 1),
            monthly_eligibility=lambda _s, _e: "ELIGIBLE",
            annual_eligibility=lambda _s, _e: "ELIGIBLE",
        )
        self.assertEqual(len(rows), 12)
        self.assertEqual(sum((r["raw_days"] for r in rows), Decimal("0")), Decimal("26"))
        self.assertEqual(rows[-1]["grant_date"], date(2026, 1, 1))

    def test_under_80_fallback_does_not_double_award_first_11_months(self):
        rows = self.api.calculate_anniversary_grants(
            hire_date=date(2025, 1, 1), as_of_date=date(2026, 1, 1),
            monthly_eligibility=lambda _s, _e: "ELIGIBLE",
            annual_eligibility=lambda _s, _e: "NOT_ELIGIBLE",
        )
        self.assertEqual(len(rows), 12)
        self.assertEqual(sum((r["raw_days"] for r in rows), Decimal("0")), Decimal("12"))
        self.assertEqual(len([r for r in rows if r["grant_type"] == "monthly_under_80"]), 1)

    def test_undetermined_eligibility_never_creates_numeric_grant(self):
        rows = self.api.calculate_anniversary_grants(
            hire_date=date(2025, 1, 31), as_of_date=date(2025, 3, 1),
            monthly_eligibility=lambda _s, _e: "UNDETERMINED",
            annual_eligibility=lambda _s, _e: "UNDETERMINED",
        )
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["raw_days"])
        self.assertEqual(rows[0]["period_start"], date(2025, 1, 31))
        self.assertEqual(rows[0]["period_end"], date(2025, 2, 27))

    def test_no_silent_eligibility_default(self):
        with self.assertRaises(ValueError):
            self.api.calculate_anniversary_grants(
                hire_date=date(2025, 1, 1), as_of_date=date(2026, 1, 1),
                monthly_eligibility=None,
                annual_eligibility=lambda _s, _e: "ELIGIBLE",
            )
        with self.assertRaises(ValueError):
            self.api.calculate_anniversary_grants(
                hire_date=date(2025, 1, 1), as_of_date=date(2025, 3, 1),
                monthly_eligibility=lambda _s, _e: "INVALID",
                annual_eligibility=lambda _s, _e: "ELIGIBLE",
            )

    def test_service_year_extra_day_cap(self):
        self.assertEqual(self.api.annual_days_for_service_year(1), 15)
        self.assertEqual(self.api.annual_days_for_service_year(3), 16)
        self.assertEqual(self.api.annual_days_for_service_year(21), 25)


class DeductionQuantityIndependentTests(unittest.TestCase):
    def setUp(self):
        self.api = module("deduction-quantity")

    def test_full_half_quarter(self):
        for unit, expected in [("DAY", "1"), ("HALF_DAY", "0.5"),
                               ("QUARTER_DAY", "0.25")]:
            result = self.api.calculate_deduction_quantity(unit=unit)
            self.assertEqual(result["quantity_days"], expected)
            self.assertEqual(result["status"], "CALCULATED")
            self.assertFalse(result["finalizable"])
            self.assertFalse(result["approved"])

    def test_hourly_explicit_denominator_only(self):
        result = self.api.calculate_deduction_quantity(
            unit="HOUR", duration_hours="2", standard_daily_hours="8")
        self.assertEqual(result["quantity_days"], "0.25")
        unknown = self.api.calculate_deduction_quantity(
            unit="HOUR", duration_hours="2")
        self.assertIsNone(unknown["quantity_days"])
        self.assertIn("HOURLY_CONVERSION_POLICY_REQUIRED", unknown["review_codes"])

    def test_invalid_hours_and_conflicting_fixed_inputs(self):
        for value in ("NaN", "-2", "0", "Infinity"):
            with self.assertRaises(ValueError):
                self.api.calculate_deduction_quantity(
                    unit="HOUR", duration_hours=value, standard_daily_hours="8")
        with self.assertRaises(ValueError):
            self.api.calculate_deduction_quantity(
                unit="HOUR", duration_hours="9", standard_daily_hours="8")
        with self.assertRaises(ValueError):
            self.api.calculate_deduction_quantity(unit="DAY", duration_hours="8")
        with self.assertRaises(ValueError):
            self.api.calculate_deduction_quantity(unit="UNRECOGNIZED")


class ModuleBoundaryTests(unittest.TestCase):
    def test_no_child_io_or_physical_flow_directory(self):
        root = Path(__file__).resolve().parents[1] / "paid-time-off"
        self.assertFalse((root / "flow").exists())
        for name in ("entitlement", "eligibility", "deduction-quantity"):
            self.assertTrue((root / name / "__init__.py").is_file())
            self.assertFalse((root / name / "input").exists())
            self.assertFalse((root / name / "output").exists())

    def test_pure_modules_do_not_import_each_other_or_legacy_tool(self):
        root = Path(__file__).resolve().parents[1] / "paid-time-off"
        for name in ("entitlement", "eligibility", "deduction-quantity"):
            source = (root / name / "__init__.py").read_text(encoding="utf-8")
            tree = ast.parse(source)
            imports = [
                node.module for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            ]
            self.assertFalse(any(
                entry and ("pto-calculator" in entry or
                           entry.startswith("bhandara.paid-time-off"))
                for entry in imports))
            self.assertNotIn("provisional_remaining_before_expiry_days", source)


if __name__ == "__main__":
    unittest.main()
