"""Pin Common required-row XLSX validation while reusing the shared stream.

Synthetic data only: no Gearbox, cloud access, employee records or approvals.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from bhandara.common.contracts.findings import Scope
from bhandara.common.io.xlsx import SpreadsheetInputError, read_required_rows
from bhandara.common.utils.hashing import sha256_file


class CommonXlsxValidationStreamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bhandara-xlsx-validate-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def workbook(self, filename, rows, *, sheet="DATA"):
        path = self.root / filename
        book = Workbook()
        try:
            book.active.title = sheet
            for row in rows:
                book.active.append(row)
            book.save(path)
        finally:
            book.close()
        return path

    def test_individual_bad_rows_do_not_erase_good_rows_or_lineage(self):
        path = self.workbook("mixed.xlsx", [
            ["worker_id", "amount", None, "other", "other"],
            ["W1", 0, "ignored", 1, 2],
            [None, None, None, None, None],
            ["W2", None, None, None, None],
            ["W3", "=1+1", None, None, None],
            ["W4", 20, None, None, None],
        ])
        result = read_required_rows(
            path, required_headers=("worker_id", "amount"), sheet_name="DATA",
        )
        self.assertEqual(result.sheet, "DATA")
        self.assertEqual(result.source, "mixed.xlsx")
        self.assertEqual(result.source_sha256, sha256_file(path))
        self.assertEqual(result.nonempty_rows, 4)
        self.assertEqual(result.rejected_rows, 2)
        self.assertEqual(result.accepted_rows, 2)
        self.assertEqual(
            [(r.row_number, r.values) for r in result.rows],
            [(2, {"worker_id": "W1", "amount": 0}),
             (6, {"worker_id": "W4", "amount": 20})],
        )
        self.assertEqual(
            {(f.code, f.row_number, f.field, f.source, f.sheet) for f in result.findings},
            {("REQUIRED_CELL_MISSING", 4, "amount", "mixed.xlsx", "DATA"),
             ("FORMULA_UNSUPPORTED", 5, "amount", "mixed.xlsx", "DATA")},
        )
        self.assertTrue(all(f.scope == Scope.CELL for f in result.findings))

    def test_header_row_offset_and_selected_sheet(self):
        path = self.workbook("offset.xlsx", [
            ["instructions", None],
            ["worker_id", "approved"],
            ["W1", False],
            ["W2", True],
        ])
        result = read_required_rows(
            path, required_headers=("worker_id", "approved"),
            sheet_name="DATA", header_row=2,
        )
        self.assertEqual(
            [(r.row_number, r.values["approved"]) for r in result.rows],
            [(3, False), (4, True)],
        )
        self.assertEqual(result.rejected_rows, 0)
        self.assertEqual(result.findings, ())

    def test_only_required_headers_need_to_be_unique(self):
        extras = self.workbook("extra.xlsx", [
            ["worker_id", "amount", "", "duplicate", "duplicate"],
            ["W1", 1, None, 2, 3],
        ])
        self.assertEqual(read_required_rows(
            extras, required_headers=("worker_id", "amount"),
        ).accepted_rows, 1)
        duplicate = self.workbook("duplicate.xlsx", [
            ["worker_id", "worker_id", "amount"],
            ["W1", "W1", 2],
        ])
        with self.assertRaisesRegex(
            SpreadsheetInputError, "DATA: ambiguous duplicate required header: worker_id",
        ):
            read_required_rows(
                duplicate, required_headers=("worker_id", "amount"),
            )
        with self.assertRaisesRegex(
            SpreadsheetInputError, "DATA: missing required header: unknown",
        ):
            read_required_rows(extras, required_headers=("unknown",))

    def test_formula_in_unselected_extra_column_is_ignored(self):
        path = self.workbook("extra-formula.xlsx", [
            ["worker_id", "amount", "other"],
            ["W1", 1, "=2+2"],
        ])
        result = read_required_rows(
            path, required_headers=("worker_id", "amount"),
        )
        self.assertEqual(result.accepted_rows, 1)
        self.assertEqual(result.rejected_rows, 0)
        self.assertEqual(result.findings, ())

    def test_no_populated_rows_records_run_finding(self):
        path = self.workbook("blank.xlsx", [
            ["worker_id", "amount"], [None, None],
        ])
        result = read_required_rows(
            path, required_headers=("worker_id", "amount"),
        )
        self.assertEqual(result.accepted_rows, 0)
        self.assertEqual(result.nonempty_rows, 0)
        self.assertEqual(result.rejected_rows, 0)
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].code, "NO_DATA_ROWS")
        self.assertEqual(result.findings[0].scope, Scope.RUN)

    def test_existing_input_validation_and_error_messages_remain(self):
        path = self.workbook("source.xlsx", [
            ["worker_id", "amount"], ["W1", 20],
        ])
        with self.assertRaisesRegex(
            SpreadsheetInputError, "worksheet not found: ABSENT",
        ):
            read_required_rows(
                path, required_headers=("worker_id",), sheet_name="ABSENT",
            )
        with self.assertRaisesRegex(
            SpreadsheetInputError, "header_row must be 1 or greater",
        ):
            read_required_rows(
                path, required_headers=("worker_id",), header_row=0,
            )
        with self.assertRaisesRegex(
            SpreadsheetInputError, "only XLSX/XLSM input is supported",
        ):
            read_required_rows(
                self.root / "source.csv", required_headers=("worker_id",),
            )
        with self.assertRaisesRegex(
            SpreadsheetInputError, "Excel input is not a file: missing.xlsx",
        ):
            read_required_rows(
                self.root / "missing.xlsx", required_headers=("worker_id",),
            )
        corrupted = self.root / "bad.xlsx"
        corrupted.write_bytes(b"not an Excel ZIP")
        with self.assertRaisesRegex(
            SpreadsheetInputError, "could not open workbook bad.xlsx: BadZipFile",
        ):
            read_required_rows(corrupted, required_headers=("worker_id",))

    def test_modified_source_is_still_a_run_wide_error(self):
        path = self.workbook("changed.xlsx", [
            ["worker_id", "amount"], ["W1", 10],
        ])
        with patch(
            "bhandara.common.io.xlsx.sha256_file",
            side_effect=["before", "after"],
        ):
            with self.assertRaisesRegex(
                SpreadsheetInputError,
                "workbook changed during read; restart with stable input",
            ):
                read_required_rows(
                    path, required_headers=("worker_id", "amount"),
                )


if __name__ == "__main__":
    unittest.main()
