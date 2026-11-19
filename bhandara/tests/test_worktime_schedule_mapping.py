"""Unittest: Worktime schedule map uses explicit IDs, not guessed daily clocks."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from bhandara.worktime.schedule import reconcile_schedule
from bhandara.worktime.schedule.mapping import (
    ScheduleMappingError, read_schedule_mapping, for_attendance_verification,
)


HEADERS = (
    "schedule_id", "schedule_type", "scheduled_start", "scheduled_end",
    "end_day_offset", "break_min", "scheduled_min", "valid_from", "valid_to",
)
ASSIGN_HEADERS = ("employee_id", "work_date", "schedule_id", "day_type")


def create_fixture(path: Path, definitions=None, assignments=None):
    defs = definitions if definitions is not None else [
        ("DAY_A", "DAY", "09:00", "18:00", 0, 60, 480, "2026-01-01", "2026-12-31"),
        ("NIGHT_A", "NIGHT", "21:00", "06:00", 1, 60, 480, "2026-01-01", "2026-12-31"),
    ]
    assignments = assignments if assignments is not None else [
        ("E001", "2026-11-03", "DAY_A", "WORK"),
        ("E002", "2026-11-03", "NIGHT_A", "WORK"),
        ("E003", "2026-11-03", None, "OFF"),
    ]
    book = Workbook()
    legacy = book.active
    legacy.title = "Legacy"
    legacy.append(("existing_input_must_remain",))
    mapping = book.create_sheet("SCHEDULE MAP")
    mapping.append(HEADERS)
    for row in defs:
        mapping.append(row)
    assignment = book.create_sheet("ASSIGNMENTS")
    assignment.append(ASSIGN_HEADERS)
    for row in assignments:
        assignment.append(row)
    book.save(path)
    book.close()


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bhandara-schedule-map-")
        self.path = Path(self.temp.name) / "work-schedule.xlsx"
        create_fixture(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def load(self):
        return read_schedule_mapping(
            self.path, period_from="2026-11-01", period_to="2026-11-30"
        )

    def test_expands_day_night_off_and_preserves_legacy_sheet(self):
        rows = self.load()
        by_id = {row["employee_id"]: row for row in rows}
        self.assertEqual(len(rows), 3)
        self.assertEqual(by_id["E001"]["scheduled_min"], 480)
        self.assertEqual(by_id["E001"]["schedule_id"], "DAY_A")
        self.assertEqual(by_id["E002"]["schedule_type"], "NIGHT")
        self.assertEqual(by_id["E002"]["end_day_offset"], 1)
        self.assertEqual(by_id["E003"]["scheduled_min"], 0)
        self.assertIsNone(by_id["E003"]["schedule_id"])
        book = load_workbook(self.path, read_only=True)
        try:
            self.assertEqual(book.sheetnames, ["Legacy", "SCHEDULE MAP", "ASSIGNMENTS"])
            self.assertEqual(book["Legacy"]["A1"].value, "existing_input_must_remain")
        finally:
            book.close()

    def test_overnight_is_dated_only_for_attendance_verification(self):
        source = self.load()
        projected = for_attendance_verification(source)
        night = next(row for row in projected if row["employee_id"] == "E002")
        original = next(row for row in source if row["employee_id"] == "E002")
        self.assertEqual(original["scheduled_end"], "06:00")
        self.assertEqual(night["scheduled_end"], "2026-11-04T06:00")
        self.assertEqual(night["scheduled_start"], "21:00")
        self.assertEqual(projected[0]["scheduled_end"], "18:00")

    def test_new_rows_are_accepted_by_existing_schedule_module(self):
        rows = self.load()
        ledger = [{"employee_id": "E001", "work_date": "2026-11-03",
                   "clock_in": "09:00", "clock_out": "18:00", "break_min": 60}]
        result = reconcile_schedule(rows, ledger, period_from="2026-11-01",
                                    period_to="2026-11-30")
        statuses = {row["employee_id"]: row["status"] for row in result["rows"]}
        self.assertEqual(statuses["E001"], "WORK_MATCH")
        self.assertEqual(statuses["E002"], "MISSING")
        self.assertEqual(statuses["E003"], "NON_WORK_MATCH")

    def test_missing_new_sheets_fail_without_legacy_fallback(self):
        book = load_workbook(self.path)
        del book["SCHEDULE MAP"]
        book.save(self.path)
        book.close()
        with self.assertRaises(ScheduleMappingError):
            self.load()

    def test_duplicate_schedule_id_rejected(self):
        book = load_workbook(self.path)
        book["SCHEDULE MAP"].append(
            ("DAY_A", "DAY", "08:00", "17:00", 0, 60, 480, None, None))
        book.save(self.path)
        book.close()
        with self.assertRaisesRegex(ScheduleMappingError, "duplicate schedule_id"):
            self.load()

    def test_unknown_or_expired_schedule_id_rejected(self):
        create_fixture(self.path, assignments=[
            ("E001", "2026-11-03", "MISSING_ID", "WORK")])
        with self.assertRaisesRegex(ScheduleMappingError, "unknown schedule_id"):
            self.load()
        create_fixture(self.path, definitions=[
            ("DAY_A", "DAY", "09:00", "18:00", 0, 60, 480, "2026-01-01", "2026-10-31")],
            assignments=[("E001", "2026-11-03", "DAY_A", "WORK")])
        with self.assertRaisesRegex(ScheduleMappingError, "outside validity"):
            self.load()

    def test_duplicate_employee_day_rejected(self):
        create_fixture(self.path, assignments=[
            ("E001", "2026-11-03", "DAY_A", "WORK"),
            ("E001", "2026-11-03", "DAY_A", "WORK")])
        with self.assertRaisesRegex(ScheduleMappingError, "duplicate employee/date"):
            self.load()

    def test_off_with_id_or_work_without_id_rejected(self):
        for invalid in (("E001", "2026-11-03", "DAY_A", "OFF"),
                        ("E001", "2026-11-03", None, "WORK")):
            with self.subTest(invalid=invalid):
                create_fixture(self.path, assignments=[invalid])
                with self.assertRaises(ScheduleMappingError):
                    self.load()

    def test_impossible_duration_and_formula_rejected(self):
        create_fixture(self.path, definitions=[
            ("DAY_A", "DAY", "09:00", "18:00", 0, 60, 600, None, None)],
            assignments=[("E001", "2026-11-03", "DAY_A", "WORK")])
        with self.assertRaisesRegex(ScheduleMappingError, "impossible duration"):
            self.load()
        create_fixture(self.path)
        book = load_workbook(self.path)
        book["SCHEDULE MAP"]["G2"] = "=480"
        book.save(self.path)
        book.close()
        with self.assertRaises(ScheduleMappingError):
            self.load()

    def test_only_existing_assignments_are_expanded(self):
        rows = read_schedule_mapping(
            self.path, period_from="2026-11-04", period_to="2026-11-30")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
