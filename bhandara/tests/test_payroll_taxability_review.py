"""Contract tests for separate, never-finalized employee taxability review."""
from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from bhandara.common.io.input_layout import InputLayoutError

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "bhandara/payroll-calculator"
reviewer = importlib.import_module(
    "bhandara.payroll-calculator.functions.taxability_review"
)


def _line(worker, code, amount, *, item_type="지급", direction="pay"):
    return {
        "worker_id": worker, "payroll_period": "2026-07",
        "pay_item_code": code, "calculated_amount": Decimal(amount),
        "item_type": item_type, "direction": direction, "source": "synthetic",
    }


def _composition():
    rows = [
        _line("W1", "base_salary", "3500000"),
        _line("W1", "meal_allowance", "80000"),
        _line("W1", "meal_allowance", "70000"),
        _line("W1", "position_allowance", "150000"),
        _line("W1", "retroactive_pay", "50000", item_type="정산"),
        _line("W1", "national_pension", "150000", item_type="공제",
              direction="deduction"),
    ]
    rows2 = [
        _line("W2", "base_salary", "2100000"),
        _line("W2", "meal_allowance", "90000"),
    ]
    return {"worker_runs": {
        "W1": {
            "results": rows,
            "final_payroll": {"totals": {"pay_total": Decimal("3850000")}},
        },
        "W2": {
            "results": rows2,
            "final_payroll": {"totals": {"pay_total": Decimal("2190000")}},
        },
    }}


def _tax_policy():
    return {
        "taxability_review": {
            "schema_version": "1.0",
            "pay_items": {
                "base_salary": {
                    "status": "TAXABLE", "policy_ref": "SYNTHETIC-BASE-2026",
                },
                "meal_allowance": {
                    "status": "NON_TAXABLE",
                    "policy_ref": "SYNTHETIC-MEAL-2026",
                    "cap_per_worker_period": "100000",
                },
                "retroactive_pay": {
                    "status": "TAXABLE", "policy_ref": "SYNTHETIC-RETRO-2026",
                },
            },
        },
    }


class TaxabilityReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(
            (MODULE / "resources/pay-item-registry.json").read_text(
                encoding="utf-8"
            )
        )

    def _review(self, policy=None, composition=None, *, expected=None):
        return reviewer.review_payment_taxability(
            composition or _composition(),
            {} if policy is None else policy,
            self.registry,
            payroll_period="2026-07",
            expected_worker_ids=expected or ["W1", "W2"],
        )

    def test_all_unknown_without_policy_never_auto_non_taxable(self):
        report = self._review()
        self.assertEqual(report["totals"], {
            "taxable_candidate": "0",
            "non_taxable_candidate": "0",
            "review_required": "6040000",
            "employee_payment_total": "6040000",
        })
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertFalse(report["approved"])
        self.assertFalse(report["finalizable"])
        self.assertFalse(report["tax_and_insurance_computed"])
        self.assertFalse(report["policy_enabled"])
        self.assertTrue(
            all(row["classification"] == "REVIEW" for row in report["rows"])
        )

    def test_policy_candidate_split_is_capped_and_worker_specific(self):
        report = self._review(_tax_policy())
        self.assertEqual(report["totals"], {
            "taxable_candidate": "5600000",
            "non_taxable_candidate": "190000",
            "review_required": "250000",
            "employee_payment_total": "6040000",
        })
        meal_w1 = [
            row for row in report["rows"]
            if row["worker_id"] == "W1"
            and row["pay_item_code"] == "meal_allowance"
        ]
        self.assertEqual(
            sum(Decimal(x["amount"]) for x in meal_w1
                if x["classification"] == "NON_TAXABLE"),
            Decimal("100000"),
        )
        self.assertEqual(
            sum(Decimal(x["amount"]) for x in meal_w1
                if x["classification"] == "REVIEW"),
            Decimal("50000"),
        )
        retro = [r for r in report["rows"]
                 if r["pay_item_code"] == "retroactive_pay"]
        self.assertEqual(retro[0]["classification"], "REVIEW")
        self.assertTrue(all(not r["approved"] for r in report["rows"]))
        self.assertEqual(
            sum((Decimal(report["totals"][k]) for k in (
                "taxable_candidate", "non_taxable_candidate",
                "review_required",
            )), Decimal("0")), Decimal(report["totals"]["employee_payment_total"]),
        )

    def test_missing_worker_keeps_partial_review_unfinalizable(self):
        composition = _composition()
        composition["worker_runs"]["W2"]["final_payroll"] = None
        report = self._review(_tax_policy(), composition=composition)
        self.assertEqual(report["classified_worker_count"], 1)
        self.assertEqual(report["missing_worker_ids"], ["W2"])
        self.assertEqual(report["totals"]["employee_payment_total"], "3850000")
        self.assertFalse(report["finalizable"])

    def test_bad_rule_and_unjustified_non_taxable_cap_fail_closed(self):
        invalid = [
            {"meal_allowance": {"status": "NON_TAXABLE", "policy_ref": "X"}},
            {"meal_allowance": {"status": "NON_TAXABLE",
                                "policy_ref": "X", "cap_per_worker_period": "-100"}},
            {"meal_allowance": {"status": "NON_TAXABLE",
                                "policy_ref": "X", "cap_per_worker_period": "NaN"}},
            {"meal_allowance": {"status": "NON_TAXABLE",
                                "cap_per_worker_period": "100"}},
            {"base_salary": {"status": "UNKNOWN"}},
            {"national_pension": {"status": "TAXABLE", "policy_ref": "X"}},
            {"unknown_code": {"status": "TAXABLE", "policy_ref": "X"}},
        ]
        for item in invalid:
            with self.subTest(item=item):
                policy = {"taxability_review": {
                    "schema_version": "1.0", "pay_items": item,
                }}
                with self.assertRaises(reviewer.TaxabilityReviewError):
                    self._review(policy)

    def test_payroll_pay_total_must_conserve_all_payment_items(self):
        wrong = _composition()
        wrong["worker_runs"]["W1"]["final_payroll"]["totals"]["pay_total"] = "1"
        with self.assertRaisesRegex(
            reviewer.TaxabilityReviewError, "differs from Payroll pay_total"
        ):
            self._review(_tax_policy(), composition=wrong)

    def test_unknown_worker_rejected_without_fabricating_tax_amount(self):
        comp = _composition()
        comp["worker_runs"]["UNEXPECTED"] = comp["worker_runs"]["W2"]
        with self.assertRaisesRegex(
            reviewer.TaxabilityReviewError, "unexpected worker"
        ):
            self._review(_tax_policy(), composition=comp)

    def test_public_cli_emits_separate_taxability_sidecars_legacy_unchanged(self):
        # Reuse the exact two-worker synthetic demo from the historical
        # migration test, not any real payroll or HR data.
        spec = importlib.util.spec_from_file_location(
            "_taxability_migration_fixture",
            ROOT / "bhandara/tests/test_payroll_migration.py"
        )
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        with tempfile.TemporaryDirectory(prefix="bhandara-tax-review-") as temp:
            base = Path(temp)
            config = fixture._create_synthetic_inputs(base)
            policy_file = base / "company-policy.json"
            policy = json.loads(policy_file.read_text(encoding="utf-8"))
            policy["taxability_review"] = _tax_policy()["taxability_review"]
            policy_file.write_text(json.dumps(policy), encoding="utf-8")
            out = base / "review"
            proc = subprocess.run(
                [sys.executable, str(ROOT / "run.py"), "bhandara",
                 "payroll-calculator", "--config", str(config),
                 "--output-dir", str(out)],
                text=True, capture_output=True, check=False, cwd=ROOT,
            )
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn("TAXABILITY_REVIEW=REVIEW_REQUIRED", proc.stdout)
            review_path = out / "taxability-review.json"
            workbook = out / "taxability-review.xlsx"
            self.assertTrue(review_path.is_file())
            self.assertTrue(workbook.is_file())
            report = json.loads(review_path.read_text(encoding="utf-8"))
            self.assertTrue(report["policy_enabled"])
            self.assertFalse(report["approved"])
            self.assertFalse(report["tax_and_insurance_computed"])
            pay = json.loads((out / "payroll-calculation.json").read_text())
            self.assertFalse(pay["finalizable"])
            self.assertFalse(pay["ledger_committed"])
            self.assertNotIn("taxability_review", pay)
            book = load_workbook(workbook, read_only=True)
            try:
                self.assertEqual(book.sheetnames, [
                    "Review Totals", "Taxability Candidates",
                    "Uncalculated Workers",
                ])
            finally:
                book.close()


if __name__ == "__main__":
    unittest.main()
