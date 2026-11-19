"""P1-3: Cross-check candidate evidence against an independently supplied registry.

This is consistency validation, NOT signature verification, identity verification,
or proof that an external approval is authentic. The registry's provenance
must be established at the external boundary before this function is used.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

from bhandara.payroll.overtime_candidates import (
    APPROVAL_FIELDS, WORK_FIELDS, OvertimeCandidateError, _date,
    _interval, _rules, _text,
)


class EvidenceReconciliationError(ValueError):
    """Claimed evidence and the separately provided source ledger disagree."""


REGISTRY_FIELDS = frozenset({
    "schema_version", "period_from", "period_to", "source_system",
    "snapshot_ref", "work_verifications", "approvals",
    "classifications", "base_inclusions",
})
WORK_RECORD_FIELDS = frozenset(WORK_FIELDS | {"status"})
APPROVAL_RECORD_FIELDS = frozenset(APPROVAL_FIELDS | {"status"})
CLASSIFICATION_FIELDS = frozenset({
    "classification_ref", "segment_id", "rule_id", "category", "policy_ref", "status",
})
BASE_INCLUSION_FIELDS = frozenset({
    "base_inclusion_ref", "segment_id", "base_pay_includes_time", "status",
})


def _records(source: Any, *, name: str, key: str, fields: frozenset[str]) -> dict[str, Mapping[str, Any]]:
    if not isinstance(source, (list, tuple)):
        raise EvidenceReconciliationError(f"{name}: list required")
    result: dict[str, Mapping[str, Any]] = {}
    for row in source:
        if not isinstance(row, Mapping) or set(row) != fields:
            raise EvidenceReconciliationError(f"{name}: exact fields required")
        try:
            identifier = _text(row.get(key), f"{name}.{key}")
        except OvertimeCandidateError as exc:
            raise EvidenceReconciliationError(f"{name}: invalid identifier") from exc
        if identifier in result:
            raise EvidenceReconciliationError(f"{name}: duplicate key")
        result[identifier] = row
    return result


def _same(source: Mapping[str, Any], reference: Mapping[str, Any], names: tuple[str, ...], label: str) -> None:
    if any(source.get(name) != reference.get(name) for name in names):
        raise EvidenceReconciliationError(f"{label}: referenced source values differ")


def _require_state(row: Mapping[str, Any], field: str, expected: str, name: str) -> None:
    if row.get(field) != expected:
        raise EvidenceReconciliationError(f"{name}: required {field}={expected}")


def _period(registry: Mapping[str, Any], period_from: str, period_to: str) -> tuple[date, date]:
    try:
        begin = _date(period_from, "period_from")
        end = _date(period_to, "period_to")
    except OvertimeCandidateError as exc:
        raise EvidenceReconciliationError("period: valid explicit dates required") from exc
    if begin > end:
        raise EvidenceReconciliationError("period: reversed dates")
    if registry.get("period_from") != period_from or registry.get("period_to") != period_to:
        raise EvidenceReconciliationError("registry: payroll period mismatch")
    return begin, end


def reconcile_overtime_evidence(
    *,
    verified_work: Iterable[Mapping[str, Any]],
    approved_segments: Iterable[Mapping[str, Any]],
    registry: Mapping[str, Any],
    overtime_rules: Iterable[Mapping[str, Any]],
    period_from: str,
    period_to: str,
) -> dict[str, Any]:
    """Reconcile source refs, exact intervals, IDs, classifications and inclusion.

    The ledger is passed separately from claimed segments. References with
    mismatched facts or unverified/revoked status block the entire run.
    This is never a pay decision, external source authentication, or proof of
    legal eligibility. Empty lists are valid but never imply zero overtime.
    """
    if not isinstance(registry, Mapping) or set(registry) != REGISTRY_FIELDS:
        raise EvidenceReconciliationError("registry: exact envelope required")
    if registry.get("schema_version") != "0.1":
        raise EvidenceReconciliationError("registry: unsupported schema")
    for field in ("source_system", "snapshot_ref"):
        try:
            _text(registry.get(field), field)
        except OvertimeCandidateError as exc:
            raise EvidenceReconciliationError(f"registry: {field} missing") from exc
    begin, end = _period(registry, period_from, period_to)
    try:
        rules = _rules(overtime_rules)
    except OvertimeCandidateError as exc:
        raise EvidenceReconciliationError("rules: invalid rule set") from exc

    work_registry = _records(
        registry["work_verifications"], name="work_verifications",
        key="verification_ref", fields=WORK_RECORD_FIELDS,
    )
    approval_registry = _records(
        registry["approvals"], name="approvals",
        key="approval_ref", fields=APPROVAL_RECORD_FIELDS,
    )
    class_registry = _records(
        registry["classifications"], name="classifications",
        key="classification_ref", fields=CLASSIFICATION_FIELDS,
    )
    base_registry = _records(
        registry["base_inclusions"], name="base_inclusions",
        key="base_inclusion_ref", fields=BASE_INCLUSION_FIELDS,
    )

    works = tuple(verified_work)
    segments = tuple(approved_segments)
    used_work: set[str] = set()
    used_segments: set[str] = set()
    seen_work_id: set[str] = set()
    seen_segment_id: set[str] = set()
    for row in works:
        if not isinstance(row, Mapping) or set(row) != WORK_FIELDS:
            raise EvidenceReconciliationError("verified_work: exact fields required")
        try:
            ref = _text(row["verification_ref"], "verification_ref")
            evidence_id = _text(row["evidence_id"], "evidence_id")
        except OvertimeCandidateError as exc:
            raise EvidenceReconciliationError("verified_work: invalid text identifiers") from exc
        if ref not in work_registry or ref in used_work:
            raise EvidenceReconciliationError("verified_work: missing or reused verification reference")
        used_work.add(ref)
        if evidence_id in seen_work_id:
            raise EvidenceReconciliationError("verified_work: duplicate evidence ID")
        seen_work_id.add(evidence_id)
        record = work_registry[ref]
        _require_state(record, "status", "VERIFIED", "work_verifications")
        _same(row, record, tuple(WORK_FIELDS), "verified_work")
        try:
            start, _, _ = _interval(row, "verified_work")
        except OvertimeCandidateError as exc:
            raise EvidenceReconciliationError("verified_work: invalid interval") from exc
        if not begin <= start.date() <= end:
            raise EvidenceReconciliationError("verified_work: date outside payroll period")

    for row in segments:
        if not isinstance(row, Mapping) or set(row) != APPROVAL_FIELDS:
            raise EvidenceReconciliationError("approved_segments: exact fields required")
        try:
            ref = _text(row["approval_ref"], "approval_ref")
            segment_id = _text(row["segment_id"], "segment_id")
            work_evidence_id = _text(row["work_evidence_id"], "work_evidence_id")
            cls_ref = _text(row["classification_ref"], "classification_ref")
            base_ref = _text(row["base_inclusion_ref"], "base_inclusion_ref")
            rule_id = _text(row["rule_id"], "rule_id")
        except OvertimeCandidateError as exc:
            raise EvidenceReconciliationError("approved_segments: invalid reference identifiers") from exc
        if ref not in approval_registry or ref in used_segments:
            raise EvidenceReconciliationError("approved_segments: missing or reused approval reference")
        used_segments.add(ref)
        if segment_id in seen_segment_id:
            raise EvidenceReconciliationError("approved_segments: duplicate segment ID")
        seen_segment_id.add(segment_id)
        record = approval_registry[ref]
        _require_state(record, "status", "CURRENT", "approvals")
        _require_state(record, "approval_status", "APPROVED", "approvals")
        _same(row, record, tuple(APPROVAL_FIELDS), "approved_segments")
        if work_evidence_id not in seen_work_id:
            raise EvidenceReconciliationError("approved_segments: missing verified work evidence")
        try:
            start, _, _ = _interval(row, "approved_segment")
        except OvertimeCandidateError as exc:
            raise EvidenceReconciliationError("approved_segments: invalid interval") from exc
        if not begin <= start.date() <= end:
            raise EvidenceReconciliationError("approved_segments: date outside payroll period")
        if rule_id not in rules:
            raise EvidenceReconciliationError("approved_segments: rule missing")
        if cls_ref not in class_registry or base_ref not in base_registry:
            raise EvidenceReconciliationError("approved_segments: classification or base source missing")
        classification, base = class_registry[cls_ref], base_registry[base_ref]
        _require_state(classification, "status", "VERIFIED", "classifications")
        _require_state(base, "status", "VERIFIED", "base_inclusions")
        if (classification["segment_id"] != row["segment_id"]
                or classification["rule_id"] != rule_id
                or classification["category"] != rules[rule_id]["category"]
                or classification["policy_ref"] != rules[rule_id]["policy_ref"]):
            raise EvidenceReconciliationError("classifications: rule/policy/category mismatch")
        if (base["segment_id"] != row["segment_id"]
                or type(base["base_pay_includes_time"]) is not bool
                or type(row["base_pay_includes_time"]) is not bool
                or base["base_pay_includes_time"] != row["base_pay_includes_time"]):
            raise EvidenceReconciliationError("base_inclusions: inconsistent base-pay inclusion")

    return {
        "schema_version": "0.1",
        "source_system": registry["source_system"],
        "snapshot_ref": registry["snapshot_ref"],
        "work_reference_count": len(used_work),
        "approval_reference_count": len(used_segments),
        "claim_consistency": "MATCHED_SOURCE_RECORDS",
        "source_authenticity": "NOT_AUTHENTICATED_BY_THIS_MODULE",
        "statutory_eligibility": "NOT_ASSESSED",
        "approval_state": "NOT_APPROVED",
        "verified_work": works,
        "approved_segments": segments,
    }
