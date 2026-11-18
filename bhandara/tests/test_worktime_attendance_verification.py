"""Synthetic unittest for independent attendance/device-evidence reconciliation."""
from __future__ import annotations

import unittest

from bhandara.worktime.attendance_verification import verify_attendance
from bhandara.worktime.attendance_verification.calculation import (
    AttendanceVerificationInputError,
)


class AttendanceVerificationTests(unittest.TestCase):
    PERIOD = {"period_from": "2026-11-01", "period_to": "2026-11-30"}

    def ledger(self, **overrides):
        row = {
            "employee_id": "E001", "worker_id": "EP0001",
            "work_date": "2026-11-16", "clock_in": "09:00",
            "clock_out": "18:00", "source_ref": "ledger-fixture",
            "_row_number": 2,
        }
        row.update(overrides)
        return row

    def punch(self, event_id="in-1", mode="CLOCK_IN", event_time="09:00", **overrides):
        row = {
            "employee_id": "E001", "worker_id": "EP0001",
            "work_date": "2026-11-16", "event_id": event_id,
            "event_time": event_time, "mode": mode,
            "direction": "UNKNOWN", "auth_status": "SUCCESS",
            "auth_method": "FINGERPRINT", "source_ref": "reader-fixture",
            "_row_number": 2, "device_id": "SYN-READER",
        }
        row.update(overrides)
        return row

    def paired(self):
        return [self.punch(), self.punch("out-1", "CLOCK_OUT", "18:00", _row_number=3)]

    def run_one(self, ledger=None, events=None, **kwargs):
        return verify_attendance(
            [self.ledger()] if ledger is None else ledger,
            self.paired() if events is None else events,
            **self.PERIOD, **kwargs,
        )

    def test_matching_fingerprint_punches_are_record_match(self):
        result = self.run_one()
        row = result["rows"][0]
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(row["status"], "RECORD_MATCH")
        self.assertEqual(row["device_punches"]["clock_in"], "2026-11-16T09:00")
        self.assertEqual(row["device_punches"]["clock_out"], "2026-11-16T18:00")
        self.assertFalse(result["approved"])
        self.assertFalse(result["verified_work_hours"])

    def test_difference_is_not_lateness_or_overtime(self):
        result = self.run_one(events=[self.punch(event_time="09:17"),
                                      self.punch("out-1", "CLOCK_OUT", "18:05")])
        row = result["rows"][0]
        self.assertEqual(row["status"], "RECORD_DIFFERENT")
        self.assertEqual(row["different_fields"], ["clock_in", "clock_out"])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertNotIn("late_minutes", row)
        self.assertNotIn("overtime_hours", row)

    def test_missing_all_events_requires_evidence(self):
        row = self.run_one(events=[])["rows"][0]
        self.assertEqual(row["status"], "MISSING_EVIDENCE")
        self.assertEqual(row["review_codes"], [
            "CLOCK_IN_EVIDENCE_MISSING", "CLOCK_OUT_EVIDENCE_MISSING"
        ])

    def test_access_only_is_unconfirmed_candidate(self):
        row = self.run_one(events=[
            self.punch(mode="ACCESS", event_time="08:53"),
            self.punch("access-2", "ACCESS", "18:02", _row_number=3),
        ])["rows"][0]
        self.assertEqual(row["status"], "ACCESS_ONLY")
        self.assertEqual(row["first_access_candidate"], {
            "event_time": "2026-11-16T08:53",
            "basis": "FIRST_GENERIC_ACCESS", "confirmed": False,
        })
        self.assertIsNone(row["device_punches"]["clock_in"])

    def test_unknown_physical_direction_does_not_invalidate_clock_mode(self):
        row = self.run_one()["rows"][0]
        self.assertEqual(row["status"], "RECORD_MATCH")
        self.assertEqual(row["access_evidence"][0]["direction"], "UNKNOWN")

    def test_device_only_never_creates_attendance(self):
        result = self.run_one(ledger=[])
        row = result["rows"][0]
        self.assertEqual(row["status"], "DEVICE_ONLY")
        self.assertIsNone(row["reported"])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")

    def test_failed_fingerprint_is_not_authentic(self):
        row = self.run_one(events=[
            self.punch(auth_status="FAILED"),
            self.punch("out-1", "CLOCK_OUT", "18:00"),
        ])["rows"][0]
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertIn("EVENT_AUTH_NOT_VERIFIED", row["review_codes"])
        self.assertIsNone(row["device_punches"]["clock_in"])

    def test_unknown_auth_status_fails_closed(self):
        events = self.paired()
        events[0].pop("auth_status")
        row = self.run_one(events=events)["rows"][0]
        self.assertIn("EVENT_AUTH_NOT_VERIFIED", row["review_codes"])
        self.assertEqual(row["status"], "REVIEW_REQUIRED")

    def test_missing_auth_method_cannot_impersonate_fingerprint(self):
        events = self.paired()
        events[0].pop("auth_method")
        row = self.run_one(events=events)["rows"][0]
        self.assertIn("EVENT_AUTH_METHOD_UNKNOWN", row["review_codes"])
        self.assertIsNone(row["device_punches"]["clock_in"])

    def test_card_auth_is_not_fingerprint_by_default(self):
        events = self.paired()
        events[0]["auth_method"] = "CARD"
        row = self.run_one(events=events)["rows"][0]
        self.assertIn("EVENT_AUTH_METHOD_NOT_ACCEPTED", row["review_codes"])
        self.assertEqual(row["status"], "REVIEW_REQUIRED")

    def test_explicit_policy_can_accept_card_without_claiming_fingerprint(self):
        events = self.paired()
        for item in events:
            item["auth_method"] = "CARD"
        result = self.run_one(events=events, accepted_auth_methods=["CARD"])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["rows"][0]["access_evidence"][0]["auth_method"], "CARD")

    def test_duplicate_ledger_requires_review(self):
        ledgers = [self.ledger(), self.ledger(_row_number=3)]
        row = self.run_one(ledger=ledgers)["rows"][0]
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertIn("DUPLICATE_LEDGER", row["review_codes"])

    def test_duplicate_punch_id_cannot_be_used(self):
        row = self.run_one(events=[
            self.punch(event_id="duplicate"),
            self.punch("duplicate", "CLOCK_OUT", "18:00", _row_number=3),
        ])["rows"][0]
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertIn("EVENT_ID_DUPLICATED", row["review_codes"])
        self.assertIsNone(row["device_punches"]["clock_in"])

    def test_multiple_clock_in_is_not_silently_reduced(self):
        row = self.run_one(events=[
            self.punch(),
            self.punch("in-2", "CLOCK_IN", "09:03", _row_number=3),
            self.punch("out-1", "CLOCK_OUT", "18:00", _row_number=4),
        ])["rows"][0]
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertIn("MULTIPLE_CLOCK_IN", row["review_codes"])
        self.assertIsNone(row["device_punches"]["clock_in"])

    def test_conflicting_worker_id_blocks_matching(self):
        row = self.run_one(events=[
            self.punch(worker_id="OTHER"),
            self.punch("out-1", "CLOCK_OUT", "18:00"),
        ])["rows"][0]
        self.assertEqual(row["status"], "REVIEW_REQUIRED")
        self.assertIn("WORKER_ID_CONFLICT", row["review_codes"])

    def test_bad_time_preserved_as_review(self):
        row = self.run_one(events=[
            self.punch(event_time="09:00:35"),
            self.punch("out-1", "CLOCK_OUT", "18:00"),
        ])["rows"][0]
        self.assertIn("EVENT_TIME_INVALID", row["review_codes"])
        self.assertEqual(row["status"], "REVIEW_REQUIRED")

    def test_cross_midnight_needs_explicit_end_date(self):
        row = self.run_one(ledger=[self.ledger(clock_in="22:00", clock_out="06:00")],
                           events=[self.punch(event_time="22:00"),
                                   self.punch("out-1", "CLOCK_OUT", "06:00")])["rows"][0]
        self.assertIn("OVERNIGHT_DATE_REQUIRED", row["review_codes"])
        self.assertEqual(row["status"], "REVIEW_REQUIRED")

    def test_cross_midnight_full_iso_is_supported(self):
        row = self.run_one(
            ledger=[self.ledger(clock_in="2026-11-16T22:00",
                                clock_out="2026-11-17T06:00")],
            events=[self.punch(event_time="2026-11-16T22:00"),
                    self.punch("out-1", "CLOCK_OUT", "2026-11-17T06:00")],
        )["rows"][0]
        self.assertEqual(row["status"], "RECORD_MATCH")

    def test_out_of_period_record_is_not_silently_accepted(self):
        row = self.punch(work_date="2026-12-03")
        result = self.run_one(events=self.paired() + [row])
        self.assertEqual(result["rows"][0]["status"], "RECORD_MATCH")
        self.assertEqual(result["source_issues"][0]["code"], "OUTSIDE_PERIOD")
        self.assertEqual(result["status"], "REVIEW_REQUIRED")

    def test_invalid_key_isolated_as_source_issue(self):
        bad = self.ledger(employee_id="", _row_number=3)
        result = self.run_one(ledger=[self.ledger(), bad])
        self.assertEqual(result["rows"][0]["status"], "RECORD_MATCH")
        self.assertEqual(result["source_issues"][0]["code"], "ROW_KEY_INVALID")

    def test_empty_sources_do_not_pass(self):
        result = self.run_one(ledger=[], events=[])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["source_issues"][0]["code"], "NO_COMPARABLE_ROWS")

    def test_unknown_access_mode_requires_review(self):
        row = self.run_one(events=self.paired() + [
            self.punch("other", "UNKNOWN", "12:00", _row_number=4),
        ])["rows"][0]
        self.assertIn("EVENT_MODE_UNKNOWN", row["review_codes"])
        self.assertEqual(row["status"], "REVIEW_REQUIRED")

    def test_outing_and_disarm_are_not_clock_punches(self):
        row = self.run_one(events=[
            self.punch(mode="OUTING", event_time="12:00"),
            self.punch("return", "RETURN", "12:30", _row_number=3),
            self.punch("disarm", "DISARM", "08:00", _row_number=4),
        ])["rows"][0]
        self.assertEqual(row["status"], "MISSING_EVIDENCE")
        self.assertIsNone(row["device_punches"]["clock_in"])

    def test_invalid_batch_contract_fails(self):
        with self.assertRaises(AttendanceVerificationInputError):
            verify_attendance([], [], period_from="2026-11-30",
                              period_to="2026-11-01")
        with self.assertRaises(AttendanceVerificationInputError):
            self.run_one(accepted_auth_methods="FINGERPRINT")
        with self.assertRaises(AttendanceVerificationInputError):
            self.run_one(accepted_auth_methods=["UNKNOWN"])

    def test_clean_and_bad_days_do_not_cross_contaminate(self):
        second = self.ledger(employee_id="E002", worker_id="EP0002",
                             work_date="2026-11-17", clock_in="09:00",
                             clock_out="18:00", _row_number=3)
        result = self.run_one(
            ledger=[self.ledger(), second],
            events=self.paired(),
        )
        self.assertEqual([row["status"] for row in result["rows"]],
                         ["RECORD_MATCH", "MISSING_EVIDENCE"])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
