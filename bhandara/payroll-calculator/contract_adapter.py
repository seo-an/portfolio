"""Versioned contract -> monthly compensation adapter for the Bhandara easy CLI.

Does NOT alter the migrated Payroll arithmetic engine. Contract amounts
and components are separate, so base salary is derived, never guessed.
Hourly/daily wage quantities come from an explicit, unclosed Worktime handoff.
Their premiums/weekly holiday compensation are NOT silently inferred; such
workers get explicit REVIEW_REQUIRED findings and are excluded from the
legacy monthly-wage premium resolver.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from openpyxl import Workbook, load_workbook

from bhandara.common.io.input_layout import (
    InputLayoutError, as_day, hash_file, period_bounds, read_sheet, role,
)

CONTRACT_COLUMNS = (
    "contract_id", "employee_id", "pay_basis", "contract_amount",
    "effective_from", "effective_to", "standard_day_hours",
)
COMPONENT_COLUMNS = ("contract_id", "pay_item_code", "monthly_amount")
SERVICE_COLUMNS = (
    "service_contract_id", "external_vendor_id", "pay_basis",
    "contract_amount", "effective_from", "effective_to",
)
SALARY_BASIS = {"ANNUAL", "MONTHLY"}
TIME_BASIS = {"HOURLY", "DAILY"}
EMPLOYEE_BASIS = SALARY_BASIS | TIME_BASIS
COMPONENT_CODES = {"position_allowance", "meal_allowance"}


def _decimal(value: Any, field: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool) or value in (None, ""):
        raise InputLayoutError(f"{field}: positive numeric value required")
    try:
        amount = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise InputLayoutError(f"{field}: valid numeric value required") from exc
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        raise InputLayoutError(f"{field}: nonnegative finite amount required")
    return amount


def _optional_day(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    return as_day(value, field)


def _inside(day: str, start: str, end: str | None) -> bool:
    return start <= day and (end is None or day <= end)


def _load_employee_contracts(path: Path, identities: Mapping[str, Any],
                             period: str) -> tuple[list[dict], set[str]]:
    rows = read_sheet(path, CONTRACT_COLUMNS)
    if not rows:
        raise InputLayoutError("pay-contract.xlsx: at least one contract is required")
    ids = set()
    by_employee: dict[str, list[dict]] = defaultdict(list)
    validated: list[dict] = []
    for row in rows:
        line = row["_row_number"]
        contract_id = str(row["contract_id"] or "").strip()
        employee_id = str(row["employee_id"] or "").strip()
        basis = str(row["pay_basis"] or "").strip().upper()
        if not contract_id or contract_id in ids:
            raise InputLayoutError(f"pay-contract.xlsx row {line}: duplicate/blank contract_id")
        if employee_id not in identities:
            raise InputLayoutError(f"pay-contract.xlsx row {line}: unmapped employee_id")
        if basis not in EMPLOYEE_BASIS:
            raise InputLayoutError(f"pay-contract.xlsx row {line}: unknown pay_basis {basis!r}")
        start = as_day(row["effective_from"], "effective_from")
        end = _optional_day(row.get("effective_to"), "effective_to")
        if end is not None and end < start:
            raise InputLayoutError(f"pay-contract.xlsx row {line}: inverted date range")
        rate = _decimal(row["contract_amount"], f"contract_amount row {line}")
        hours = row.get("standard_day_hours")
        if basis in TIME_BASIS:
            hours = _decimal(hours, f"standard_day_hours row {line}")
            if not Decimal("0") < hours <= Decimal("24"):
                raise InputLayoutError(f"pay-contract.xlsx row {line}: unreasonable day hours")
        elif hours not in (None, ""):
            hours = _decimal(hours, f"standard_day_hours row {line}")
        else:
            hours = None
        item = {
            "contract_id": contract_id,
            "employee_id": employee_id,
            "worker_id": identities[employee_id]["worker_id"],
            "pay_basis": basis,
            "contract_amount": rate,
            "standard_day_hours": hours,
            "effective_from": start,
            "effective_to": end,
            "source_row": line,
        }
        ids.add(contract_id)
        by_employee[employee_id].append(item)
        validated.append(item)
    for employee_id, employee_rows in by_employee.items():
        ordered = sorted(employee_rows, key=lambda x: x["effective_from"])
        for old, new in zip(ordered, ordered[1:]):
            if old["effective_to"] is None or new["effective_from"] <= old["effective_to"]:
                raise InputLayoutError(f"pay-contract.xlsx: overlapping contracts for {employee_id}")
    # Never silently drop employees whose contract was not supplied.
    if set(by_employee) != set(identities):
        missing = sorted(set(identities) - set(by_employee))
        raise InputLayoutError(f"pay-contract.xlsx missing employees: {missing[:10]}")
    return validated, ids


def _load_components(path: Path, contracts: Mapping[str, dict]) -> dict[str, dict[str, Decimal]]:
    rows = read_sheet(path, COMPONENT_COLUMNS)
    components: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for row in rows:
        line = row["_row_number"]
        ident = str(row.get("contract_id") or "").strip()
        code = str(row.get("pay_item_code") or "").strip()
        if ident not in contracts:
            raise InputLayoutError(f"pay-contract-components.xlsx row {line}: unknown contract")
        if code not in COMPONENT_CODES:
            raise InputLayoutError(f"pay-contract-components.xlsx row {line}: unsupported item {code}")
        if contracts[ident]["pay_basis"] not in SALARY_BASIS:
            raise InputLayoutError(f"pay-contract-components.xlsx row {line}: hourly/daily cannot include fixed monthly components")
        if code in components[ident]:
            raise InputLayoutError(f"pay-contract-components.xlsx row {line}: duplicate contract/item")
        components[ident][code] = _decimal(row["monthly_amount"], f"monthly_amount row {line}")
    return components


def _load_services(path: Path | None) -> list[dict]:
    if path is None:
        return []
    rows = read_sheet(path, SERVICE_COLUMNS)
    result, seen = [], set()
    for row in rows:
        ident = str(row.get("service_contract_id") or "").strip()
        vendor = str(row.get("external_vendor_id") or "").strip()
        basis = str(row.get("pay_basis") or "").strip().upper()
        if not ident or ident in seen or not vendor or basis not in {"HOURLY", "DAILY"}:
            raise InputLayoutError(f"service-contracts.xlsx row {row['_row_number']}: invalid contract/vendor/basis")
        start = as_day(row["effective_from"], "effective_from")
        end = _optional_day(row.get("effective_to"), "effective_to")
        if end and end < start:
            raise InputLayoutError(f"service-contracts.xlsx row {row['_row_number']}: inverted period")
        amount = _decimal(row["contract_amount"], "service contract rate")
        result.append({
            "service_contract_id": ident, "external_vendor_id": vendor,
            "pay_basis": basis, "contract_rate": str(amount),
            "effective_from": start, "effective_to": end,
            "status": "REVIEW_REQUIRED",
            "reason": "SERVICE_CONTRACT_OUTSIDE_EMPLOYMENT_PAYROLL",
        })
        seen.add(ident)
    return result


def _load_worktime(path: Path, expected_workers: set[str], from_day: str,
                   to_day: str) -> tuple[dict, dict[str, list[dict]]]:
    with path.open("r", encoding="utf-8") as stream:
        source = json.load(stream)
    if not isinstance(source, dict) or source.get("schema_version") != "0.1":
        raise InputLayoutError("contract calculation requires Worktime JSON schema 0.1")
    if source.get("status") not in {"REVIEW_REQUIRED", "CALCULATED_UNCLOSED"}:
        raise InputLayoutError("contract calculation cannot use BLOCKED/finalized Worktime")
    if source.get("period_from") != from_day or source.get("period_to") != to_day:
        raise InputLayoutError("Worktime source period does not match payroll attribution period")
    if source.get("close_receipt") is not None or source.get("coverage_verified") is True:
        raise InputLayoutError("unclosed Worktime adapter requires explicit unclosed handoff")
    if set(source.get("covered_worker_ids") or []) != expected_workers:
        raise InputLayoutError("Worktime covered worker IDs do not match ID_MAP")
    groups: dict[str, list[dict]] = defaultdict(list)
    observed: set[tuple[str, str]] = set()
    for row in source.get("rows", []):
        worker = str(row.get("worker_id") or "").strip()
        day = as_day(row.get("work_date"), "work_date")
        if worker not in expected_workers or not from_day <= day <= to_day:
            raise InputLayoutError("Worktime result contains unexpected worker/date")
        if (worker, day) in observed:
            raise InputLayoutError("Worktime result contains duplicate worker/day")
        observed.add((worker, day))
        groups[worker].append(row)
    return source, groups


def _emit_generated_xlsx(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    if path.exists():
        book = load_workbook(path, read_only=True, data_only=True)
        try:
            existing = list(book.active.values)
        finally:
            book.close()
        if existing != [tuple(headers), *(tuple(row) for row in rows)]:
            raise InputLayoutError(f"generated Excel collision; refusing to overwrite: {path}")
        return
    book = Workbook()
    try:
        sheet = book.active
        sheet.title = "active"
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        book.save(path)
    finally:
        book.close()
    os.chmod(path, 0o600)


def _emit_json(path: Path, payload: dict) -> None:
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise InputLayoutError(f"generated source collision: {path}")
        return
    path.write_text(content, encoding="utf-8")
    os.chmod(path, 0o600)


def build_contract_compensation(
    root: Path,
    period: str,
    identities: Mapping[str, Mapping[str, str]],
    *,
    worktime_path: Path,
    generated_dir: Path,
    overrides: Mapping | None = None,
) -> dict:
    """Compute auditable base_salary, excluding unsupported non-salary premiums.

    The old Payroll Gear receives a standard Compensation workbook. Services
    are validated and excluded from employee payroll; no tax rate is guessed.
    """
    from importlib import import_module

    module = import_module("bhandara.payroll-calculator.functions.operating_period_resolver")
    module_root = Path(__file__).resolve().parent
    operating_config = json.loads((module_root / "operating-config.json").read_text(encoding="utf-8"))
    attr = module.resolve_source_period(period, "worktime", operating_config)
    source_from, source_to = attr["period_from"].isoformat(), attr["period_to"].isoformat()
    target_from, target_to = period_bounds(period)

    contract_path = role(root, "payroll", "contracts", overrides)
    component_path = role(root, "payroll", "contract_components", overrides)
    service_path = role(root, "payroll", "service_contracts", overrides)
    contracts, _ = _load_employee_contracts(contract_path, identities, period)
    contract_map = {x["contract_id"]: x for x in contracts}
    components = _load_components(component_path, contract_map)
    services = _load_services(service_path)
    worktime, source_rows = _load_worktime(
        worktime_path,
        {x["worker_id"] for x in identities.values()},
        source_from, source_to,
    )

    source_hashes = {
        "pay_contract": hash_file(contract_path),
        "contract_components": hash_file(component_path),
        "service_contracts": hash_file(service_path),
        "worktime_result": hash_file(worktime_path),
    }
    fingerprint = hashlib.sha256(
        json.dumps({"period": period, "source_hashes": source_hashes},
                   sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    generated_dir.mkdir(parents=True, exist_ok=True)
    compensation_path = generated_dir / f"contract-compensation-{period}-{fingerprint}.xlsx"
    handoff_path = generated_dir / f"contract-worktime-salary-{period}-{fingerprint}.json"
    review_path = generated_dir / f"contract-basis-review-{period}-{fingerprint}.json"

    employee_by_worker = {x["worker_id"]: x for x in identities.values()}
    results = []
    source_comp = []
    time_workers = set()
    salary_workers = set()

    for employee_id in sorted(identities):
        worker_id = identities[employee_id]["worker_id"]
        employee_contracts = sorted(
            [x for x in contracts if x["employee_id"] == employee_id],
            key=lambda x: x["effective_from"]
        )
        monthly_base = Decimal("0")
        monthly_items: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        contract_traces = []
        review_codes: set[str] = set()
        for c in employee_contracts:
            basis, rate = c["pay_basis"], c["contract_amount"]
            source_span = (source_from, source_to) if basis in TIME_BASIS else (target_from, target_to)
            span_from = max(source_span[0], c["effective_from"])
            span_to = min(source_span[1], c["effective_to"] or source_span[1])
            if span_to < span_from:
                continue
            if basis in SALARY_BASIS:
                monthly_gross = rate / Decimal("12") if basis == "ANNUAL" else rate
                included = components.get(c["contract_id"], {})
                allowance_total = sum(included.values(), Decimal("0"))
                base = monthly_gross - allowance_total
                if base <= 0:
                    raise InputLayoutError(f"{employee_id}: contract fixed components exceed gross")
                salary_workers.add(worker_id)
                if basis == "ANNUAL" and (monthly_gross * 12 != rate):
                    review_codes.add("ANNUAL_DIVISION_PRECISION_REVIEW")
                source_comp.append({
                    "worker_id": worker_id,
                    "effective_from": c["effective_from"],
                    "effective_to": c["effective_to"],
                    "base_salary": base,
                    **included,
                })
                contract_traces.append({
                    "contract_id": c["contract_id"],
                    "pay_basis": basis,
                    "contract_amount": str(rate),
                    "monthly_contract_amount": str(monthly_gross),
                    "monthly_base_salary": str(base),
                    "included_fixed_allowances": {k: str(v) for k,v in included.items()},
                    "effective_from": c["effective_from"],
                    "effective_to": c["effective_to"],
                    "calculation": "ANNUAL/12-minus-included-components" if basis=="ANNUAL" else "MONTHLY-minus-included-components",
                })
                monthly_base += base
                for code, amount in included.items():
                    monthly_items[code] += amount
                continue
            time_workers.add(worker_id)
            if components.get(c["contract_id"]):
                raise InputLayoutError("hourly/daily contracts cannot declare included monthly components")
            matching = [
                row for row in source_rows.get(worker_id, [])
                if _inside(row["work_date"], span_from, span_to)
            ]
            if not matching:
                raise InputLayoutError(
                    f"{employee_id}: no payable Worktime rows in contract period"
                )
            total_hours = Decimal("0")
            eligible_days = 0
            for row in matching:
                ordinary = _decimal(
                    row.get("ordinary_hours"), "ordinary_hours", allow_zero=True)
                worked = _decimal(row.get("worked_hours"), "worked_hours", allow_zero=True)
                total_hours += ordinary
                if ordinary >= c["standard_day_hours"] and worked > 0:
                    eligible_days += 1
                elif basis == "DAILY" and worked > 0:
                    review_codes.add("PARTIAL_DAY_PAYMENT_POLICY_REQUIRED")
                for key in ("overtime_hours", "night_hours",
                            "holiday_work_hours_within_8", "holiday_work_hours_over_8"):
                    if _decimal(row.get(key, 0), key, allow_zero=True):
                        review_codes.add("NONMONTHLY_PREMIUM_NOT_CALCULATED")
                if row.get("validation_flags"):
                    review_codes.add("WORKTIME_FLAGS_NEED_APPROVAL")
            base = (rate * total_hours) if basis == "HOURLY" else (rate * eligible_days)
            monthly_base += base
            review_codes.update({
                "WORKTIME_UNCLOSED",
                "NONMONTHLY_PREMIUM_NOT_CALCULATED",
                "WEEKLY_PAID_HOLIDAY_NOT_RESOLVED",
            })
            contract_traces.append({
                "contract_id": c["contract_id"], "pay_basis": basis,
                "contract_amount": str(rate), "worktime_period_from": span_from,
                "worktime_period_to": span_to,
                "ordinary_hours": str(total_hours), "qualified_days": eligible_days,
                "standard_day_hours": str(c["standard_day_hours"]),
                "calculated_base_salary": str(base),
                "calculation": "HOURLY*ordinary_hours" if basis=="HOURLY" else "DAILY*full_eligible_days",
            })
        if not contract_traces:
            raise InputLayoutError(f"{employee_id}: no effective contract for payment period")
        has_salary = worker_id in salary_workers
        has_time = worker_id in time_workers
        if has_salary and has_time:
            raise InputLayoutError(f"{employee_id}: mixed salary and time-based contracts in one period need manual review")
        if has_time:
            source_comp.append({
                "worker_id": worker_id,
                "effective_from": target_from,
                "effective_to": target_to,
                "base_salary": monthly_base,
            })
        results.append({
            "employee_id": employee_id, "worker_id": worker_id,
            "monthly_base_sum_before_proration": str(monthly_base),
            "contract_details": contract_traces,
            "review_codes": sorted(review_codes),
            "approved": False, "finalizable": False,
        })

    # One column per allowed compensation item. Missing allowances remain
    # blank, preserving the Payroll legacy registry/cell contract.
    item_keys = sorted({k for x in source_comp for k in x if k not in {
        "worker_id", "effective_from", "effective_to", "base_salary"}})
    headers = ["worker_id", "effective_from", "effective_to", "base_salary", *item_keys]
    xlsx_rows = []
    for row in sorted(source_comp, key=lambda x: (x["worker_id"], x["effective_from"])):
        xlsx_rows.append([
            row["worker_id"], row["effective_from"], row["effective_to"],
            str(row["base_salary"]),
            *(str(row[code]) if code in row else None for code in item_keys),
        ])
    _emit_generated_xlsx(compensation_path, headers, xlsx_rows)

    salary_worktime = {
        **worktime,
        "rows": [
            row for row in worktime["rows"]
            if str(row["worker_id"]) in salary_workers
        ],
        "candidate_expected_keys": [
            item for item in worktime.get("candidate_expected_keys", [])
            if str(item.get("worker_id")) in salary_workers
        ],
        "coverage_verified": False,
        "close_receipt": None,
        "derivation": {
            "kind": "CONTRACT_PREMIUM_FILTER",
            "upstream_sha256": source_hashes["worktime_result"],
            "salary_workers": len(salary_workers),
            "time_based_workers_excluded_from_legacy_premium": len(time_workers),
            "warning": "Hourly/daily premiums excluded, see contract-basis-review",
        },
    }
    _emit_json(handoff_path, salary_worktime)

    review = {
        "schema_version": "1.0",
        "payroll_period": period,
        "worktime_source_period": {"from": source_from, "to": source_to},
        "status": "REVIEW_REQUIRED",
        "approved": False, "finalizable": False,
        "source_hashes": source_hashes,
        "worktime_unclosed": True,
        "time_based_premiums_calculated": False,
        "employee_count": len(results),
        "time_based_worker_count": len(time_workers),
        "salary_based_worker_count": len(salary_workers),
        "employees": results,
        "service_contracts": services,
        "service_contracts_in_employee_payroll": False,
        "message": (
            "Contract-based base wages are estimates for review; hourly/daily "
            "premiums and paid holidays require separate verified policies. "
            "Freelance service agreements are not employment payroll."
        ),
    }
    _emit_json(review_path, review)
    return {
        "compensation_path": compensation_path,
        "worktime_result_path": handoff_path,
        "review_path": review_path,
        "worktime_input_path": worktime_path,
        "time_workers": time_workers,
        "salary_workers": salary_workers,
    }
