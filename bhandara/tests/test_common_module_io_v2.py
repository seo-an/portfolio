"""Common module-local IO v2 contract: synthetic paths and public manifests only."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from bhandara.common.io.module_io import (
    ModuleIOError, load_module_io_contract, output_directory, output_file,
    resolve_input,
)


ROOT = Path(__file__).resolve().parents[1]
MODULES = ("pto-calculator", "worktime-calculator", "payroll-calculator")


class ModuleIOContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="bhandara-module-io-v2-")
        self.addCleanup(self.tmp.cleanup)
        self.private = Path(self.tmp.name) / "private"

    def _contract(self, name="pto-calculator"):
        return load_module_io_contract(name)

    def _write_default(self, contract, role, content=b"synthetic"):
        filename = contract.input_roles[role]
        path = self.private / contract.module_id / "input" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_all_three_read_only_their_own_declarations(self):
        for name in MODULES:
            with self.subTest(module=name):
                contract = self._contract(name)
                original = json.loads(
                    (ROOT / name / "module.json").read_text(encoding="utf-8")
                )
                self.assertEqual(contract.module_id, name)
                self.assertEqual(contract.module_version, original["module_version"])
                self.assertEqual(contract.input_roles["employees"], "common/employee.xlsx")
                self.assertIn("schedule" if name != "payroll-calculator"
                              else "worktime_result", contract.input_roles)
                self.assertTrue(contract.output_files)
                self.assertEqual(contract.module_version, {
                    "pto-calculator": "0.2.1",
                    "worktime-calculator": "0.6.0",
                    "payroll-calculator": "0.3.3",
                }[name])

    def test_each_default_is_anchored_inside_its_own_module(self):
        files = []
        for name in MODULES:
            contract = self._contract(name)
            expected = self._write_default(contract, "employees")
            result = resolve_input(contract, self.private, "employees")
            self.assertEqual(result.source, "default")
            self.assertEqual(result.role, "employees")
            self.assertEqual(result.path, expected)
            files.append(result.path)
        self.assertEqual(len(set(files)), 3)

    def test_absolute_explicit_handoff_does_not_copy_or_run_predecessor(self):
        worktime = self._contract("worktime-calculator")
        payroll = self._contract("payroll-calculator")
        predecessor_result = output_file(
            worktime, self.private, "work-2026-07", "worktime-result.json"
        )
        predecessor_result.parent.mkdir(parents=True, exist_ok=True)
        predecessor_result.write_text('{"status":"REVIEW_REQUIRED"}', encoding="utf-8")
        selected = resolve_input(
            payroll, self.private, "worktime_result",
            explicit_path=predecessor_result,
        )
        self.assertEqual(selected.source, "explicit")
        self.assertEqual(selected.path, predecessor_result)
        self.assertFalse(
            (self.private / "payroll-calculator" / "input" / "payroll"
             / "worktime-result.json").exists()
        )

    def test_relative_explicit_is_inside_own_input(self):
        contract = self._contract()
        chosen = self.private / contract.module_id / "input" / "user" / "person.xlsx"
        chosen.parent.mkdir(parents=True)
        chosen.write_bytes(b"fixture")
        resolved = resolve_input(
            contract, self.private, "employees", explicit_path="user/person.xlsx"
        )
        self.assertEqual(resolved.path, chosen)
        self.assertEqual(resolved.source, "explicit")

    def test_missing_explicit_never_falls_back_to_existing_default(self):
        contract = self._contract()
        default = self._write_default(contract, "employees")
        for invalid in ("missing.xlsx", "../other.xlsx", "", "/not-real/path.xlsx"):
            with self.subTest(explicit=invalid):
                with self.assertRaises(ModuleIOError):
                    resolve_input(
                        contract, self.private, "employees", explicit_path=invalid
                    )
        self.assertTrue(default.is_file())

    def test_unprovided_role_uses_only_its_declared_default(self):
        contract = self._contract()
        with self.assertRaisesRegex(ModuleIOError, "default input file not found"):
            resolve_input(contract, self.private, "employees")
        with self.assertRaisesRegex(ModuleIOError, "unknown input role"):
            resolve_input(contract, self.private, "nonexistent")

    def test_output_paths_are_module_owned_and_run_specific(self):
        for name in MODULES:
            with self.subTest(name=name):
                contract = self._contract(name)
                first = output_directory(contract, self.private, "run-A")
                second = output_directory(contract, self.private, "run-B")
                self.assertEqual(
                    first, self.private / name / "output" / "run-A"
                )
                self.assertNotEqual(first, second)
                self.assertFalse(first.exists())
                self.assertFalse(second.exists())

    def test_only_declared_outputs_allowed(self):
        for name, filename in (
            ("pto-calculator", "pto-result.json"),
            ("worktime-calculator", "worktime-result.json"),
            ("payroll-calculator", "payroll-calculation.json"),
        ):
            with self.subTest(module=name):
                contract = self._contract(name)
                expected = output_directory(contract, self.private, "abc") / filename
                self.assertEqual(
                    output_file(contract, self.private, "abc", filename), expected
                )
                with self.assertRaisesRegex(ModuleIOError, "undeclared"):
                    output_file(contract, self.private, "abc", "secret.xlsx")

    def test_run_id_rejects_implicit_latest_and_traversal(self):
        contract = self._contract()
        for invalid in ("", "../x", "a/b", ".hidden", "x y", "x" * 129, None):
            with self.subTest(run_id=invalid):
                with self.assertRaises(ModuleIOError):
                    output_directory(contract, self.private, invalid)
        # 'latest' is a plain caller-chosen ID, not an auto-resolution rule.
        self.assertEqual(
            output_directory(contract, self.private, "latest").name, "latest"
        )

    def test_symlinked_default_input_must_not_escape_workspace(self):
        contract = self._contract()
        default = self._write_default(contract, "employees")
        external = Path(self.tmp.name) / "outside.xlsx"
        external.write_bytes(b"external")
        default.unlink()
        default.symlink_to(external)
        with self.assertRaisesRegex(ModuleIOError, "escapes"):
            resolve_input(contract, self.private, "employees")

    def test_symlinked_output_root_rejected(self):
        contract = self._contract()
        module = self.private / contract.module_id
        module.mkdir(parents=True)
        external = Path(self.tmp.name) / "elsewhere"
        external.mkdir()
        (module / "output").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ModuleIOError, "symlink"):
            output_directory(contract, self.private, "abc")

    def test_no_other_calculator_needs_to_be_installed(self):
        contract = self._contract("payroll-calculator")
        single = Path(self.tmp.name) / "single"
        module = single / "payroll-calculator"
        module.mkdir(parents=True)
        shutil.copy2(ROOT / "payroll-calculator" / "module.json",
                     module / "module.json")
        isolated = load_module_io_contract(
            "payroll-calculator", bhandara_root=single
        )
        self.assertEqual(isolated.input_roles, contract.input_roles)
        self.assertFalse((single / "worktime-calculator").exists())

    def test_malformed_manifest_fails_closed(self):
        isolated = Path(self.tmp.name) / "bad"
        path = isolated / "pto-calculator" / "module.json"
        path.parent.mkdir(parents=True)
        original = json.loads(
            (ROOT / "pto-calculator" / "module.json").read_text(encoding="utf-8")
        )
        candidates = [
            {"module_id": "payroll-calculator"},
            {**original, "shared_excel_input": {
                "supported": True, "common_roles": {
                    "employees": "../outside.xlsx"
                }, "roles": {},
            }},
            {**original, "output_files": ["../../private.json"]},
        ]
        for data in candidates:
            with self.subTest(data=data.get("output_files")):
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ModuleIOError):
                    load_module_io_contract(
                        "pto-calculator", bhandara_root=isolated
                    )

    def test_invalid_module_name_rejected_without_directory_walk(self):
        for name in ("../payroll-calculator", "payroll", "/tmp/pto-calculator", ""):
            with self.subTest(name=name):
                with self.assertRaises(ModuleIOError):
                    load_module_io_contract(name)



    def test_public_checkout_is_never_a_private_runtime_root(self):
        contract = self._contract("common")
        with self.assertRaisesRegex(ModuleIOError, "outside the public Git checkout"):
            output_directory(contract, ROOT.parent, "unsafe")


if __name__ == "__main__":
    unittest.main()
