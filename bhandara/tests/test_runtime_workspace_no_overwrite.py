"""Runtime workspace + Excel no-overwrite contracts (unittest, synthetic only).

No production input is opened, no real HR files or Slack data. Test output lives
exclusively in temporary directories and is never committed.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import importlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook

from bhandara.common.runtime import workspace
from bhandara.common.io.xlsx import read_required_rows
from bhandara.worktime.output_excel import write_worktime_xlsx
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.payroll.output import (
    FILENAME as PAYROLL_FILENAME,
    SCHEMA_VERSION as PAYROLL_SCHEMA,
    SHEET_NAME as PAYROLL_SHEET,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def lie_about_existing_target(target: Path):
    """Simulate target created after an existence check (TOCTOU race)."""
    actual_exists = Path.exists

    def pretend_missing(path: Path):
        if path == target:
            return False
        return actual_exists(path)

    with patch.object(Path, "exists", pretend_missing):
        yield


class WorkspaceTest(unittest.TestCase):
    def test_one_run_attempt_creates_private_guide_folders_even_without_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            with patch.object(workspace, "DATA_ROOT", root):
                # Tool code calls the workspace helper BEFORE loading a
                # private config: a missing configuration cannot hide the
                # directory that tells the user where to place the input.
                modules = [
                    ("paid-time-off", "bhandara.paid-time-off.tool_cli"),
                    ("worktime", "bhandara.worktime.tool_cli"),
                    ("payroll", "bhandara.payroll.tool_cli"),
                    ("workflow", "bhandara.workflow"),
                ]
                for tool, module_name in modules:
                    with self.subTest(tool=tool):
                        module = importlib.import_module(module_name)
                        with self.assertRaises((OSError, ValueError)):
                            module.execute(Path(tmp) / "missing-private-config.json")
                        for directory in (
                            root / "config",
                            root / "input",
                            root / "input" / "common",
                            root / "input" / tool,
                            root / "output",
                            root / "output" / tool,
                        ):
                            self.assertTrue(directory.is_dir(), str(directory))
                        self.assertEqual(list((root / "output" / tool).iterdir()), [])
                self.assertEqual(
                    sorted(p.name for p in (root / "output").iterdir()),
                    ["paid-time-off", "payroll", "workflow", "worktime"],
                )

    def test_repeated_scaffolding_does_not_modify_existing_input_or_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            with patch.object(workspace, "DATA_ROOT", root):
                first = workspace.ensure_tool_workspace("worktime")
                source = first["tool_input"] / "original.xlsx"
                source.write_bytes(b"SYNTHETIC_ORIGINAL_KEEP")
                old = first["tool_output"] / "past-run"
                old.mkdir()
                old_output = old / "worktime-result.xlsx"
                old_output.write_bytes(b"SYNTHETIC_PREVIOUS_RESULT")
                again = workspace.ensure_tool_workspace("worktime")
                self.assertEqual(first, again)
                self.assertEqual(source.read_bytes(), b"SYNTHETIC_ORIGINAL_KEEP")
                self.assertEqual(old_output.read_bytes(), b"SYNTHETIC_PREVIOUS_RESULT")
                self.assertEqual(sorted(x.name for x in first["tool_output"].iterdir()),
                                 ["past-run"])

    def test_readonly_checkout_skips_only_optional_workspace_hints(self):
        # Hermes mounts the source tree (:ro); unlike host mode, it cannot
        # mkdir under bhandara/data. Configured private runs must continue.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            before = sorted(Path(tmp).iterdir())
            with (
                patch.object(workspace, "DATA_ROOT", root),
                patch.object(Path, "mkdir",
                             side_effect=OSError(errno.EROFS, "read-only checkout")),
            ):
                self.assertEqual(workspace.ensure_tool_workspace("worktime"), {})
                self.assertEqual(workspace.ensure_tool_workspace("payroll"), {})
            self.assertEqual(sorted(Path(tmp).iterdir()), before)
            self.assertFalse(root.exists())

    def test_readonly_checkout_does_not_mask_missing_tool_config(self):
        # Verify that each real entrypoint proceeds to config validation, not
        # an EROFS error from an unrelated guide-folder creation.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "readonly-src-data"
            missing = Path(tmp) / "missing-private-config.json"
            modules = (
                ("paid-time-off", "bhandara.paid-time-off.tool_cli"),
                ("worktime", "bhandara.worktime.tool_cli"),
                ("payroll", "bhandara.payroll.tool_cli"),
                ("workflow", "bhandara.workflow"),
            )
            with (
                patch.object(workspace, "DATA_ROOT", root),
                patch.object(Path, "mkdir",
                             side_effect=OSError(errno.EROFS, "read-only checkout")),
            ):
                for tool, name in modules:
                    with self.subTest(tool=tool):
                        module = importlib.import_module(name)
                        with self.assertRaises(ValueError) as caught:
                            module.execute(missing)
                        self.assertNotIn("read-only checkout", str(caught.exception))
            self.assertFalse(root.exists())

    def test_permission_denied_is_not_silently_treated_as_readonly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            with (
                patch.object(workspace, "DATA_ROOT", root),
                patch.object(Path, "mkdir",
                             side_effect=PermissionError(errno.EACCES, "denied")),
            ):
                with self.assertRaises(PermissionError):
                    workspace.ensure_tool_workspace("paid-time-off")

    def test_symlink_and_non_directory_never_redirect_workspace_to_other_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            outside = Path(tmp) / "outside"
            outside.mkdir()
            root.mkdir()
            (root / "input").symlink_to(outside, target_is_directory=True)
            with patch.object(workspace, "DATA_ROOT", root):
                with self.assertRaises(workspace.WorkspaceError):
                    workspace.ensure_tool_workspace("worktime")
            self.assertEqual(list(outside.iterdir()), [])
            (root / "input").unlink()
            (root / "input").write_bytes(b"DO_NOT_REPLACE")
            with patch.object(workspace, "DATA_ROOT", root):
                with self.assertRaises(workspace.WorkspaceError):
                    workspace.ensure_tool_workspace("payroll")
            self.assertEqual((root / "input").read_bytes(), b"DO_NOT_REPLACE")

    def test_unknown_tool_cannot_create_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            with patch.object(workspace, "DATA_ROOT", root):
                with self.assertRaises(workspace.WorkspaceError):
                    workspace.ensure_tool_workspace("untrusted")
                self.assertFalse(root.exists())

    def test_gitignore_excludes_runtime_xlsx_but_not_public_samples(self):
        ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/bhandara/data/**", ignore)
        self.assertIn("/bhandara/worktime/output/**", ignore)
        self.assertIn("/bhandara/payroll/output/**", ignore)
        names = (
            "bhandara/data/input/worktime/employee.xlsx",
            "bhandara/data/output/worktime/worktime-001/worktime-result.xlsx",
            "bhandara/data/output/payroll/payroll-001/payroll-result.xlsx",
            "bhandara/paid-time-off/output/pto-001/deduction-quantity-result.xlsx",
            "bhandara/worktime/output/worktime-result.xlsx",
            "bhandara/payroll/output/payroll-result.xlsx",
            "bhandara/common/module/normalizer/output/run-001/result.xlsx",
        )
        for name in names:
            with self.subTest(name=name):
                checked = subprocess.run(
                    ["git", "check-ignore", "-q", "--no-index", name],
                    cwd=PROJECT_ROOT, capture_output=True, check=False,
                )
                self.assertEqual(checked.returncode, 0, name)
        public_example = subprocess.run(
            ["git", "check-ignore", "-q", "--no-index",
             "bhandara/tests/synthetic-example.xlsx"],
            cwd=PROJECT_ROOT, capture_output=True, check=False,
        )
        self.assertEqual(public_example.returncode, 1)

    def test_copied_json_examples_use_generated_private_paths(self):
        for module in ("paid-time-off", "worktime", "payroll"):
            with self.subTest(module=module):
                path = PROJECT_ROOT / "bhandara" / module / "config.example.json"
                config = json.loads(path.read_text(encoding="utf-8"))
                base = PROJECT_ROOT / "bhandara" / "data" / "config"
                self.assertEqual((base / config["input_root"]).resolve(),
                                 (PROJECT_ROOT / "bhandara/data/input").resolve())
                self.assertEqual((base / config["output_root"]).resolve(),
                                 (PROJECT_ROOT / "bhandara/data/output" / module).resolve())


    def test_workflow_default_output_roots_are_siblings_not_ancestor(self):
        base = PROJECT_ROOT / "bhandara/data/config"
        outputs = {}
        for module in ("paid-time-off", "worktime", "payroll"):
            config = json.loads(
                (PROJECT_ROOT / "bhandara" / module / "config.example.json")
                .read_text(encoding="utf-8")
            )
            outputs[module] = (base / config["output_root"]).resolve()
        self.assertEqual(len(set(outputs.values())), 3)
        payroll_root = outputs["payroll"]
        for name in ("paid-time-off", "worktime"):
            with self.subTest(tool=name):
                self.assertFalse(outputs[name].is_relative_to(payroll_root))
                self.assertFalse(payroll_root.is_relative_to(outputs[name]))
        # The Workflow handoff guard rejects any upstream source under Payroll
        # output_root: the distributed examples must satisfy that contract.


class ExclusiveExcelOutputTest(unittest.TestCase):
    def test_worktime_never_overwrites_when_exists_check_races(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "worktime-result.xlsx"
            target.write_bytes(b"EXISTING_WORKTIME_EXCEL")
            result = {"schema_version": "0.1", "rows": []}
            with lie_about_existing_target(target):
                with self.assertRaises(FileExistsError):
                    write_worktime_xlsx(result, target)
            self.assertEqual(target.read_bytes(), b"EXISTING_WORKTIME_EXCEL")

    def test_payroll_never_overwrites_when_exists_check_races(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / PAYROLL_FILENAME
            target.write_bytes(b"EXISTING_PAYROLL_EXCEL")
            result = {
                "schema_version": PAYROLL_SCHEMA,
                "sheet_name": PAYROLL_SHEET,
                "file_name": PAYROLL_FILENAME,
                "approval_state": "NOT_APPROVED",
                "columns": [{
                    "key": "employee_id", "group": "직원정보", "label": "사번",
                }],
                "rows": [{"employee_id": "SYNTH001"}],
            }
            with lie_about_existing_target(target):
                with self.assertRaises(FileExistsError):
                    write_payroll_result_xlsx(result, target)
            self.assertEqual(target.read_bytes(), b"EXISTING_PAYROLL_EXCEL")

    def test_spreadsheet_reader_does_not_modify_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original.xlsx"
            book = Workbook()
            book.active.append(["employee_id"])
            book.active.append(["SYNTH001"])
            book.save(original)
            book.close()
            before = original.read_bytes()
            rows = read_required_rows(original, required_headers=["employee_id"])
            self.assertEqual(rows.accepted_rows, 1)
            self.assertEqual(original.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
