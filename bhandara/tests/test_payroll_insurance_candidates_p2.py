"""P2-1 insurance candidates: exact bases, eligibility and existing one-sheet XLSX."""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from openpyxl import Workbook, load_workbook

from bhandara.common.utils.hashing import sha256_file
from bhandara.payroll.contract_scoped_overtime import (
    ContractOvertimeAdapterError, build_contract_scoped_overtime_preview,
)
from bhandara.payroll.input_excel import read_payroll_inputs
from bhandara.payroll.insurance_candidates import (
    InsuranceCandidateError, calculate_insurance_candidates,
)
from bhandara.payroll.output_excel import write_payroll_result_xlsx
from bhandara.payroll.settlement_coverage import validate_settlement_coverage
from bhandara.tests.test_payroll_attendance_settlement_p1 import wage_plan
from bhandara.tests.test_payroll_contract_scoped_overtime_p1 import ROLES, ROLLUP, source_registry
from bhandara.tests.test_payroll_input_reader_p0 import SCHEMA, SAMPLES
from bhandara.tests.test_payroll_overtime_candidates_p1 import policy, rate
from bhandara.tests.test_payroll_segmented_settlement_p1 import (
    FROM, TO, allocated, contract, employment, plan, split, split_plan,
)
from bhandara.tests.test_payroll_worktime_bridge_p1 import fact
from bhandara.worktime.output_excel import write_worktime_xlsx

ALL_ROLES = (*ROLES, "deduction_map")


def assessment(worker="0001", **changes):
    row = {
        "employee_id": worker,
        "national_pension_basis_won": 3000000,
        "health_insurance_basis_won": 3000000,
        "employment_insurance_basis_won": 3000000,
        "national_pension_applicable": True,
        "health_insurance_applicable": True,
        "longterm_care_applicable": True,
        "employment_insurance_applicable": True,
        "assessment_ref": f"SYNTHETIC-ASSESSMENT-{worker}",
        "applicability_ref": f"SYNTHETIC-STATUS-{worker}",
        "approval_status": "APPROVED",
        "not_pre_deducted": True,
    }
    row.update(changes)
    return row


def assessment_plan(*, records=None, **changes):
    row = {
        "schema_version": "0.1",
        "period_from": FROM, "period_to": TO,
        "policy_ref": "SYNTHETIC-ROUNDING-POLICY",
        "rounding_mode": "DOWN",
        "longterm_care_base_mode": "ROUNDED_HEALTH_PREMIUM",
        "assessments": [assessment()] if records is None else records,
    }
    row.update(changes)
    return row


def calculate(*, records=None, mapping=None, contracts=None,
              settlement=None, **changes):
    coverage = validate_settlement_coverage(
        [contract()] if contracts is None else contracts,
        plan=plan() if settlement is None else settlement,
        period_from=FROM, period_to=TO,
    )
    return calculate_insurance_candidates(
        coverage,
        [deepcopy(SAMPLES["deduction_map"])] if mapping is None else mapping,
        assessment_plan=assessment_plan(records=records, **changes),
        period_from=FROM, period_to=TO,
    )


