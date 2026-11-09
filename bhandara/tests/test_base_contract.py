"""Synthetic-only Bhandara Base validation tests; never run against real HR data."""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bhandara.common.contracts.findings import Finding, RunStatus, Scope, Severity, summarize_status
from bhandara.common.io.xlsx import SpreadsheetInputError, read_required_rows
from bhandara.common.runtime.artifacts import ArtifactBatch, ArtifactError
from bhandara.common.runtime.receipt import build_receipt
from bhandara.common.utils.hashing import sha256_file
from bhandara.common.validation.headers import HeaderContractError, parse_headers


class BaseTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def workbook(self, rows, *, sheet="Employees"):
        path = self.root / "synthetic.xlsx"
        book = Workbook()
        page = book.active
        page.title = sheet
        for row in rows:
            page.append(row)
        book.save(path)
        book.close()
        return path

    def test_header_allows_unrelated_duplicate_and_blank_extras(self):
        matched = parse_headers(["note", None, " id ", "note", "salary"], ["id", "salary"])
        self.assertEqual(matched.positions, (2, 4))
        self.assertEqual(matched.project([1, 2, "E001", 4, 300]), {"id": "E001", "salary": 300})

    def test_missing_required_header_raises(self):
        with self.assertRaisesRegex(HeaderContractError, "missing required header"):
            parse_headers(["name"], ["name", "id"])

    def test_ambiguous_required_header_raises(self):
        with self.assertRaisesRegex(HeaderContractError, "ambiguous duplicate"):
            parse_headers(["id", "id"], ["id"])

    def test_invalid_contract_raises(self):
        with self.assertRaises(HeaderContractError):
            parse_headers(["id"], ["id", "id"])

    def test_excel_invalid_rows_isolated_and_source_preserved(self):
        source = self.workbook([
            ["id", "pay", "other", "other"],
            ["E001", 0, "junk", "junk"],
            ["E002", None, "note", "note"],
            ["E003", 19, None, None],
            [None, None, None, None],
            [None, 22, "note", None],
        ])
        old_sha = sha256_file(source)
        result = read_required_rows(source, required_headers=("id", "pay"))
        self.assertEqual(result.accepted_rows, 2)
        self.assertEqual(result.rejected_rows, 2)
        self.assertEqual(result.nonempty_rows, 4)
        self.assertEqual([r.row_number for r in result.rows], [2, 4])
        self.assertEqual([r.values for r in result.rows], [
            {"id": "E001", "pay": 0}, {"id": "E003", "pay": 19},
        ])
        self.assertEqual([f.row_number for f in result.findings], [3, 6])
        self.assertEqual({f.code for f in result.findings}, {"REQUIRED_CELL_MISSING"})
        self.assertEqual(sha256_file(source), old_sha)
        self.assertEqual(result.source_sha256, old_sha)

    def test_excel_formula_is_not_silently_evaluated(self):
        source = self.workbook([["id", "amount"], ["E001", "=1+2"], ["E002", 5]])
        result = read_required_rows(source, required_headers=("id", "amount"))
        self.assertEqual(result.accepted_rows, 1)
        self.assertEqual(result.rows[0].values["amount"], 5)
        self.assertIn("FORMULA_UNSUPPORTED", [x.code for x in result.findings])

    def test_excel_zero_and_false_not_missing(self):
        source = self.workbook([["id", "flag"], [0, False]])
        result = read_required_rows(source, required_headers=("id", "flag"))
        self.assertEqual(result.accepted_rows, 1)
        self.assertEqual(result.findings, ())

    def test_excel_duplicate_required_header_is_sheet_failure(self):
        source = self.workbook([["id", "id"], ["one", "two"]])
        with self.assertRaisesRegex(SpreadsheetInputError, "ambiguous duplicate"):
            read_required_rows(source, required_headers=("id",))

    def test_excel_missing_sheet_is_failure(self):
        source = self.workbook([["id"], ["E001"]])
        with self.assertRaisesRegex(SpreadsheetInputError, "worksheet not found"):
            read_required_rows(source, required_headers=("id",), sheet_name="Missing")

    def test_excel_custom_header_row(self):
        source = self.workbook([["header title"], ["id"], ["E001"]])
        result = read_required_rows(source, required_headers=("id",), header_row=2)
        self.assertEqual(result.rows[0].row_number, 3)

    def test_excel_empty_sheet_cannot_be_marked_pass(self):
        source = self.workbook([["id", "amount"]])
        result = read_required_rows(source, required_headers=("id", "amount"))
        self.assertEqual(result.status, RunStatus.ERROR)
        self.assertEqual(result.accepted_rows, 0)
        self.assertIn("NO_DATA_ROWS", [issue.code for issue in result.findings])

    def test_excel_invalid_file_fails_without_misreporting(self):
        source = self.root / "bad.xlsx"
        source.write_bytes(b"not an xlsx")
        with self.assertRaises(SpreadsheetInputError):
            read_required_rows(source, required_headers=("id",))

    def test_finding_status_and_serialization(self):
        issue = Finding(code="MISSING", severity=Severity.ERROR, scope=Scope.ROW,
                        message="required", source="example.xlsx", row_number=2)
        self.assertEqual(issue.to_dict()["severity"], "ERROR")
        self.assertEqual(summarize_status([]), RunStatus.PASS)
        review = Finding(code="UNCERTAIN", severity=Severity.REVIEW, scope=Scope.RUN,
                         message="review")
        self.assertEqual(summarize_status([review]), RunStatus.REVIEW_REQUIRED)
        self.assertEqual(summarize_status([review, issue]), RunStatus.ERROR)
        with self.assertRaises(ValueError):
            Finding(code="oops", severity="WARN", scope=Scope.RUN, message="bad")

    def test_collision_suffix_applies_to_entire_batch(self):
        output = self.root / "out"
        output.mkdir()
        existing = output / "result.xlsx"
        existing.write_bytes(b"original")
        with ArtifactBatch(output, ["result.xlsx", "review.json"]) as batch:
            self.assertEqual(batch.suffix_number, 1)
            batch.write_bytes("result.xlsx", b"new workbook")
            batch.write_json("review.json", {"status": "REVIEW_REQUIRED"})
            paths = batch.commit()
        self.assertEqual(existing.read_bytes(), b"original")
        self.assertEqual(paths["result.xlsx"].name, "result(1).xlsx")
        self.assertEqual(paths["review.json"].name, "review(1).json")
        self.assertEqual(json.loads(paths["review.json"].read_text())["status"], "REVIEW_REQUIRED")

    def test_second_collision_uses_suffix_two_for_all(self):
        out = self.root / "out"
        with ArtifactBatch(out, ["a.json", "b.json"]) as first:
            first.write_json("a.json", {"n": 1})
            first.write_json("b.json", {"n": 1})
            first.commit()
        with ArtifactBatch(out, ["a.json", "b.json"]) as second:
            second.write_json("a.json", {"n": 2})
            second.write_json("b.json", {"n": 2})
            second.commit()
        with ArtifactBatch(out, ["a.json", "b.json"]) as third:
            self.assertEqual(third.suffix_number, 2)
            third.write_json("a.json", {"n": 3})
            third.write_json("b.json", {"n": 3})
            third.commit()
        self.assertEqual(sorted(x.name for x in out.iterdir()),
                         ["a(1).json", "a(2).json", "a.json", "b(1).json", "b(2).json", "b.json"])

    def test_exception_rolls_back_reservation_and_staging(self):
        out = self.root / "out"
        with self.assertRaisesRegex(RuntimeError, "forced"):
            with ArtifactBatch(out, ["one.json", "two.json"]) as batch:
                batch.write_json("one.json", {"x": 1})
                raise RuntimeError("forced")
        self.assertEqual(list(out.iterdir()), [])

    def test_partial_publish_failure_rolls_back_batch_only(self):
        out = self.root / "out"
        out.mkdir()
        existing = out / "untouched.json"
        existing.write_bytes(b"original")
        real_replace = os.replace
        called = 0

        def fail_second_replace(src, dst):
            nonlocal called
            called += 1
            if called == 2:
                raise OSError("synthetic publication failure")
            return real_replace(src, dst)

        with self.assertRaisesRegex(OSError, "synthetic publication failure"):
            with ArtifactBatch(out, ["a.json", "b.json"]) as batch:
                batch.write_json("a.json", {"secret": 1})
                batch.write_json("b.json", {"secret": 2})
                with patch("bhandara.common.runtime.artifacts.os.replace", fail_second_replace):
                    batch.commit()
        self.assertEqual([p.name for p in out.iterdir()], ["untouched.json"])
        self.assertEqual(existing.read_bytes(), b"original")

    def test_unstaged_files_cannot_be_published(self):
        out = self.root / "out"
        with ArtifactBatch(out, ["one.json", "two.json"]) as batch:
            batch.write_json("one.json", {"x": 1})
            with self.assertRaises(ArtifactError):
                batch.commit()
        self.assertEqual(list(out.iterdir()), [])

    def test_duplicate_or_traversing_filenames_rejected(self):
        for name in ("../other.json", "x/y.json", "\\x.json", ".hidden", ""):
            with self.subTest(name=name), self.assertRaises(ArtifactError):
                ArtifactBatch(self.root / "out", [name])
        with self.assertRaises(ArtifactError):
            ArtifactBatch(self.root / "out", ["a", "a"])

    def test_staged_hashes_and_receipt(self):
        source = self.workbook([["id"], ["E001"]])
        with ArtifactBatch(self.root / "out", ["result.json", "receipt.json"]) as batch:
            batch.write_json("result.json", {"amount": Decimal("1.20")})
            hashes = batch.staged_hashes()
            self.assertEqual(len(hashes["result.json"]), 64)
            issues = [Finding(code="REVIEW", severity=Severity.REVIEW, scope=Scope.RUN,
                              message="manual approval required")]
            receipt = build_receipt(module_id="pto-calculator", module_version="0.1.0",
                                    input_files={"source": source}, output_sha256=hashes,
                                    findings=issues, run_id="synthetic-id", recorded_at="synthetic-time")
            batch.write_json("receipt.json", receipt)
            paths = batch.commit()
        parsed = json.loads(paths["receipt.json"].read_text(encoding="utf-8"))
        self.assertEqual(parsed["status"], "REVIEW_REQUIRED")
        self.assertEqual(parsed["approved"], False)
        self.assertEqual(parsed["finalizable"], False)
        self.assertEqual(parsed["input_sha256"]["source"], sha256_file(source))
        self.assertEqual(parsed["output_sha256"]["result.json"], sha256_file(paths["result.json"]))
        self.assertEqual(json.loads(paths["result.json"].read_text())["amount"], "1.20")

    def test_concurrent_reservations_do_not_overwrite(self):
        out = self.root / "out"
        barrier = threading.Barrier(4)
        results = []
        errors = []

        def write_run(number):
            try:
                barrier.wait(timeout=5)
                with ArtifactBatch(out, ["a.json", "b.json"]) as batch:
                    batch.write_json("a.json", {"number": number})
                    batch.write_json("b.json", {"number": number})
                    results.append(batch.commit())
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=write_run, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(errors)
        self.assertEqual(len(results), 4)
        self.assertEqual(len({paths["a.json"].name for paths in results}), 4)
        for paths in results:
            a = json.loads(paths["a.json"].read_text())
            b = json.loads(paths["b.json"].read_text())
            self.assertEqual(a, b)

    def test_copy_file_does_not_mutate_source(self):
        input_file = self.root / "original.bin"
        input_file.write_bytes(b"protected-source")
        before = sha256_file(input_file)
        with ArtifactBatch(self.root / "out", ["copy.bin"]) as batch:
            batch.copy_file("copy.bin", input_file)
            paths = batch.commit()
        self.assertEqual(paths["copy.bin"].read_bytes(), b"protected-source")
        self.assertEqual(sha256_file(input_file), before)

    def test_permissions_private_on_posix(self):
        if os.name != "posix":
            self.skipTest("POSIX file modes")
        with ArtifactBatch(self.root / "out", ["result.json"]) as batch:
            batch.write_json("result.json", {})
            paths = batch.commit()
        self.assertEqual(stat.S_IMODE(paths["result.json"].stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
