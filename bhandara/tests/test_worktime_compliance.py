"""Synthetic regression tests for independent Worktime Compliance module."""
from __future__ import annotations

import unittest
from importlib import import_module

mod = import_module("bhandara.worktime.worktime-compliance")
review = mod.review_worktime_compliance
ComplianceInputError = mod.ComplianceInputError


class WorktimeComplianceTests(unittest.TestCase):
    START = "2026-11-16"
    END = "2026-11-22"

    def policy(self, **overrides):
        base = {
            "schema_version": "0.1",
            "policy_ref": "SYNTHETIC_KR_STANDARD_V1",
            "daily_standard_min": 480,
            "weekly_standard_min": 2400,
            "weekly_limit_min": 3120,
            "rest_every_work_min": 240,
            "rest_per_block_min": 30,
            "break_overrun_tolerance_min": 0,
        }
        base.update(overrides)
        return base

    def day(self, employee="E001", work_date="2026-11-16", **overrides):
        row = {
            "employee_id": employee, "work_date": work_date,
            "actor_type": "EMPLOYEE",
            "worktime_system": "standard",
            "policy_ref": "SYNTHETIC_KR_STANDARD_V1",
            "worked_min": 480, "worked_verified": True,
            "worked_evidence_ref": "SYNTHETIC-WORK-1",
            "rest_min": 60, "rest_verified": True,
            "rest_evidence_ref": "SYNTHETIC-REST-1",
            "rest_within_workday_verified": True,
            "rest_coverage_complete": True,
            "rest_coverage_ref": "SYNTHETIC-COVERAGE-1",
            "planned_break_min": 60,
            "source_ref": "synthetic-daily",
            "_row_number": 2,
        }
        row.update(overrides)
        return row

    def week(self, employee="E001", week_start="2026-11-16", **overrides):
        row = {
            "employee_id": employee, "week_start": week_start,
            "coverage_complete": True,
            "evidence_ref": "SYNTHETIC-FULL-WEEK",
            "exception_status": "NONE",
        }
        row.update(overrides)
        return row

    def run_one(self, days=None, weeks=None, policy=None, start=None, end=None):
        return review(
            [self.day()] if days is None else days,
            [self.week()] if weeks is None else weeks,
            self.policy() if policy is None else policy,
            period_from=start or self.START, period_to=end or self.END,
        )

    def test_verified_standard_day_and_week_can_pass(self):
        result = self.run_one()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["daily"][0]["status"], "PASS")
        self.assertEqual(result["daily"][0]["required_rest_min"], 60)
        self.assertEqual(result["weekly"][0]["total_worked_min"], 480)
        self.assertFalse(result["approved"])
        self.assertFalse(result["legal_conclusion"])

    def test_four_hour_minimum_requires_30_before_amendment(self):
        result = self.run_one(days=[self.day(worked_min=240, rest_min=0,
                                               planned_break_min=0)])
        self.assertIn("REST_SHORTFALL_REVIEW", result["daily"][0]["review_codes"])
        self.assertEqual(result["daily"][0]["required_rest_min"], 30)

    def test_four_hour_waiver_after_effective_date_requires_reference(self):
        day = self.day(work_date="2026-12-10", worked_min=240,
                       rest_min=0, planned_break_min=0,
                       four_hour_waiver_ref="SYNTHETIC-REQUEST-1")
        week = self.week(week_start="2026-12-07")
        result = self.run_one(days=[day], weeks=[week],
                              start="2026-12-07", end="2026-12-13")
        self.assertEqual(result["daily"][0]["required_rest_min"], 0)
        self.assertEqual(result["status"], "PASS")

    def test_four_hour_waiver_before_effective_date_not_applied(self):
        day = self.day(worked_min=240, rest_min=0, planned_break_min=0,
                       four_hour_waiver_ref="SYNTHETIC-REQUEST-1")
        result = self.run_one(days=[day])
        self.assertEqual(result["daily"][0]["required_rest_min"], 30)
        self.assertIn("BREAK_WAIVER_NOT_APPLICABLE",
                      result["daily"][0]["review_codes"])

    def test_rest_shortfall_requires_complete_evidence(self):
        day = self.day(rest_min=30, planned_break_min=30,
                       rest_coverage_complete=True)
        result = self.run_one(days=[day])
        self.assertIn("REST_SHORTFALL_REVIEW", result["daily"][0]["review_codes"])

    def test_without_coverage_rest_shortfall_is_undetermined(self):
        day = self.day(rest_min=30, planned_break_min=30,
                       rest_coverage_complete=False, rest_coverage_ref="")
        result = self.run_one(days=[day])
        self.assertIn("REST_SHORTFALL_UNDETERMINED",
                      result["daily"][0]["review_codes"])
        self.assertNotIn("REST_SHORTFALL_REVIEW", result["daily"][0]["review_codes"])

    def test_rest_overrun_is_company_rule_not_legal_maximum(self):
        result = self.run_one(days=[self.day(rest_min=90)])
        self.assertIn("COMPANY_BREAK_OVERRUN_REVIEW",
                      result["daily"][0]["review_codes"])
        self.assertNotIn("LEGAL_REST_MAX_EXCEEDED",
                         result["daily"][0]["review_codes"])

    def test_planned_break_missing_does_not_create_overrun(self):
        result = self.run_one(days=[self.day(planned_break_min=None)])
        self.assertEqual(result["daily"][0]["status"], "PASS")

    def test_ten_hour_day_marks_standard_exceedance_not_overtime_pay(self):
        result = self.run_one(days=[self.day(worked_min=600, rest_min=60)])
        self.assertIn("DAILY_STANDARD_EXCEEDED_REVIEW",
                      result["daily"][0]["review_codes"])
        self.assertNotIn("overtime_minutes", result["daily"][0])

    def test_unverified_worktime_fails_closed(self):
        result = self.run_one(days=[self.day(worked_verified=False)])
        self.assertIn("WORK_EVIDENCE_UNVERIFIED",
                      result["daily"][0]["review_codes"])
        self.assertIsNone(result["weekly"][0]["total_worked_min"])

    def test_rest_unverified_is_never_assumed_zero(self):
        result = self.run_one(days=[self.day(rest_min=None, rest_verified=False,
                                               rest_evidence_ref="")])
        self.assertIn("REST_MINUTES_UNKNOWN", result["daily"][0]["review_codes"])
        self.assertIn("REST_SUFFICIENCY_UNDETERMINED",
                      result["daily"][0]["review_codes"])

    def test_rest_location_must_be_verified(self):
        result = self.run_one(days=[self.day(rest_within_workday_verified=False)])
        self.assertIn("REST_PLACEMENT_UNVERIFIED",
                      result["daily"][0]["review_codes"])
        self.assertIn("REST_SUFFICIENCY_UNDETERMINED",
                      result["daily"][0]["review_codes"])

    def test_nonstandard_system_cannot_be_treated_as_standard(self):
        result = self.run_one(days=[self.day(worktime_system="selective")])
        self.assertIn("WORKTIME_SYSTEM_REVIEW", result["daily"][0]["review_codes"])
        self.assertIsNone(result["daily"][0]["required_rest_min"])
        self.assertIsNone(result["weekly"][0]["total_worked_min"])

    def test_external_service_never_assumed_employee(self):
        result = self.run_one(days=[self.day(actor_type="EXTERNAL_SERVICE")])
        self.assertIn("RELATIONSHIP_POLICY_REVIEW",
                      result["daily"][0]["review_codes"])
        self.assertIsNone(result["weekly"][0]["total_worked_min"])

    def test_missing_weekly_coverage_does_not_pass(self):
        result = self.run_one(weeks=[])
        self.assertIn("WEEKLY_COVERAGE_UNVERIFIED",
                      result["weekly"][0]["review_codes"])

    def test_partial_week_is_review_not_false_compliance(self):
        result = self.run_one(start="2026-11-16", end="2026-11-18")
        self.assertIn("WEEK_CROSSES_INPUT_PERIOD",
                      result["weekly"][0]["review_codes"])

    def test_weekly_over_40_hrs_is_review_not_approved_overtime(self):
        days = [self.day(work_date=f"2026-11-{d:02}") for d in range(16, 22)]
        result = self.run_one(days=days)
        self.assertEqual(result["weekly"][0]["total_worked_min"], 2880)
        self.assertIn("WEEKLY_STANDARD_EXCEEDED_REVIEW",
                      result["weekly"][0]["review_codes"])
        self.assertNotIn("WEEKLY_LIMIT_EXCEEDED_REVIEW",
                         result["weekly"][0]["review_codes"])

    def test_weekly_over_52_hrs_is_limit_review(self):
        days = [self.day(work_date=f"2026-11-{d:02}") for d in range(16, 23)]
        result = self.run_one(days=days)
        self.assertEqual(result["weekly"][0]["total_worked_min"], 3360)
        self.assertIn("WEEKLY_LIMIT_EXCEEDED_REVIEW",
                      result["weekly"][0]["review_codes"])
        self.assertFalse(result["legal_conclusion"])

    def test_special_exception_does_not_silently_use_standard_cap(self):
        days = [self.day(work_date=f"2026-11-{d:02}") for d in range(16, 23)]
        result = self.run_one(days=days, weeks=[
            self.week(exception_status="PRESENT"),
        ])
        self.assertIn("WEEKLY_EXCEPTION_REVIEW",
                      result["weekly"][0]["review_codes"])
        self.assertNotIn("WEEKLY_LIMIT_EXCEEDED_REVIEW",
                         result["weekly"][0]["review_codes"])

    def test_invalid_daily_day_is_source_issue_not_other_day_error(self):
        good = self.day()
        bad = self.day(employee="E002", work_date="bad-date")
        result = self.run_one(days=[good, bad])
        self.assertEqual(result["daily"][0]["status"], "PASS")
        self.assertEqual(result["source_issues"][0]["code"], "DAILY_KEY_INVALID")
        self.assertEqual(result["status"], "REVIEW_REQUIRED")

    def test_duplicate_day_not_doubled_into_weekly(self):
        result = self.run_one(days=[self.day(), self.day(_row_number=3)])
        self.assertIn("DUPLICATE_DAILY_FACT", result["daily"][0]["review_codes"])
        self.assertIsNone(result["weekly"][0]["total_worked_min"])

    def test_duplicate_weekly_coverage_requires_review(self):
        result = self.run_one(weeks=[self.week(), self.week()])
        self.assertIn("DUPLICATE_WEEKLY_COVERAGE",
                      result["weekly"][0]["review_codes"])

    def test_missing_weekly_exception_decision_is_review(self):
        result = self.run_one(weeks=[self.week(exception_status="UNKNOWN")])
        self.assertIn("WEEKLY_EXCEPTION_REVIEW",
                      result["weekly"][0]["review_codes"])

    def test_policy_version_and_limits_are_validated(self):
        with self.assertRaises(ComplianceInputError):
            self.run_one(policy=self.policy(weekly_limit_min=2000))
        with self.assertRaises(ComplianceInputError):
            self.run_one(policy=self.policy(schema_version="2.0"))

    def test_no_data_does_not_pass(self):
        result = self.run_one(days=[], weeks=[])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["source_issues"][0]["code"], "NO_COMPARABLE_ROWS")

    def test_weekly_coverage_without_daily_evidence_stays_review(self):
        result = self.run_one(days=[])
        self.assertIn("WEEK_WITHOUT_DAILY_FACTS",
                      result["weekly"][0]["review_codes"])

    def test_break_overrun_tolerance_is_configurable(self):
        result = self.run_one(days=[self.day(rest_min=65)],
                              policy=self.policy(break_overrun_tolerance_min=10))
        self.assertEqual(result["daily"][0]["status"], "PASS")

    def test_source_reference_preserved(self):
        result = self.run_one()
        self.assertEqual(result["daily"][0]["source_ref"], "synthetic-daily")


if __name__ == "__main__":
    unittest.main()
