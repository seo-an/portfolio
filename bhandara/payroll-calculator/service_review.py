"""Review-only external-service contracts from the SAME Contracts workbook.

Hourly/daily service quantities come from the validated Worktime handoff, not
an extra service-work-records spreadsheet. Neither a building-access event nor
a draft Worktime calculation is approved vendor billing evidence. No service
estimate is sent to employee Payroll or treated as a tax/withholding decision.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from bhandara.common.io.input_layout import InputLayoutError, as_day, read_sheet


SERVICE_BASIS = {"HOURLY", "DAILY", "PROJECT"}


def _positive(value: Any, name: str, *, zero: bool = False) -> Decimal:
    if value is None or value == "" or isinstance(value, bool):
        raise InputLayoutError(f"{name}: a numeric value is required")
    try:
        result = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise InputLayoutError(f"{name}: invalid numeric value") from exc
    if not result.is_finite() or result < 0 or (not zero and result == 0):
        raise InputLayoutError(f"{name}: positive finite value required")
    return result


def _optional_day(value: Any, field: str) -> str | None:
    return None if value in (None, "") else as_day(value, field)


def load_v2_services(
    path: Path, identities: Mapping[str, Mapping[str, str]], *,
    service_relationships: set[str] | frozenset[str],
) -> list[dict]:
    """Read service entries in Contracts without guessing meaning from IDs.

    `party_id` and `worker_id` are optional workbook columns only for
    employee contracts; service entries must explicitly provide party_id.
    Time-based services must identify the Worktime worker_id as well.
    """
    rows = read_sheet(
        path, (
            "contract_id", "employee_id", "pay_basis", "contract_amount",
            "effective_from", "effective_to", "standard_day_hours",
            "amount_type", "relationship_type",
        ), sheet_name="Contracts",
    )
    internal_workers = {x["worker_id"] for x in identities.values()}
    by_worker: dict[str, list[dict]] = defaultdict(list)
    party_by_worker: dict[str, str] = {}
    found: list[dict] = []
    for row in rows:
        relationship = str(row.get("relationship_type") or "").strip().upper()
        if relationship not in service_relationships:
            continue
        line = row["_row_number"]
        ident = str(row.get("contract_id") or "").strip()
        party = str(row.get("party_id") or "").strip()
        internal_employee = str(row.get("employee_id") or "").strip()
        worker = str(row.get("worker_id") or "").strip()
        basis = str(row.get("pay_basis") or "").strip().upper()
        amount_type = str(row.get("amount_type") or "").strip().upper()
        if not ident or not party or internal_employee:
            raise InputLayoutError(
                f"pay-contract.xlsx Contracts row {line}: service requires "
                "contract_id and party_id with blank employee_id"
            )
        if party in identities:
            raise InputLayoutError(
                f"pay-contract.xlsx Contracts row {line}: service party_id "
                "collides with employee identity"
            )
        if basis not in SERVICE_BASIS:
            raise InputLayoutError(
                f"pay-contract.xlsx Contracts row {line}: unsupported service pay_basis"
            )
        if basis in {"HOURLY", "DAILY"}:
            if amount_type != "RATE":
                raise InputLayoutError(
                    f"pay-contract.xlsx Contracts row {line}: "
                    "hourly/daily service amount_type must be RATE"
                )
            if not worker or worker in internal_workers:
                raise InputLayoutError(
                    f"pay-contract.xlsx Contracts row {line}: service worker_id "
                    "required and must not duplicate employee payroll worker"
                )
            previous = party_by_worker.setdefault(worker, party)
            if previous != party:
                raise InputLayoutError(
                    f"pay-contract.xlsx Contracts row {line}: worker_id mapped "
                    "to multiple service parties"
                )
        else:
            if amount_type != "TOTAL" or worker:
                raise InputLayoutError(
                    f"pay-contract.xlsx Contracts row {line}: PROJECT requires "
                    "TOTAL amount_type and blank worker_id"
                )
        start = as_day(row.get("effective_from"), "effective_from")
        end = _optional_day(row.get("effective_to"), "effective_to")
        if end is not None and end < start:
            raise InputLayoutError(
                f"pay-contract.xlsx Contracts row {line}: inverted dates"
            )
        standard_hours = row.get("standard_day_hours")
        if basis == "DAILY":
            standard_hours = _positive(
                standard_hours, f"service standard_day_hours row {line}"
            )
            if standard_hours > 24:
                raise InputLayoutError(
                    f"pay-contract.xlsx Contracts row {line}: day hours exceed 24"
                )
        elif standard_hours not in (None, ""):
            raise InputLayoutError(
                f"pay-contract.xlsx Contracts row {line}: "
                "standard_day_hours is only used for DAILY service"
            )
        else:
            standard_hours = None
        entry = {
            "service_contract_id": ident,
            "external_vendor_id": party,
            "relationship_type": relationship,
            "worker_id": worker or None,
            "pay_basis": basis,
            "contract_rate": _positive(
                row.get("contract_amount"), f"service contract_amount row {line}"
            ),
            "effective_from": start,
            "effective_to": end,
            "standard_day_hours": standard_hours,
            "source_row": line,
        }
        if worker and basis in {"HOURLY", "DAILY"}:
            by_worker[worker].append(entry)
        found.append(entry)
    # A vendor may have simultaneous independent projects or different workers.
    # Reusing *one* Worktime worker for overlapping time-based contracts is
    # ambiguous: its hours could otherwise be counted more than once.
    for worker, contracts in by_worker.items():
        ordered = sorted(contracts, key=lambda x: x["effective_from"])
        for previous, next_item in zip(ordered, ordered[1:]):
            if (previous["effective_to"] is None
                    or next_item["effective_from"] <= previous["effective_to"]):
                raise InputLayoutError(
                    f"pay-contract.xlsx: overlapping Worktime service contracts for {worker}"
                )
    return found


def time_worker_ids(services: list[dict]) -> set[str]:
    return {
        str(c["worker_id"]) for c in services
        if c["pay_basis"] in {"HOURLY", "DAILY"}
    }


def review_services(
    services: list[dict], source_rows: Mapping[str, list[dict]], *,
    source_from: str, source_to: str, pay_period: str,
) -> list[dict]:
    """Estimate using Worktime *facts*, always review-only and never payable."""
    output: list[dict] = []
    for contract in sorted(services, key=lambda c: c["service_contract_id"]):
        basis = contract["pay_basis"]
        start = max(source_from, contract["effective_from"])
        end = min(source_to, contract["effective_to"] or source_to)
        matches = [
            row for row in source_rows.get(contract["worker_id"], [])
            if start <= str(row["work_date"]) <= end
        ] if basis != "PROJECT" and start <= end else []
        hours = Decimal("0")
        days = 0
        flags = False
        partial = False
        for row in matches:
            ordinary = _positive(
                row.get("ordinary_hours"), "Worktime ordinary_hours", zero=True
            )
            worked = _positive(
                row.get("worked_hours"), "Worktime worked_hours", zero=True
            )
            hours += ordinary
            if worked > 0 and ordinary >= (contract["standard_day_hours"] or 0):
                days += 1
            elif basis == "DAILY" and worked > 0:
                partial = True
            if row.get("validation_flags"):
                flags = True
        quantity = hours if basis == "HOURLY" else Decimal(days)
        estimate = (
            contract["contract_rate"] * quantity
            if basis in {"HOURLY", "DAILY"} and matches and quantity > 0
            else None
        )
        reason = (
            "PROJECT_DELIVERY_EVIDENCE_REQUIRED"
            if basis == "PROJECT" else
            "WORKTIME_QUANTITY_MISSING"
            if not matches or estimate is None else
            "WORKTIME_FLAGS_AND_BILLING_REVIEW_REQUIRED"
            if flags or partial else
            "SERVICE_BILLING_AND_TAX_REVIEW_REQUIRED"
        )
        output.append({
            "service_contract_id": contract["service_contract_id"],
            "external_vendor_id": contract["external_vendor_id"],
            "relationship_type": contract["relationship_type"],
            "worker_id": contract["worker_id"],
            "pay_basis": basis,
            "contract_rate": str(contract["contract_rate"]),
            "effective_from": contract["effective_from"],
            "effective_to": contract["effective_to"],
            "payroll_period": pay_period,
            "billable_quantity": str(quantity) if matches else "0",
            "estimated_service_amount": str(estimate) if estimate is not None else None,
            "source_record_count": len(matches),
            "source_kind": "WORKTIME_UNCLOSED" if basis != "PROJECT" else "PROJECT_CONTRACT",
            "status": "REVIEW_REQUIRED",
            "approved": False,
            "finalizable": False,
            "reason": reason,
        })
    return output
