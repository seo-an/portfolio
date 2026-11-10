"""Approved Worktime closes -> operational Payroll -> final register/journal.

All account codes and approvals are supplied by the operator. This module does
not calculate social insurance, withholding tax or flexible-work legal limits.
"""
from __future__ import annotations

import hashlib
import importlib.util
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_HERE = Path(__file__).resolve()
_worktime = _load(_HERE.parents[2] / "common" / "contracts" / "worktime_close.py",
                  "payroll_worktime_close")
_operating = _load(_HERE.with_name("operating_period_resolver.py"), "payroll_operating_period")
_entrypoint = _load(_HERE.with_name("payroll_operational_entrypoint.py"), "payroll_entrypoint")
_output = _load(_HERE.with_name("payroll_output_xlsx.py"), "payroll_output_xlsx")


class FinalPayrollRegisterError(ValueError):
    pass


def _required(value: Any, field: str) -> str:
    result = str(value).strip() if value is not None else ""
    if not result:
        raise FinalPayrollRegisterError(f"{field} required")
    return result


def _amount(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise FinalPayrollRegisterError(f"{field}: invalid amount") from exc
    if not number.is_finite():
        raise FinalPayrollRegisterError(f"{field}: amount is not finite")
    return number


def _excel_amount(value: Any) -> int | float:
    amount = _amount(value, "excel amount")
    if amount.adjusted() > 13:
        raise FinalPayrollRegisterError("amount exceeds supported Excel numeric precision")
    if amount == amount.to_integral_value():
        return int(amount)
    return float(amount)


def _source_hash(path: str | Path) -> str:
    item = Path(path)
    if not item.is_file():
        raise FinalPayrollRegisterError(f"source workbook missing: {item}")
    return hashlib.sha256(item.read_bytes()).hexdigest()


def _receipt_hash(payload: Mapping[str, Any]) -> str:
    return _worktime._digest(payload)


def _check_account_mapping(accounts: Mapping[str, str]) -> dict[str, str]:
    required = ("wages", "deductions_clearing", "net_payable", "rounding_carry")
    if not isinstance(accounts, Mapping):
        raise FinalPayrollRegisterError("accounts must be a mapping")
    return {key: _required(accounts.get(key), f"accounts.{key}") for key in required}


def _journal_for_worker(worker_id: str, final: Mapping[str, Any],
                        accounts: Mapping[str, str]) -> list[dict[str, Any]]:
    totals = final["totals"]
    gross = sum((_amount(totals[field], field) for field in
                 ("pay_total", "settlement_total", "settlement_adjustment")), Decimal(0))
    deduction = _amount(totals["deduction_total"], "deduction_total")
    payable = _amount(final["payable_amount"], "payable_amount")
    rounding = _amount(final["rounding_remainder"], "rounding_remainder")
    if gross < 0 or deduction < 0 or payable < 0 or rounding < 0:
        raise FinalPayrollRegisterError(f"{worker_id}: negative journal amount needs manual treatment")
    if gross != deduction + payable + rounding:
        raise FinalPayrollRegisterError(f"{worker_id}: journal is not balanced")
    return [
        {"worker_id": worker_id, "account": accounts["wages"], "side": "DEBIT", "amount": gross},
        {"worker_id": worker_id, "account": accounts["deductions_clearing"], "side": "CREDIT", "amount": deduction},
        {"worker_id": worker_id, "account": accounts["net_payable"], "side": "CREDIT", "amount": payable},
        {"worker_id": worker_id, "account": accounts["rounding_carry"], "side": "CREDIT", "amount": rounding},
    ]


def _validate_approval(approved_at: str, **refs: str) -> dict[str, str]:
    try:
        parsed = datetime.fromisoformat(approved_at)
    except (TypeError, ValueError) as exc:
        raise FinalPayrollRegisterError("approved_at must use ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FinalPayrollRegisterError("approved_at must include timezone offset")
    return {"approved_at": parsed.isoformat(),
            **{field: _required(value, field) for field, value in refs.items()}}


def build_final_payroll_register(
    operational_result: Mapping[str, Any],
    *,
    worktime_closes: Iterable[Mapping[str, Any]],
    operating_config: Mapping[str, Any],
    expected_worker_ids: Iterable[str],
    compensation_path: str | Path,
    payroll_input_path: str | Path,
    source_approval_ref: str,
    tax_insurance_approval_ref: str,
    approved_by: str,
    approved_at: str,
    accounts: Mapping[str, str],
    ledger_commit_ref: str | None = None,
) -> dict[str, Any]:
    """Validate already-calculated Payroll against immutable close receipts.

    tax_insurance_approval_ref attests separately supplied mandatory deductions;
    it never means these deductions were calculated by this package.
    """
    period = _required(operational_result.get("payroll_period"), "payroll_period")
    approval = _validate_approval(
        approved_at, approved_by=approved_by,
        source_approval_ref=source_approval_ref,
        tax_insurance_approval_ref=tax_insurance_approval_ref,
    )
    account_map = _check_account_mapping(accounts)
    resolved = _operating.resolve_source_period(period, "worktime", dict(operating_config))
    workers_expected = {_required(w, "expected_worker_ids") for w in expected_worker_ids}
    if not workers_expected:
        raise FinalPayrollRegisterError("expected_worker_ids must not be empty")
    receipts = list(worktime_closes)
    try:
        closed_rows = _worktime.select_closed_worktime(
            receipts, period_from=resolved["period_from"].isoformat(),
            period_to=resolved["period_to"].isoformat(),
            required_worker_ids=workers_expected,
        )
    except (ValueError, KeyError) as exc:
        raise FinalPayrollRegisterError(f"worktime close invalid: {exc}") from exc

    prepared_rows = operational_result.get("prepared_input", {}).get("worktime", {}).get("rows")
    if not isinstance(prepared_rows, list):
        raise FinalPayrollRegisterError("operational result lacks prepared worktime")
    if len(prepared_rows) != len(closed_rows):
        raise FinalPayrollRegisterError("prepared Worktime count differs from closed facts")
    fields = _worktime.REQUIRED_FIELDS
    def digest_rows(rows):
        return _receipt_hash({"rows": sorted(
            [{field: row.get(field) for field in fields} for row in rows],
            key=lambda row: (str(row["worker_id"]), str(row["work_date"]))),
        })
    if digest_rows(prepared_rows) != digest_rows(closed_rows):
        raise FinalPayrollRegisterError("prepared Worktime facts differ from approved closes")

    composition = operational_result.get("composition", {})
    runs = composition.get("worker_runs", {})
    if not isinstance(runs, Mapping) or set(runs) != workers_expected:
        raise FinalPayrollRegisterError("worker roster differs from final Payroll runs")
    pending = list(operational_result.get("ledger_write_requests", []))
    pending += list(operational_result.get("final_ledger_requests", []))
    if pending and not str(ledger_commit_ref or "").strip():
        raise FinalPayrollRegisterError("pending Settlement Ledger writes need ledger_commit_ref")

    detail = []
    journal = []
    summary = []
    for worker in sorted(runs):
        run = runs[worker]
        final = run.get("final_payroll")
        validation = run.get("validation_summary", {})
        if not final or not run.get("can_auto_finalize") or (
            validation.get("has_error") or validation.get("requires_action")
        ):
            raise FinalPayrollRegisterError(f"{worker}: unresolved Payroll validation")
        if final.get("payroll_period") != period or final.get("worker_id") != worker:
            raise FinalPayrollRegisterError(f"{worker}: Payroll identity mismatch")
        totals = final["totals"]
        journal.extend(_journal_for_worker(worker, final, account_map))
        summary.append({
            "worker_id": worker,
            "pay_total": totals["pay_total"],
            "deduction_total": totals["deduction_total"],
            "settlement_total": totals["settlement_total"],
            "settlement_adjustment": totals["settlement_adjustment"],
            "payable_amount": final["payable_amount"],
            "rounding_remainder": final["rounding_remainder"],
        })
        detail.extend(dict(row) for row in run.get("results", []))

    receipt = {
        "schema_version": "0.1",
        "status": "FINALIZED",
        "payroll_period": period,
        "worktime_source_period": {
            "from": resolved["period_from"].isoformat(),
            "to": resolved["period_to"].isoformat(),
        },
        "worktime_close_hashes": [item["receipt_hash"] for item in receipts],
        "source_sha256": {
            "compensation_xlsx": _source_hash(compensation_path),
            "payroll_input_xlsx": _source_hash(payroll_input_path),
        },
        "expected_worker_ids": sorted(workers_expected),
        "accounts": account_map,
        "summary": summary,
        "journal": journal,
        "pay_items": detail,
        "pending_ledger_request_count": len(pending),
        "ledger_commit_ref": ledger_commit_ref or "",
        **approval,
    }
    return {**receipt, "register_hash": _receipt_hash(receipt)}


def verify_final_payroll_register(register: Mapping[str, Any]) -> None:
    if register.get("status") != "FINALIZED":
        raise FinalPayrollRegisterError("FINALIZED register required")
    hash_value = _required(register.get("register_hash"), "register_hash")
    actual = _receipt_hash({k: v for k, v in register.items() if k != "register_hash"})
    if actual != hash_value:
        raise FinalPayrollRegisterError("register checksum mismatch")


def run_closed_payroll(
    *,
    worktime_closes: Iterable[Mapping[str, Any]],
    expected_worker_ids: Iterable[str],
    source_approval_ref: str,
    tax_insurance_approval_ref: str,
    approved_by: str,
    approved_at: str,
    accounts: Mapping[str, str],
    ledger_commit_ref: str | None = None,
    **payroll_kwargs: Any,
) -> dict[str, Any]:
    """Run the current operational calculator strictly from the closed facts."""
    if "worktime_rows" in payroll_kwargs:
        raise FinalPayrollRegisterError("worktime_rows cannot bypass approved closes")
    required = ("payroll_period", "operating_config", "compensation_path",
                "payroll_input_path")
    for field in required:
        if field not in payroll_kwargs:
            raise FinalPayrollRegisterError(f"{field} required")
    receipts = list(worktime_closes)
    workers = list(expected_worker_ids)
    resolved = _operating.resolve_source_period(
        payroll_kwargs["payroll_period"], "worktime", dict(payroll_kwargs["operating_config"]))
    rows = _worktime.select_closed_worktime(
        receipts, period_from=resolved["period_from"].isoformat(),
        period_to=resolved["period_to"].isoformat(), required_worker_ids=workers)
    result = _entrypoint.run_operational_payroll(worktime_rows=rows, **payroll_kwargs)
    register = build_final_payroll_register(
        result, worktime_closes=receipts,
        operating_config=payroll_kwargs["operating_config"],
        expected_worker_ids=workers,
        compensation_path=payroll_kwargs["compensation_path"],
        payroll_input_path=payroll_kwargs["payroll_input_path"],
        source_approval_ref=source_approval_ref,
        tax_insurance_approval_ref=tax_insurance_approval_ref,
        approved_by=approved_by, approved_at=approved_at,
        accounts=accounts, ledger_commit_ref=ledger_commit_ref,
    )
    return {"operational_result": result, "final_register": register}


def write_final_payroll_register_xlsx(
    output_path: str | Path,
    *,
    final_register: Mapping[str, Any],
    operational_result: Mapping[str, Any],
) -> Path:
    """Write an approved workbook once. Never silently overwrite finalized books."""
    verify_final_payroll_register(final_register)
    if final_register["payroll_period"] != operational_result.get("payroll_period"):
        raise FinalPayrollRegisterError("Payroll period mismatch on workbook export")
    # Never export a different calculation under an already-approved checksum.
    actual_runs = operational_result.get("composition", {}).get("worker_runs", {})
    if set(actual_runs) != set(final_register["expected_worker_ids"]):
        raise FinalPayrollRegisterError("export worker roster differs from final register")
    summaries = []
    details = []
    for worker in sorted(actual_runs):
        run = actual_runs[worker]
        final = run.get("final_payroll")
        if final is None:
            raise FinalPayrollRegisterError("export contains unfinalized worker")
        totals = final["totals"]
        summaries.append({
            "worker_id": worker, "pay_total": totals["pay_total"],
            "deduction_total": totals["deduction_total"],
            "settlement_total": totals["settlement_total"],
            "settlement_adjustment": totals["settlement_adjustment"],
            "payable_amount": final["payable_amount"],
            "rounding_remainder": final["rounding_remainder"],
        })
        details.extend(dict(item) for item in run.get("results", []))
    if _receipt_hash({"summary": summaries, "pay_items": details}) != _receipt_hash({
        "summary": final_register["summary"], "pay_items": final_register["pay_items"]}):
        raise FinalPayrollRegisterError("export calculation differs from approved register")
    path = Path(output_path)
    if path.exists():
        raise FinalPayrollRegisterError("final register file exists; issue a revised version instead")
    path.parent.mkdir(parents=True, exist_ok=True)
    _output.write_payroll_output_xlsx(path, operational_result["composition"])
    workbook = load_workbook(path)
    try:
        workbook["Summary"].title = "Final Register"
        summary_sheet = workbook["Final Register"]
        for row in summary_sheet.iter_rows(min_row=2):
            row[2].value = "FINALIZED"
            for cell in row[4:11]:
                if cell.value not in (None, ""):
                    cell.value = _excel_amount(cell.value)
                    cell.number_format = "#,##0.##"
        for row in workbook["Calculation Detail"].iter_rows(min_row=2):
            if row[5].value not in (None, ""):
                row[5].value = _excel_amount(row[5].value)
                row[5].number_format = "#,##0.##"
        journal = workbook.create_sheet("Journal")
        journal.append(["worker_id", "account", "side", "amount"])
        for item in final_register["journal"]:
            journal.append([item["worker_id"], item["account"], item["side"],
                            _excel_amount(item["amount"])])
        last_row = journal.max_row
        journal.append(["", "TOTAL DEBIT", "", f'=SUMIF(C2:C{last_row},"DEBIT",D2:D{last_row})'])
        debit_row = journal.max_row
        journal.append(["", "TOTAL CREDIT", "", f'=SUMIF(C2:C{last_row},"CREDIT",D2:D{last_row})'])
        credit_row = journal.max_row
        journal.append(["", "BALANCE CHECK", "", f"=D{debit_row}-D{credit_row}"])
        for row in journal.iter_rows(min_row=2, min_col=4, max_col=4):
            row[0].number_format = "#,##0.##"
        audit = workbook.create_sheet("Approval")
        audit.append(["field", "value"])
        for key in ("status", "payroll_period", "approved_by", "approved_at",
                    "source_approval_ref", "tax_insurance_approval_ref",
                    "ledger_commit_ref", "register_hash"):
            audit.append([key, str(final_register[key])])
        for key, value in final_register["source_sha256"].items():
            audit.append([key, value])
        for index, value in enumerate(final_register["worktime_close_hashes"], 1):
            audit.append([f"worktime_close_hash_{index}", value])
        for sheet in workbook:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="17365D")
        workbook.save(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        workbook.close()
    return path
