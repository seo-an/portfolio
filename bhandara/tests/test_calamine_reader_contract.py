"""Synthetic Calamine value reader and strict formula guard contracts."""
from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook

from bhandara.common.io.input_layout import InputLayoutError, read_sheet
from bhandara.common.io.xlsx_stream import XlsxStreamError, open_xlsx_rows


class CalamineReaderTests(unittest.TestCase):
    def test_blank_area_and_physical_row_number_are_preserved(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "source.xlsx"
            book = Workbook()
            sheet = book.active
            sheet.title = "ID_MAP"
            sheet["A3"] = "employee_id"
            sheet["B3"] = "worker_id"
            sheet["A4"] = "E001"
            sheet["B4"] = "EP0001"
            book.save(path)
            book.close()
            with open_xlsx_rows(path, sheet_name="ID_MAP", header_row=3) as opened:
                self.assertEqual([c.value for c in opened.header_cells], ["employee_id", "worker_id"])
                data = next(opened.rows)
                self.assertEqual([c.value for c in data], ["E001", "EP0001"])
            # Calling the shared read_sheet still requires header at row 1.
            with self.assertRaises(InputLayoutError):
                read_sheet(path, ("employee_id", "worker_id"), sheet_name="ID_MAP")

    def test_calamine_input_and_date_compatibility(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "data.xlsx"
            book = Workbook()
            sheet = book.active
            sheet.append(["employee_id", "hire_date", "termination_date", "rate"])
            sheet.append(["E001", date(2026, 11, 14), None, 12.5])
            book.save(path)
            book.close()
            rows = read_sheet(path, ("employee_id", "hire_date"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["_row_number"], 2)
            self.assertEqual(rows[0]["employee_id"], "E001")
            self.assertEqual(rows[0]["hire_date"], datetime(2026, 11, 14))
            self.assertIsNone(rows[0]["termination_date"])
            self.assertEqual(rows[0]["rate"], 12.5)

    def test_cached_formula_does_not_bypass_strict_import(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "formula.xlsx"
            book = Workbook()
            sheet = book.active
            sheet.append(["employee_id", "amount"])
            sheet.append(["E001", "=1+1"])
            book.save(path)
            book.close()
            with self.assertRaisesRegex(InputLayoutError, "formula at row 2"):
                read_sheet(path, ("employee_id", "amount"))

    def test_formula_header_fails_closed(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "formula-header.xlsx"
            book = Workbook()
            book.active.append(["employee_id", "=1+1"])
            book.save(path)
            book.close()
            with self.assertRaisesRegex(InputLayoutError, "formula"):
                read_sheet(path, ("employee_id",))

    def test_strict_reader_rejects_unverified_binary_formula_semantics(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "not-an-xls.xls"
            path.write_bytes(b"synthetic")
            with self.assertRaises(XlsxStreamError):
                with open_xlsx_rows(path, data_only=False):
                    pass


if __name__ == "__main__":
    unittest.main()
