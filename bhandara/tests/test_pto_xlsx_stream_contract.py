"""Regression contracts for PTO's Common XLSX stream handoff.

Only synthetic workbooks. No Gearbox runtime, private files or real employees.
"""
from __future__ import annotations

import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook
from openpyxl.utils.datetime import CALENDAR_MAC_1904, to_excel

from bhandara.common.utils.hashing import sha256_file


PTO = importlib.import_module("bhandara.pto-calculator.src.input_adapter")


class PTOXlsxStreamContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pto-xlsx-stream-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def workbook(self, filename, headers, rows, *, epoch=None):
        path = self.root / filename
        book = Workbook()
        try:
            book.active.title = "DATA"
            if epoch is not None:
                book.epoch = epoch
            book.active.append(list(headers))
            for row in rows:
                book.active.append(list(row))
            book.save(path)
        finally:
            book.close()
        return path

    def test_employee_errors_remain_owner_scoped_and_physical_rows_survive(self):
        path = self.workbook(
            "employee.xlsx", PTO.EMPLOYEE_HEADERS + ("extra", "extra"), [
                ["E001", date(2025, 1, 1), None, "FIXED", None, None],
                [None, None, None, None, None, None],
                ["E002", "=TODAY()", None, "FIXED", None, None],
                ["E003", "not-a-date", None, "FIXED", None, None],
                ["E005", date(2024, 1, 1), None, "FIXED", None, None],
            ],
        )
        loaded = PTO.read_pto_sheet(path, "employees", sheet_name="DATA")
        self.assertEqual([row["employee_id"] for row in loaded.rows], ["E001", "E005"])
        self.assertEqual(loaded.row_numbers, [2, 6])
        self.assertEqual(loaded.rejected_owners, {"E002", "E003"})
        self.assertFalse(loaded.unassignable_error)
        self.assertEqual(loaded.source_hash, sha256_file(path))
        self.assertIn(("FORMULA_UNSUPPORTED", 4, "hire_date"),
                      {(f.code, f.row_number, f.field) for f in loaded.findings})
        self.assertIn(("INVALID_DATE", 5, "hire_date"),
                      {(f.code, f.row_number, f.field) for f in loaded.findings})

    def test_invalid_unowned_employee_or_shared_schedule_still_blocks_globally(self):
        roster = self.workbook("blank-owner.xlsx", PTO.EMPLOYEE_HEADERS, [
            [None, "not-a-date", None, "FIXED"],
            ["E005", date(2025, 1, 1), None, "FIXED"],
        ])
        loaded = PTO.read_pto_sheet(roster, "employees")
        self.assertTrue(loaded.unassignable_error)
        self.assertEqual([r["employee_id"] for r in loaded.rows], ["E005"])
        self.assertTrue(any(f.code == "REQUIRED_CELL_MISSING" for f in loaded.findings))

        schedule = self.workbook("schedule.xlsx", PTO.SCHEDULE_HEADERS, [
            ["S1", "FIXED", "=1+1", "WORK", "A", "09:00", "18:00", 60, 8, None],
            ["S2", "FIXED", 1, "WORK", "A", "09:00", "18:00", 60, 8, None],
        ])
        loaded = PTO.read_pto_sheet(schedule, "schedule")
        self.assertTrue(loaded.unassignable_error)
        self.assertEqual([r["schedule_id"] for r in loaded.rows], ["S2"])
        self.assertEqual(loaded.row_numbers, [3])
        self.assertTrue(any(
            f.code == "FORMULA_UNSUPPORTED" and f.row_number == 2
            for f in loaded.findings
        ))

    def test_event_optional_reduced_hours_retains_row_scoped_validation(self):
        headers = PTO.EVENT_HEADERS + ("reduced_hours",)
        rows = [
            ["R1", "E001", "REDUCED_HOURS", "2026-01-05", "HOUR", "CONFIRMED", None, 2.5],
            ["R2", "E002", "REDUCED_HOURS", "2026-01-06", "HOUR", "CONFIRMED", None, -1],
            ["R3", "E003", "REDUCED_HOURS", "2026-01-07", "HOUR", "CONFIRMED", None, "=1+1"],
            ["R4", "E004", "REDUCED_HOURS", "2026-01-08", "HOUR", "CONFIRMED", None, None],
        ]
        path = self.workbook("events.xlsx", headers, rows)
        loaded = PTO.read_pto_sheet(path, "events")
        self.assertEqual([r["employee_id"] for r in loaded.rows], ["E001", "E004"])
        self.assertEqual(loaded.rows[0]["reduced_hours"], 2.5)
        self.assertEqual(loaded.rejected_owners, {"E002", "E003"})
        self.assertFalse(loaded.unassignable_error)
        self.assertIn(("INVALID_REDUCED_HOURS", 3),
                      {(f.code, f.row_number) for f in loaded.findings})
        self.assertIn(("FORMULA_UNSUPPORTED", 4),
                      {(f.code, f.row_number) for f in loaded.findings})

        legacy = self.workbook("events-seven.xlsx", PTO.EVENT_HEADERS, [
            ["R5", "E005", "CONFIRMED_ABSENCE", "2026-01-09", "DAY", "CONFIRMED", ""],
        ])
        legacy_loaded = PTO.read_pto_sheet(legacy, "events")
        self.assertEqual(legacy_loaded.rejected_owners, set())
        self.assertNotIn("reduced_hours", legacy_loaded.rows[0])

    def test_legacy_date_conversion_uses_workbook_epoch(self):
        serial = to_excel(date(2026, 1, 1), epoch=CALENDAR_MAC_1904)
        path = self.workbook("mac-epoch.xlsx", PTO.EMPLOYEE_HEADERS, [
            ["E001", serial, None, "FIXED"],
        ], epoch=CALENDAR_MAC_1904)
        loaded = PTO.read_pto_sheet(path, "employees")
        self.assertEqual(loaded.rows[0]["hire_date"], date(2026, 1, 1))
        self.assertEqual(loaded.row_numbers, [2])
        self.assertEqual(loaded.findings, [])

    def test_missing_sheet_and_required_header_keep_pto_error_messages(self):
        path = self.workbook("missing-sheet.xlsx", PTO.EMPLOYEE_HEADERS, [
            ["E001", "2025-01-01", None, "FIXED"],
        ])
        with self.assertRaisesRegex(
            PTO.PTOInputError, "missing-sheet.xlsx: required worksheet missing: OTHER",
        ):
            PTO.read_pto_sheet(path, "employees", sheet_name="OTHER")
        path = self.workbook("missing-header.xlsx", [
            "employee_id", "wrong_header", "termination_date", "work_system",
        ], [["E001", "2025-01-01", None, "FIXED"]])
        with self.assertRaisesRegex(
            PTO.PTOInputError, "missing-header.xlsx: missing required header: hire_date",
        ):
            PTO.read_pto_sheet(path, "employees")

    def test_unused_formula_column_does_not_change_selected_column_contract(self):
        path = self.workbook("extra-formula.xlsx", PTO.EMPLOYEE_HEADERS + ("extra",), [
            ["E001", "2025-01-01", None, "FIXED", "=2+2"],
        ])
        loaded = PTO.read_pto_sheet(path, "employees")
        self.assertEqual([r["employee_id"] for r in loaded.rows], ["E001"])
        self.assertEqual(loaded.findings, [])

    def test_source_hash_change_still_aborts_before_results(self):
        path = self.workbook("changed.xlsx", PTO.EMPLOYEE_HEADERS, [
            ["E001", "2025-01-01", None, "FIXED"],
        ])
        with patch.object(PTO, "sha256_file", side_effect=["initial", "changed"]):
            with self.assertRaisesRegex(
                PTO.PTOInputError, "changed.xlsx: input changed during read",
            ):
                PTO.read_pto_sheet(path, "employees")


if __name__ == "__main__":
    unittest.main()
