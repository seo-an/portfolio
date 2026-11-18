"""Synthetic unittest: Attendance Detection keeps presence separate from work."""
from __future__ import annotations

import unittest
from importlib import import_module

mod = import_module("bhandara.worktime.attendance-detection")
detect_attendance = mod.detect_attendance
DetectionInputError = mod.DetectionInputError


class AttendanceDetectionTests(unittest.TestCase):
    PERIOD = {"period_from": "2026-11-16", "period_to": "2026-11-22"}

    def plan(self, **changes):
        row = {
            "employee_id": "E001", "worker_id": "W001",
            "work_date": "2026-11-16", "day_type": "WORK",
            "scheduled_start": "09:00", "scheduled_end": "18:00",
            "source_ref": "synthetic-schedule.xlsx", "_row_number": 2,
        }
        row.update(changes)
        return row

    def ledger(self, **changes):
        row = {
            "employee_id": "E001", "worker_id": "W001",
            "work_date": "2026-11-16",
            "clock_in": "09:00", "clock_out": "18:00",
            "source_ref": "synthetic-attendance.xlsx", "_row_number": 2,
        }
        row.update(changes)
        return row

    def candidate(self, **changes):
        row = {
            "employee_id": "E001", "worker_id": "W001",
            "work_date": "2026-11-16",
            "arrival_time": "2026-11-16T08:45:11",
            "departure_time": "2026-11-16T18:21:44",
            "arrival_basis": "INFERRED_FIRST_ACCESS",
            "departure_basis": "INFERRED_LAST_ACCESS",
            "candidate_status": "INFERRED_PAIR",
            "confirmed": False,
            "evidence_event_ids": "A1,A2",
            "source_vendor": "SECOM",
            "source_ref": "synthetic-access.xlsx",
        }
        row.update(changes)
        return row

    def work(self, start="18:00", end="19:00", **changes):
        row = {
            "employee_id": "E001", "worker_id": "W001",
            "work_date": "2026-11-16",
            "start": start, "end": end,
            "verified": True, "evidence_ref": "SYNTHETIC-VERIFIED-WORK",
            "source_ref": "synthetic-work-evidence", "_row_number": 2,
        }
        row.update(changes)
        return row

    def run_one(self, plans=None, ledgers=None, candidates=None, work=None,
                policy=None, **period):
        return detect_attendance(
            [self.plan()] if plans is None else plans,
            [self.ledger()] if ledgers is None else ledgers,
            candidate_rows=[] if candidates is None else candidates,
            verified_work_intervals=[] if work is None else work,
            policy=policy,
            **(period or self.PERIOD),
        )

    @staticmethod
    def signal_codes(report):
        return [signal["code"] for signal in report["rows"][0]["signals"]]

    @staticmethod
    def signal(report, code):
        return next(item for item in report["rows"][0]["signals"] if item["code"] == code)

    def test_exact_schedule_and_ledger_have_no_findings(self):
        report = self.run_one()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["rows"][0]["status"], "NO_FINDINGS")
        self.assertEqual(report["rows"][0]["signals"], [])
        self.assertFalse(report["approved"])
        self.assertFalse(report["verified_work_hours"])
        self.assertFalse(report["payroll_finalizable"])

    def test_late_arrival_is_reported_candidate_not_legal_lateness(self):
        report = self.run_one(ledgers=[self.ledger(clock_in="09:17:35")])
        self.assertEqual(self.signal(report, "LATE_ARRIVAL_REPORTED_CANDIDATE")["duration_seconds"], 1055)
        self.assertEqual(report["rows"][0]["status"], "CANDIDATES_FOUND")
        self.assertNotIn("late_minutes", report["rows"][0])

    def test_early_departure_is_reported_candidate(self):
        report = self.run_one(ledgers=[self.ledger(clock_out="17:54:40")])
        self.assertEqual(self.signal(report, "EARLY_LEAVE_REPORTED_CANDIDATE")["duration_seconds"], 320)
        self.assertNotIn("EARLY_PRESENCE", self.signal_codes(report))

    def test_late_tolerance_is_configurable(self):
        report = self.run_one(
            ledgers=[self.ledger(clock_in="09:08")],
            policy={"late_grace_min": 10},
        )
        self.assertEqual(report["status"], "PASS")

    def test_early_departure_tolerance_is_configurable(self):
        report = self.run_one(
            ledgers=[self.ledger(clock_out="17:55")],
            policy={"early_leave_grace_min": 5},
        )
        self.assertEqual(report["status"], "PASS")

    def test_pre_shift_presence_is_not_extra_work(self):
        report = self.run_one(ledgers=[self.ledger(clock_in="08:45")])
        self.assertIn("PRE_SHIFT_PRESENCE_CANDIDATE", self.signal_codes(report))
        self.assertNotIn("EXTENDED_WORK_CANDIDATE", self.signal_codes(report))
        self.assertEqual(self.signal(report, "PRE_SHIFT_PRESENCE_CANDIDATE")["duration_seconds"], 900)

    def test_post_shift_presence_is_not_extra_work(self):
        report = self.run_one(ledgers=[self.ledger(clock_out="19:00")])
        self.assertIn("POST_SHIFT_PRESENCE_CANDIDATE", self.signal_codes(report))
        self.assertNotIn("EXTENDED_WORK_CANDIDATE", self.signal_codes(report))

    def test_night_presence_is_not_night_work(self):
        report = self.run_one(ledgers=[self.ledger(clock_out="22:30")])
        self.assertEqual(self.signal(report, "NIGHT_PRESENCE_CANDIDATE")["duration_seconds"], 1800)
        self.assertNotIn("NIGHT_WORK_CANDIDATE", self.signal_codes(report))
        self.assertEqual(report["rows"][0]["reported"]["clock_out"], "2026-11-16T22:30:00")

    def test_independent_verified_interval_creates_extra_work_candidate(self):
        report = self.run_one(
            ledgers=[self.ledger(clock_out="19:00")],
            work=[self.work()],
        )
        item = self.signal(report, "EXTENDED_WORK_CANDIDATE")
        self.assertEqual(item["duration_seconds"], 3600)
        self.assertEqual(item["basis"], "VERIFIED_WORK")
        self.assertEqual(item["evidence_refs"], ["SYNTHETIC-VERIFIED-WORK"])
        self.assertFalse(report["approved"])
        self.assertNotIn("approved_overtime_min", report["rows"][0])

    def test_verified_external_work_can_be_outside_reader_presence(self):
        report = self.run_one(
            ledgers=[self.ledger()],
            work=[self.work()],
        )
        self.assertIn("EXTENDED_WORK_CANDIDATE", self.signal_codes(report))
        self.assertNotIn("POST_SHIFT_PRESENCE_CANDIDATE", self.signal_codes(report))

    def test_night_work_overlap_counts_actual_seconds(self):
        report = self.run_one(
            ledgers=[self.ledger(clock_out="23:20:30")],
            work=[self.work("21:30", "23:10:30")],
        )
        self.assertEqual(self.signal(report, "NIGHT_WORK_CANDIDATE")["duration_seconds"], 4230)
        self.assertNotEqual(
            self.signal(report, "NIGHT_PRESENCE_CANDIDATE")["duration_seconds"],
            self.signal(report, "NIGHT_WORK_CANDIDATE")["duration_seconds"],
        )

    def test_verified_multiple_nonoverlapping_intervals_sum_work_only(self):
        report = self.run_one(work=[
            self.work("18:00", "18:30", evidence_ref="EVIDENCE-1"),
            self.work("18:45", "19:00", evidence_ref="EVIDENCE-2"),
        ])
        item = self.signal(report, "EXTENDED_WORK_CANDIDATE")
        self.assertEqual(item["duration_seconds"], 2700)
        self.assertEqual(item["evidence_refs"], ["EVIDENCE-1", "EVIDENCE-2"])

    def test_overlapping_work_spans_cannot_be_double_counted(self):
        report = self.run_one(work=[
            self.work("18:00", "19:00"),
            self.work("18:30", "19:30", evidence_ref="SYNTHETIC-2"),
        ])
        self.assertEqual(report["rows"][0]["status"], "REVIEW_REQUIRED")
        self.assertIn("WORK_INTERVAL_OVERLAP_REVIEW", report["rows"][0]["review_codes"])
        self.assertNotIn("EXTENDED_WORK_CANDIDATE", self.signal_codes(report))

    def test_unverified_work_does_not_create_extension(self):
        report = self.run_one(work=[self.work(verified=False)])
        self.assertIn("WORK_INTERVAL_EVIDENCE_UNVERIFIED", report["rows"][0]["review_codes"])
        self.assertNotIn("EXTENDED_WORK_CANDIDATE", self.signal_codes(report))

    def test_empty_work_evidence_reference_does_not_create_extension(self):
        report = self.run_one(work=[self.work(evidence_ref="")])
        self.assertIn("WORK_INTERVAL_EVIDENCE_UNVERIFIED", report["rows"][0]["review_codes"])

    def test_overnight_schedule_and_work_use_explicit_next_date(self):
        report = self.run_one(
            plans=[self.plan(scheduled_start="21:00",
                             scheduled_end="2026-11-17T02:00")],
            ledgers=[self.ledger(clock_in="21:00",
                                 clock_out="2026-11-17T02:00")],
            work=[self.work("21:00", "2026-11-17T02:00")],
        )
        self.assertEqual(report["rows"][0]["status"], "CANDIDATES_FOUND")
        self.assertEqual(self.signal(report, "NIGHT_WORK_CANDIDATE")["duration_seconds"], 14400)
        self.assertNotIn("EXTENDED_WORK_CANDIDATE", self.signal_codes(report))
        self.assertNotIn("HOLIDAY_WORK_CANDIDATE", self.signal_codes(report))

    def test_overnight_end_without_date_cannot_be_guessed(self):
        report = self.run_one(
            plans=[self.plan(scheduled_start="22:00", scheduled_end="06:00")],
            ledgers=[self.ledger(clock_in="22:00", clock_out="06:00")],
        )
        self.assertEqual(report["rows"][0]["status"], "REVIEW_REQUIRED")
        self.assertIn("SCHEDULE_OVERNIGHT_DATE_REQUIRED", report["rows"][0]["review_codes"])
        self.assertIn("LEDGER_OVERNIGHT_DATE_REQUIRED", report["rows"][0]["review_codes"])

    def test_schedule_work_without_attendance_is_record_missing_not_absence(self):
        report = self.run_one(ledgers=[])
        self.assertIn("MISSING_ATTENDANCE_RECORD", self.signal_codes(report))
        self.assertNotIn("ABSENT", self.signal_codes(report))
        self.assertFalse(report["approved"])

    def test_unconfirmed_reader_first_last_is_not_reported_lateness(self):
        report = self.run_one(candidates=[self.candidate()])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["rows"][0]["device_candidate"]["candidate_status"], "INFERRED_PAIR")
        self.assertEqual(report["rows"][0]["signals"], [])

    def test_reader_only_does_not_fill_missing_ledger(self):
        report = self.run_one(ledgers=[], candidates=[self.candidate()])
        self.assertEqual(set(self.signal_codes(report)), {
            "MISSING_ATTENDANCE_RECORD", "DEVICE_PRESENCE_UNCONFIRMED",
        })
        self.assertEqual(report["rows"][0]["reported"], None)
        self.assertNotIn("LATE_ARRIVAL_REPORTED_CANDIDATE", self.signal_codes(report))

    def test_reader_only_without_schedule_is_not_work(self):
        report = self.run_one(plans=[], ledgers=[], candidates=[self.candidate()])
        self.assertEqual(self.signal_codes(report), ["DEVICE_PRESENCE_UNCONFIRMED"])
        self.assertNotIn("UNSCHEDULED_WORK_CANDIDATE", self.signal_codes(report))

    def test_reader_events_without_clock_candidate_require_review(self):
        report = self.run_one(plans=[], ledgers=[], candidates=[
            self.candidate(arrival_time="", departure_time="",
                           arrival_basis="MISSING", departure_basis="MISSING",
                           candidate_status="NO_ATTENDANCE_CANDIDATE"),
        ])
        self.assertIn("DEVICE_EVENTS_WITHOUT_ATTENDANCE_CANDIDATE", self.signal_codes(report))

    def test_device_candidate_claimed_confirmed_is_rejected(self):
        report = self.run_one(candidates=[self.candidate(confirmed=True)])
        self.assertEqual(report["rows"][0]["status"], "REVIEW_REQUIRED")
        self.assertIn("DEVICE_CANDIDATE_MUST_BE_UNCONFIRMED",
                      report["rows"][0]["review_codes"])

    def test_duplicate_device_candidates_require_review(self):
        report = self.run_one(candidates=[self.candidate(), self.candidate()])
        self.assertIn("DUPLICATE_DEVICE_CANDIDATE", report["rows"][0]["review_codes"])

    def test_ambiguous_explicit_candidate_requires_review(self):
        report = self.run_one(candidates=[
            self.candidate(candidate_status="MULTIPLE_EXPLICIT_REVIEW")
        ])
        self.assertIn("DEVICE_CANDIDATE_NEEDS_REVIEW", report["rows"][0]["review_codes"])

    def test_holiday_presence_is_not_work(self):
        report = self.run_one(plans=[self.plan(day_type="HOLIDAY",
                                              scheduled_start=None, scheduled_end=None)])
        self.assertIn("HOLIDAY_PRESENCE_CANDIDATE", self.signal_codes(report))
        self.assertNotIn("HOLIDAY_WORK_CANDIDATE", self.signal_codes(report))

    def test_holiday_work_requires_independent_verified_interval(self):
        report = self.run_one(
            plans=[self.plan(day_type="HOLIDAY",
                             scheduled_start=None, scheduled_end=None)],
            work=[self.work("10:00", "12:00")],
        )
        self.assertIn("HOLIDAY_WORK_CANDIDATE", self.signal_codes(report))
        self.assertEqual(self.signal(report, "HOLIDAY_WORK_CANDIDATE")["duration_seconds"], 7200)

    def test_offday_work_and_presence_are_separated(self):
        report = self.run_one(
            plans=[self.plan(day_type="OFF", scheduled_start=None,
                             scheduled_end=None)],
            work=[self.work("10:00", "12:00")],
        )
        self.assertIn("REST_DAY_PRESENCE_CANDIDATE", self.signal_codes(report))
        self.assertIn("REST_DAY_WORK_CANDIDATE", self.signal_codes(report))

    def test_offday_without_any_attendance_is_not_false_absence(self):
        report = self.run_one(
            plans=[self.plan(day_type="OFF", scheduled_start=None,
                             scheduled_end=None)],
            ledgers=[],
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["rows"][0]["signals"], [])

    def test_unscheduled_ledger_and_verified_work_are_separate(self):
        report = self.run_one(plans=[], work=[self.work("18:00", "19:00")])
        self.assertIn("UNSCHEDULED_PRESENCE_CANDIDATE", self.signal_codes(report))
        self.assertIn("UNSCHEDULED_WORK_CANDIDATE", self.signal_codes(report))

    def test_unscheduled_ledger_without_verified_work(self):
        report = self.run_one(plans=[])
        self.assertEqual(self.signal_codes(report), ["UNSCHEDULED_PRESENCE_CANDIDATE"])

    def test_verified_work_with_no_ledger_keeps_missing_record_signal(self):
        report = self.run_one(ledgers=[], work=[self.work()])
        self.assertIn("MISSING_ATTENDANCE_RECORD", self.signal_codes(report))
        self.assertIn("EXTENDED_WORK_CANDIDATE", self.signal_codes(report))

    def test_duplicate_schedule_disables_detection(self):
        report = self.run_one(plans=[self.plan(), self.plan(_row_number=3)],
                              ledgers=[self.ledger(clock_in="09:15")])
        self.assertEqual(report["rows"][0]["status"], "REVIEW_REQUIRED")
        self.assertIn("DUPLICATE_SCHEDULE", report["rows"][0]["review_codes"])
        self.assertEqual(report["rows"][0]["signals"], [])

    def test_duplicate_attendance_disables_detection(self):
        report = self.run_one(ledgers=[self.ledger(), self.ledger(_row_number=3)])
        self.assertIn("DUPLICATE_ATTENDANCE", report["rows"][0]["review_codes"])

    def test_source_identity_conflict_disables_detection(self):
        report = self.run_one(ledgers=[self.ledger(worker_id="WRONG", clock_in="09:15")])
        self.assertIn("WORKER_ID_CONFLICT", report["rows"][0]["review_codes"])
        self.assertEqual(report["rows"][0]["signals"], [])

    def test_partial_attendance_is_review_without_invented_time(self):
        report = self.run_one(ledgers=[self.ledger(clock_out=None)])
        self.assertIn("LEDGER_INCOMPLETE", report["rows"][0]["review_codes"])
        self.assertEqual(report["rows"][0]["signals"], [])

    def test_unknown_day_type_is_review(self):
        report = self.run_one(plans=[self.plan(day_type="VACATION")])
        self.assertIn("DAY_TYPE_INVALID", report["rows"][0]["review_codes"])

    def test_outside_period_input_isolated_from_clean_row(self):
        report = self.run_one(plans=[self.plan(), self.plan(
            employee_id="E002", work_date="2026-12-01")])
        self.assertEqual(report["rows"][0]["status"], "NO_FINDINGS")
        self.assertEqual(report["source_issues"][0]["code"], "OUTSIDE_PERIOD")
        self.assertEqual(report["status"], "REVIEW_REQUIRED")

    def test_invalid_row_key_isolated(self):
        report = self.run_one(ledgers=[self.ledger(), self.ledger(
            employee_id="", work_date="bad-date")])
        self.assertEqual(report["rows"][0]["status"], "NO_FINDINGS")
        self.assertEqual(report["source_issues"][0]["code"], "ROW_KEY_INVALID")

    def test_empty_sources_cannot_pass(self):
        report = self.run_one(plans=[], ledgers=[])
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertEqual(report["source_issues"][0]["code"], "NO_COMPARABLE_ROWS")

    def test_policy_invalid_values_fail_at_request_boundary(self):
        with self.assertRaises(DetectionInputError):
            self.run_one(policy={"late_grace_min": -1})
        with self.assertRaises(DetectionInputError):
            self.run_one(policy={"night_start": "22:00", "night_end": "22:00"})
        with self.assertRaises(DetectionInputError):
            self.run_one(policy={"late_tolerance": 10})

    def test_night_window_is_configurable(self):
        report = self.run_one(
            plans=[self.plan(scheduled_start="20:00",
                             scheduled_end="2026-11-17T00:00")],
            ledgers=[self.ledger(clock_in="20:00",
                                 clock_out="2026-11-17T00:00")],
            policy={"night_start": "23:00", "night_end": "05:00"},
        )
        self.assertEqual(self.signal(report, "NIGHT_PRESENCE_CANDIDATE")["duration_seconds"], 3600)

    def test_order_of_employee_date_output_is_stable(self):
        second_plan = self.plan(employee_id="E002", worker_id="W002",
                                work_date="2026-11-17")
        second_ledger = self.ledger(employee_id="E002", worker_id="W002",
                                    work_date="2026-11-17")
        report = self.run_one(plans=[second_plan, self.plan()],
                              ledgers=[second_ledger, self.ledger()])
        self.assertEqual([row["employee_id"] for row in report["rows"]],
                         ["E001", "E002"])
        self.assertEqual(report["status"], "PASS")

    def test_source_lineage_is_kept(self):
        report = self.run_one()
        self.assertEqual(report["rows"][0]["sources"]["schedule"],
                         [{"source_ref": "synthetic-schedule.xlsx", "row_number": 2}])

    def test_device_candidate_must_not_overwrite_ledger(self):
        report = self.run_one(
            ledgers=[self.ledger(clock_in="09:17")],
            candidates=[self.candidate(arrival_time="2026-11-16T08:30:00")],
        )
        self.assertIn("LATE_ARRIVAL_REPORTED_CANDIDATE", self.signal_codes(report))
        self.assertEqual(report["rows"][0]["reported"]["clock_in"], "2026-11-16T09:17:00")
        self.assertEqual(report["rows"][0]["device_candidate"]["arrival_time"],
                         "2026-11-16T08:30:00")


if __name__ == "__main__":
    unittest.main()
