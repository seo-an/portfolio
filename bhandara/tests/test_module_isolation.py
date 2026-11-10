"""Mutual-exclusion acceptance: Base + exactly one published calculator.

Runs each copied module in a fresh, isolated temporary root with no other
calculator's Python files, no Gearbox, no Hermes, and no Python import path
pointing back to this repository. Inputs are synthetic. This is a migration
isolation check, not a policy/exception correctness review.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bhandara.tests.test_payroll_migration import _create_synthetic_inputs
from bhandara.tests.test_worktime_migration import (
    synthetic_config,
    synthetic_normalized,
)

ROOT = Path(__file__).resolve().parents[2]
MODULES = ("pto-calculator", "worktime-calculator", "payroll-calculator")


def _install_one(target: Path, module_id: str) -> Path:
    """Copy the exact published files, not a synthetic mock module."""
    if module_id not in MODULES:
        raise ValueError("unknown calculator")
    shutil.copy2(ROOT / "run.py", target / "run.py")
    shutil.copy2(ROOT / "install.py", target / "install.py")
    shutil.copy2(ROOT / "requirements.txt", target / "requirements.txt")
    package = target / "bhandara"
    package.mkdir()
    shutil.copy2(ROOT / "bhandara/__init__.py", package / "__init__.py")
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ROOT / "bhandara/common", package / "common", ignore=ignore)
    shutil.copytree(ROOT / "bhandara" / module_id, package / module_id,
                    ignore=ignore)
    # Fail before test execution if an unrequested module was installed.
    present = sorted(
        child.name for child in package.iterdir()
        if child.is_dir() and child.name in MODULES
    )
    if present != [module_id]:
        raise AssertionError("isolated package contains an unexpected calculator")
    return target / "run.py"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Ignore inherited PYTHONPATH, user-site paths and app secrets."""
    env = {
        "HOME": str(root),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, "-E", *args], cwd=root, env=env,
        text=True, capture_output=True, check=False, timeout=90,
    )


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def _worktime_inputs(root: Path, approved: bool) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "normalized-input.json"
    config = root / "worktime-config.json"
    _write_json(source, synthetic_normalized())
    _write_json(config, synthetic_config(approved=approved))
    return source, config


