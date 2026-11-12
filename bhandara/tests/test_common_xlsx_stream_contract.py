"""Pin different Common XLSX reader contracts before PTO/Worktime migration."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from bhandara.common.io.input_layout import InputLayoutError, read_sheet
from bhandara.common.io.tabular import TabularInputError, read_xlsx_rows
from bhandara.common.io.xlsx import read_required_rows
from bhandara.common.io.xlsx_stream import XlsxStreamError, open_xlsx_rows


class CommonXlsxStreamContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bhandara-xlsx-contract-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def workbook(self, filename, rows, *, sheet="DATA"):
        path = self.root / filename
        book = Workbook()
        try:
            active = book.active
            active.title = sheet
            for row in rows:
                active.append(row)
            book.save(path)
        finally:
            book.close()
        return path

    def test_stream_preserves_header_offset_formula_metadata_and_row_position(self):
        path = self.workbook("source.xlsx", [
            ["instructions", None],
            ["worker_id", "amount"],
            [None, None],
            ["W1", "=1+1"],
        ])
        with open_xlsx_rows(
            path, sheet_name="DATA", header_row=2, data_only=False,
        ) as opened:
            self.assertEqual(opened.sheet.title, "DATA")
            self.assertEqual([c.value for c in opened.header_cells],
                             ["worker_id", "amount"])
            rows = list(opened.rows)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1][1].data_type, "f")

        # Payroll source mapping deliberately uses cached values instead.
        parsed = read_xlsx_rows(path, {"sheet": "DATA", "header_row": 2})
        self.assertEqual([number for number, _ in parsed], [4])
        self.assertEqual(parsed[0][1]["worker_id"], "W1")
        self.assertIsNone(parsed[0][1]["amount"])

    def test_shared_layout_keeps_formula_rejection_and_physical_row_numbers(self):
        valid = self.workbook("valid.xlsx", [
            ["worker_id", "amount"],
            [None, None],
            ["W1", 0],
        ])
        self.assertEqual(
            read_sheet(valid, ("worker_id", "amount"), sheet_name="DATA"),
            [{"worker_id": "W1", "amount": 0, "_row_number": 3}],
        )
        formula = self.workbook("formula.xlsx", [
            ["worker_id", "amount"],
            ["W1", "=1+1"],
        ])
        with self.assertRaisesRegex(
            InputLayoutError, "formula.xlsx: formula at row 2 is unsupported",
        ):
            read_sheet(formula, ("worker_id", "amount"))

    def test_header_strictness_remains_reader_specific(self):
        source = self.workbook("extra.xlsx", [
            ["worker_id", "amount", "extra", "extra"],
            ["W1", 10, "a", "b"],
        ])
        # Shared layout rejects duplicate *any* headers.
        with self.assertRaisesRegex(InputLayoutError, "headers must be unique"):
            read_sheet(source, ("worker_id", "amount"))
        with self.assertRaisesRegex(TabularInputError, "source headers"):
            read_xlsx_rows(source, {})
        # Common's validation reader accepts duplicate *unrelated* headers.
        result = read_required_rows(
            source, required_headers=("worker_id", "amount"),
        )
        self.assertEqual(result.accepted_rows, 1)
        self.assertEqual(result.rows[0].row_number, 2)

    def test_worksheet_and_header_error_types_remain_stable(self):
        source = self.workbook("source.xlsx", [
            ["worker_id", "amount"],
            ["W1", 5],
        ])
        with self.assertRaisesRegex(InputLayoutError,
                                    "source.xlsx: missing sheet UNKNOWN"):
            read_sheet(source, ("worker_id",), sheet_name="UNKNOWN")
        with self.assertRaisesRegex(TabularInputError,
                                    "worksheet not found: UNKNOWN"):
            read_xlsx_rows(source, {"sheet": "UNKNOWN"})
        with self.assertRaisesRegex(XlsxStreamError,
                                    "header_row must be a positive integer"):
            with open_xlsx_rows(source, header_row=True):
                pass


if __name__ == "__main__":
    unittest.main()
