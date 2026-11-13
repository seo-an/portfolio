"""Synthetic security-reader mode / direction / attendance candidate contracts."""
from __future__ import annotations

import importlib
import unittest

old_tests = importlib.import_module("bhandara.tests.test_worktime_caps_break_review")
breaks = importlib.import_module("bhandara.worktime-calculator.break_review")
batch = importlib.import_module("bhandara.worktime-calculator.functions.worktime_batch")


def source_with(events, candidates=None):
    bundle = old_tests.synthetic_bundle(events)
    if candidates is not None:
        bundle["sources"]["attendance_candidates"] = {
            "rows": candidates, "source_sha256": "synthetic-attendance-candidates",
            "lineage": [{"status": "ACCEPTED", "row_number": i + 2, "issue_codes": []}
                        for i in range(len(candidates))],
        }
    return bundle


def mode_event(event_id, at, mode, direction="UNKNOWN"):
    row = old_tests.evt(event_id, at, direction)
    row["mode"] = mode
    row["auth_status"] = "SUCCESS"
    row["device_id"] = "SYN-DEVICE"
    row["device_name"] = "Synthetic reader"
    return row


class ModeAwareWorktimeTests(unittest.TestCase):
    def assess(self, events, candidates=None):
        source = source_with(events, candidates)
        config = old_tests.settings()
        core = batch.calculate_worktime_batch(source, config)
        return breaks.analyze_access_breaks(source, config, core)

    def test_generic_access_without_direction_is_kept_and_reviewed(self):
        report = self.assess([mode_event("a1", "12:03", "ACCESS")])
        row = report["rows"][0]
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertIn("UNKNOWN_ACCESS_DIRECTION", row["review_codes"])
        self.assertEqual(row["access_evidence"][0]["mode"], "ACCESS")
        self.assertEqual(row["access_evidence"][0]["direction"], "UNKNOWN")
        self.assertEqual(row["event_intervals"], [])

    def test_explicit_clock_modes_are_not_automatically_rest(self):
        report = self.assess([
            mode_event("entry", "09:00", "CLOCK_IN"),
            mode_event("exit", "18:00", "CLOCK_OUT"),
        ])
        self.assertEqual(report["rows"][0]["event_intervals"], [])
        self.assertNotIn("UNKNOWN_ACCESS_DIRECTION", report["rows"][0]["review_codes"])

    def test_outing_and_return_mode_pair_without_fabricating_door_direction(self):
        report = self.assess([
            mode_event("leave", "12:05", "OUTING"),
            mode_event("return", "12:55", "RETURN"),
        ])
        row = report["rows"][0]
        self.assertEqual(row["event_intervals"][0]["duration_min"], 50)
        self.assertEqual(row["event_intervals"][0]["classification"],
                         "PLANNED_BREAK_CANDIDATE")
        self.assertEqual(row["verified_rest_min"], 0)
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertEqual(row["access_evidence"][0]["direction"], "UNKNOWN")

    def test_disarm_does_not_pair_or_claim_clock(self):
        row = self.assess([mode_event("d", "10:00", "DISARM")])["rows"][0]
        self.assertEqual(row["event_intervals"], [])
        self.assertEqual(row["verified_rest_min"], 0)

    def test_conflicting_physical_direction_and_mode_is_review(self):
        row = self.assess([mode_event("bad", "12:00", "OUTING", "IN")])["rows"][0]
        self.assertIn("ACCESS_MODE_DIRECTION_CONFLICT", row["review_codes"])

    def test_inferred_attendance_candidate_remains_unconfirmed(self):
        candidate = {
            "employee_id": "E001", "worker_id": "EP0001",
            "work_date": "2026-11-13", "arrival_candidate": "08:56",
            "arrival_basis": "INFERRED_FIRST_ACCESS",
            "departure_candidate": None, "departure_basis": "MISSING",
            "review_codes": ["MISSING_EXPLICIT_CLOCK_IN", "MISSING_EXPLICIT_CLOCK_OUT"],
            "confirmed": False,
        }
        row = self.assess([], [candidate])["rows"][0]
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertIn("ATTENDANCE_CANDIDATE_REVIEW", row["review_codes"])
        self.assertEqual(row["attendance_candidate"]["arrival_basis"],
                         "INFERRED_FIRST_ACCESS")

    def test_candidate_cannot_claim_approved_attendance(self):
        candidate = {
            "employee_id": "E001", "worker_id": "EP0001",
            "work_date": "2026-11-13", "arrival_basis": "EXPLICIT_CLOCK_IN",
            "departure_basis": "EXPLICIT_CLOCK_OUT", "confirmed": True,
        }
        with self.assertRaisesRegex(breaks.BreakReviewError, "unconfirmed"):
            self.assess([], [candidate])

    def test_unmatched_candidate_is_present_even_without_a_worktime_result(self):
        bundle = source_with([])
        bundle["sources"]["schedule"]["rows"] = []
        bundle["sources"]["schedule"]["lineage"] = []
        source = bundle["sources"]
        source["attendance"]["rows"] = []
        source["attendance"]["lineage"] = []
        source["attendance_candidates"] = {
            "rows": [{"employee_id": "E001", "worker_id": "EP0001",
                      "work_date": "2026-11-13", "arrival_basis": "INFERRED_FIRST_ACCESS",
                      "departure_basis": "MISSING", "confirmed": False}],
            "source_sha256": "synthetic",
            "lineage": [{"status": "ACCEPTED", "row_number": 2, "issue_codes": []}],
        }
        config = old_tests.settings()
        report = breaks.analyze_access_breaks(
            bundle, config, batch.calculate_worktime_batch(bundle, config),
        )
        self.assertEqual(report["rows"][0]["status"], "REVIEW_REQUIRED")
        self.assertIn("ATTENDANCE_CANDIDATE_NOT_APPLIED",
                      report["rows"][0]["review_codes"])


if __name__ == "__main__":
    unittest.main()
