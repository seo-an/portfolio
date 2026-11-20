"""Review-only, two-tier Payroll register output contract.

This module renders already-verified monetary items. It never derives overtime,
insurance, withholding, tax-exempt eligibility, approval, or settlement.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


class PayrollOutputError(ValueError):
    """An output input is malformed or could create misleading payroll."""


SHEET_NAME = "PAYROLL"
FILENAME = "payroll-result.xlsx"
SCHEMA_VERSION = "0.1"

# Stable display order. A category with no nonzero amount is omitted entirely.
ITEM_GROUPS = (
    ("fixed_allowances", "고정수당"),
    ("overtime_allowances", "초과근무수당"),
    ("performance_bonuses", "성과급"),
    ("deductions", "공제"),
)


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PayrollOutputError(f"{field}: nonempty text required")
    result = value.strip()
    # Treat spreadsheet-leading control/formula characters as unsafe metadata.
    if result[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        raise PayrollOutputError(f"{field}: unsafe spreadsheet text")
    return result


def _amount(value: Any, field: str, *, allow_negative: bool = True) -> int:
    if isinstance(value, bool) or value is None or isinstance(value, float):
        raise PayrollOutputError(f"{field}: integer KRW required")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PayrollOutputError(f"{field}: invalid monetary amount") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise PayrollOutputError(f"{field}: integer KRW required")
    if not allow_negative and number < 0:
        raise PayrollOutputError(f"{field}: negative base pay not allowed")
    return int(number)


def _items(source: Any, employee_id: str, category: str) -> list[dict[str, Any]]:
    if not isinstance(source, (list, tuple)):
        raise PayrollOutputError(f"{employee_id}.{category}: list required")
    seen: set[str] = set()
    normalized = []
    for item in source:
        if not isinstance(item, Mapping):
            raise PayrollOutputError(f"{employee_id}.{category}: object required")
        code = _required_text(item.get("item_id"), f"{category}.item_id")
        label = _required_text(item.get("label"), f"{category}.label")
        if code in seen:
            raise PayrollOutputError(f"{employee_id}.{category}: duplicate item_id {code}")
        seen.add(code)
        normalized.append({
            "item_id": code,
            "label": label,
            "amount": _amount(item.get("amount"), f"{category}.{code}.amount"),
        })
    return normalized


def _columns_for_group(
    group_key: str,
    group_name: str,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    labels: dict[str, str] = {}
    active: set[str] = set()
    for row in rows:
        for item in row[group_key]:
            code, label, amount = item["item_id"], item["label"], item["amount"]
            if code in labels and labels[code] != label:
                raise PayrollOutputError(f"{group_key}.{code}: inconsistent label")
            labels[code] = label
            if amount != 0:
                active.add(code)
    # Reused labels must remain distinguishable through their stable IDs.
    label_counts: dict[str, int] = {}
    for code in active:
        label_counts[labels[code]] = label_counts.get(labels[code], 0) + 1
    return [{
        "key": f"{group_key}:{code}",
        "group": group_name,
        "label": f"{labels[code]} [{code}]" if label_counts[labels[code]] > 1 else labels[code],
        "item_id": code,
        "source": group_key,
    } for code in sorted(active)]


def build_payroll_register(
    rows: Iterable[Mapping[str, Any]],
    *,
    show_partial_totals: bool = False,
    review_reasons_by_employee: Mapping[str, list[str]] | None = None,
    employer_industrial_by_employee: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Build the existing dynamic one-sheet register, optionally showing known sums.

    The independent preview keeps blank totals by default. The integrated
    Flow sets show_partial_totals=True: known amounts are added ONCE and
    incomplete-source flags are recorded separately. Neither is authorization
    to pay the displayed net candidate.
    """
    if type(show_partial_totals) is not bool:
        raise PayrollOutputError("show_partial_totals: explicit boolean required")
    if review_reasons_by_employee is not None and not show_partial_totals:
        raise PayrollOutputError("review_reasons_by_employee: partial totals required")
    if employer_industrial_by_employee is not None and not show_partial_totals:
        raise PayrollOutputError("employer_industrial_by_employee: partial totals required")
    normalized: list[dict[str, Any]] = []
    seen_employees: set[str] = set()
    for source in rows:
        if not isinstance(source, Mapping):
            raise PayrollOutputError("employee row must be an object")
        employee_id = _required_text(source.get("employee_id"), "employee_id")
        if employee_id in seen_employees:
            raise PayrollOutputError(f"duplicate employee_id: {employee_id}")
        seen_employees.add(employee_id)
        name = source.get("employee_name")
        if name not in (None, ""):
            name = _required_text(name, "employee_name")
        else:
            name = None
        complete = {}
        for field in ("earnings_complete", "deductions_complete"):
            value = source.get(field)
            if type(value) is not bool:
                raise PayrollOutputError(f"{employee_id}.{field}: explicit boolean required")
            complete[field] = value
        row = {
            "employee_id": employee_id,
            "employee_name": name,
            "base_pay": _amount(source.get("base_pay"), "base_pay", allow_negative=False),
            **complete,
        }
        for key, _ in ITEM_GROUPS:
            row[key] = _items(source.get(key, []), employee_id, key)
        normalized.append(row)
    if not normalized:
        raise PayrollOutputError("at least one employee required")
    if review_reasons_by_employee is not None:
        if not isinstance(review_reasons_by_employee, Mapping):
            raise PayrollOutputError("review_reasons_by_employee: mapping required")
        if set(review_reasons_by_employee) != seen_employees:
            raise PayrollOutputError("review_reasons_by_employee: employee roster mismatch")
        for reasons in review_reasons_by_employee.values():
            if not isinstance(reasons, list) or len(reasons) != len(set(reasons)):
                raise PayrollOutputError("review_reasons_by_employee: distinct list required")
            for reason in reasons:
                _required_text(reason, "review_reason")

    if employer_industrial_by_employee is not None:
        if not isinstance(employer_industrial_by_employee, Mapping):
            raise PayrollOutputError("employer industrial: mapping required")
        if set(employer_industrial_by_employee) != seen_employees:
            raise PayrollOutputError("employer industrial: complete employee roster required")
        for amount in employer_industrial_by_employee.values():
            if type(amount) is not int or amount < 0:
                raise PayrollOutputError("employer industrial: nonnegative integer KRW required")

    has_names = any(row["employee_name"] is not None for row in normalized)
    columns = [{"key": "employee_id", "group": "직원정보", "label": "직원 ID"}]
    if has_names:
        columns.append({"key": "employee_name", "group": "직원정보", "label": "직원명"})
    columns.append({"key": "base_pay", "group": "기본급", "label": "기본급"})

    earning_fields = {"fixed_allowances", "overtime_allowances", "performance_bonuses"}
    for key, label in ITEM_GROUPS:
        if key in earning_fields:
            columns.extend(_columns_for_group(key, label, normalized))
    columns.append({"key": "gross_pay", "group": "지급합계", "label": "지급합계"})
    columns.extend(_columns_for_group("deductions", "공제", normalized))
    columns.extend([
        {"key": "deduction_total", "group": "공제합계", "label": "공제합계"},
        {"key": "net_pay", "group": "실지급액", "label": "실지급액"},
    ])
    if employer_industrial_by_employee is not None:
        if any(employer_industrial_by_employee.values()):
            columns.append({
                "key": "employer_industrial", "group": "사업주 부담·회사 전용",
                "label": "산재보험료(사업주)",
            })
        columns.append({
            "key": "known_company_outlay",
            "group": "회사 비용·확인분", "label": "회사 비용(확인분)",
        })
    columns.append({"key": "review_status", "group": "검토", "label": "검토상태"})

    result_rows: list[dict[str, Any]] = []
    review_flags: dict[str, list[str]] = {}
    for source in normalized:
        item_maps = {
            category: {item["item_id"]: item["amount"] for item in source[category]}
            for category, _ in ITEM_GROUPS
        }
        earnings_total = source["base_pay"] + sum(
            sum(item_maps[category].values()) for category in earning_fields
        )
        deductions_total = sum(item_maps["deductions"].values())
        if review_reasons_by_employee is None:
            # Backward-compatible standalone Preview: retain the historical
            # earnings/deductions completion markers in this mode only.
            flags = []
            if not source["earnings_complete"]:
                flags.append("EARNINGS_UNVERIFIED")
            if not source["deductions_complete"]:
                flags.append("DEDUCTIONS_UNVERIFIED")
        else:
            # Integrated Flow: only tax and social-insurance checks determine
            # 검증요청. Unassigned benefits and other deductions are N/A.
            flags = list(review_reasons_by_employee[source["employee_id"]])
        review_flags[source["employee_id"]] = flags
        gross = earnings_total if show_partial_totals or source["earnings_complete"] else None
        deduction = deductions_total if show_partial_totals or source["deductions_complete"] else None
        net = gross - deduction if gross is not None and deduction is not None else None
        row = {
            "employee_id": source["employee_id"],
            "base_pay": source["base_pay"],
            "gross_pay": gross,
            "deduction_total": deduction,
            "net_pay": net,
            "review_status": (
                "검증요청 · 잠정합계" if show_partial_totals and flags
                else "공제 확인 · 승인 전"
                if show_partial_totals and review_reasons_by_employee is not None
                else "REVIEW_REQUIRED" if net is not None
                else "PARTIAL_REVIEW_ONLY"
            ),
        }
        if employer_industrial_by_employee is not None:
            employer_premium = employer_industrial_by_employee[source["employee_id"]]
            if any(column["key"] == "employer_industrial" for column in columns):
                row["employer_industrial"] = employer_premium if employer_premium else None
            # Gross wages, not employee net pay, are the base company expense.
            # This is a *known subset*; other employer charges aren't inferred.
            row["known_company_outlay"] = earnings_total + employer_premium
        if has_names:
            row["employee_name"] = source["employee_name"]
        for column in columns:
            category = column.get("source")
            if category:
                amount = item_maps[category].get(column["item_id"])
                row[column["key"]] = amount if amount not in (None, 0) else None
        result_rows.append(row)

    return {
        "schema_version": SCHEMA_VERSION,
        "file_name": FILENAME,
        "sheet_name": SHEET_NAME,
        "columns": columns,
        "rows": result_rows,
        "approval_state": "NOT_APPROVED",
        "review_flags": review_flags,
        "totals_are_provisional": bool(show_partial_totals and any(review_flags.values())),
        "employer_cost_complete": False if employer_industrial_by_employee is not None else None,
        "employer_cost_scope": (
            "INTERNAL_ADMIN_ONLY_KNOWN_COST_COMPONENTS"
            if employer_industrial_by_employee is not None else None
        ),
    }



def build_employee_payroll_view(
    register: Mapping[str, Any], *, employee_id: str,
) -> dict[str, Any]:
    """Explicitly exclude employer costs from any future employee notice.

    Never send the administrative PAYROLL workbook to employees. Consumers
    generating an employee view must use this safe allowlisted projection.
    """
    employee_id = _required_text(employee_id, "employee_id")
    rows = [row for row in register["rows"] if row["employee_id"] == employee_id]
    if len(rows) != 1:
        raise PayrollOutputError("employee view: expected one selected employee")
    allowed_columns = [
        col for col in register["columns"]
        if col["key"] not in ("employer_industrial", "known_company_outlay")
    ]
    allowed_keys = {col["key"] for col in allowed_columns}
    return {
        "columns": allowed_columns,
        "rows": [{key: value for key, value in rows[0].items()
                  if key in allowed_keys}],
        "approval_state": register["approval_state"],
        "employee_id": employee_id,
        "report_scope": "EMPLOYEE_ONLY_NO_EMPLOYER_CHARGES",
    }
