"""Migration-only gates for the original review-only Payroll calculator.

Checks exact legacy Git blob identity (with reversible import/path rewrites)
and the same synthetic input through migrated direct and Portfolio entrypoints.
No new payroll rules, exceptions, entitlements, or finalization are tested.
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "bhandara/payroll-calculator"
MANIFEST = MODULE / "migration-manifest.json"


def _blob_hash(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], cwd=cwd, capture_output=True,
        text=True, check=False,
    )


def _json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _xlsx(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    book = Workbook()
    try:
        sheet = book.active
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        book.save(path)
    finally:
        book.close()


def _worktime(worker: str) -> dict:
    return {
        "worker_id": worker, "work_date": "2026-09-15",
        "worktime_system": "standard", "rule_ref": "labor_standard_50_53",
        "scheduled_hours": "8", "worked_hours": "8",
        "ordinary_hours": "8", "overtime_hours": "0", "night_hours": "0",
        "holiday_work_hours_within_8": "0",
        "holiday_work_hours_over_8": "0", "absence_hours": "0",
        "late_minutes": 0, "early_leave_minutes": 0, "approval_ref": "",
        "validation_flags": [
            {"code": "TIMESHEET_APPROVAL_MISSING", "severity": "REVIEW",
             "message": "approval missing"}
        ],
    }


def _create_synthetic_inputs(root: Path) -> Path:
    _xlsx(
        root / "compensation.xlsx",
        ["worker_id", "effective_from", "effective_to", "base_salary"],
        [["W1", "2026-01-01", None, 3200000],
         ["W2", "2026-01-01", None, 2800000]],
    )
    _xlsx(
        root / "payroll-input.xlsx",
        ["worker_id", "pay_item_code", "amount", "quantity",
         "origin_pay_item_code", "origin_from", "origin_to", "note"],
        [["W1", "performance_bonus", 100000, None, None, None, None,
          "synthetic bonus"]],
    )
    _json(root / "employment.json", [
        {"worker_id": worker, "employment_from": "2026-01-01",
         "employment_to": None} for worker in ("W1", "W2")
    ])
    _json(root / "worktime-result.json", {
        "schema_version": "0.1", "status": "REVIEW_REQUIRED",
        "period_from": "2026-09-15", "period_to": "2026-09-15",
        "coverage_verified": False, "close_receipt": None,
        "rows": [_worktime("W1"), _worktime("W2")],
    })
    _json(root / "company-policy.json", {
        "proration": {"base_salary": {"method": "역일수"}},
        "ordinary_wage": {"monthly_basis_hours": 200, "pay_items": {}},
        "worktime_pay": {"base_component_policy": {}},
        "amount_processing": {
            "unit": 10, "method": "절사", "apply_at": "최종지급액",
            "remainder": {
                "handling": "settlement_ledger",
                "transaction_type": "rounding_carry", "settlement_month": 12,
            },
        },
    })
    path = root / "payroll-config.json"
    _json(path, {
        "schema_version": "0.1", "payroll_period": "2026-10",
        "expected_worker_ids": ["W1", "W2"],
        "compensation_path": "compensation.xlsx",
        "payroll_input_path": "payroll-input.xlsx",
        "worktime_result_path": "worktime-result.json",
        "registry_path": str(MODULE / "resources/pay-item-registry.json"),
        "operating_config_path": str(MODULE / "operating-config.json"),
        "company_policy_path": "company-policy.json",
        "legal_policy_path": str(MODULE / "resources/policy/2026.json"),
        "employment_facts_path": "employment.json",
        "recurring_pay_item_codes": ["base_salary"],
    })
    return path


def _xlsx_rows(path: Path) -> dict[str, list[tuple]]:
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        return {
            sheet.title: [tuple(row) for row in sheet.iter_rows(values_only=True)]
            for sheet in book.worksheets
        }
    finally:
        book.close()


class PayrollMigrationTests(unittest.TestCase):
    def test_every_source_hash_matches_original_or_reversible_path_only_patch(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["migration_type"],
                         "copy_with_path_only_adaptations")
        self.assertEqual(len(manifest["files"]), 85)
        self.assertEqual(len(manifest["resources"]), 5)
        changes = manifest["adaptations"]
        self.assertEqual(len(changes), 10)
        # The initial migration manifest is an immutable historic snapshot.
        # Only separately declared, reviewed post-migration extractions may
        # change the original Git blob contents.
        refactors = json.loads(
            (MODULE / "post-migration-refactors.json").read_text(encoding="utf-8")
        )
        self.assertEqual(refactors["schema_version"], "1.0")
        self.assertEqual(refactors["historical_manifest"], "migration-manifest.json")
        declared = {item["destination"]: item for item in refactors["refactors"]}
        self.assertEqual(set(declared), {
            "bhandara/payroll-calculator/functions/source_mapping.py"
        })
        adapted_paths = set()
        for entry in manifest["files"]:
            with self.subTest(path=entry["destination"]):
                path = ROOT / entry["destination"]
                self.assertTrue(path.is_file())
                data = path.read_bytes()
                relative = path.relative_to(MODULE).as_posix()
                if relative in changes:
                    adapted_paths.add(relative)
                    restored = data.decode("utf-8")
                    for original, relocated in reversed(changes[relative]):
                        self.assertEqual(restored.count(relocated), 1)
                        restored = restored.replace(relocated, original)
                    data = restored.encode("utf-8")
                if entry["destination"] in declared:
                    item = declared[entry["destination"]]
                    self.assertEqual(item["original_source_git_blob_sha"],
                                     entry["source_git_blob_sha"])
                    # A refactor changes its source SHA only by an explicitly
                    # reviewed new Git blob; all other 84 files still match
                    # the original (or reversible imports/path patches).
                    self.assertNotEqual(item["current_git_blob_sha"],
                                        item["original_source_git_blob_sha"])
                    self.assertEqual(_blob_hash(data), item["current_git_blob_sha"])
                else:
                    self.assertEqual(_blob_hash(data),
                                     entry["source_git_blob_sha"])
        self.assertEqual(adapted_paths, set(changes))
        for entry in manifest["resources"]:
            with self.subTest(resource=entry["destination"]):
                self.assertEqual(
                    _blob_hash((ROOT / entry["destination"]).read_bytes()),
                    entry["source_git_blob_sha"],
                )

    def test_migrated_python_imports_no_longer_depend_on_gearbox(self):
        files = [MODULE / "run.py"] + sorted((MODULE / "functions").glob("*.py"))
        for path in files:
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        self.assertFalse(
                            (node.module or "").startswith("gearbox"),
                            "Payroll runtime must not import private Gearbox",
                        )
                    elif isinstance(node, ast.Import):
                        self.assertTrue(all(
                            item.name != "gearbox"
                            and not item.name.startswith("gearbox.")
                            for item in node.names
                        ))

    def test_module_contract_is_review_only(self):
        info = json.loads((MODULE / "module.json").read_text(encoding="utf-8"))
        self.assertEqual(info["module_id"], "payroll-calculator")
        self.assertIs(info["non_finalization_guards"]["finalizable"], False)
        self.assertIs(info["non_finalization_guards"]["ledger_committed"], False)

    def test_public_root_dispatch_matches_direct_legacy_calculate(self):
        with tempfile.TemporaryDirectory(prefix="payroll-migration-") as temp:
            root = Path(temp)
            config = _create_synthetic_inputs(root)
            old = _run(str(MODULE / "run.py"), "calculate",
                       "--config", str(config),
                       "--output-dir", str(root / "direct"),
                       cwd=root)
            new = _run(str(ROOT / "run.py"), "bhandara", "payroll-calculator",
                       "--config", str(config),
                       "--output-dir", str(root / "portfolio"),
                       cwd=root)
            self.assertEqual(old.returncode, 2, old.stderr)
            self.assertEqual(new.returncode, 2, new.stderr)
            self.assertIn("REVIEW_REQUIRED", old.stdout)
            self.assertIn("REVIEW_REQUIRED", new.stdout)
            for filename in (
                "payroll-calculation.json", "payroll-review.json",
                "policy-resolution.json",
            ):
                with self.subTest(filename=filename):
                    direct = json.loads((root / "direct" / filename).read_text())
                    routed = json.loads((root / "portfolio" / filename).read_text())
                    self.assertEqual(direct, routed)
            for filename in ("payroll-calculation.xlsx", "payroll-review.xlsx"):
                with self.subTest(filename=filename):
                    self.assertEqual(
                        _xlsx_rows(root / "direct" / filename),
                        _xlsx_rows(root / "portfolio" / filename),
                    )
            calculation = json.loads(
                (root / "portfolio" / "payroll-calculation.json").read_text()
            )
            self.assertFalse(calculation["finalizable"])
            self.assertFalse(calculation["ledger_committed"])
            self.assertEqual(calculation["status"], "REVIEW_REQUIRED")

    def test_public_root_dispatch_matches_direct_legacy_normalize(self):
        source = MODULE / "examples/source-mapping-demo"
        with tempfile.TemporaryDirectory(prefix="payroll-mapping-") as temp:
            root = Path(temp)
            old = _run(str(MODULE / "run.py"), "normalize",
                       "--input-dir", str(source),
                       "--output-dir", str(root / "direct"), cwd=root)
            new = _run(str(ROOT / "run.py"), "bhandara", "payroll-calculator",
                       "--operation", "normalize", "--input-dir", str(source),
                       "--output-dir", str(root / "portfolio"), cwd=root)
            self.assertEqual(old.returncode, 0, old.stderr)
            self.assertEqual(new.returncode, 0, new.stderr)
            self.assertIn("READY_FOR_CALCULATION", old.stdout)
            self.assertIn("READY_FOR_CALCULATION", new.stdout)
            for filename in ("normalized-input.json", "review-report.json"):
                with self.subTest(filename=filename):
                    self.assertEqual(
                        json.loads((root / "direct" / filename).read_text()),
                        json.loads((root / "portfolio" / filename).read_text()),
                    )

    def test_no_json_default_requires_real_excel_input(self):
        out = _run(str(ROOT / "run.py"), "bhandara", "payroll-calculator",
                   cwd=ROOT)
        self.assertEqual(out.returncode, 2)
        self.assertIn("PAYROLL_INPUT_INVALID", out.stderr)
        self.assertIn("Missing required input", out.stderr)


if __name__ == "__main__":
    unittest.main()
