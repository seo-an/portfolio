"""Phase 1 regression: bootstrap must never pretend a calculator ran."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def invoke(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / script), *args],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )


class BootstrapTests(unittest.TestCase):
    def test_help_is_accessible(self):
        result = invoke("run.py", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bhandara", result.stdout)

    def test_unknown_calculator_fails_closed(self):
        result = invoke("run.py", "bhandara", "unpublished-calculator")
        self.assertEqual(result.returncode, 2)
        self.assertIn("UNAVAILABLE", result.stderr)
        self.assertIn("No calculations were performed", result.stderr)

    def test_missing_command_is_nonzero(self):
        result = invoke("run.py")
        self.assertNotEqual(result.returncode, 0)

    def test_check_does_not_install_packages(self):
        result = invoke("install.py", "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No packages were installed", result.stdout)
        self.assertIn("openpyxl==3.1.5", result.stdout)

    def test_python_version_check(self):
        spec = importlib.util.spec_from_file_location("portfolio_install", ROOT / "install.py")
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(module.check_python((3, 11, 9))[0])
        self.assertTrue(module.check_python((3, 12, 0))[0])
        self.assertTrue(module.check_python((3, 14, 9))[0])
        self.assertEqual(module.check_packages(), [])

    def test_base_dependency_pin_matches_hermes(self):
        lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        packages = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(packages, ["openpyxl==3.1.5", "korean-lunar-calendar==0.4.0"])

    def test_local_runtime_data_is_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/bhandara/data/**", ignore)


if __name__ == "__main__":
    unittest.main()
