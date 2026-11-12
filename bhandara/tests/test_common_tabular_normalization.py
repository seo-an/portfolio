"""Regression for common, company-agnostic structural input normalization."""
from __future__ import annotations

import ast
import hashlib
import importlib
import json
import tempfile
import unittest
from datetime import date, datetime, time
from pathlib import Path

from openpyxl import Workbook

from bhandara.common.io.tabular import (
    MISSING,
    TabularInputError,
    column_names,
    is_blank_value,
    lookup_field,
    read_csv_rows,
    read_json_rows,
    read_xlsx_rows,
    resolve_source_path,
)
from bhandara.common.validation.scalars import (
    UnsupportedScalarType,
    convert_scalar,
)

ROOT = Path(__file__).resolve().parents[2]


class CommonTabularNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bhandara-common-input-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_exact_dotted_header_precedes_nested_json_path(self):
        row = {
            "record.code": "literal",
            "record": {"code": "nested"},
            "nested": [{"code": "first"}],
        }
        self.assertEqual(lookup_field(row, "record.code"), "literal")
        self.assertEqual(lookup_field(row, "nested.0.code"), "first")
        self.assertIs(lookup_field(row, "nested.2.code"), MISSING)
        self.assertIs(lookup_field(row, "not_present"), MISSING)

    def test_blank_value_preserves_zero_and_false(self):
        self.assertTrue(is_blank_value(MISSING))
        self.assertTrue(is_blank_value(None))
        self.assertTrue(is_blank_value("  "))
        self.assertFalse(is_blank_value(0))
        self.assertFalse(is_blank_value(False))
        self.assertFalse(is_blank_value("0"))

    def test_header_contract_and_relative_path_containment(self):
        self.assertEqual(column_names([" worker_id ", "hours"]), ["worker_id", "hours"])
        for bad in (["a", " a "], ["", "a"], []):
            with self.subTest(headers=bad), self.assertRaises(TabularInputError):
                column_names(bad)
        source = self.root / "raw.csv"
        source.write_text("a\n1\n", encoding="utf-8")
        self.assertEqual(resolve_source_path(self.root, "raw.csv"), source)
        with self.assertRaisesRegex(TabularInputError, "input directory"):
            resolve_source_path(self.root, "../untrusted.csv")
        with self.assertRaisesRegex(TabularInputError, "source.path"):
            resolve_source_path(self.root, "")

    def test_csv_multiline_line_numbers_and_represented_empty_record(self):
        source = self.root / "raw.csv"
        source.write_text('worker,description\nW1,"first\nsecond"\n\n,""\n',
                          encoding="utf-8")
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        rows = read_csv_rows(source, {})
        self.assertEqual(rows, [
            (2, {"worker": "W1", "description": "first\nsecond"}),
            (5, {"worker": "", "description": ""}),
        ])
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)

    def test_csv_rejects_misaligned_columns_or_invalid_delimiter(self):
        path = self.root / "bad.csv"
        path.write_text("a,b\none\n", encoding="utf-8")
        with self.assertRaisesRegex(TabularInputError, "column count mismatch"):
            read_csv_rows(path, {})
        with self.assertRaisesRegex(TabularInputError, "single character"):
            read_csv_rows(path, {"delimiter": "||"})

    def test_json_rows_path_is_explicit_and_every_record_is_an_object(self):
        path = self.root / "input.json"
        path.write_text(
            json.dumps({"response": {"items": [{"id": "W1"}, {"id": "W2"}]}}),
            encoding="utf-8",
        )
        self.assertEqual(
            read_json_rows(path, {"records_path": "response.items"}),
            [(1, {"id": "W1"}), (2, {"id": "W2"})],
        )
        with self.assertRaisesRegex(TabularInputError, "select a list"):
            read_json_rows(path, {"records_path": "missing"})
        path.write_text(json.dumps([{"id": "W1"}, "bad"]), encoding="utf-8")
        with self.assertRaisesRegex(TabularInputError, "row 2"):
            read_json_rows(path, {})

    def test_xlsx_sheet_header_row_and_cell_types_preserved(self):
        file = self.root / "input.xlsx"
        book = Workbook()
        try:
            book.active.title = "Unused"
            sheet = book.create_sheet("RAW")
            sheet.append(["explanatory note"])
            sheet.append(["worker_id", "work_day", "amount"])
            sheet.append(["W1", date(2026, 11, 12), 0])
            sheet.append([None, None, None])
            sheet.append(["W2", date(2026, 11, 13), 150])
            book.save(file)
        finally:
            book.close()
        checksum = hashlib.sha256(file.read_bytes()).hexdigest()
        rows = read_xlsx_rows(file, {"sheet": "RAW", "header_row": 2})
        self.assertEqual([number for number, _ in rows], [3, 5])
        self.assertEqual(rows[0][1]["worker_id"], "W1")
        self.assertEqual(rows[0][1]["amount"], 0)
        self.assertEqual(rows[0][1]["work_day"], datetime(2026, 11, 12))
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), checksum)
        with self.assertRaisesRegex(TabularInputError, "positive integer"):
            read_xlsx_rows(file, {"header_row": True})
        with self.assertRaisesRegex(TabularInputError, "worksheet not found"):
            read_xlsx_rows(file, {"sheet": "Absent"})

    def test_scalar_coercion_matches_existing_source_mapping_contract(self):
        cases = (
            ("  W1  ", "str", None, "W1"),
            ("2026/11/12", "date", "%Y/%m/%d", "2026-11-12"),
            (date(2026, 11, 12), "date", None, "2026-11-12"),
            ("08:15", "time", None, "08:15"),
            (time(8, 15), "time", None, "08:15"),
            ("2026-11-12T08:15", "datetime", None, "2026-11-12T08:15"),
            ("1,234.50", "decimal", None, "1234.50"),
            ("2.0", "int", None, 2),
            ("YES", "bool", None, True),
            ("false", "bool", None, False),
            (False, "bool", None, False),
        )
        for value, kind, fmt, expected in cases:
            with self.subTest(value=value, kind=kind):
                self.assertEqual(convert_scalar(value, kind=kind, fmt=fmt), expected)

    def test_scalar_conversion_rejects_unsafe_or_ambiguous_values(self):
        samples = (
            (True, "decimal"),
            (False, "int"),
            ("NaN", "decimal"),
            ("Infinity", "decimal"),
            ("1.2", "int"),
            ("08:15:01", "time"),
            ("2026-11-12T08:15:03", "datetime"),
            ("sometimes", "bool"),
        )
        for value, kind in samples:
            with self.subTest(value=value, kind=kind), self.assertRaises(ValueError):
                convert_scalar(value, kind=kind)
        with self.assertRaises(UnsupportedScalarType):
            convert_scalar("x", kind="arbitrary_script")

    def test_payroll_mapping_still_preserves_explicit_alias_values_and_rejects(self):
        mapper = importlib.import_module(
            "bhandara.payroll-calculator.functions.source_mapping"
        )
        raw = self.root / "source.csv"
        raw.write_text(
            "worker,company_pay_code,qty\n"
            "W1,OVERTIME,1\n"
            "W2,UNSUPPORTED,2\n",
            encoding="utf-8",
        )
        spec = {
            "path": "source.csv",
            "format": "csv",
            "fields": {
                "worker_id": {"source": "worker", "required": True},
                "pay_item_code": {
                    "source": "company_pay_code",
                    "required": True,
                    "value_map": {"OVERTIME": "overtime_hours"},
                },
                "quantity": {"source": "qty", "required": True, "type": "int"},
            },
            "unique_by": ["worker_id"],
        }
        result = mapper.normalize_source("payroll_input", spec, input_dir=self.root)
        self.assertEqual(result["total_rows"], 2)
        self.assertEqual(result["accepted_rows"], 1)
        self.assertEqual(result["rejected_rows"], 1)
        self.assertEqual(result["rows"][0], {
            "worker_id": "W1", "pay_item_code": "overtime_hours", "quantity": 1,
        })
        self.assertEqual([entry["status"] for entry in result["lineage"]],
                         ["ACCEPTED", "REJECTED"])
        self.assertEqual(result["lineage"][1]["issue_codes"],
                         ["SOURCE_VALUE_INVALID"])
        self.assertEqual(result["source_sha256"],
                         hashlib.sha256(raw.read_bytes()).hexdigest())
        self.assertEqual(result["lineage"][0]["selected_columns"],
                         {"worker_id": "worker",
                          "pay_item_code": "company_pay_code", "quantity": "qty"})

    def test_public_mapper_keeps_its_existing_error_type(self):
        mapper = importlib.import_module(
            "bhandara.payroll-calculator.functions.source_mapping"
        )
        (self.root / "bad.csv").write_text("a,b\nvalue\n", encoding="utf-8")
        with self.assertRaises(mapper.SourceMappingError):
            mapper.normalize_source("employees", {
                "path": "bad.csv",
                "fields": {"worker_id": {"source": "a", "required": True}},
            }, input_dir=self.root)

    def test_common_modules_have_no_calculator_or_gearbox_imports(self):
        for path in (
            ROOT / "bhandara/common/io/tabular.py",
            ROOT / "bhandara/common/validation/scalars.py",
        ):
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        prefix = node.module or ""
                        self.assertFalse(prefix.startswith(("gearbox", "bhandara.payroll-calculator", "bhandara.worktime-calculator", "bhandara.pto-calculator")))
                    elif isinstance(node, ast.Import):
                        self.assertFalse(any(alias.name.startswith(("gearbox", "bhandara.payroll-calculator", "bhandara.worktime-calculator", "bhandara.pto-calculator")) for alias in node.names))


if __name__ == "__main__":
    unittest.main()
