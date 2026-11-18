"""Evidence-safe signed clock deviations; independent synthetic unittest."""
from __future__ import annotations

import unittest
from importlib import import_module

verification = import_module("bhandara.worktime.attendance-verification")


class SignedAttendanceDeviationTests(unittest.TestCase):
    PERIOD = {"period_from": "2026-11-16", "period_to": "2026-11-16"}

    def plan(self, **changes):
        base = {"employee_id": "E001", "worker_id": "W001",
                "work_date": "2026-11-16", "day_type": "WORK",
                "scheduled_start": "09:00", "scheduled_end": "18:00",
                "source_ref": "synthetic-schedule"}
        base.update(changes)
        return base

    def ledger(self, **changes):
        base = {"employee_id": "E001", "worker_id": "W001",
                "work_date": "2026-11-16", "clock_in": "08:40",
                "clock_out": "18:16", "clock_in_reason": "시차출퇴근",
                "clock_out_reason": "업무 마무리",
                "source_ref": "synthetic-attendance"}
        base.update(changes)
        return base

    def event(self, mode, when, number, **changes):
        base = {"employee_id": "E001", "worker_id": "W001",
                "work_date": "2026-11-16", "event_id": f"P{number}",
                "event_time": when, "mode": mode, "direction": "UNKNOWN",
                "auth_status": "SUCCESS", "auth_method": "FINGERPRINT",
                "source_ref": "synthetic-caps"}
        base.update(changes)
        return base

    def candidate(self, **changes):
        base = {"employee_id": "E001", "worker_id": "W001",
                "work_date": "2026-11-16",
                "arrival_time": "2026-11-16T08:40:15",
                "departure_time": "2026-11-16T18:16:45",
                "arrival_basis": "INFERRED_FIRST_ACCESS",
                "departure_basis": "INFERRED_LAST_ACCESS",
                "candidate_status": "INFERRED_PAIR",
                "confirmed": False,
                "source_vendor": "SECOM",
                "evidence_event_ids": "AC1,AC2"}
        base.update(changes)
        return base

    def run_one(self, *, plans=None, ledger=None, events=None, candidates=None):
        return verification.verify_attendance(
            [self.ledger()] if ledger is None else ledger,
            [self.event("CLOCK_IN", "08:40", 1),
             self.event("CLOCK_OUT", "18:16", 2)] if events is None else events,
            schedule_rows=[self.plan()] if plans is None else plans,
            candidate_rows=[] if candidates is None else candidates,
            **self.PERIOD,
        )

    def test_signed_deviations_are_separate_by_clock_and_reason(self):
        report = self.run_one()
        row = report["rows"][0]
        self.assertEqual(row["status"], "RECORD_MATCH")
        self.assertEqual(row["time_deviations"]["status"], "DIFFERENT")
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        cin = row["time_deviations"]["clock_in"]
        cout = row["time_deviations"]["clock_out"]
        self.assertEqual(cin["ledger_vs_expected"]["delta_minutes"], -20)
        self.assertEqual(cout["ledger_vs_expected"]["delta_minutes"], 16)
        self.assertEqual(cin["device_vs_expected"]["delta_minutes"], -20)
        self.assertEqual(cout["device_vs_expected"]["delta_minutes"], 16)
        self.assertEqual(cin["reason"], "시차출퇴근")
        self.assertEqual(cout["reason"], "업무 마무리")
        self.assertFalse(cin["device_confirmed_as_work"])
        self.assertNotIn("approved_overtime_min", row)

    def test_source_to_source_deviation_has_own_baseline(self):
        report = self.run_one(ledger=[self.ledger(clock_in="08:45")])
        row = report["rows"][0]
        self.assertEqual(row["status"], "RECORD_DIFFERENT")
        cin = row["time_deviations"]["clock_in"]
        self.assertEqual(cin["ledger_vs_expected"]["delta_minutes"], -15)
        self.assertEqual(cin["device_vs_expected"]["delta_minutes"], -20)
        self.assertEqual(cin["device_vs_ledger"]["delta_minutes"], -5)

    def test_unconfirmed_first_last_access_can_be_compared_but_not_approved(self):
        events = [self.event("ACCESS", "08:40", 1),
                  self.event("ACCESS", "18:16", 2)]
        report = self.run_one(events=events, candidates=[self.candidate()])
        row = report["rows"][0]
        self.assertEqual(row["status"], "ACCESS_ONLY")
        cin = row["time_deviations"]["clock_in"]
        self.assertEqual(cin["device_origin"], "UNCONFIRMED_ACCESS_CANDIDATE")
        self.assertEqual(cin["device_basis"], "INFERRED_FIRST_ACCESS")
        self.assertEqual(cin["device_vs_expected"]["delta_seconds"], -1185)
        self.assertEqual(cin["device_vs_expected"]["delta_minutes"], -19.75)
        self.assertFalse(cin["device_confirmed_as_work"])

    def test_confirmed_candidate_is_rejected(self):
        report = self.run_one(events=[], candidates=[self.candidate(confirmed=True)])
        self.assertIn("DEVICE_CANDIDATE_MUST_BE_UNCONFIRMED",
                      report["rows"][0]["review_codes"])
        self.assertIsNone(report["rows"][0]["time_deviations"]["clock_in"]["device_recorded"])

    def test_conflicting_worker_id_blocks_candidate_deviation(self):
        report = self.run_one(events=[], candidates=[self.candidate(worker_id="WRONG")])
        row = report["rows"][0]
        self.assertIn("DEVICE_CANDIDATE_ID_CONFLICT", row["review_codes"])
        self.assertIsNone(row["time_deviations"]["clock_out"]["device_recorded"])

    def test_same_ledger_without_schedule_has_no_invented_expectation(self):
        report = self.run_one(plans=[])
        row = report["rows"][0]
        self.assertEqual(row["time_deviations"]["status"], "NOT_COMPARABLE")
        self.assertIsNone(row["time_deviations"]["clock_in"]["expected"])
        self.assertEqual(row["time_deviations"]["clock_in"]["device_vs_ledger"]["delta_minutes"], 0)
        self.assertEqual(report["status"], "PASS")

    def test_missing_reason_stays_none_and_does_not_change_delta(self):
        report = self.run_one(ledger=[
            self.ledger(clock_in_reason=None, clock_out_reason=None)
        ])
        a = report["rows"][0]["time_deviations"]
        self.assertIsNone(a["clock_in"]["reason"])
        self.assertEqual(a["clock_out"]["ledger_vs_expected"]["delta_minutes"], 16)

    def test_invalid_reason_causes_review(self):
        report = self.run_one(ledger=[self.ledger(clock_in_reason={"bad": True})])
        self.assertIn("INVALID_CLOCK_IN_REASON", report["rows"][0]["review_codes"])
        self.assertEqual(report["status"], "REVIEW_REQUIRED")

    def test_expected_work_times_can_be_missing_without_fabrication(self):
        report = self.run_one(plans=[
            self.plan(day_type="OFF", scheduled_start=None, scheduled_end=None)
        ])
        deviation = report["rows"][0]["time_deviations"]
        self.assertIsNone(deviation["clock_in"]["ledger_vs_expected"]["delta_minutes"])
        self.assertEqual(deviation["status"], "NOT_COMPARABLE")

    def test_duplicate_schedule_cannot_choose_arbitrary_expectation(self):
        report = self.run_one(plans=[self.plan(), self.plan()])
        row = report["rows"][0]
        self.assertIn("DUPLICATE_SCHEDULE", row["review_codes"])
        self.assertIsNone(row["time_deviations"]["clock_in"]["expected"])

    def test_invalid_expected_time_not_silently_replaced(self):
        report = self.run_one(plans=[self.plan(scheduled_start="09:XX")])
        self.assertIn("EXPECTED_SCHEDULED_START_INVALID", report["rows"][0]["review_codes"])

    def test_midnight_without_explicit_date_is_not_minus_1433_minutes(self):
        report = self.run_one(
            plans=[self.plan(scheduled_start="23:55")],
            ledger=[self.ledger(clock_in="00:02")],
            events=[self.event("CLOCK_IN", "00:02", 1)],
        )
        row = report["rows"][0]
        self.assertIn("CLOCK_DATE_AMBIGUOUS", row["review_codes"])
        self.assertIsNone(row["time_deviations"]["clock_in"]["ledger_vs_expected"]["delta_minutes"])

    def test_schedule_vs_attendance_worker_conflict_not_matched(self):
        report = self.run_one(plans=[self.plan(worker_id="OTHER")])
        self.assertIn("SCHEDULE_ATTENDANCE_ID_CONFLICT",
                      report["rows"][0]["review_codes"])

    def test_access_candidate_not_allowed_to_fill_explicit_punch_on_other_side(self):
        report = self.run_one(
            events=[self.event("CLOCK_IN", "08:40", 1)],
            candidates=[self.candidate()],
        )
        cin = report["rows"][0]["time_deviations"]["clock_in"]
        cout = report["rows"][0]["time_deviations"]["clock_out"]
        self.assertEqual(cin["device_origin"], "AUTHENTICATED_PUNCH")
        self.assertEqual(cout["device_origin"], "UNCONFIRMED_ACCESS_CANDIDATE")
        self.assertFalse(cout["device_confirmed_as_work"])

    def test_second_precision_preserved_without_truncation(self):
        report = self.run_one(events=[], candidates=[self.candidate()])
        self.assertEqual(report["rows"][0]["time_deviations"]["clock_out"]
                         ["device_recorded"], "2026-11-16T18:16:45")
        self.assertEqual(report["rows"][0]["time_deviations"]["clock_out"]
                         ["device_vs_expected"]["delta_seconds"], 1005)


if __name__ == "__main__":
    unittest.main()
