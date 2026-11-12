"""PTO review cases: mixed synthetic Excel inputs + evidence-aware assertions.

These tests validate selected contracts, not a universal legal "golden" result.
"""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "bhandara/pto-calculator/examples/generate_review_cases.py"


def pto_module(name: str):
    return importlib.import_module(f"bhandara.pto-calculator.src.{name}")


def daily(day: date, *, credit: str = "PRESENT", denominator: str = "INCLUDED") -> dict:
    return {
        "work_date": day,
        "employment": {"within_employment": True},
        "scheduled_work_day": denominator == "INCLUDED",
        "attendance_denominator": denominator,
        "attendance_credit": credit,
        "attendance_policy": {},
        "employee_event": {"status": "NONE"},
    }


class PTOReviewRuleTests(unittest.TestCase):
    def test_incomplete_calendar_does_not_become_full_attendance(self):
        eligibility = pto_module("eligibility")
        start, end = date(2025, 1, 1), date(2025, 1, 31)
        partial = [daily(start + timedelta(days=i)) for i in range(10)]
        self.assertEqual(
            eligibility.evaluate_monthly_full_attendance(partial, start, end),
            "UNDETERMINED",
        )
        self.assertEqual(
            eligibility.evaluate_annual_attendance_80(
                partial, start, date(2025, 12, 31)
            ),
            "UNDETERMINED",
        )
        self.assertFalse(
            eligibility.has_complete_calendar_coverage(
                [daily(start), daily(start)], start, start + timedelta(days=1)
            )
        )

    def test_no_scheduled_workdays_requires_review(self):
        eligibility = pto_module("eligibility")
        start, end = date(2025, 1, 1), date(2025, 1, 31)
        rows = [
            daily(start + timedelta(days=i), credit="REVIEW", denominator="EXCLUDED")
            for i in range(31)
        ]
        self.assertEqual(
            eligibility.evaluate_monthly_full_attendance(rows, start, end),
            "UNDETERMINED",
        )

    def test_unresolved_month_end_diagnostic_uses_hire_anchor(self):
        result = pto_module("accrual_pipeline").calculate_anniversary_accrual(
            hire_date=date(2025, 1, 31),
            as_of_date=date(2025, 2, 28),
            daily_records=[],
        )
        finding = result["unresolved_grants"][0]
        self.assertEqual(finding["period_start"], date(2025, 1, 31))
        self.assertEqual(finding["period_end"], date(2025, 2, 27))
        reasons = [
            x for item in finding["unresolved_reasons"] for x in item["reasons"]
        ]
        self.assertIn("PERIOD_SOURCE_COVERAGE_INCOMPLETE", reasons)

    def test_confirmed_absence_and_missing_clock_are_not_equivalent(self):
        policy = pto_module("attendance_policy")
        kwargs = {
            "within_employment": True,
            "scheduled_work_day": True,
            "attendance_status": "NO_RECORD",
        }
        missing = policy.resolve_daily_attendance_policy(**kwargs)
        confirmed = policy.resolve_daily_attendance_policy(
            **kwargs,
            event={"event_type": "CONFIRMED_ABSENCE", "status": "CONFIRMED"},
        )
        contradictory = policy.resolve_daily_attendance_policy(
            **{**kwargs, "attendance_status": "PRESENT"},
            event={"event_type": "CONFIRMED_ABSENCE", "status": "CONFIRMED"},
        )
        self.assertEqual(missing["credit"], "REVIEW")
        self.assertEqual(confirmed["credit"], "NOT_PRESENT")
        self.assertEqual(contradictory["credit"], "REVIEW")
        self.assertEqual(
            contradictory["reason"], "ATTENDANCE_CONFLICTS_WITH_ABSENCE"
        )

    def test_under_80_year_grants_next_year_without_annual_15(self):
        core = pto_module("core")
        grants = core.anniversary_grants(
            hire_date=date(2024, 1, 1),
            as_of_date=date(2026, 1, 1),
            annual_attendance_met=lambda start, end: (
                False if start == date(2025, 1, 1) else True
            ),
            monthly_attendance_met=lambda start, end: (
                start.month not in (1, 2)
            ),
        )
        fallback = [g for g in grants if g["grant_type"] == "monthly_under_80"]
        self.assertEqual(len(fallback), 10)
        self.assertTrue(all(g["grant_date"] == date(2026, 1, 1) for g in fallback))
        self.assertFalse(any(
            g["grant_type"] == "annual"
            and g["grant_date"] == date(2026, 1, 1)
            for g in grants
        ))

    def test_timing_and_threshold_boundaries(self):
        eligibility = pto_module("eligibility")
        start = date(2025, 1, 1)
        period = [start + timedelta(days=i) for i in range(100)]
        for present_count, expected in ((79, "NOT_ELIGIBLE"),
                                        (80, "ELIGIBLE"),
                                        (81, "ELIGIBLE")):
            rows = [
                daily(day, credit="PRESENT" if i < present_count else "NOT_PRESENT")
                for i, day in enumerate(period)
            ]
            with self.subTest(present_count=present_count):
                self.assertEqual(
                    eligibility.evaluate_annual_attendance_80(
                        rows, start, period[-1]
                    ),
                    expected,
                )


