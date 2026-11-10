"""Standalone Payroll calculation using existing operational Gear, never approval.

Input files are independent of Worktime raw-source processing. The CLI accepts
versioned Worktime handoff data, computes source Payroll Results once, then
recomposes review-only worker runs carrying explicit ACTION_REQUIRED records.
"""
from __future__ import annotations

from typing import Any, Mapping

try:
    from .payroll_operational_entrypoint import run_operational_payroll
    from .payroll_run import run_worker_payroll
    from .payroll_validation import build_validation
except ImportError:
    from payroll_operational_entrypoint import run_operational_payroll
    from payroll_run import run_worker_payroll
    from payroll_validation import build_validation


def _issue(code: str, message: str, *, worker_id: str | None = None,
           severity: str = "ACTION_REQUIRED", work_date: str = "") -> dict[str, Any]:
    return {
        "code": code, "severity": severity, "worker_id": worker_id,
        "work_date": work_date, "message": message,
    }


def _review_only_validations(worker_id: str, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = []
    for item in issues:
        if item["worker_id"] not in (None, worker_id):
            continue
        # Every employee/day issue remains a structured action item.
        entries.append(build_validation(
            item["code"],
            "ACTION_REQUIRED",
            item["message"],
            action="Review supporting source documents and record required approval separately.",
            context={
                "worker_id": worker_id,
                "work_date": item.get("work_date", ""),
                "standalone_payroll": True,
            },
        ))
    return entries


def run_standalone_payroll(data: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate and flag every output as review-only; never commit settlement."""
    worker_ids = list(data["expected_worker_ids"])
    worktime = data["worktime"]
    issues = [
        _issue(str(warning["code"]), str(warning["message"]),
               worker_id=warning.get("worker_id"),
               work_date=str(warning.get("work_date") or ""))
        for warning in worktime["warnings"]
    ]
    issues.append(_issue(
        "PAYROLL_REVIEW_ONLY",
        "Standalone Payroll computation does not approve or finalize wages",
    ))
    issues.append(_issue(
        "TAX_INSURANCE_UNVERIFIED",
        "Tax withholding and social insurance have not been computed or verified by this CLI",
    ))
    if not data["ledger_supplied"]:
        issues.append(_issue(
            "LEDGER_NOT_SUPPLIED",
            "No existing settlement ledger was provided; previous adjustments are not verified",
        ))
    operational = run_operational_payroll(
        payroll_period=data["payroll_period"],
        compensation_path=data["compensation_path"],
        payroll_input_path=data["payroll_input_path"],
        worktime_rows=worktime["rows"],
        registry=data["registry"],
        operating_config=data["operating_config"],
        company_policy=data["company_policy"],
        legal_policy=data["legal_policy"],
        employment_facts=data["employment_facts"],
        recurring_pay_item_codes=data["recurring_pay_item_codes"],
        eligibility_facts=data["optional"]["eligibility_facts"],
        settlement_ledger_rows=data["settlement_ledger_rows"],
        absence_events=data["optional"]["absence_events"],
        absence_deduction_inputs=data["optional"]["absence_deduction_inputs"],
        weekly_holiday_inputs=data["optional"]["weekly_holiday_inputs"],
        historical_rerun_results=data["optional"]["historical_rerun_results"],
    )
    computed = operational["composition"]
    runs = dict(computed["worker_runs"])
    expected = set(worker_ids)
    actual = set(runs)
    for worker_id in sorted(expected - actual):
        issues.append(_issue(
            "MISSING_PAYROLL_RESULT",
            "Expected employee has no Payroll Result; cannot assert complete payroll register",
            worker_id=worker_id, severity="ERROR",
        ))
    for worker_id in sorted(actual - expected):
        issues.append(_issue(
            "UNEXPECTED_PAYROLL_WORKER",
            "Payroll Result references worker absent from independent expected roster",
            worker_id=worker_id, severity="ERROR",
        ))
    # Recompose the same source Results for review-only output instead of
    # editing the legacy algorithm or misrepresenting can_auto_finalize=True.
    # No payroll source stage, Worktime stage or ledger commit is rerun.
    for worker_id, old in sorted(runs.items()):
        settlement = operational["ledger_settlements"].get(worker_id, {})
        recomposed = run_worker_payroll(
            old["results"], worker_id, data["payroll_period"],
            dict(data["company_policy"]),
            validations=_review_only_validations(worker_id, issues),
            settlement_adjustment=settlement.get("settlement_adjustment", 0),
        )
        runs[worker_id] = recomposed
        if recomposed["can_auto_finalize"]:
            raise RuntimeError("standalone CLI must never return auto-finalizable worker")
        if recomposed["validation_summary"]["has_error"]:
            issues.append(_issue(
                "WORKER_PAYROLL_VALIDATION_ERROR",
                "Worker Payroll Result contains unresolved calculation error",
                worker_id=worker_id, severity="ERROR",
            ))
    composition = {**computed, "worker_runs": runs}
    has_error = any(item["severity"] == "ERROR" for item in issues)
    status = "BLOCKED" if has_error else "REVIEW_REQUIRED"
    return {
        "schema_version": "0.1",
        "policy_selection": data.get("policy_selection"),
        "resolved_company_policy": data["company_policy"],
        "payroll_period": data["payroll_period"],
        "status": status,
        "finalizable": False,
        "ledger_committed": False,
        "worktime_mode": worktime["mode"],
        "worktime_source_period": worktime["source_period"],
        "expected_worker_ids": worker_ids,
        "source_hashes": data["source_hashes"],
        "worktime_receipt_hashes": worktime["receipt_hashes"],
        "composition": composition,
        "issues": issues,
        "ledger_write_requests": operational["ledger_write_requests"],
        "final_ledger_requests": operational["final_ledger_requests"],
        "source_counts": computed["source_counts"],
    }
