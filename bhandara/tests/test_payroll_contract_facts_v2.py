"""Payroll v2: synthetic two-sheet agreement facts and additive pay items.

No private employee, tax, payroll approval, or Gearbox data.
"""
from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook

from bhandara.common.io.input_layout import InputLayoutError, read_id_map


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "bhandara/examples/sample/input"
adapter = importlib.import_module("bhandara.payroll-calculator.contract_adapter")
terms = importlib.import_module("bhandara.payroll-calculator.contract_terms")


class ContractFactsV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bhandara-contract-v2-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "payroll").mkdir()
        self.contract = self.root / "payroll/pay-contract.xlsx"
        self._write_modern_workbook()

    def _write_modern_workbook(self):
        prior = load_workbook(SOURCE / "payroll/pay-contract.xlsx", read_only=True)
        components = load_workbook(
            SOURCE / "payroll/pay-contract-components.xlsx", read_only=True
        )
        try:
            contract_rows = list(prior.active.values)
            component_rows = list(components.active.values)
        finally:
            prior.close()
            components.close()
        amounts = {}
        for row in component_rows[1:]:
            if row[0] is not None:
                amounts.setdefault(row[0], {})[row[1]] = Decimal(str(row[2]))

        book = Workbook()
        contracts = book.active
        contracts.title = "Contracts"
        contracts.append((*contract_rows[0], "amount_type", "relationship_type"))
        items = book.create_sheet("Components")
        items.append(("contract_id", "pay_item_code", "monthly_amount"))
        for row in contract_rows[1:]:
            if row[0] is None:
                continue
            contract_id, employee_id, basis, rate = row[:4]
            if basis in {"ANNUAL", "MONTHLY"}:
                amount_type = "BASE" if employee_id == "E006" else "TOTAL"
                reference = Decimal(str(rate)) / (
                    Decimal("12") if basis == "ANNUAL" else Decimal("1")
                )
                if amount_type == "TOTAL":
                    included = sum(
                        amounts.get(contract_id, {}).values(), Decimal("0")
                    )
                    items.append((
                        contract_id, "base_salary", float(reference - included),
                    ))
                for code, amount in amounts.get(contract_id, {}).items():
                    items.append((contract_id, code, float(amount)))
            else:
                amount_type = "RATE"
            contracts.append((
                *row, amount_type,
                "DAILY_EMPLOYEE" if basis == "DAILY" else "REGULAR_EMPLOYEE",
            ))
        try:
            book.save(self.contract)
        finally:
            book.close()

    def _audit(self):
        result = adapter.build_contract_compensation(
            self.root, "2026-07", read_id_map(SOURCE),
            worktime_path=SOURCE / "payroll/worktime-result.json",
            generated_dir=self.root / "generated",
        )
        audit = json.loads(result["review_path"].read_text(encoding="utf-8"))
        return result, audit

    def _update_cell(self, sheet_name, header_name, employee_id, value):
        book = load_workbook(self.contract)
        try:
            sheet = book[sheet_name]
            names = [cell.value for cell in sheet[1]]
            target = names.index(header_name) + 1
            emp_col = names.index("employee_id") + 1
            for row in range(2, sheet.max_row + 1):
                if sheet.cell(row, emp_col).value == employee_id:
                    sheet.cell(row, target, value)
                    break
            else:
                raise AssertionError("missing synthetic employee")
            book.save(self.contract)
        finally:
            book.close()

    def test_base_and_total_use_same_additive_payroll_output(self):
        result, report = self._audit()
        self.assertEqual(report["contract_input_layout"], "v2")
        self.assertEqual(report["employee_count"], 80)
        self.assertEqual(report["source_hashes"]["contract_components"],
                         "IN_PAY_CONTRACT_XLSX")
        book = load_workbook(result["compensation_path"], read_only=True)
        try:
            rows = list(book.active.values)
        finally:
            book.close()
        workers = {row[0]: dict(zip(rows[0], row)) for row in rows[1:]}
        # E006 MONTHLY contract fact 3.5m BASE + 150k + 100k = 3.75m.
        self.assertEqual(Decimal(str(workers["EP0006"]["base_salary"])),
                         Decimal("3500000"))
        self.assertEqual(Decimal(str(workers["EP0006"]["position_allowance"])),
                         Decimal("150000"))
        self.assertEqual(Decimal(str(workers["EP0006"]["meal_allowance"])),
                         Decimal("100000"))
        # Other synthetic contracts are TOTAL with explicitly declared base.
        self.assertEqual(Decimal(str(workers["EP0002"]["base_salary"])),
                         Decimal("2900000"))
        self.assertEqual(Decimal(str(workers["EP0003"]["base_salary"])),
                         Decimal("2367200"))
        people = {x["employee_id"]: x for x in report["employees"]}
        e6 = people["E006"]["contract_details"][0]
        self.assertEqual(e6["amount_type"], "BASE")
        self.assertEqual(e6["monthly_contract_amount"], "3500000")
        self.assertEqual(e6["monthly_gross"], "3750000")
        self.assertEqual(e6["calculation"], "SUM_EXPLICIT_PAY_ITEMS")
        e18 = people["E018"]["contract_details"][0]
        self.assertEqual(e18["amount_type"], "TOTAL")
        self.assertEqual(e18["monthly_gross"], e18["monthly_contract_amount"])
        self.assertFalse(report["finalizable"])
        self.assertFalse(any(x["approved"] for x in report["employees"]))

    def test_total_requires_explicit_base_salary_and_exact_sum(self):
        book = load_workbook(self.contract)
        try:
            sheet = book["Components"]
            for row in range(2, sheet.max_row + 1):
                if (sheet.cell(row, 1).value == "CTR-0002"
                        and sheet.cell(row, 2).value == "base_salary"):
                    sheet.cell(row, 2, "position_allowance")
                    break
            book.save(self.contract)
        finally:
            book.close()
        with self.assertRaisesRegex(InputLayoutError,
                                    "TOTAL requires an explicit base_salary component"):
            self._audit()

        self._write_modern_workbook()
        book = load_workbook(self.contract)
        try:
            sheet = book["Components"]
            for row in range(2, sheet.max_row + 1):
                if (sheet.cell(row, 1).value == "CTR-0002"
                        and sheet.cell(row, 2).value == "base_salary"):
                    sheet.cell(row, 3, 2800000)
                    break
            book.save(self.contract)
        finally:
            book.close()
        with self.assertRaisesRegex(InputLayoutError,
                                    "TOTAL components do not reconcile"):
            self._audit()

    def test_base_component_mismatch_is_rejected(self):
        book = load_workbook(self.contract)
        try:
            book["Components"].append(("CTR-0006", "base_salary", 3250000))
            book.save(self.contract)
        finally:
            book.close()
        with self.assertRaisesRegex(InputLayoutError,
                                    "explicit base_salary differs from BASE"):
            self._audit()

    def test_missing_contract_semantics_and_invalid_relationship_fail_closed(self):
        self._update_cell("Contracts", "amount_type", "E006", None)
        with self.assertRaisesRegex(InputLayoutError, "invalid amount_type"):
            self._audit()
        self._write_modern_workbook()
        self._update_cell("Contracts", "relationship_type", "E006", "CORPORATE_VENDOR")
        with self.assertRaisesRegex(InputLayoutError, "unsupported relationship_type"):
            self._audit()

    def test_two_sheet_structure_is_required_in_modern_mode(self):
        book = load_workbook(self.contract)
        try:
            del book["Components"]
            book.save(self.contract)
        finally:
            book.close()
        with self.assertRaisesRegex(
            InputLayoutError, "requires both Contracts and Components",
        ):
            self._audit()

    def test_public_two_sheet_excel_example_matches_documented_sums(self):
        sample = (
            ROOT / "bhandara/payroll-calculator/examples/"
            "contract-v2-two-sheet.demo.xlsx"
        )
        book = load_workbook(sample, read_only=True, data_only=False)
        try:
            self.assertEqual(book.sheetnames, ["Contracts", "Components"])
            rows = list(book["Contracts"].values)
            self.assertEqual(rows[0][-2:], ("amount_type", "relationship_type"))
            self.assertEqual(rows[1][-2:], ("BASE", "REGULAR_EMPLOYEE"))
            self.assertEqual(rows[2][-2:], ("TOTAL", "FIXED_TERM_EMPLOYEE"))
            components = list(book["Components"].values)
        finally:
            book.close()
        amounts = {}
        for contract_id, code, value in components[1:]:
            amounts.setdefault(contract_id, {})[code] = Decimal(str(value))
        base = terms.resolve_monthly_terms(
            contract_id="CTR-BASE-001", pay_basis="MONTHLY",
            contract_amount=Decimal("3500000"),
            amount_type="BASE", components=amounts["CTR-BASE-001"],
        )
        total = terms.resolve_monthly_terms(
            contract_id="CTR-TOTAL-002", pay_basis="MONTHLY",
            contract_amount=Decimal("3500000"),
            amount_type="TOTAL", components=amounts["CTR-TOTAL-002"],
        )
        self.assertEqual(base.monthly_paid_total, Decimal("3750000"))
        self.assertEqual(total.monthly_paid_total, Decimal("3500000"))

    def test_public_semantics_registry_lists_relationships_but_not_tax_rules(self):
        path = ROOT / "bhandara/payroll-calculator/resources/contract-types.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(registry["schema_version"], "1.0")
        self.assertEqual(
            registry["relationship_types"]["REGULAR_EMPLOYEE"]["route"],
            "employee_payroll",
        )
        self.assertEqual(
            registry["relationship_types"]["CORPORATE_VENDOR"]["route"],
            "service_review",
        )
        self.assertIn("tax", registry["tax_classification"].lower())
        self.assertEqual(terms.resolve_monthly_terms(
            contract_id="C1", pay_basis="MONTHLY",
            contract_amount=Decimal("3500000"),
            amount_type="BASE", components={
                "position_allowance": Decimal("150000"),
                "meal_allowance": Decimal("100000"),
            },
        ).monthly_paid_total, Decimal("3750000"))


if __name__ == "__main__":
    unittest.main()