class PTOPublishedSampleTests(unittest.TestCase):
    def test_checked_in_sample_is_a_real_usable_set(self):
        sample = ROOT / "bhandara/pto-calculator/examples/sample"
        required = (
            "config.json",
            "case-index.json",
            "case-index.xlsx",
            "input/employee.xlsx",
            "input/work-schedule.xlsx",
            "input/work-schedule-assignment.xlsx",
            "input/work-records/2025-2026-schedule.xlsx",
            "input/work-records/2025-2026-attendance.xlsx",
            "input/employee-events.xlsx",
        )
        for name in required:
            with self.subTest(filename=name):
                path = sample / name
                self.assertTrue(path.is_file(), f"missing published sample: {path}")
                self.assertGreater(path.stat().st_size, 0)

        config = json.loads((sample / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["schema_version"], "1.0")
        for key in ("employees", "schedule", "assignments", "events"):
            self.assertTrue((sample / "input" / config["files"][key]).is_file())
        for key in ("monthly_schedule", "attendance"):
            for name in config["files"][key]:
                self.assertTrue((sample / "input" / name).is_file())

        wb = load_workbook(sample / "input/employee.xlsx", read_only=True)
        try:
            rows = list(wb.active.values)
        finally:
            wb.close()
        self.assertEqual(rows[0][-1], "case_id")
        self.assertEqual(len(rows) - 1, 14)
        ids = [r[0] for r in rows[1:]]
        self.assertNotEqual(ids, sorted(ids))


class PTOMixedExcelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="pto-cases-")
        cls.root = Path(cls.temp.name)
        proc = subprocess.run(
            [sys.executable, str(GENERATOR), "--output-dir", str(cls.root)],
            cwd=ROOT, text=True, capture_output=True, check=False, timeout=60,
        )
        if proc.returncode:
            raise RuntimeError(proc.stderr or proc.stdout)
        cls.output = cls.root / "output"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "run.py"), "bhandara",
             "pto-calculator", "--config", str(cls.root / "config.json"),
             "--input-dir", str(cls.root / "input"),
             "--output-dir", str(cls.output)],
            cwd=ROOT, text=True, capture_output=True, check=False, timeout=120,
        )
        if proc.returncode not in (0, 1):
            raise RuntimeError(proc.stderr or proc.stdout)
        cls.result = json.loads(
            (cls.output / "pto-result.json").read_text(encoding="utf-8")
        )
        cls.by_id = {row["employee_id"]: row for row in cls.result["results"]}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_employee_and_exception_cases_are_mixed_in_actual_xlsx(self):
        wb = load_workbook(self.root / "input/employee.xlsx", read_only=True)
        try:
            rows = list(wb.active.values)
        finally:
            wb.close()
        ids = [row[0] for row in rows[1:]]
        self.assertEqual(len(ids), 14)
        self.assertNotEqual(ids, sorted(ids))
        self.assertEqual(rows[0][4], "case_id")
        id_to_case = {row[0]: row[4] for row in rows[1:]}
        case_book = load_workbook(self.root / "case-index.xlsx", read_only=True)
        try:
            case_rows = list(case_book.active.values)
        finally:
            case_book.close()
        self.assertEqual(case_rows[0][:2], ("employee_id", "case_id"))
        self.assertEqual(
            {row[0]: row[1] for row in case_rows[1:]},
            id_to_case,
        )
        cases = json.loads((self.root / "case-index.json").read_text())["cases"]
        self.assertEqual({row["employee_id"] for row in cases}, set(ids))
        self.assertEqual(len(self.by_id), 14)

    def test_annual_below_equal_above_80_in_same_workbook(self):
        self.assertFalse(any(
            g["grant_type"] == "annual"
            for g in self.by_id["R002"]["grants"]
        ))
        self.assertTrue(any(
            g["grant_type"] == "monthly_under_80"
            and g["grant_date"] == "2026-01-01"
            for g in self.by_id["R002"]["grants"]
        ))
        for id_ in ("R003", "R004"):
            with self.subTest(employee_id=id_):
                annual = [g for g in self.by_id[id_]["grants"]
                          if g["grant_type"] == "annual"]
                self.assertEqual(len(annual), 1)
                self.assertEqual(Decimal(str(annual[0]["raw_days"])), Decimal(15))

    def test_terminated_employee_has_no_later_grants(self):
        grants = self.by_id["R006"]["grants"]
        self.assertTrue(grants)
        self.assertTrue(all(g["grant_date"] <= "2025-06-30" for g in grants))
        self.assertFalse(any(g["grant_type"] == "annual" for g in grants))

    def test_normal_and_end_of_month_controls(self):
        for id_ in ("R001", "R007", "R008", "R011", "R013", "R014"):
            with self.subTest(employee_id=id_):
                grants = self.by_id[id_]["grants"]
                self.assertTrue(any(g["grant_type"] == "annual" for g in grants))
                self.assertFalse(self.by_id[id_]["unresolved_grants"])

    def test_uncertain_cases_do_not_silently_pass(self):
        for id_ in ("R005", "R009", "R010", "R012"):
            with self.subTest(employee_id=id_):
                self.assertTrue(self.by_id[id_]["unresolved_grants"])
        self.assertFalse(self.result["approved"])
        self.assertFalse(self.result["finalizable"])

    def test_optional_reduced_hours_reaches_event_handoff(self):
        input_adapter = pto_module("input_adapter")
        sheet = input_adapter.read_pto_sheet(
            self.root / "input/employee-events.xlsx", "events"
        )
        found = [row for row in sheet.rows
                 if row["employee_id"] == "R008"
                 and row["event_type"] == "PREGNANCY_REDUCED_HOURS"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["reduced_hours"], 2.0)


if __name__ == "__main__":
    unittest.main()
