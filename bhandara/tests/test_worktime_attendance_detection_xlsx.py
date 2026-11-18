"""Synthetic XLSX v0.2 to Attendance Detection handoff verification."""
from __future__ import annotations

import tempfile
import unittest
from importlib import import_module
from pathlib import Path

from bhandara.worktime.access_source import write_access_events_xlsx

detect = import_module("bhandara.worktime.attendance-detection")


class AttendanceDetectionExcelHandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="bhandara-detection-xlsx-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def plan(self):
        return {
            "employee_id": "E001", "worker_id": "W001",
            "work_date": "2026-11-16", "day_type": "WORK",
            "scheduled_start": "09:00", "scheduled_end": "18:00",
        }

    def attendance(self):
        return {
            "employee_id": "E001", "worker_id": "W001",
            "work_date": "2026-11-16", "clock_in": "09:00",
            "clock_out": "18:00",
        }

    def event(self, number, timestamp, mode="ACCESS"):
        return {
            "event_id": f"SEC-{number}", "employee_id": "E001",
            "worker_id": "W001", "work_date": "2026-11-16",
            "event_time": timestamp[:16], "event_timestamp": timestamp,
            "mode": mode, "direction": "UNKNOWN",
            "auth_status": "SUCCESS", "auth_method": "FINGERPRINT",
            "device_id": "READER-1", "source_vendor": "SYN_SECOM",
            "source_ref": "synthetic-secom-raw.xlsx",
            "source_row_number": number,
        }

    def review(self, status):
        return {
            "source_vendor": "SYN_SECOM",
            "source_row_number": 9,
            "status": status,
            "issue_codes": ("SECURITY_SET_EXCLUDED" if status == "EXCLUDED"
                            else "UNMAPPED_DEPARTMENT_EMPLOYEE_NUMBER"),
            "source_ref": "synthetic-secom-raw.xlsx",
            "detail": "synthetic",
        }

    def workbook(self, reviews=(), mode="ACCESS"):
        path = self.root / "access-events.xlsx"
        return write_access_events_xlsx(
            path, [
                self.event(2, "2026-11-16T08:40:11", mode),
                self.event(3, "2026-11-16T18:20:55",
                           "CLOCK_OUT" if mode == "CLOCK_IN" else mode),
            ], reviews,
            source_vendor="SYN_SECOM", source_sha256="a"*64,
            source_file="synthetic-secom-raw.xlsx",
        )

    def run_one(self, reviews=(), ledger=True, mode="ACCESS"):
        path = self.workbook(reviews=reviews, mode=mode)
        return detect.detect_attendance_xlsx(
            [self.plan()],
            [self.attendance()] if ledger else [],
            path, period_from="2026-11-16", period_to="2026-11-16",
        )

    def test_generic_access_first_last_are_not_treated_as_work(self):
        result = self.run_one()
        self.assertEqual(result["status"], "PASS")
        row = result["rows"][0]
        self.assertEqual(row["device_candidate"]["candidate_status"], "INFERRED_PAIR")
        self.assertEqual(row["device_candidate"]["arrival_time"], "2026-11-16T08:40:11")
        self.assertEqual(row["device_candidate"]["departure_time"], "2026-11-16T18:20:55")
        self.assertEqual(row["signals"], [])
        self.assertFalse(result["verified_work_hours"])

    def test_without_ledger_device_candidate_is_review_not_attendance(self):
        result = self.run_one(ledger=False)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual({s["code"] for s in result["rows"][0]["signals"]}, {
            "MISSING_ATTENDANCE_RECORD", "DEVICE_PRESENCE_UNCONFIRMED",
        })

    def test_normalized_source_unmapped_row_blocks_clean_pass(self):
        result = self.run_one(reviews=[self.review("UNMAPPED")])
        self.assertEqual(result["rows"][0]["status"], "NO_FINDINGS")
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["normalized_source"]["unresolved_count"], 1)
        self.assertEqual(result["source_issues"][0]["code"], "NORMALIZATION_UNMAPPED")

    def test_security_set_exclusion_does_not_block_clean_run(self):
        result = self.run_one(reviews=[self.review("EXCLUDED")])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["normalized_source"]["excluded_count"], 1)
        self.assertEqual(result["normalized_source"]["unresolved_count"], 0)

    def test_explicit_punch_is_still_unapproved_candidate(self):
        result = self.run_one(mode="CLOCK_IN")
        row = result["rows"][0]
        self.assertEqual(row["device_candidate"]["candidate_status"], "EXPLICIT_PAIR")
        self.assertFalse(row["device_candidate"]["confirmed"])
        self.assertEqual(row["signals"], [])

    def test_work_segments_are_never_synthesized_from_xlsx(self):
        result = self.run_one()
        self.assertEqual(result["rows"][0]["verified_work_intervals"], [])
        self.assertEqual(result["normalized_source"]["source_vendor"], "SYN_SECOM")


if __name__ == "__main__":
    unittest.main()
