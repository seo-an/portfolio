"""Common standalone module tests; no real HR records or calculator execution."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bhandara.common.module.normalizer.paths import MODULE_DIR, resolve_paths
from bhandara.common.module.normalizer.runner import NormalizerRunError, load_mapping, run_normalizer


ROOT = Path(__file__).resolve().parents[2]


class CommonRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="bhandara-common-standalone-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private"
        self.input = self.root / "common-normalizer" / "input"
        self.input.mkdir(parents=True)
        self.source = self.input / "source.csv"
        self.mapping = self.input / "mapping.json"
        self.source.write_text(
            "staff_number,worked_minutes\nE001,450\nE002,480\n",
            encoding="utf-8",
        )
        self.mapping.write_text(json.dumps({
            "schema_version": "1.0",
            "source_format": "csv",
            "fields": {"employee_id": "staff_number",
                       "minutes": "worked_minutes"},
            "required": ["employee_id"],
        }), encoding="utf-8")

    def _cli(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "run.py"), "bhandara", "common-normalizer",
             "--data-root", str(self.root), *args],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=30,
        )

    def test_module_has_own_real_input_and_output_directories(self):
        self.assertTrue((MODULE_DIR / "input").is_dir())
        self.assertTrue((MODULE_DIR / "output").is_dir())
        self.assertTrue((MODULE_DIR / "input" / ".gitkeep").is_file())
        self.assertTrue((MODULE_DIR / "output" / ".gitkeep").is_file())
        self.assertEqual(
            resolve_paths(run_id="synthetic", source_path=self.source,
                          mapping_path=self.mapping).output,
            MODULE_DIR / "output" / "synthetic",
        )
        selected = resolve_paths(self.root, run_id="synthetic")
        self.assertEqual(selected.source, self.source)
        self.assertEqual(selected.mapping, self.mapping)
        self.assertEqual(
            selected.output, self.root / "common-normalizer" / "output" / "synthetic",
        )
        self.assertFalse(selected.output.exists())

    def test_module_runner_avoids_common_shared_library_imports(self):
        import ast
        for filename in ("runner.py", "paths.py", "user_settings.py"):
            tree = ast.parse((MODULE_DIR / filename).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertFalse(
                        node.module.startswith("bhandara.common."),
                        (filename, node.module),
                    )

    def test_standalone_default_input_and_private_output(self):
        status, paths = run_normalizer(self.root, run_id="common-001")
        self.assertEqual(status, "PASS")
        self.assertEqual(set(paths), {
            "normalizer-result.json", "normalizer-review.json", "normalizer-run.json",
        })
        for path in paths.values():
            self.assertEqual(
                path.parent, self.root / "common-normalizer" / "output" / "common-001"
            )
            self.assertTrue(path.is_file())
        result = json.loads(paths["normalizer-result.json"].read_text())
        self.assertEqual(result["module_id"], "common-normalizer")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["accepted_count"], 2)
        self.assertEqual(
            result["records"][0],
            {"source_row": 2, "values": {"employee_id": "E001", "minutes": "450"}},
        )
        self.assertFalse(result["finalizable"])
        receipt = json.loads(paths["normalizer-run.json"].read_text())
        self.assertEqual(receipt["run_id"], "common-001")
        self.assertEqual(set(receipt["output_sha256"]),
                         {"normalizer-result.json", "normalizer-review.json"})
        self.assertNotIn("normalizer-run.json", receipt["output_sha256"])
        self.assertFalse((self.root / "pto-calculator").exists())
        self.assertFalse((self.root / "payroll-calculator").exists())

    def test_cli_runs_common_and_prints_only_own_artifact_paths(self):
        run = self._cli("--run-id", "c2")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("NORMALIZER_STATUS: PASS", run.stdout)
        self.assertIn("common-normalizer/output/c2/normalizer-result.json", run.stdout)
        self.assertFalse((self.root / "worktime-calculator").exists())

    def test_explicit_external_file_works_without_copy_to_common_input(self):
        external = Path(self.tmp.name) / "external.csv"
        external.write_text(
            "staff_number,worked_minutes\nZ99,60\n", encoding="utf-8"
        )
        status, outputs = run_normalizer(
            self.root, run_id="external", source_path=external,
        )
        self.assertEqual(status, "PASS")
        result = json.loads(outputs["normalizer-result.json"].read_text())
        self.assertEqual(result["records"][0]["values"]["employee_id"], "Z99")
        self.assertEqual(self.source.read_text(encoding="utf-8").splitlines()[1],
                         "E001,450")

    def test_invalid_explicit_input_never_falls_back(self):
        run = self._cli("--source", "missing.csv", "--run-id", "missing")
        self.assertEqual(run.returncode, 2)
        self.assertIn("NORMALIZER_INVALID", run.stderr)
        self.assertFalse(
            (self.root / "common-normalizer" / "output" / "missing").exists()
        )
        self.assertTrue(self.source.exists())

    def test_bad_mapping_fails_before_writing_output(self):
        bad = self.input / "bad.json"
        bad.write_text(json.dumps({
            "schema_version": "1.0", "source_format": "csv",
            "fields": {"employee_id": "unknown_column"},
            "required": ["employee_id"],
        }), encoding="utf-8")
        run = self._cli("--config", str(bad), "--run-id", "invalid")
        self.assertEqual(run.returncode, 2)
        self.assertIn("missing declared source column", run.stderr)
        self.assertFalse((self.root / "common-normalizer/output/invalid").exists())

    def test_rejected_row_blocks_result_without_leaking_source_values_to_review(self):
        self.source.write_text(
            "staff_number,worked_minutes\nE001,450\n,990\n",
            encoding="utf-8",
        )
        status, outputs = run_normalizer(self.root, run_id="review")
        self.assertEqual(status, "BLOCKED")
        result = json.loads(outputs["normalizer-result.json"].read_text())
        self.assertEqual(result["accepted_count"], 1)
        self.assertEqual(result["rejected_count"], 1)
        self.assertFalse(result["approved"])
        review = outputs["normalizer-review.json"].read_text(encoding="utf-8")
        self.assertIn("NORMALIZER_REQUIRED_VALUE_MISSING", review)
        self.assertNotIn("990", review)
        self.assertNotIn("E001", review)

    def test_run_id_is_immutable_and_previous_result_is_unchanged(self):
        _, first = run_normalizer(self.root, run_id="immutable")
        before = first["normalizer-result.json"].read_bytes()
        self.source.write_text(
            "staff_number,worked_minutes\nE099,3\n", encoding="utf-8"
        )
        with self.assertRaises(FileExistsError):
            run_normalizer(self.root, run_id="immutable")
        self.assertEqual(first["normalizer-result.json"].read_bytes(), before)

    def test_json_source_with_declared_field_map(self):
        source = self.input / "raw.json"
        source.write_text(
            json.dumps({"entries": [{"original": " E103 "}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        self.mapping.write_text(json.dumps({
            "schema_version": "1.0", "source_format": "json",
            "records_path": "entries",
            "fields": {"employee_id": "original"},
            "required": ["employee_id"],
        }), encoding="utf-8")
        status, outputs = run_normalizer(self.root, run_id="json", source_path=source)
        self.assertEqual(status, "PASS")
        result = json.loads(outputs["normalizer-result.json"].read_text())
        self.assertEqual(result["records"][0]["values"], {"employee_id": "E103"})

    def test_missing_source_rows_is_explicit_error(self):
        self.source.write_text("staff_number,worked_minutes\n", encoding="utf-8")
        with self.assertRaisesRegex(NormalizerRunError, "no data rows"):
            run_normalizer(self.root, run_id="empty")
        self.assertFalse((self.root / "common-normalizer/output/empty").exists())

    def test_explicit_format_mismatch_fails(self):
        external = self.input / "wrong.json"
        external.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(NormalizerRunError, "source extension"):
            run_normalizer(self.root, run_id="wrong", source_path=external)
        self.assertFalse((self.root / "common-normalizer/output/wrong").exists())

    def test_missing_data_root_or_mixed_calculator_arguments_fails(self):
        run = subprocess.run(
            [sys.executable, str(ROOT / "run.py"), "bhandara", "common-normalizer"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(run.returncode, 2)
        self.assertIn("NORMALIZER_INVALID", run.stderr)
        self.assertEqual(
            self._cli("--period", "2026-07").returncode, 2
        )

    def test_invalid_mapping_required_must_be_declared(self):
        self.mapping.write_text(json.dumps({
            "schema_version": "1.0",
            "source_format": "csv",
            "fields": {"employee_id": "staff_number"},
            "required": ["unknown"],
        }), encoding="utf-8")
        with self.assertRaisesRegex(NormalizerRunError, "required"):
            load_mapping(self.mapping)



    def test_changed_source_during_run_rolls_back_new_outputs(self):
        from unittest.mock import patch
        from bhandara.common.module.normalizer import runner as normalizer_runner

        original = normalizer_runner.transform

        def mutate(rows, mapping):
            accepted, issues = original(rows, mapping)
            self.source.write_text(
                "staff_number,worked_minutes\nCHANGED,2\n", encoding="utf-8"
            )
            return accepted, issues

        with patch.object(normalizer_runner, "transform", side_effect=mutate):
            with self.assertRaisesRegex(NormalizerRunError, "changed during"):
                run_normalizer(self.root, run_id="mutated")
        self.assertFalse((self.root / "common-normalizer/output/mutated").exists())


if __name__ == "__main__":
    unittest.main()
