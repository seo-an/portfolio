"""Provisional Payroll payment taxability *review*, never a withholding engine.

No statutory exemption, non-taxable ceiling, insurance, legal employment
status or employee eligibility is inferred. Classification is opt-in through an
explicit company_policy.taxability_review rule with a recorded policy_ref.
A NON_TAXABLE ceiling is supplied as a company-reviewed amount, never hardcoded.

All results remain REVIEW_REQUIRED and cannot authorize pay, tax or insurance.
Service contractors are out of scope: only employee Payroll worker_runs are read.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


STATUSES = frozenset({"TAXABLE", "NON_TAXABLE", "REVIEW"})
ZERO = Decimal("0")


class TaxabilityReviewError(ValueError):
    pass


def _amount(value: Any, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise TaxabilityReviewError(f"{name}: finite non-negative amount required")
    try:
        out = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise TaxabilityReviewError(f"{name}: invalid amount") from exc
    if not out.is_finite() or out < 0:
        raise TaxabilityReviewError(f"{name}: finite non-negative amount required")
    return out


def _policy(
    company_policy: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    raw = company_policy.get("taxability_review", {})
    if not isinstance(raw, Mapping):
        raise TaxabilityReviewError("company_policy.taxability_review must be a mapping")
    if raw and raw.get("schema_version") != "1.0":
        raise TaxabilityReviewError("taxability_review.schema_version must be 1.0")
    configured = raw.get("pay_items", {})
    if not isinstance(configured, Mapping):
        raise TaxabilityReviewError("taxability_review.pay_items must be a mapping")
    valid_codes = {
        item.get("code") for item in registry.get("items", [])
        if isinstance(item, Mapping) and item.get("type") == "지급"
    }
    valid_codes.update({
        item.get("code") for item in registry.get("items", [])
        if isinstance(item, Mapping) and item.get("type") == "정산"
        and item.get("code") == "retroactive_pay"
    })
    validated: dict[str, dict[str, Any]] = {}
    for code, spec in configured.items():
        if not isinstance(code, str) or code not in valid_codes:
            raise TaxabilityReviewError(
                "taxability policy has unknown or non-payment pay item"
            )
        if not isinstance(spec, Mapping):
            raise TaxabilityReviewError(f"{code}: taxability rule must be a mapping")
        status = spec.get("status")
        if status not in STATUSES:
            raise TaxabilityReviewError(f"{code}: invalid taxability status")
        policy_ref = spec.get("policy_ref")
        if status != "REVIEW" and (
            not isinstance(policy_ref, str) or not policy_ref.strip()
        ):
            raise TaxabilityReviewError(
                f"{code}: TAXABLE/NON_TAXABLE require explicit policy_ref"
            )
        cap = spec.get("cap_per_worker_period")
        if status == "NON_TAXABLE":
            if cap is None:
                raise TaxabilityReviewError(
                    f"{code}: NON_TAXABLE requires explicit cap_per_worker_period"
                )
            cap_amount = _amount(cap, f"{code} cap_per_worker_period")
            if cap_amount <= ZERO:
                raise TaxabilityReviewError(f"{code}: cap must be positive")
        else:
            if cap is not None:
                raise TaxabilityReviewError(
                    f"{code}: cap only allowed for NON_TAXABLE"
                )
            cap_amount = None
        validated[code] = {
            "status": status,
            "policy_ref": policy_ref.strip()
                if isinstance(policy_ref, str) and policy_ref.strip() else None,
            "cap": cap_amount,
        }
    return validated


def _review_row(
    worker: str, code: str, amount: Decimal, classification: str, *,
    policy_ref: str | None, source: str | None, reason: str,
) -> dict[str, Any]:
    return {
        "worker_id": worker,
        "pay_item_code": code,
        "amount": str(amount),
        "classification": classification,
        "policy_ref": policy_ref,
        "source": source,
        "reason": reason,
        "approved": False,
        "finalizable": False,
    }


def review_payment_taxability(
    composition: Mapping[str, Any],
    company_policy: Mapping[str, Any],
    registry: Mapping[str, Any],
    *,
    payroll_period: str,
    expected_worker_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Partition *calculated employee payment* by explicit tentative category.

    Conservation rule: taxable_candidate + non_taxable_candidate +
    review_required == source employee pay_total for every calculated worker.
    Deductions/settlement adjustments are not remuneration and are excluded.
    Uncalculated workers have no amount asserted, and are clearly identified.
    """
    rules = _policy(company_policy, registry)
    workers = composition.get("worker_runs")
    if not isinstance(workers, Mapping):
        raise TaxabilityReviewError("composition.worker_runs must be a mapping")
    expected = set(expected_worker_ids or workers.keys())
    if not expected or any(not isinstance(w, str) or not w for w in expected):
        raise TaxabilityReviewError("expected payroll workers required")
    if set(workers) - expected:
        raise TaxabilityReviewError("unexpected worker in taxability review")
    totals = {
        "taxable_candidate": ZERO,
        "non_taxable_candidate": ZERO,
        "review_required": ZERO,
        "employee_payment_total": ZERO,
    }
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for worker in sorted(expected):
        run = workers.get(worker)
        if not isinstance(run, Mapping) or run.get("final_payroll") is None:
            missing.append(worker)
            continue
        remaining = defaultdict(lambda: ZERO)
        worker_totals = {key: ZERO for key in totals}
        for result in run.get("results", []):
            if not isinstance(result, Mapping):
                raise TaxabilityReviewError("worker payroll result must be a mapping")
            if result.get("direction") != "pay":
                continue
            if result.get("worker_id") != worker or result.get("payroll_period") != payroll_period:
                raise TaxabilityReviewError("payroll result worker/period mismatch")
            code = result.get("pay_item_code")
            if not isinstance(code, str) or not code:
                raise TaxabilityReviewError("pay_item_code required")
            value = _amount(result.get("calculated_amount"), f"{code} amount")
            worker_totals["employee_payment_total"] += value
            if value == ZERO:
                continue
            source = result.get("source")
            rule = rules.get(code, {"status": "REVIEW", "policy_ref": None, "cap": None})
            status = rule["status"]
            policy_ref = rule["policy_ref"]
            if result.get("item_type") != "지급":
                # Retroactive/settlement payments require underlying item history.
                # Do not infer tax classification from the generic settlement code.
                status = "REVIEW"
                policy_ref = None
            if status == "TAXABLE":
                parts = [(value, "TAXABLE", "EXPLICIT_POLICY_REVIEW_REQUIRED")]
            elif status == "NON_TAXABLE":
                prior = remaining[code]
                cap = rule["cap"]
                allowed = min(value, max(ZERO, cap - prior))
                remaining[code] += allowed
                parts = []
                if allowed:
                    parts.append((
                        allowed, "NON_TAXABLE",
                        "POLICY_EXEMPTION_AND_ELIGIBILITY_REVIEW_REQUIRED",
                    ))
                if value > allowed:
                    parts.append((
                        value - allowed, "REVIEW",
                        "NON_TAXABLE_CAP_EXCESS_UNCLASSIFIED",
                    ))
            else:
                parts = [(value, "REVIEW", "NO_APPROVED_TAXABILITY_CLASSIFICATION")]
            for amount, category, reason in parts:
                rows.append(_review_row(
                    worker, code, amount, category,
                    policy_ref=policy_ref, source=source, reason=reason,
                ))
                key = {
                    "TAXABLE": "taxable_candidate",
                    "NON_TAXABLE": "non_taxable_candidate",
                    "REVIEW": "review_required",
                }[category]
                worker_totals[key] += amount
        if sum((
            worker_totals["taxable_candidate"],
            worker_totals["non_taxable_candidate"],
            worker_totals["review_required"],
        ), ZERO) != worker_totals["employee_payment_total"]:
            raise TaxabilityReviewError("taxability classification amount not conserved")
        final = run["final_payroll"]
        expected_total = _amount(
            final["totals"]["pay_total"], f"{worker} pay_total"
        )
        if expected_total != worker_totals["employee_payment_total"]:
            raise TaxabilityReviewError("taxability total differs from Payroll pay_total")
        for field in totals:
            totals[field] += worker_totals[field]
    return {
        "schema_version": "1.0",
        "status": "REVIEW_REQUIRED",
        "payroll_period": payroll_period,
        "approved": False,
        "finalizable": False,
        "tax_and_insurance_computed": False,
        "policy_enabled": bool(rules),
        "source": "EMPLOYEE_PAYROLL_RESULTS_ONLY",
        "totals": {k: str(v) for k, v in totals.items()},
        "classified_worker_count": len(expected) - len(missing),
        "missing_worker_ids": missing,
        "rows": sorted(rows, key=lambda x: (
            x["worker_id"], x["pay_item_code"], x["classification"]
        )),
        "notice": (
            "Review-only candidates, not legal taxability, statutory exemption, "
            "withholding, insurance, pay approval or ledger entries. "
            "Unknown and cap-excess amounts stay REVIEW, never silently taxable."
        ),
    }
