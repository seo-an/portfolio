"""Common employee insurance states and employer-only industrial premium boundaries."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from decimal import Decimal

from openpyxl import Workbook

from bhandara.payroll.employer_insurance import (
    EmployerInsuranceError, calculate_employer_industrial_insurance,
)
from bhandara.payroll.insurance_candidates import (
    InsuranceCandidateError, apply_common_insurance_applicability,
    read_employee_insurance_status, review_employee_insurance_status,
)
from bhandara.payroll.output import (
    build_employee_payroll_view, build_payroll_register,
)


def industrial_plan(*, records=None, **changed):
    payload = {
        "schema_version": "0.1",
        "period_from": "2026-11-01", "period_to": "2026-11-30",
        "policy_ref": "SYNTHETIC-BUSINESS-INSURANCE-POLICY",
        "rounding_mode": "DOWN",
        "assessments": [] if records is None else records,
    }
    payload.update(changed)
    return payload


def industrial(worker, *, basis=3000000, rate="0.007", **changed):
    row = {
        "employee_id": worker,
        "basis_won": basis,
        "approved_total_rate": rate,
        "assessment_ref": "SYNTHETIC-WAGES-BASE",
        "rate_ref": "SYNTHETIC-WORKPLACE-RATE",
        "approval_status": "APPROVED",
        "not_pre_included": True,
    }
    row.update(changed)
    return row


def payroll_row(worker="0001"):
    return {
        "employee_id": worker,
        "base_pay": 3000000,
        "fixed_allowances": [],
        "overtime_allowances": [],
        "performance_bonuses": [],
        "deductions": [{"item_id": "TAX_INCOME", "label": "소득세", "amount": 50000}],
        "earnings_complete": False, "deductions_complete": False,
    }


class CommonEmployeeInsuranceTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "employee.xlsx"
        self.columns = [
            "employee_id", "national_pension_acquired_on",
            "health_insurance_acquired_on", "employment_insurance_acquired_on",
            "industrial_accident_acquired_on",
        ]

    def write(self, records):
        wb = Workbook()
        active = wb.active
        active.title = "재직자"
        active.append(self.columns)
        for record in records:
            active.append(record)
        terminated = wb.create_sheet("퇴사자")
        terminated.append(self.columns)
        wb.save(self.path)
        wb.close()

    def status(self, roster=("0001",)):
        return read_employee_insurance_status(
            self.path, employee_ids=roster, period_to="2026-11-30",
        )

    def test_acquisition_blank_not_enrolled_and_future_dates(self):
        self.write([
            ("0001", "", "2026-06-02", "미가입", "2026-07-01"),
            ("0002", "2026-12-01", None, None, None),
        ])
        values = self.status(("0001", "0002"))
        self.assertEqual(values["0001"]["national_pension"]["state"], "EXCLUDED")
        self.assertEqual(values["0001"]["health_insurance"]["state"], "ENROLLED")
        self.assertEqual(values["0001"]["employment_insurance"]["state"], "NOT_ENROLLED")
        self.assertEqual(values["0002"]["national_pension"]["state"], "NOT_YET_ACQUIRED")
        reasons = review_employee_insurance_status(
            values, employee_ids=("0001", "0002"), insurance_review=None,
        )
        self.assertIn("INSURANCE_NOT_ENROLLED:employment_insurance", reasons["0001"])
        self.assertIn("INSURANCE_PREMIUM_UNVERIFIED:health_insurance", reasons["0001"])
        self.assertNotIn("INSURANCE_NOT_ENROLLED:national_pension", reasons["0001"])
        self.assertNotIn("INSURANCE_NOT_ENROLLED:industrial_accident", reasons["0001"])
        self.assertEqual(reasons["0002"], [])

    def test_common_status_drives_insurance_applicability(self):
        self.write([("0001", "", "2026-03-01", "미가입", "2026-04-01")])
        state = self.status()
        source = {"assessments": [{
            "employee_id": "0001", "health_insurance_basis_won": 3200000,
            "assessment_ref": "ASSESSMENT-1",
        }]}
        normalized = apply_common_insurance_applicability(source, state)["assessments"][0]
        self.assertIs(normalized["national_pension_applicable"], False)
        self.assertIs(normalized["health_insurance_applicable"], True)
        self.assertIs(normalized["employment_insurance_applicable"], False)
        self.assertIs(normalized["longterm_care_applicable"], True)
        with self.assertRaisesRegex(InsuranceCandidateError, "conflicts"):
            apply_common_insurance_applicability({
                "assessments": [{
                    "employee_id": "0001", "national_pension_applicable": True,
                }]
            }, state)

    def test_wrong_header_duplicate_or_missing_employee_rejected(self):
        self.write([("0001", "", "", "", "")])
        with self.assertRaisesRegex(InsuranceCandidateError, "missing selected"):
            self.status(("0001", "0002"))
        wb = Workbook()
        wb.active.title = "재직자"
        wb.active.append(self.columns[:-1])
        wb.active.append(("0001", "", "", ""))
        wb.create_sheet("퇴사자").append(self.columns)
        wb.save(self.path)
        wb.close()
        with self.assertRaisesRegex(InsuranceCandidateError, "invalid employee workbook"):
            self.status()

    def test_invalid_future_status_is_not_guessable_from_age(self):
        self.write([("0001", 1, "2026-02-01", "2026-02-01", "2026-02-01")])
        with self.assertRaisesRegex(InsuranceCandidateError, "must be a date"):
            self.status()


class EmployerIndustrialInsuranceTests(TestCase):
    def setUp(self):
        self.states = {
            "0001": {"industrial_accident": {
                "state": "ENROLLED", "acquired_on": "2026-01-01",
            }},
            "0002": {"industrial_accident": {
                "state": "EXCLUDED", "acquired_on": None,
            }},
            "0003": {"industrial_accident": {
                "state": "NOT_ENROLLED", "acquired_on": None,
            }},
        }

    def calculate(self, records=None, **changes):
        return calculate_employer_industrial_insurance(
            self.states,
            plan=industrial_plan(
                records=[industrial("0001")] if records is None else records,
                **changes,
            ),
            period_from="2026-11-01", period_to="2026-11-30",
        )

    def test_employer_only_cost_and_employee_view_are_separate(self):
        result = self.calculate()
        self.assertEqual(result["amounts_by_employee"], {
            "0001": 21000, "0002": 0, "0003": 0,
        })
        self.assertEqual(result["total_candidate_won"], 21000)
        self.assertEqual(
            result["employer_review_flags"]["0003"],
            ["EMPLOYER_INDUSTRIAL_NOT_ENROLLED"],
        )
        self.assertEqual(result["employer_review_flags"]["0002"], [])
        self.assertFalse(result["worker_deduction"])
        self.assertFalse(result["employer_cost_complete"])
        register = build_payroll_register(
            [payroll_row("0001"), payroll_row("0002")],
            show_partial_totals=True,
            review_reasons_by_employee={"0001": [], "0002": []},
            employer_industrial_by_employee={
                "0001": result["amounts_by_employee"]["0001"],
                "0002": result["amounts_by_employee"]["0002"],
            },
        )
        first, second = register["rows"]
        self.assertEqual(first["gross_pay"], 3000000)
        self.assertEqual(first["deduction_total"], 50000)
        self.assertEqual(first["net_pay"], 2950000)
        self.assertEqual(first["employer_industrial"], 21000)
        self.assertEqual(first["known_company_outlay"], 3021000)
        self.assertEqual(second["known_company_outlay"], 3000000)
        self.assertIsNone(second["employer_industrial"])
        self.assertEqual(register["employer_cost_scope"],
                         "INTERNAL_ADMIN_ONLY_KNOWN_COST_COMPONENTS")
        employee_view = build_employee_payroll_view(register, employee_id="0001")
        self.assertEqual(len(employee_view["rows"]), 1)
        self.assertNotIn("employer_industrial", employee_view["rows"][0])
        self.assertNotIn("known_company_outlay", employee_view["rows"][0])
        self.assertTrue(all(
            col["key"] not in ("employer_industrial", "known_company_outlay")
            for col in employee_view["columns"]
        ))
        self.assertEqual(employee_view["rows"][0]["net_pay"], 2950000)

    def test_excluded_or_unregistered_workers_have_no_premium_or_deduction(self):
        output = self.calculate()
        self.assertEqual(output["employees"][1]["candidate_won"], 0)
        self.assertEqual(output["employees"][2]["candidate_won"], 0)
        self.assertEqual(len(output["employees"]), 3)

    def test_external_basis_and_rate_are_mandatory_and_exact(self):
        for rows in (
            [], [industrial("0002")],
            [industrial("0001"), industrial("0001")],
            [industrial("0001", basis=-1)],
            [industrial("0001", basis=3.5)],
            [industrial("0001", rate=-0.1)],
            [industrial("0001", rate="nan")],
            [industrial("0001", rate=1.1)],
            [industrial("0001", approved_total_rate=0.12)],
            [industrial("0001", approval_status="DRAFT")],
            [industrial("0001", rate_ref="")],
            [industrial("0001", not_pre_included=False)],
        ):
            with self.subTest(rows=rows), self.assertRaises(EmployerInsuranceError):
                self.calculate(records=rows)

    def test_all_excluded_employer_cost_omits_empty_insurance_column(self):
        result = build_payroll_register(
            [payroll_row("0002"), payroll_row("0003")],
            show_partial_totals=True,
            review_reasons_by_employee={"0002": [], "0003": []},
            employer_industrial_by_employee={"0002": 0, "0003": 0},
        )
        keys = [column["key"] for column in result["columns"]]
        self.assertNotIn("employer_industrial", keys)
        self.assertIn("known_company_outlay", keys)
        self.assertNotIn("employer_industrial", result["rows"][0])
        self.assertEqual(result["rows"][0]["known_company_outlay"], 3000000)

    def test_rate_rounding_uses_explicit_policy(self):
        expected = self.calculate([industrial("0001", basis=101, rate="0.015")])
        self.assertEqual(expected["amounts_by_employee"]["0001"], 1)
        different = self.calculate(
            [industrial("0001", basis=101, rate="0.015")],
            rounding_mode="HALF_UP",
        )
        self.assertEqual(different["amounts_by_employee"]["0001"], 2)


if __name__ == "__main__":
    import unittest
    unittest.main()
