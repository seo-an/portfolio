"""File boundary for operational Payroll Settlement Ledger I/O."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable, Mapping


def _load_sibling(module_name: str):
    path = Path(__file__).with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_entrypoint = _load_sibling("payroll_operational_entrypoint")
_lifecycle = _load_sibling("settlement_ledger_lifecycle")
_xlsx = _load_sibling("settlement_ledger_xlsx")
_output_xlsx = _load_sibling("payroll_output_xlsx")


class PayrollOperationalFileIOError(ValueError):
    pass


def run_operational_payroll_with_ledger_file(
    *,
    settlement_ledger_path: str | Path,
    transaction_id_factory: Callable[[Mapping[str, Any]], str],
    **payroll_kwargs: Any,
) -> dict[str, Any]:
    """Read Ledger XLSX, run Payroll, and return validated append candidates.

    This function never mutates the Settlement Ledger workbook.
    """
    ledger_rows = _xlsx.load_settlement_ledger_rows(settlement_ledger_path)
    if "settlement_ledger_rows" in payroll_kwargs:
        raise PayrollOperationalFileIOError(
            "settlement_ledger_rows is owned by settlement_ledger_path"
        )

    result = _entrypoint.run_operational_payroll(
        settlement_ledger_rows=ledger_rows,
        **payroll_kwargs,
    )
    requests = (
        list(result["ledger_write_requests"])
        + list(result["final_ledger_requests"])
    )
    append_candidates = _lifecycle.materialize_ledger_requests(
        requests,
        transaction_id_factory,
    )
    return {
        **result,
        "settlement_ledger_path": str(settlement_ledger_path),
        "ledger_append_candidates": append_candidates,
        "ledger_committed": False,
    }


def commit_ledger_append_candidates(
    settlement_ledger_path: str | Path,
    append_candidates: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Append explicitly approved candidates to the append-only Ledger."""
    try:
        return _xlsx.append_settlement_ledger_rows(
            settlement_ledger_path,
            append_candidates,
        )
    except _xlsx.SettlementLedgerXlsxError as exc:
        raise PayrollOperationalFileIOError(str(exc)) from exc

def run_operational_payroll_to_xlsx(
    *,
    output_path: str | Path,
    settlement_ledger_path: str | Path,
    transaction_id_factory: Callable[[Mapping[str, Any]], str],
    **payroll_kwargs: Any,
) -> dict[str, Any]:
    """Run file-based Payroll and write its human-review workbook.

    Writing the review workbook does not commit Settlement Ledger candidates.
    """
    result = run_operational_payroll_with_ledger_file(
        settlement_ledger_path=settlement_ledger_path,
        transaction_id_factory=transaction_id_factory,
        **payroll_kwargs,
    )
    _output_xlsx.write_payroll_output_xlsx(
        output_path,
        result["composition"],
    )
    return {
        **result,
        "output_path": str(output_path),
    }

