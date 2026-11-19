"""P1-3 composition of independently supplied evidence registry and P1-2 preview.

Registry consistency is checked before any candidate arithmetic, but the
registry is NOT authenticated here. Never treat this as payroll authorization.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from bhandara.payroll.evidence_reconciliation import reconcile_overtime_evidence
from bhandara.payroll.input_excel import PayrollInputs
from bhandara.payroll.overtime_preview import build_overtime_candidate_preview


def build_reconciled_overtime_preview(
    inputs: PayrollInputs,
    worktime_xlsx: str | Path,
    *,
    period_from: str,
    period_to: str,
    verified_work: Iterable[Mapping[str, Any]],
    approved_segments: Iterable[Mapping[str, Any]],
    evidence_registry: Mapping[str, Any],
    rate_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Reconcile trusted-boundary records and keep the same partial register."""
    reconciled = reconcile_overtime_evidence(
        verified_work=verified_work,
        approved_segments=approved_segments,
        registry=evidence_registry,
        overtime_rules=inputs.for_role("overtime_rules"),
        period_from=period_from,
        period_to=period_to,
    )
    result = build_overtime_candidate_preview(
        inputs, worktime_xlsx,
        period_from=period_from, period_to=period_to,
        verified_work=reconciled["verified_work"],
        approved_segments=reconciled["approved_segments"],
        rate_policy=rate_policy,
    )
    result["evidence_review"] = {
        key: value for key, value in reconciled.items()
        if key not in ("verified_work", "approved_segments")
    }
    result["approval_state"] = "NOT_APPROVED"
    result["status"] = "PARTIAL_REVIEW_ONLY"
    return result
