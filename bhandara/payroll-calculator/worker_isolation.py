"""Optional Bhandara Payroll employee-level recovery after batch failure.

This module belongs to the standalone public calculation package, not
Gearbox. It splits validated, roster-bound inputs and calculates each employee
independently only when the all-worker engine raises. It never invents zeros,
approvals or a complete payroll where worker calculations failed.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from openpyxl import Workbook, load_workbook

from .functions.payroll_standalone_runner import run_standalone_payroll


class WorkerIsolationError(ValueError):
    pass


def _split_xlsx(path: str | Path, allowed: set[str]) -> tuple[list[str], dict[str, list[tuple[Any, ...]]]]:
    """Retain exact column order; reject orphan/ambiguous employee identities."""
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        iterator = book.active.iter_rows(values_only=True)
        headers = next(iterator, None)
        if headers is None or not headers or any(
            not isinstance(name, str) or not name.strip() for name in headers
        ) or len(headers) != len(set(headers)) or "worker_id" not in headers:
            raise WorkerIsolationError(f"{Path(path).name}: worker_id and unique headers required")
        index = headers.index("worker_id")
        partition = {worker: [] for worker in allowed}
        for row_number, raw in enumerate(iterator, start=2):
            if not any(value is not None and value != "" for value in raw):
                continue
            worker = raw[index]
            if not isinstance(worker, str) or worker not in allowed:
                # Never erase a third-party wage transaction just to make
                # remaining workers appear complete.
                raise WorkerIsolationError(
                    f"{Path(path).name}: unassigned worker row {row_number}"
                )
            partition[worker].append(tuple(raw))
        return list(headers), partition
    finally:
        book.close()


def _write_xlsx(path: Path, headers: list[str], rows: list[tuple[Any, ...]]) -> None:
    book = Workbook()
    try:
        sheet = book.active
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        book.save(path)
        path.chmod(0o600)
    finally:
        book.close()


def _filter_objects(rows: Any, worker: str, allowed: set[str], label: str) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise WorkerIsolationError(f"{label} must be a list")
    selected = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise WorkerIsolationError(f"{label}[{index}] must be an object")
        owner = row.get("worker_id")
        if not isinstance(owner, str) or owner not in allowed:
            raise WorkerIsolationError(
                f"{label}[{index}]: missing or unexpected worker_id"
            )
        if owner == worker:
            selected.append(dict(row))
    return selected


def _for_worker(
    data: Mapping[str, Any],
    worker: str,
    allowed: set[str],
    root: Path,
    compensation: tuple[list[str], dict[str, list[tuple[Any, ...]]]],
    monthly: tuple[list[str], dict[str, list[tuple[Any, ...]]]],
) -> dict[str, Any]:
    comp_path = root / "compensation.xlsx"
    input_path = root / "payroll-input.xlsx"
    _write_xlsx(comp_path, compensation[0], compensation[1][worker])
    _write_xlsx(input_path, monthly[0], monthly[1][worker])
    wt = data["worktime"]
    warnings = [
        dict(item) for item in wt["warnings"]
        if item.get("worker_id") in (None, worker)
    ]
    employee_data = {
        **data,
        "expected_worker_ids": [worker],
        "compensation_path": comp_path,
        "payroll_input_path": input_path,
        "worktime": {
            **wt,
            "rows": _filter_objects(wt["rows"], worker, allowed, "worktime.rows"),
            "warnings": warnings,
        },
        "employment_facts": _filter_objects(
            data["employment_facts"], worker, allowed, "employment_facts"
        ),
        "settlement_ledger_rows": _filter_objects(
            data["settlement_ledger_rows"], worker, allowed, "settlement_ledger_rows"
        ),
        "optional": {
            name: _filter_objects(rows, worker, allowed, name)
            for name, rows in data["optional"].items()
        },
    }
    return employee_data


def _issue(worker: str, exc: Exception) -> dict[str, Any]:
    return {
        "worker_id": worker,
        "severity": "ERROR",
        "code": "WORKER_PAYROLL_CALCULATION_FAILED",
        "message": f"Employee Payroll calculation failed: {type(exc).__name__}",
        "error_type": type(exc).__name__,
    }


def _aggregate(data: Mapping[str, Any], successes: dict[str, dict[str, Any]],
               failures: dict[str, dict[str, Any]]) -> dict[str, Any]:
    runs = {}
    issues = []
    issue_keys = set()
    counts = {}
    ledger_requests = []
    final_requests = []
    for worker in sorted(successes):
        result = successes[worker]
        run = result["composition"]["worker_runs"].get(worker)
        if run is None or run.get("final_payroll") is None:
            failures[worker] = {
                "worker_id": worker, "severity": "ERROR",
                "code": "WORKER_PAYROLL_RESULT_MISSING",
                "message": "Employee calculation returned no usable Payroll result",
                "error_type": "NoPayrollResult",
            }
            continue
        runs[worker] = run
        for source, count in result["source_counts"].items():
            counts[source] = counts.get(source, 0) + count
        ledger_requests.extend(result["ledger_write_requests"])
        final_requests.extend(result["final_ledger_requests"])
        for issue in result["issues"]:
            key = (issue.get("worker_id"), issue.get("code"),
                   issue.get("work_date"), issue.get("message"))
            if key not in issue_keys:
                issues.append(issue)
                issue_keys.add(key)
    issues.extend(failures[worker] for worker in sorted(failures))
    status = "BLOCKED" if failures else "REVIEW_REQUIRED"
    return {
        "schema_version": "0.1",
        "policy_selection": data.get("policy_selection"),
        "resolved_company_policy": data["company_policy"],
        "payroll_period": data["payroll_period"],
        "status": status,
        "finalizable": False,
        "ledger_committed": False,
        "worktime_mode": data["worktime"]["mode"],
        "worktime_source_period": data["worktime"]["source_period"],
        "worktime_receipt_hashes": data["worktime"]["receipt_hashes"],
        "source_hashes": data["source_hashes"],
        "expected_worker_ids": sorted(data["expected_worker_ids"]),
        "composition": {
            "payroll_period": data["payroll_period"],
            "source_counts": counts,
            "result_count": sum(counts.values()),
            "worker_count": len(runs),
            "worker_runs": runs,
        },
        "issues": issues,
        "ledger_write_requests": ledger_requests,
        "final_ledger_requests": final_requests,
        "source_counts": counts,
        "failed_workers": {
            worker: failures[worker] for worker in sorted(failures)
        },
        "partial_calculation": True,
        "recovery_mode": "PER_WORKER_RETRY_AFTER_BATCH_FAILURE",
    }


def recover_employee_payroll(data: Mapping[str, Any], *, temp_parent: str | Path) -> dict[str, Any]:
    """Retry independently, keeping only complete worker payroll results."""
    workers = data["expected_worker_ids"]
    if not isinstance(workers, list) or not workers or len(workers) != len(set(workers)):
        raise WorkerIsolationError("an independent unique employee roster is required")
    allowed = set(workers)
    comp = _split_xlsx(data["compensation_path"], allowed)
    monthly = _split_xlsx(data["payroll_input_path"], allowed)
    # Fail closed on any unassignable optional/ledger row BEFORE retries.
    for name, values in (
        ("employment_facts", data["employment_facts"]),
        ("settlement_ledger_rows", data["settlement_ledger_rows"]),
        ("worktime.rows", data["worktime"]["rows"]),
        *data["optional"].items(),
    ):
        _filter_objects(values, workers[0], allowed, name)
    successes: dict[str, dict[str, Any]] = {}
    failures: dict[str, dict[str, Any]] = {}
    with TemporaryDirectory(prefix=".payroll-worker-isolation-", dir=temp_parent) as tmp:
        parent = Path(tmp)
        parent.chmod(0o700)
        for index, worker in enumerate(sorted(workers), start=1):
            folder = parent / f"worker-{index:05d}"
            folder.mkdir(mode=0o700)
            try:
                one = _for_worker(data, worker, allowed, folder, comp, monthly)
                result = run_standalone_payroll(one)
                if set(result["composition"]["worker_runs"]) - {worker}:
                    raise WorkerIsolationError("single-worker Payroll emitted another worker")
                successes[worker] = result
            except Exception as exc:
                failures[worker] = _issue(worker, exc)
    return _aggregate(data, successes, failures)
