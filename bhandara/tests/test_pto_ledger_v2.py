"""PTO v0.2 provisional ledger and boundary tests; synthetic data only."""
from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from datetime import date, time
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook


def pto(name: str):
    return importlib.import_module("bhandara.pto-calculator." + name)


class LeaveLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = pto("src.leave_ledger")
        self.asof = date(2026, 7, 31)

    def event(self, ident: str, label: str, unit: str,
              *, day: int, status: str = "APPROVED") -> dict:
        return {
            "employee_id": "E001", "request_id": ident,
            "event_type": label, "event_date": date(2026, 7, day),
            "unit": unit, "status": status,
        }

    def calculate(self, events, grants=None):
        if grants is None:
            grants = [{"grant_date": date(2026, 7, 1),
                       "grant_type": "annual", "raw_days": Decimal("15")}]
        return self.ledger.calculate_leave_ledger(
            employee_id="E001", grants=grants, event_rows=events,
            as_of_date=self.asof, period_start=date(2026, 1, 1),
            hire_date=date(2024, 1, 1))

    def test_annual_and_both_half_days_are_deducted(self):
        result = self.calculate([
            self.event("r1", "연차", "DAY", day=1),
            self.event("r2", "오전 반차", "HALF_DAY", day=2),
            self.event("r3", "오후 반차", "HALF_DAY", day=2),
            self.event("r4", "조기퇴근", "HOURS", day=3),
            self.event("r5", "연차", "DAY", day=4, status="REQUESTED"),
        ])
        self.assertEqual(result["known_granted_days"], "15")
        self.assertEqual(result["known_used_days"], "2.0")
        self.assertEqual(result["provisional_remaining_before_expiry_days"], "13.0")
        self.assertIsNone(result["confirmed_balance_days"])
        self.assertIsNone(result["expired_days"])
        self.assertEqual(len(result["other_events"]), 1)
        self.assertEqual(len(result["usage"]), 4)
        self.assertIn("EXPIRY_POLICY_NOT_VERIFIED", result["review_codes"])

    def test_same_day_full_and_half_overlap_are_not_silently_deducted(self):
        result = self.calculate([
            self.event("r1", "연차", "DAY", day=3),
            self.event("r2", "오전 반차", "HALF_DAY", day=3),
        ])
        self.assertEqual(result["known_used_days"], "0")
        self.assertIn("OVERLAPPING_ANNUAL_LEAVE", result["review_codes"])

    def test_hourly_without_policy_is_not_guessed(self):
        result = self.calculate([self.event("r1", "시간차", "HOURS", day=3)])
        self.assertEqual(result["known_used_days"], "0")
        self.assertIn("HOURLY_CONVERSION_POLICY_REQUIRED", result["review_codes"])

    def test_duplicate_request_id_is_not_double_debited(self):
        result = self.calculate([
            self.event("same", "연차", "DAY", day=3),
            self.event("same", "연차", "DAY", day=4),
        ])
        self.assertEqual(result["known_used_days"], "1")
        self.assertIn("DUPLICATE_OR_MISSING_REQUEST_ID", result["review_codes"])

    def test_explicit_half_day_label_with_full_day_unit_requires_review(self):
        result = self.calculate([self.event("r1", "오전 반차", "DAY", day=3)])
        self.assertEqual(result["known_used_days"], "0")
        self.assertIn("LEAVE_UNIT_CONFLICT", result["review_codes"])

    def test_grant_uncertainty_and_overuse_exposed_not_finalized(self):
        result = self.calculate([
            self.event("r1", "연차", "DAY", day=1),
        ], grants=[{"grant_date": date(2026, 7, 1), "raw_days": None}])
        self.assertEqual(result["unresolved_grant_count"], 1)
        self.assertIn("KNOWN_USAGE_EXCEEDS_KNOWN_GRANTS", result["review_codes"])
        self.assertFalse(result["finalizable"])


class PTODailyBoundaryTests(unittest.TestCase):
    def test_complementary_half_days_are_one_full_deemed_day(self):
        events = [
            {"employee_id": "E001", "event_date": date(2026, 7, 2),
             "event_type": label, "unit": "HALF_DAY", "status": "APPROVED"}
            for label in ("오전 반차", "오후 반차")
        ]
        reconciliation = pto("src.event_reconciliation").reconcile_daily_employee_event(
            events, "E001", date(2026, 7, 2))
        self.assertEqual(reconciliation["status"], "RESOLVED")
        self.assertEqual(reconciliation["event"]["unit"], "DAY")

    def test_single_half_day_is_not_equivalent_to_full_presence(self):
        policy = pto("src.attendance_policy").resolve_event_attendance_policy({
            "event_type": "오후 반차", "status": "APPROVED", "unit": "HALF_DAY",
        })
        self.assertEqual(policy["credit"], "REVIEW")

    def test_missing_break_does_not_become_zero_or_sixty(self):
        observed = pto("src.partial_attendance").observed_work_hours
        record = {"clock_in": time(9), "clock_out": time(18)}
        self.assertIsNone(observed(record))
        self.assertEqual(observed({**record, "break_min": 60}), 8)
        self.assertEqual(observed({**record, "break_min": 0}), 9)

    def test_monthly_dated_schedule_does_not_need_assignment_workbook(self):
        generator = pto("examples.generate_demo")
        runner = pto("runner")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, config_path = generator.generate_demo(root)
            settings = json.loads(config_path.read_text(encoding="utf-8"))
            settings["files"].pop("assignments")
            config_path.write_text(json.dumps(settings), encoding="utf-8")
            status, output = runner.run_pto(
                config_path=config_path, input_dir=source,
                output_dir=root / "output")
            self.assertIn(status.value, ("PASS", "REVIEW_REQUIRED"))
            result = json.loads(output["pto-result.json"].read_text(encoding="utf-8"))
            self.assertEqual(len(result["results"]), 2)
            self.assertTrue(all("ledger" in item for item in result["results"]))
            wb = load_workbook(output["pto-result.xlsx"], read_only=True)
            try:
                self.assertEqual(wb.sheetnames[:2], ["Summary", "Accruals"])
                self.assertIn("Usage", wb.sheetnames)
                self.assertIn("Balances", wb.sheetnames)
                self.assertIn("Grants", wb.sheetnames)
            finally:
                wb.close()


    def test_synthetic_excel_contains_all_nine_requested_event_cases(self):
        generator = pto("examples.generate_leave_usage_cases")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            produced = generator.generate_cases(root)
            self.assertEqual(produced["employee_count"], 9)
            self.assertEqual(produced["event_count"], 9)
            cfg = json.loads((root / "config.json").read_text(encoding="utf-8"))
            self.assertNotIn("assignments", cfg["files"])
            book = load_workbook(root / "input/employee-events.xlsx", read_only=True)
            try:
                rows = list(book.active.values)
            finally:
                book.close()
            self.assertEqual(len(rows), 10)
            kinds = [row[2] for row in rows[1:]]
            self.assertEqual(kinds.count("연차"), 2)
            self.assertEqual(kinds.count("오전 반차"), 3)
            self.assertEqual(kinds.count("오후 반차"), 2)
            self.assertEqual(kinds.count("조기퇴근"), 1)
            self.assertEqual(kinds.count("육아기근로시간단축"), 1)
            self.assertEqual(len({row[1] for row in rows[1:]}), 9)


if __name__ == "__main__":
    unittest.main()
