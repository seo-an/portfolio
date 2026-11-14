"""No-JSON module-local settings tests; only synthetic sample workbooks."""
from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bhandara.common.config.resolver import (
    SettingsContractError, load_local_settings, resolve_config,
)


ROOT = Path(__file__).resolve().parents[2]
from bhandara.tests._seed_fixture import SEED_INPUT
SAMPLE = SEED_INPUT

spec = importlib.util.spec_from_file_location("portfolio_settings_entrypoint", ROOT / "run.py")
assert spec is not None and spec.loader is not None
root_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(root_cli)


def invoke(*args: str):
    return subprocess.run(
        [sys.executable, str(ROOT / "run.py"), "bhandara", *args],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=120,
    )


class ModuleLocalSettingsTests(unittest.TestCase):
    def test_module_variables_build_plain_json_for_each_calculator(self):
        for module in ("pto-calculator", "worktime-calculator", "payroll-calculator"):
            with self.subTest(module=module):
                result = root_cli.local_cli_config(module)
                self.assertEqual(result["period"], "2026-06" if module == "worktime-calculator" else "2026-07")
                self.assertIn("common", result["files"])
                self.assertEqual(
                    json.loads(json.dumps(result, ensure_ascii=False)), result
                )
                self.assertNotIn("gearbox", str(result).lower())
                roles = result["files"]
                self.assertEqual(set(roles), {
                    "common", module.removesuffix("-calculator")
                })

    def test_external_complete_json_never_loads_python_defaults(self):
        provided = {"schema_version": "0.1", "files": {"only": "external"}}
        def unexpected():
            raise AssertionError("user_settings.py must never be consulted")
        self.assertEqual(resolve_config(provided, unexpected), provided)
        self.assertEqual(resolve_config({}, unexpected), {})  # no local merge
        with self.assertRaises(SettingsContractError):
            resolve_config(None, lambda: {"invalid": object()})

    def test_local_changes_to_strings_are_read_by_only_that_module(self):
        module = importlib.import_module("bhandara.pto-calculator.user_settings")
        with (
            patch.object(module, "PERIOD", "2026-08"),
            patch.object(module, "SCHEDULE_FILE", "pto/alternate-schedule.xlsx"),
        ):
            cfg = root_cli.local_cli_config("pto-calculator")
            self.assertEqual(cfg["period"], "2026-08")
            self.assertEqual(
                cfg["files"]["pto"]["schedule"], "pto/alternate-schedule.xlsx"
            )
            self.assertEqual(
                root_cli.local_cli_config("worktime-calculator")["period"],
                "2026-06",
            )

    def test_bad_local_month_and_path_rejected_without_fallback(self):
        module = importlib.import_module("bhandara.worktime-calculator.user_settings")
        for invalid in ("2026-7", "2026-13", "", 202607):
            with self.subTest(period=invalid), patch.object(module, "PERIOD", invalid):
                with self.assertRaises(SettingsContractError):
                    root_cli.local_cli_config("worktime-calculator")
        for invalid in ("../private.csv", "/etc/passwd", r"C:\\private.xlsx", ""):
            with self.subTest(filename=invalid), patch.object(
                module, "ATTENDANCE_FILE", invalid
            ):
                with self.assertRaises(SettingsContractError):
                    root_cli.local_cli_config("worktime-calculator")

    def test_unknown_module_rejected(self):
        with self.assertRaises(SettingsContractError):
            load_local_settings("unknown-module", {"PERIOD": "month"})

    def test_no_json_cli_uses_own_settings_and_existing_shared_excel(self):
        for module, filename, expected_code, expected_status in (
            ("pto-calculator", "pto-result.json", 1, "REVIEW_REQUIRED"),
            ("worktime-calculator", "worktime-result.json", 2, "REVIEW_REQUIRED"),
            ("payroll-calculator", "payroll-calculation.json", 2, "REVIEW_REQUIRED"),
        ):
            with self.subTest(module=module):
                with tempfile.TemporaryDirectory(prefix="bhandara-local-settings-") as td:
                    out = Path(td) / "output"
                    process = invoke(module, "--input-dir", str(SAMPLE),
                                     "--output-dir", str(out))
                    self.assertEqual(process.returncode, expected_code,
                                     process.stderr + process.stdout)
                    payload = json.loads((out / filename).read_text(encoding="utf-8"))
                    self.assertEqual(payload["status"], expected_status)
                    self.assertFalse(payload["finalizable"])
                    if module == "pto-calculator":
                        self.assertIs(payload["approved"], False)
                    elif module == "payroll-calculator":
                        self.assertIs(payload["ledger_committed"], False)
                    self.assertFalse((out / "gearbox").exists())

    def test_bad_local_config_is_not_treated_as_external_default(self):
        module = importlib.import_module("bhandara.payroll-calculator.user_settings")
        with patch.object(module, "PERIOD", "invalid"):
            with self.assertRaises(SettingsContractError):
                root_cli.local_cli_config("payroll-calculator")


if __name__ == "__main__":
    unittest.main()