def _payroll_inputs(root: Path, installed_module: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    config = _create_synthetic_inputs(root)
    data = json.loads(config.read_text(encoding="utf-8"))
    # The fixture helper targets the full original checkout by default.
    # Force every registry/policy reference into the isolated installation.
    data["registry_path"] = str(installed_module / "resources/pay-item-registry.json")
    data["legal_policy_path"] = str(installed_module / "resources/policy/2026.json")
    data["operating_config_path"] = str(installed_module / "operating-config.json")
    _write_json(config, data)
    return config


class ModuleIsolationTests(unittest.TestCase):
    def test_base_and_each_single_calculator_install_without_others(self):
        for selected in MODULES:
            with self.subTest(module=selected):
                with tempfile.TemporaryDirectory(prefix="bhandara-isolated-") as tmp:
                    root = Path(tmp)
                    _install_one(root, selected)
                    self.assertFalse((root / "gearbox").exists())
                    for other in MODULES:
                        self.assertEqual(
                            (root / "bhandara" / other).exists(),
                            selected == other,
                        )
                    result = _run(root, "install.py", "--check")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("BASE_CHECK_OK", result.stdout)

    def test_pto_runs_with_only_base_and_pto(self):
        with tempfile.TemporaryDirectory(prefix="bhandara-pto-only-") as tmp:
            root = Path(tmp)
            entry = _install_one(root, "pto-calculator")
            demo = root / "synthetic"
            generator = root / "bhandara/pto-calculator/examples/generate_demo.py"
            create = _run(root, str(generator), "--output-dir", str(demo))
            self.assertEqual(create.returncode, 0, create.stderr)
            output = root / "result"
            result = _run(
                root, str(entry), "bhandara", "pto-calculator",
                "--config", str(demo / "config.json"),
                "--input-dir", str(demo / "input"),
                "--output-dir", str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((output / "pto-result.json").read_text())
            self.assertEqual(data["status"], "PASS")
            self.assertIs(data["approved"], False)
            self.assertIs(data["finalizable"], False)
            self.assertEqual(len(data["results"]), 2)
            self.assertFalse((root / "bhandara/worktime-calculator").exists())
            self.assertFalse((root / "bhandara/payroll-calculator").exists())

    def test_worktime_runs_with_only_base_and_worktime(self):
        with tempfile.TemporaryDirectory(prefix="bhandara-worktime-only-") as tmp:
            root = Path(tmp)
            entry = _install_one(root, "worktime-calculator")
            source, config = _worktime_inputs(root / "inputs", approved=True)
            output = root / "result"
            result = _run(
                root, str(entry), "bhandara", "worktime-calculator",
                "--normalized", str(source), "--config", str(config),
                "--output-dir", str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((output / "worktime-result.json").read_text())
            self.assertEqual(data["status"], "CALCULATED_UNCLOSED")
            self.assertIs(data["finalizable"], False)
            self.assertIsNone(data["close_receipt"])
            self.assertEqual(len(data["rows"]), 2)
            self.assertFalse((root / "bhandara/pto-calculator").exists())
            self.assertFalse((root / "bhandara/payroll-calculator").exists())

    def test_payroll_runs_with_only_base_and_payroll(self):
        with tempfile.TemporaryDirectory(prefix="bhandara-payroll-only-") as tmp:
            root = Path(tmp)
            entry = _install_one(root, "payroll-calculator")
            module = root / "bhandara/payroll-calculator"
            config = _payroll_inputs(root / "inputs", module)
            output = root / "result"
            result = _run(
                root, str(entry), "bhandara", "payroll-calculator",
                "--config", str(config), "--output-dir", str(output),
            )
            # Payroll intentionally exits 2 even when review-only amounts exist.
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("REVIEW_REQUIRED", result.stdout)
            data = json.loads((output / "payroll-calculation.json").read_text())
            self.assertEqual(data["status"], "REVIEW_REQUIRED")
            self.assertIs(data["finalizable"], False)
            self.assertIs(data["ledger_committed"], False)
            self.assertFalse((root / "bhandara/worktime-calculator").exists())
            self.assertFalse((root / "bhandara/pto-calculator").exists())

    def test_payroll_close_helper_imports_without_worktime_package(self):
        """Test the optional close-receipt entrypoint's import boundary."""
        with tempfile.TemporaryDirectory(prefix="bhandara-payroll-import-") as tmp:
            root = Path(tmp)
            _install_one(root, "payroll-calculator")
            self.assertFalse((root / "bhandara/worktime-calculator").exists())
            script = (
                "import importlib.util, pathlib; "
                "path = pathlib.Path('bhandara/payroll-calculator/functions/payroll_register.py'); "
                "spec = importlib.util.spec_from_file_location('isolation_payroll_register', path); "
                "module = importlib.util.module_from_spec(spec); "
                "spec.loader.exec_module(module); "
                "assert callable(module.verify_final_payroll_register)"
            )
            result = _run(root, "-c", script)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_calculator_is_not_substituted(self):
        for selected in MODULES:
            with self.subTest(module=selected):
                with tempfile.TemporaryDirectory(prefix="bhandara-negative-") as tmp:
                    root = Path(tmp)
                    entry = _install_one(root, selected)
                    other = next(x for x in MODULES if x != selected)
                    result = _run(root, str(entry), "bhandara", other)
                    self.assertEqual(result.returncode, 2)
                    self.assertNotEqual(result.stderr.strip(), "")
                    self.assertFalse((root / "bhandara" / other).exists())

    def test_worktime_json_handoff_to_payroll_without_cross_installation(self):
        """Only the Worktime JSON crosses independent module boundaries."""
        with tempfile.TemporaryDirectory(prefix="bhandara-handoff-") as tmp:
            root = Path(tmp)
            wt_root = root / "worktime"
            pr_root = root / "payroll"
            wt_root.mkdir()
            pr_root.mkdir()
            wt_cli = _install_one(wt_root, "worktime-calculator")
            pr_cli = _install_one(pr_root, "payroll-calculator")
            source, config = _worktime_inputs(root / "inputs", approved=False)
            handoff = root / "worktime-result"
            worktime = _run(
                wt_root, str(wt_cli), "bhandara", "worktime-calculator",
                "--normalized", str(source), "--config", str(config),
                "--output-dir", str(handoff),
            )
            self.assertEqual(worktime.returncode, 2, worktime.stderr)
            worktime_json = handoff / "worktime-result.json"
            worktime_data = json.loads(worktime_json.read_text())
            self.assertEqual(worktime_data["schema_version"], "0.1")
            self.assertEqual(worktime_data["status"], "REVIEW_REQUIRED")
            self.assertIsNone(worktime_data["close_receipt"])
            self.assertIs(worktime_data["finalizable"], False)

            payroll_demo = root / "synthetic-payroll"
            generator = (
                pr_root / "bhandara/payroll-calculator/"
                "examples/payroll-standalone-demo/generate.py"
            )
            generated = _run(
                pr_root, str(generator),
                "--worktime-result", str(worktime_json),
                "--output-dir", str(payroll_demo),
            )
            self.assertEqual(generated.returncode, 0, generated.stderr)
            result = _run(
                pr_root, str(pr_cli), "bhandara", "payroll-calculator",
                "--config", str(payroll_demo / "payroll-config.json"),
                "--output-dir", str(root / "payroll-result"),
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("REVIEW_REQUIRED", result.stdout)
            review = json.loads((root / "payroll-result/payroll-review.json").read_text())
            calculation = json.loads(
                (root / "payroll-result/payroll-calculation.json").read_text()
            )
            self.assertEqual(review["status"], "REVIEW_REQUIRED")
            self.assertIs(review["finalizable"], False)
            self.assertIs(review["ledger_committed"], False)
            self.assertEqual(calculation["status"], "REVIEW_REQUIRED")
            self.assertEqual(calculation["worktime_mode"], "UNCLOSED")
            self.assertIs(calculation["finalizable"], False)
            self.assertIs(calculation["ledger_committed"], False)
            self.assertFalse((wt_root / "bhandara/payroll-calculator").exists())
            self.assertFalse((pr_root / "bhandara/worktime-calculator").exists())


if __name__ == "__main__":
    unittest.main()