class InsuranceCandidatesTests(unittest.TestCase):
    def test_distinct_bases_and_health_premium_longterm_care(self):
        out = calculate(records=[assessment(
            health_insurance_basis_won=2000000,
            employment_insurance_basis_won=1200000,
        )])
        self.assertEqual(out["employees"][0]["candidate_by_kind_won"], {
            "national_pension": 142500,
            "health_insurance": 71900,
            "longterm_care": 9447,
            "employment_insurance": 10800,
        })
        self.assertEqual(out["employees"][0]["candidate_total_won"], 234647)
        self.assertEqual(out["tax_withholding"], "NOT_ASSESSED")
        self.assertFalse(out["deductions_complete"])

    def test_explicit_exemption_and_incompatible_applicability(self):
        out = calculate(records=[assessment(
            national_pension_applicable=False,
            longterm_care_applicable=False,
            employment_insurance_applicable=False,
        )])
        self.assertEqual(out["employees"][0]["candidate_total_won"], 107850)
        with self.assertRaisesRegex(InsuranceCandidateError, "health insurance must"):
            calculate(records=[assessment(
                health_insurance_applicable=False, longterm_care_applicable=True,
            )])

    def test_rounding_policy_is_explicit_and_changes_fractions(self):
        row = dict(SAMPLES["deduction_map"], **{
            key: Decimal("0.5") for key in (
                "national_pension", "health_insurance",
                "longterm_care", "employment_insurance",
            )
        })
        sample = [assessment(
            national_pension_basis_won=3, health_insurance_basis_won=3,
            employment_insurance_basis_won=3,
        )]
        low = calculate(mapping=[row], records=sample)
        high = calculate(mapping=[row], records=sample, rounding_mode="HALF_UP")
        self.assertEqual(low["employees"][0]["candidate_total_won"], 3)
        self.assertEqual(high["employees"][0]["candidate_total_won"], 7)

    def test_missing_unknown_duplicate_pre_deducted_and_bad_bases_fail(self):
        for records in (
            [], [assessment(), assessment()], [assessment(worker="0002")],
            [assessment(approval_status="PENDING")],
            [assessment(not_pre_deducted=False)],
            [assessment(national_pension_basis_won=-1)],
            [assessment(health_insurance_basis_won=1.5)],
            [assessment(employment_insurance_basis_won=None)],
            [assessment(national_pension_applicable=1)],
            [assessment(assessment_ref="")],
            [assessment(applicability_ref="")],
            [dict(assessment(), extra=True)],
        ):
            with self.subTest(records=records), self.assertRaises(InsuranceCandidateError):
                calculate(records=records)

    def test_expired_deduction_map_missing_source_and_invalid_policy_fail(self):
        for change in (
            {"effective_from": "2026-11-02"},
            {"effective_to": "2026-11-29"},
            {"source_ref": ""}, {"deduction_code": "D02"},
        ):
            with self.subTest(change=change), self.assertRaises(InsuranceCandidateError):
                calculate(mapping=[dict(SAMPLES["deduction_map"], **change)])
        for change in (
            {"rounding_mode": "DEFAULT"},
            {"longterm_care_base_mode": "SALARY"},
            {"period_from": "2026-10-01"},
            {"policy_ref": ""}, {"schema_version": "0.2"},
            {"extra": True},
        ):
            with self.subTest(change=change), self.assertRaises(InsuranceCandidateError):
                calculate(**change)

    def test_recontract_same_code_allowed_but_changed_code_blocked(self):
        self.assertEqual(
            calculate(contracts=split(), settlement=split_plan())["employees"][0]["deduction_code"],
            "D01",
        )
        bad = split()
        bad[1]["deduction_code"] = "D02"
        with self.assertRaisesRegex(InsuranceCandidateError, "multiple insurance"):
            calculate(contracts=bad, settlement=split_plan())

    def test_fifty_workers_must_have_explicit_status_even_when_exempt(self):
        workers = [f"{i:04d}" for i in range(1, 51)]
        contracts = [contract(worker=w, contract_id=f"C-{w}") for w in workers]
        settlement = plan(
            facts=[employment(worker=w) for w in workers],
            allocations=[allocated(worker=w, contract_id=f"C-{w}") for w in workers],
        )
        rows = [assessment(
            worker=w, national_pension_applicable=(w == "0017"),
            health_insurance_applicable=(w == "0017"),
            longterm_care_applicable=(w == "0017"),
            employment_insurance_applicable=(w == "0017"),
        ) for w in workers]
        out = calculate(contracts=contracts, settlement=settlement, records=rows)
        self.assertEqual(len(out["employees"]), 50)
        self.assertEqual(out["employees"][16]["employee_id"], "0017")
        self.assertEqual(sum(row["candidate_total_won"] > 0 for row in out["employees"]), 1)
        with self.assertRaisesRegex(InsuranceCandidateError, "all selected employees"):
            calculate(contracts=contracts, settlement=settlement, records=rows[:-1])


class InsuranceOneSheetExcelTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "payroll").mkdir()

    def put(self, role, rows):
        spec = SCHEMA["workbooks"][role]
        book = Workbook()
        book.active.title = spec["sheet"]
        book.active.append(spec["columns"])
        for row in rows:
            book.active.append([row.get(column) for column in spec["columns"]])
        book.save(self.root / "payroll" / spec["filename"])
        book.close()

    def run_flow(self, insurance=None, *, include_map=True):
        data = {
            "contracts": [contract()],
            "allowance_assignments": [],
            "fixed_allowance_map": [deepcopy(SAMPLES["fixed_allowance_map"])],
            "bonus_budget": [], "bonus_allocation": [],
            "overtime_rules": [rate(minimum_minutes=0)],
            "deduction_map": [deepcopy(SAMPLES["deduction_map"])],
        }
        roles = ALL_ROLES if include_map else ROLES
        for role in roles:
            self.put(role, data[role])
        inputs = read_payroll_inputs(self.root, roles=roles)
        wt = self.root / "worktime-result.xlsx"
        if not wt.exists():
            write_worktime_xlsx({"schema_version": "0.1", "rows": [
                fact(day="2026-11-02", actual_min=480),
            ]}, wt)
        return build_contract_scoped_overtime_preview(
            inputs, wt, settlement_plan=plan(),
            attendance_plan=wage_plan(items=[], sha=sha256_file(wt)),
            period_from=FROM, period_to=TO,
            verified_work=[], approved_segments=[],
            evidence_registry=source_registry([], [], [rate(minimum_minutes=0)]),
            rate_policy=policy(reference_day_minutes_by_contract={"C-OLD": 480}),
            rollup_policy=ROLLUP, insurance_assessment_plan=insurance,
        )

    def test_seven_excel_and_dynamic_insurance_columns_single_sheet(self):
        out = self.run_flow(assessment_plan())
        row = out["payroll_register"]["rows"][0]
        self.assertEqual(row["deductions:INS_NATIONAL_PENSION"], 142500)
        self.assertEqual(row["deductions:INS_HEALTH_INSURANCE"], 107850)
        self.assertEqual(row["deductions:INS_LONGTERM_CARE"], 14171)
        self.assertEqual(row["deductions:INS_EMPLOYMENT_INSURANCE"], 27000)
        self.assertIsNone(row["gross_pay"])
        self.assertIsNone(row["deduction_total"])
        self.assertIsNone(row["net_pay"])
        self.assertEqual(out["approval_state"], "NOT_APPROVED")
        xlsx = self.root / "payroll-result.xlsx"
        write_payroll_result_xlsx(out["payroll_register"], xlsx)
        book = load_workbook(xlsx, read_only=True)
        try:
            self.assertEqual(book.sheetnames, ["PAYROLL"])
            self.assertEqual(len(book["PAYROLL"][1]), len(out["payroll_register"]["columns"]))
        finally:
            book.close()

    def test_optional_absence_keeps_original_empty_deduction_columns(self):
        out = self.run_flow()
        self.assertFalse(any(
            col["key"].startswith("deductions:")
            for col in out["payroll_register"]["columns"]
        ))
        self.assertNotIn("insurance_review", out)

    def test_absent_deduction_map_role_blocks_without_guessing_rates(self):
        with self.assertRaisesRegex(ContractOvertimeAdapterError, "DEDUCTION MAP"):
            self.run_flow(assessment_plan(), include_map=False)

    def test_all_exempt_staff_has_no_deduction_column(self):
        out = self.run_flow(assessment_plan(records=[assessment(
            national_pension_applicable=False,
            health_insurance_applicable=False,
            longterm_care_applicable=False,
            employment_insurance_applicable=False,
        )]))
        self.assertFalse(any(
            col["key"].startswith("deductions:")
            for col in out["payroll_register"]["columns"]
        ))
        self.assertEqual(out["insurance_review"]["employees"][0]["candidate_total_won"], 0)


if __name__ == "__main__":
    unittest.main()
