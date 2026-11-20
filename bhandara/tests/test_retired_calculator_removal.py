"""Keep retired entrypoints and unsupported documentation from regressing.

This tests repository structure only; it never processes employee data.
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
import subprocess
import sys
import unittest

import run as root_cli

ROOT = Path(__file__).resolve().parents[2]
RETIRED = ("pto-calculator", "worktime-calculator", "payroll-calculator")
ACTIVE = ("paid-time-off", "worktime", "payroll", "workflow")


class RetiredCodeRemovalTests(unittest.TestCase):
    def test_only_supported_tools_are_exposed(self):
        self.assertEqual(root_cli.TOOLS, frozenset(ACTIVE))
        self.assertEqual(set(root_cli.CONFIG_NAMES), set(ACTIVE))
        for name in RETIRED:
            proc = subprocess.run(
                [sys.executable, str(ROOT / "run.py"), "bhandara", name],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 2, name)
            self.assertIn("UNAVAILABLE", proc.stderr)

    def test_retired_code_and_fixture_trees_are_absent(self):
        for name in RETIRED:
            self.assertFalse((ROOT / "bhandara" / name).exists(), name)
        self.assertFalse((ROOT / "bhandara/examples/sample").exists())
        self.assertFalse((ROOT / "bhandara/common/io/payroll_legacy_xlsx.py").exists())

    def test_supported_tool_modules_still_import(self):
        for name in ACTIVE:
            module = ("bhandara.workflow" if name == "workflow"
                      else f"bhandara.{name}.tool_cli")
            with self.subTest(name=name):
                import_module(module)

    def test_python_and_workflow_files_have_no_removed_package_imports(self):
        # This test itself names retired modules for its negative assertions;
        # examine production source and workflow definitions only.
        candidates = list((ROOT / "bhandara").rglob("*.py"))
        candidates += list((ROOT / ".github/workflows").glob("*.yml"))
        for path in candidates:
            if "tests" in path.parts:
                continue
            data = path.read_text(encoding="utf-8")
            for old in RETIRED:
                with self.subTest(path=str(path.relative_to(ROOT)), old=old):
                    self.assertNotIn(old, data)

    def test_docs_do_not_link_to_deleted_code_or_examples(self):
        documents = [ROOT / "README.md"] + list(
            (ROOT / "bhandara").rglob("*.md")
        )
        forbidden = (*RETIRED, "bhandara/examples/sample",
                     "LEGACY-RETIREMENT.md", "DEVELOPMENT-STATUS-2026-11-19.md")
        for doc in documents:
            content = doc.read_text(encoding="utf-8")
            for phrase in forbidden:
                with self.subTest(document=doc.name, phrase=phrase):
                    self.assertNotIn(phrase, content)


if __name__ == "__main__":
    unittest.main()
