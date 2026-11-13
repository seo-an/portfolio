"""New recommended v2 example, preserving the old 80-person regression sample."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from bhandara.common.io.input_layout import InputLayoutError, read_id_map

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "bhandara/examples/integrated/generate.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "bhandara_integrated_example_generator", GENERATOR
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IntegratedExampleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bhandara-example-")
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / "v2-demo"

    def _generate(self):
        demo = _load_generator().generate(self.destination)
        self.assertEqual(demo, self.destination)
        return demo / "input"

    def test_integrated_demo_is_generated_without_legacy_service_files(self):
        source = self._generate()
        payroll = source / "payroll"
        self.assertFalse((payroll / "pay-contract-components.xlsx").exists())
        self.assertFalse((payroll / "service-contracts.xlsx").exists())
        self.assertFalse((payroll / "service-work-records.xlsx").exists())
        book = load_workbook(payroll / "pay-contract.xlsx", read_only=True)
        try:
            self.assertEqual(book.sheetnames, ["Contracts", "Components"])
            contracts = list(book["Contracts"].values)
            components = list(book["Components"].values)
        finally:
            book.close()
        self.assertEqual(len(contracts) - 1, 83)
        self.assertEqual({r[8] for r in contracts[1:]}, {
            "BASE", "TOTAL", "RATE",
        })
        self.assertEqual(sum(r[9] == "REGULAR_EMPLOYEE" for r in contracts[1:]), 80)
        e6 = next(r for r in contracts if r[1] == "E006")
        self.assertEqual(e6[8], "BASE")
        self.assertEqual(e6[3], 3500000)
        e6_components = {
            code: int(amount)
            for contract_id, code, amount in components[1:]
            if contract_id == e6[0]
        }
        self.assertEqual(e6_components, {
            "base_salary": 3500000,
            "meal_allowance": 100000,
            "position_allowance": 150000,
        })
        employee_ids = read_id_map(source)
        self.assertEqual(len(employee_ids), 80)
        ids = load_workbook(source / "common/id-map.xlsx", read_only=True)
        try:
            self.assertEqual(ids.sheetnames, ["ID_MAP", "EXTERNAL"])
        finally:
            ids.close()
        handoff = json.loads(
            (payroll / "worktime-result.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(handoff["covered_worker_ids"]), 82)
        self.assertEqual(handoff["status"], "REVIEW_REQUIRED")
        self.assertFalse(handoff["finalizable"])
        self.assertIsNone(handoff["close_receipt"])
        meta = json.loads(
            (self.destination / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(meta["schema_version"], "2.0")
        self.assertFalse((self.destination / "worktime-output").exists())
        with self.assertRaises(FileExistsError):
            _load_generator().generate(self.destination)

    def test_real_worktime_handoff_feeds_new_payroll_contracts(self):
        from importlib import import_module
        source = self._generate()
        adapter = import_module("bhandara.payroll-calculator.contract_adapter")
        artifacts = adapter.build_contract_compensation(
            source, "2026-07", read_id_map(source),
            worktime_path=source / "payroll/worktime-result.json",
            generated_dir=Path(self.temp.name) / "config",
        )
        report = json.loads(
            artifacts["review_path"].read_text(encoding="utf-8")
        )
        self.assertEqual(report["employee_count"], 80)
        self.assertEqual(report["service_worker_count"], 2)
        self.assertEqual(report["contract_input_layout"], "v2")
        self.assertFalse(report["finalizable"])
        services = {item["service_contract_id"]: item
                    for item in report["service_contracts"]}
        self.assertEqual(
            services["SVC-H001"]["estimated_service_amount"], "814000"
        )
        self.assertEqual(
            services["SVC-D002"]["estimated_service_amount"], "460000"
        )
        self.assertIsNone(
            services["SVC-P003"]["estimated_service_amount"]
        )
        xlsx = load_workbook(artifacts["compensation_path"], read_only=True)
        try:
            rows = list(xlsx.active.values)
        finally:
            xlsx.close()
        self.assertEqual(len(rows) - 1, 80)
        self.assertFalse({"EXT-W001", "EXT-W002"} &
                         {x[0] for x in rows[1:]})

    def test_fixture_preserves_legacy_reproduction_data(self):
        baseline = ROOT / "bhandara/examples/sample/input"
        for file in (
            "payroll/pay-contract-components.xlsx",
            "payroll/service-contracts.xlsx",
            "payroll/service-work-records.xlsx",
        ):
            self.assertTrue((baseline / file).is_file())


if __name__ == "__main__":
    unittest.main()
