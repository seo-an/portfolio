"""Unittest: Schedule independent source-fact reconciliation (synthetic only)."""
from __future__ import annotations

import unittest
from bhandara.worktime.schedule import reconcile_schedule
from bhandara.worktime.schedule.calculation import ScheduleInputError


class ScheduleTests(unittest.TestCase):
    PERIOD = {"period_from": "2026-11-01", "period_to": "2026-11-30"}

    def plan(self, employee="E001", day="2026-11-16", **kwargs):
        return {
            "employee_id": employee, "work_date": day, "day_type": "WORK",
            "scheduled_start": "09:00", "scheduled_end": "18:00",
            "break_min": 60, "source_ref": "schedule-fixture", "_row_number": 2,
            **kwargs,
        }

    def ledger(self, employee="E001", day="2026-11-16", **kwargs):
        return {
            "employee_id": employee, "work_date": day,
            "clock_in": "09:00", "clock_out": "18:00", "break_min": 60,
            "source_ref": "ledger-fixture", "_row_number": 2, **kwargs,
        }

    def run_one(self, plans, ledger):
        return reconcile_schedule(plans, ledger, **self.PERIOD)

    def test_exact_match_with_source_lineage(self):
        result = self.run_one([self.plan()], [self.ledger()])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["rows"][0]["status"], "WORK_MATCH")
        self.assertEqual(result["rows"][0]["schedule_sources"],
                         [{"source_ref": "schedule-fixture", "row_number": 2}])
        self.assertFalse(result["approved"])

    def test_discrepancy_is_not_lateness(self):
        actual = self.ledger()
        actual["clock_in"] = "09:17"
        result = self.run_one([self.plan()], [actual])
        self.assertEqual(result["rows"][0]["status"], "RECORD_DIFFERENT")
        self.assertEqual(result["rows"][0]["different_fields"], ["clock_in"])
        self.assertNotIn("late_minutes", result["rows"][0])
        self.assertNotIn("overtime_hours", result["rows"][0])

    def test_missing_attendance_not_absence(self):
        result = self.run_one([self.plan()], [])
        self.assertEqual(result["rows"][0]["status"], "MISSING")
        self.assertEqual(result["status"], "REVIEW_REQUIRED")

    def test_unscheduled_attendance_not_approved_holiday(self):
        result = self.run_one([], [self.ledger()])
        self.assertEqual(result["rows"][0]["status"], "UNSCHEDULED")
        self.assertFalse(result["approved"])

    def test_off_without_times_has_no_expected_attendance(self):
        plan = self.plan()
        plan.update(day_type="OFF", scheduled_start=None, scheduled_end=None, break_min=None)
        result = self.run_one([plan], [])
        self.assertEqual(result["rows"][0]["status"], "NON_WORK_MATCH")
        self.assertEqual(result["status"], "PASS")

    def test_holiday_with_scheduled_hours_expects_record(self):
        plan = self.plan()
        plan["day_type"] = "HOLIDAY"
        result = self.run_one([plan], [])
        self.assertEqual(result["rows"][0]["status"], "MISSING")

    def test_duplicate_schedule_is_reviewed_without_guessing(self):
        plan2 = self.plan()
        plan2["_row_number"] = 3
        result = self.run_one([self.plan(), plan2], [self.ledger()])
        row = result["rows"][0]
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertEqual(row["review_codes"], ["DUPLICATE_SCHEDULE"])
        self.assertEqual(len(row["schedule_sources"]), 2)

    def test_duplicate_attendance_is_reviewed(self):
        ledger2 = self.ledger()
        ledger2["_row_number"] = 3
        result = self.run_one([self.plan()], [self.ledger(), ledger2])
        self.assertEqual(result["rows"][0]["review_codes"], ["DUPLICATE_ATTENDANCE"])

    def test_invalid_time_kept_as_review_not_silently_corrected(self):
        plan = self.plan()
        plan["scheduled_start"] = "09:00:23"
        result = self.run_one([plan], [self.ledger()])
        self.assertIn("INVALID_SCHEDULED_START", result["rows"][0]["review_codes"])
        self.assertEqual(result["rows"][0]["status"], "REVIEW_REQUIRED")

    def test_break_unknown_is_not_assumed_zero(self):
        plan = self.plan()
        plan["break_min"] = None
        ledger = self.ledger()
        ledger["break_min"] = 0
        result = self.run_one([plan], [ledger])
        self.assertEqual(result["rows"][0]["different_fields"], ["break_min"])
        self.assertIsNone(result["rows"][0]["planned"]["break_min"])

    def test_partial_attendance_review_without_inference(self):
        actual = self.ledger()
        actual["clock_out"] = None
        result = self.run_one([self.plan()], [actual])
        self.assertEqual(result["rows"][0]["review_codes"], ["INCOMPLETE_ATTENDANCE"])
        self.assertEqual(result["rows"][0]["status"], "REVIEW_REQUIRED")

    def test_invalid_row_does_not_block_other_employee(self):
        wrong = self.plan(employee="E002")
        wrong["work_date"] = "bad-date"
        result = self.run_one([self.plan(), wrong], [self.ledger()])
        self.assertEqual(result["rows"][0]["status"], "WORK_MATCH")
        self.assertEqual(result["source_issues"][0]["code"], "ROW_KEY_INVALID")
        self.assertEqual(result["status"], "REVIEW_REQUIRED")

    def test_outside_period_does_not_pollute_comparison(self):
        other = self.plan(employee="E002", day="2026-12-01")
        result = self.run_one([self.plan(), other], [self.ledger()])
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["source_issues"][0]["code"], "OUTSIDE_PERIOD")

    def test_empty_input_is_not_misrepresented_as_verified(self):
        result = self.run_one([], [])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["source_issues"][0]["code"], "NO_COMPARABLE_ROWS")

    def test_aggregate_pass_with_mixed_work_and_non_work(self):
        off = self.plan(employee="E002", day="2026-11-17")
        off.update(day_type="OFF", scheduled_start=None,
                   scheduled_end=None, break_min=None)
        result = self.run_one([self.plan(), off], [self.ledger()])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual([row["status"] for row in result["rows"]],
                         ["WORK_MATCH", "NON_WORK_MATCH"])
        self.assertTrue(all(row["status"] != "LEAVE_MATCH" for row in result["rows"]))

    def test_discrepancy_sets_aggregate_review(self):
        actual = self.ledger()
        actual["clock_out"] = "18:20"
        result = self.run_one([self.plan()], [actual])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["rows"][0]["status"], "RECORD_DIFFERENT")

    def test_bad_period_and_mapping_rejected(self):
        with self.assertRaises(ScheduleInputError):
            reconcile_schedule([], [], period_from="2026-12-01", period_to="2026-11-30")
        with self.assertRaises(ScheduleInputError):
            reconcile_schedule({}, [], **self.PERIOD)

    def test_mixed_rows_are_sorted_by_employee_and_date(self):
        p1 = self.plan(employee="E002")
        p2 = self.plan(employee="E001")
        l1 = self.ledger(employee="E001")
        l2 = self.ledger(employee="E002")
        result = self.run_one([p1, p2], [l2, l1])
        self.assertEqual([r["employee_id"] for r in result["rows"]], ["E001", "E002"])


if __name__ == "__main__":
    unittest.main()
