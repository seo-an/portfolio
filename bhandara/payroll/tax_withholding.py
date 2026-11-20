"""P2-2: review taxability of calculated pay and externally approved withholding.

Do not infer taxable bases, statutory exemptions, withholding tables, or
employment income tax from salary alone. The *final* current employee pay items
must each be explicitly classified, including PTO-adjusted wages.

This module never completes final deductions/earnings or authorizes payroll.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping


class PayrollWithholdingError(ValueError):
    """Tax classification, item population, or withholding evidence disagrees."""


PLAN_FIELDS = frozenset({
    "schema_version", "period_from", "period_to", "policy_ref",
    "source_snapshot_ref", "employees",
})
EMPLOYEE_FIELDS = frozenset({
    "employee_id", "classifications", "income_tax_won",
    "local_income_tax_won", "withholding_ref",
    "approval_status", "not_pre_deducted",
})
CLASSIFICATION_FIELDS = frozenset({
    "source", "item_id", "taxable_won", "non_taxable_won", "classification_ref",
})
PAY_SOURCES = frozenset({
    "base_pay", "fixed_allowances", "overtime_allowances",
    "performance_bonuses",
})
TAX_ITEMS = (
    ("TAX_INCOME", "근로소득세", "income_tax_won"),
    ("TAX_LOCAL_INCOME", "지방소득세", "local_income_tax_won"),
)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PayrollWithholdingError(f"{field}: nonempty text required")
    value = value.strip()
    if value[0] in "=+-@\t\r\n":
        raise PayrollWithholdingError(f"{field}: unsafe reference")
    return value


def _won(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise PayrollWithholdingError(f"{field}: nonnegative integer KRW required")
    return value


def _current_pay_items(row: Mapping[str, Any]) -> dict[tuple[str, str], int]:
    expected = {("base_pay", "BASE"): _won(row["base_pay"], "base_pay")}
    for category in ("fixed_allowances", "overtime_allowances", "performance_bonuses"):
        for item in row[category]:
            code = _text(item["item_id"], f"{category}.item_id")
            key = (category, code)
            if key in expected:
                raise PayrollWithholdingError("payroll: duplicate earnings item")
            expected[key] = _won(item["amount"], f"{category}.amount")
    return expected


def _fixed_allowance_rules(
    coverage: Mapping[str, Any],
    fixed_map: Iterable[Mapping[str, Any]],
    assignments: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], tuple[str, str | None]]:
    """Follow selected contract IDs and levels, not every historical map row."""
    mapping = {}
    for item in fixed_map:
        key = (_text(item["allowance_id"], "allowance_id"),
               _text(item["level"], "level"))
        if key in mapping:
            raise PayrollWithholdingError("fixed map: duplicate allowance/level")
        mapping[key] = (item["payroll_taxability"], item.get("taxability_policy_ref"))
    by_contract: dict[str, dict[str, tuple[str, str | None]]] = defaultdict(dict)
    for row in assignments:
        contract_id = _text(row["contract_id"], "assignment.contract_id")
        code = _text(row["allowance_id"], "assignment.allowance_id")
        level = _text(row["level"], "assignment.level")
        if (code, level) not in mapping:
            raise PayrollWithholdingError("fixed assignment: missing taxability map")
        if code in by_contract[contract_id]:
            raise PayrollWithholdingError("fixed assignment: duplicate allowance ID")
        by_contract[contract_id][code] = mapping[(code, level)]

    result = {}
    for worker, segments in coverage["segments_by_employee"].items():
        seen: dict[str, tuple[str, str | None]] = {}
        for segment in segments:
            for code, decision in by_contract.get(segment["contract_id"], {}).items():
                if code in seen and seen[code] != decision:
                    raise PayrollWithholdingError(
                        "fixed allowance taxability changes across selected contracts"
                    )
                seen[code] = decision
        for code, decision in seen.items():
            result[(worker, code)] = decision
    return result


def review_taxability_and_withholding(
    payroll_rows: Iterable[Mapping[str, Any]],
    coverage: Mapping[str, Any],
    fixed_map: Iterable[Mapping[str, Any]],
    assignments: Iterable[Mapping[str, Any]],
    *,
    withholding_plan: Mapping[str, Any],
    period_from: str,
    period_to: str,
) -> dict[str, Any]:
    """Return *candidate* income/local tax deductions and auditable pay splits.

    Taxable and exempt amounts must add to each already calculated pay item.
    External tax amounts are passed through without inventing a tax table.
    """
    if not isinstance(withholding_plan, Mapping) or set(withholding_plan) != PLAN_FIELDS:
        raise PayrollWithholdingError("withholding_plan: exact fields required")
    if withholding_plan["schema_version"] != "0.1":
        raise PayrollWithholdingError("withholding_plan: unsupported schema")
    if ((withholding_plan["period_from"], withholding_plan["period_to"])
            != (period_from, period_to)
            or (coverage["period_from"], coverage["period_to"]) != (period_from, period_to)):
        raise PayrollWithholdingError("withholding_plan: period mismatch")
    _text(withholding_plan["policy_ref"], "withholding_plan.policy_ref")
    _text(withholding_plan["source_snapshot_ref"], "withholding_plan.source_snapshot_ref")
    reports = withholding_plan["employees"]
    if not isinstance(reports, (list, tuple)):
        raise PayrollWithholdingError("employees: list required")
    roster = {}
    for row in payroll_rows:
        employee = _text(row.get("employee_id"), "payroll.employee_id")
        if employee in roster:
            raise PayrollWithholdingError("payroll: duplicate employee")
        roster[employee] = row
    if set(roster) != set(coverage["segments_by_employee"]):
        raise PayrollWithholdingError("payroll: incomplete contract roster")

    fixed_rules = _fixed_allowance_rules(coverage, fixed_map, assignments)
    given = {}
    for report in reports:
        if not isinstance(report, Mapping) or set(report) != EMPLOYEE_FIELDS:
            raise PayrollWithholdingError("employee: exact fields required")
        worker = _text(report["employee_id"], "employee_id")
        if worker in given or worker not in roster:
            raise PayrollWithholdingError("employee: duplicate or unknown worker")
        if report["approval_status"] != "APPROVED":
            raise PayrollWithholdingError("withholding: external approval required")
        if report["not_pre_deducted"] is not True:
            raise PayrollWithholdingError("withholding: tax previously deducted")
        _text(report["withholding_ref"], "withholding_ref")
        _won(report["income_tax_won"], "income_tax_won")
        _won(report["local_income_tax_won"], "local_income_tax_won")
        if not isinstance(report["classifications"], (list, tuple)):
            raise PayrollWithholdingError("classifications: list required")
        given[worker] = report
    if set(given) != set(roster):
        raise PayrollWithholdingError("withholding: complete employee roster required")

    withholding_items: dict[str, list[dict[str, Any]]] = {}
    audits = []
    for worker in sorted(roster):
        expected = _current_pay_items(roster[worker])
        submitted = {}
        classification_refs = {}
        taxable = 0
        exempt = 0
        for entry in given[worker]["classifications"]:
            if not isinstance(entry, Mapping) or set(entry) != CLASSIFICATION_FIELDS:
                raise PayrollWithholdingError("classification: exact fields required")
            category = _text(entry["source"], "classification.source")
            code = _text(entry["item_id"], "classification.item_id")
            if category not in PAY_SOURCES:
                raise PayrollWithholdingError("classification: unknown pay category")
            key = (category, code)
            if key not in expected or key in submitted:
                raise PayrollWithholdingError("classification: missing pay item or duplicate")
            taxable_amount = _won(entry["taxable_won"], "taxable_won")
            exempt_amount = _won(entry["non_taxable_won"], "non_taxable_won")
            if taxable_amount + exempt_amount != expected[key]:
                raise PayrollWithholdingError(
                    "classification: taxable + exempt must equal candidate item amount"
                )
            ref = _text(entry["classification_ref"], "classification_ref")
            if category == "fixed_allowances":
                rule = fixed_rules.get((worker, code))
                if rule is None:
                    raise PayrollWithholdingError("classification: fixed allowance not assigned")
                classification, policy_ref = rule
                if classification == "TAXABLE" and exempt_amount:
                    raise PayrollWithholdingError(
                        "classification: fixed allowance TAXABLE map forbids exempt amount"
                    )
                if classification not in ("TAXABLE", "NON_TAXABLE", "REVIEW"):
                    raise PayrollWithholdingError("classification: unknown fixed map category")
                if exempt_amount:
                    _text(policy_ref, "fixed allowance taxability_policy_ref")
            submitted[key] = {"taxable_won": taxable_amount,
                              "non_taxable_won": exempt_amount}
            classification_refs[key] = ref
            taxable += taxable_amount
            exempt += exempt_amount
        if set(submitted) != set(expected):
            raise PayrollWithholdingError(
                "classification: every selected base/allowance/overtime/bonus item required"
            )
        report = given[worker]
        withholding_items[worker] = [
            {"item_id": item_id, "label": label, "amount": report[field]}
            for item_id, label, field in TAX_ITEMS
        ]
        audits.append({
            "employee_id": worker,
            "taxable_earnings_won": taxable,
            "non_taxable_earnings_won": exempt,
            "candidate_earnings_won": sum(expected.values()),
            "item_classifications": [
                {"source": cat, "item_id": code, **submitted[(cat, code)],
                 "classification_ref": classification_refs[(cat, code)]}
                for cat, code in sorted(submitted)
            ],
            "income_tax_candidate_won": report["income_tax_won"],
            "local_income_tax_candidate_won": report["local_income_tax_won"],
            "withholding_ref": report["withholding_ref"],
        })
    return {
        "schema_version": "0.1",
        "period_from": period_from,
        "period_to": period_to,
        "policy_ref": withholding_plan["policy_ref"],
        "source_snapshot_ref": withholding_plan["source_snapshot_ref"],
        "employees": audits,
        "items_by_employee": withholding_items,
        "statutory_tax_tables": "NOT_COMPUTED",
        "source_authenticity": "NOT_AUTHENTICATED_BY_THIS_MODULE",
        "deductions_complete": False,
        "earnings_complete": False,
        "approval_state": "NOT_APPROVED",
    }
