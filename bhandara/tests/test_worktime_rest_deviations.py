"""Signed rest differences belong to Worktime Compliance, not Schedule."""
from __future__ import annotations

import unittest
from importlib import import_module

compliance = import_module("bhandara.worktime.worktime-compliance")


class SignedRestDeviationTests(unittest.TestCase):
    PERIOD = {"period_from": "2026-11-16", "period_to": "2026-11-22"}

    def policy(self):
        return {
            "schema_version": "0.1",
            "policy_ref": "SYNTHETIC_STANDARD",
            "daily_standard_min": 480,
            "weekly_standard_min": 2400,
            "weekly_limit_min": 3120,
            "rest_every_work_min": 240,
            "rest_per_block_min": 30,
            "break_overrun_tolerance_min": 30,
        }

    def day(self, **changes):
        row = {
            "employee_id": "E001", "work_date": "2026-11-16",
            "actor_type": "EMPLOYEE", "worktime_system": "standard",
            "policy_ref": "SYNTHETIC_STANDARD",
            "worked_min": 480, "worked_verified": True,
            "worked_evidence_ref": "WORK-REF",
            "rest_min": 60, "rest_verified": True,
            "rest_evidence_ref": "REST-REF",
            "rest_within_workday_verified": True,
            "rest_coverage_complete": True,
            "rest_coverage_ref": "COVERAGE-REF",
            "planned_break_min": 60,
            "source_ref": "SYNTHETIC-COMPLIANCE",
        }
        row.update(changes)
        return row

    def week(self):
        return {
            "employee_id": "E001", "week_start": "2026-11-16",
            "coverage_complete": True,
            "evidence_ref": "SYNTHETIC-WEEK",
            "exception_status": "NONE",
        }

    def run_one(self, *, days=None):
        return compliance.review_worktime_compliance(
            [self.day()] if days is None else days,
            [self.week()],
            self.policy(), **self.PERIOD,
        )["daily"][0]

    def test_exact_required_rest_is_zero_delta(self):
        row = self.run_one()
        self.assertEqual(row["rest_deviation"]["required_min"], 60)
        self.assertEqual(row["rest_deviation"]["recorded_min"], 60)
        self.assertEqual(row["rest_deviation"]["delta_min"], 0)
        self.assertEqual(row["rest_deviation"]["direction"], "ZERO")
        self.assertIsNone(row["rest_deviation"]["reason"])

    def test_more_rest_has_positive_delta_not_legal_violation(self):
        row = self.run_one(days=[self.day(rest_min=90, rest_reason="개인 사정")])
        self.assertEqual(row["rest_deviation"]["delta_min"], 30)
        self.assertEqual(row["rest_deviation"]["direction"], "POSITIVE")
        self.assertEqual(row["rest_deviation"]["reason"], "개인 사정")
        self.assertFalse(row["rest_deviation"]["shortfall_confirmable"])
        self.assertNotIn("LEGAL_REST_MAX_EXCEEDED", row["review_codes"])

    def test_less_rest_has_negative_delta_with_complete_evidence(self):
        row = self.run_one(days=[self.day(rest_min=45, rest_reason="업무 중단 불가")])
        self.assertEqual(row["rest_deviation"]["delta_min"], -15)
        self.assertEqual(row["rest_deviation"]["direction"], "NEGATIVE")
        self.assertTrue(row["rest_deviation"]["shortfall_confirmable"])
        self.assertIn("REST_SHORTFALL_REVIEW", row["review_codes"])

    def test_incomplete_rest_coverage_preserves_delta_but_not_final_shortfall(self):
        row = self.run_one(days=[self.day(
            rest_min=45, rest_coverage_complete=False, rest_coverage_ref="",
        )])
        self.assertEqual(row["rest_deviation"]["delta_min"], -15)
        self.assertFalse(row["rest_deviation"]["shortfall_confirmable"])
        self.assertIn("REST_SHORTFALL_UNDETERMINED", row["review_codes"])
        self.assertNotIn("REST_SHORTFALL_REVIEW", row["review_codes"])

    def test_unverified_rest_does_not_produce_signed_difference(self):
        row = self.run_one(days=[self.day(rest_verified=False)])
        self.assertIsNone(row["rest_deviation"]["delta_min"])
        self.assertEqual(row["rest_deviation"]["direction"], "UNKNOWN")
        self.assertFalse(row["rest_deviation"]["shortfall_confirmable"])

    def test_missing_rest_is_unknown_not_zero(self):
        row = self.run_one(days=[self.day(rest_min=None)])
        self.assertIsNone(row["rest_deviation"]["delta_min"])
        self.assertIsNone(row["rest_deviation"]["recorded_min"])

    def test_nonstandard_worktime_system_has_no_required_rest_comparison(self):
        row = self.run_one(days=[self.day(worktime_system="selective")])
        self.assertIsNone(row["rest_deviation"]["required_min"])
        self.assertIsNone(row["rest_deviation"]["delta_min"])

    def test_reason_not_inferred_even_for_negative_delta(self):
        row = self.run_one(days=[self.day(rest_min=30)])
        self.assertIsNone(row["rest_deviation"]["reason"])
        self.assertEqual(row["rest_deviation"]["delta_min"], -30)

    def test_invalid_reason_type_requires_review(self):
        row = self.run_one(days=[self.day(rest_reason={"untrusted": "value"})])
        self.assertIn("INVALID_REST_REASON", row["review_codes"])
        self.assertIsNone(row["rest_deviation"]["reason"])

    def test_duplicate_daily_source_has_unknown_signed_delta(self):
        row = self.run_one(days=[self.day(), self.day()])
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertIsNone(row["rest_deviation"]["delta_min"])


if __name__ == "__main__":
    unittest.main()
