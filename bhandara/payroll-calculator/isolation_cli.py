"""Standalone CLI for optional, review-only per-worker Payroll recovery.

This layer is invoked by Portfolio's public root CLI. It has no Gearbox
imports, performs no approvals/ledger commits, and does not print source
payloads, employee identities, or raw exception text to stdout/stderr.
"""
from __future__ import annotations

from pathlib import Path

from .functions.payroll_standalone_input import load_standalone_inputs
from .functions.payroll_standalone_runner import run_standalone_payroll
from .functions.payroll_standalone_report import write_standalone_outputs
from .worker_isolation import recover_employee_payroll


class PayrollRecoveryError(RuntimeError):
    """Stable error code for protected review-only output."""


def _calculate_with_optional_recovery(config: Path, output: Path, scenario_id: str | None):
    """Use normal batch first; retry independently only after engine exception."""
    data = load_standalone_inputs(config, scenario_id=scenario_id)
    try:
        return run_standalone_payroll(data)
    except Exception:
        # Never substitute a Gearbox engine or invent zero-valued employees.
        candidate = recover_employee_payroll(data, temp_parent=output.parent)
        if not candidate["composition"]["worker_runs"]:
            raise PayrollRecoveryError("NO_RECOVERABLE_WORKERS") from None
        candidate["issues"].append({
            "worker_id": None,
            "severity": "ACTION_REQUIRED",
            "code": "PAYROLL_BATCH_RECOVERY_USED",
            "message": "The batch calculation failed; results require worker-level review.",
        })
        return candidate


def calculate_cli(config: str | Path, output_dir: str | Path,
                  *, scenario_id: str | None = None) -> int:
    """Always review-only; return exit code 2 regardless of worker count."""
    output = Path(output_dir)
    result = None
    error = None
    try:
        if not output.parent.is_dir() or output.is_symlink() or output.exists():
            raise PayrollRecoveryError("PAYROLL_OUTPUT_UNAVAILABLE")
        result = _calculate_with_optional_recovery(Path(config), output, scenario_id)
    except Exception:
        # Raw input/worker exceptions may contain protected identifiers.
        error = PayrollRecoveryError("PAYROLL_INPUT_OR_CALCULATION_BLOCKED")
    try:
        paths = write_standalone_outputs(output, result, error=error)
    except Exception:
        print("PAYROLL_ISOLATION_OUTPUT_FAILED")
        return 2
    if result is None:
        print("PAYROLL_STATUS: BLOCKED (review artifact only)")
    else:
        print("PAYROLL_STATUS: " + str(result["status"]) + " (review only, no approval)")
        print("CALCULATED_WORKERS: " + str(len(result["composition"]["worker_runs"])))
        print("FAILED_WORKERS: " + str(len(result.get("failed_workers", {}))))
    print("PAYROLL_ARTIFACT_COUNT: " + str(len(paths)))
    return 2
