"""Calendar source contracts for national, company, and employee event data.

This layer preserves what an event is and who owns it. Legal effects are
resolved separately by effective-dated policy records.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any


EVENT_SOURCES = {"NATIONAL", "COMPANY"}
DATE_RULE_TYPES = {"FIXED_SOLAR", "FIXED_LUNAR", "NTH_WEEKDAY", "ONE_OFF"}
DAY_TREATMENTS = {
    "NORMAL_DAY",
    "PUBLIC_HOLIDAY",
    "PAID_HOLIDAY",
    "UNPAID_HOLIDAY",
    "SPECIAL_SCHEDULE",
}


def _load_json(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be an object")
    return data


def _validate_date_rule(rule: dict[str, Any], context: str) -> None:
    rule_type = rule.get("type")
    if rule_type not in DATE_RULE_TYPES:
        raise ValueError(f"{context}: unsupported date_rule.type: {rule_type!r}")

    if rule_type in {"FIXED_SOLAR", "FIXED_LUNAR"}:
        month = rule.get("month")
        day = rule.get("day")
        if not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError(f"{context}: month must be 1..12")
        if not isinstance(day, int) or not 1 <= day <= 31:
            raise ValueError(f"{context}: day must be 1..31")
    elif rule_type == "NTH_WEEKDAY":
        month = rule.get("month")
        nth = rule.get("nth")
        weekday = rule.get("weekday")
        if not isinstance(month, int) or not 1 <= month <= 12:
            raise ValueError(f"{context}: month must be 1..12")
        if not isinstance(nth, int) or not 1 <= nth <= 5:
            raise ValueError(f"{context}: nth must be 1..5")
        if weekday not in {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}:
            raise ValueError(f"{context}: invalid weekday")
    elif rule_type == "ONE_OFF":
        try:
            date.fromisoformat(str(rule["date"]))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"{context}: ONE_OFF requires ISO date") from exc


def validate_calendar_events(data: dict[str, Any], source: str) -> dict[str, Any]:
    source = source.upper()
    if source not in EVENT_SOURCES:
        raise ValueError(f"unsupported calendar source: {source}")

    events = data.get("events")
    if not isinstance(events, list):
        raise ValueError("calendar requires events array")

    seen: set[str] = set()
    for index, event in enumerate(events):
        context = f"events[{index}]"
        if not isinstance(event, dict):
            raise ValueError(f"{context}: event must be an object")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError(f"{context}: id is required")
        if event_id in seen:
            raise ValueError(f"duplicate event id: {event_id}")
        seen.add(event_id)

        if not isinstance(event.get("name"), str) or not event["name"].strip():
            raise ValueError(f"{context}: name is required")
        rule = event.get("date_rule")
        if not isinstance(rule, dict):
            raise ValueError(f"{context}: date_rule is required")
        _validate_date_rule(rule, context)

        if source == "COMPANY":
            treatment = event.get("day_treatment")
            if treatment not in DAY_TREATMENTS:
                raise ValueError(
                    f"{context}: company event requires valid day_treatment"
                )

    return data


def load_calendar_events(path: Path | str, source: str) -> dict[str, Any]:
    return validate_calendar_events(_load_json(path), source=source)


def validate_national_calendar_policy(data: dict[str, Any]) -> dict[str, Any]:
    policies = data.get("policies")
    if not isinstance(policies, list):
        raise ValueError("national calendar policy requires policies array")

    for index, policy in enumerate(policies):
        context = f"policies[{index}]"
        if not isinstance(policy, dict):
            raise ValueError(f"{context}: policy must be an object")
        if not policy.get("event_id"):
            raise ValueError(f"{context}: event_id is required")
        try:
            effective_from = date.fromisoformat(str(policy["effective_from"]))
            effective_to = (
                date.fromisoformat(str(policy["effective_to"]))
                if policy.get("effective_to") is not None
                else None
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(f"{context}: invalid effective date") from exc
        if effective_to is not None and effective_from > effective_to:
            raise ValueError(f"{context}: effective_from must be <= effective_to")
        legal_effects = policy.get("legal_effects")
        if not isinstance(legal_effects, dict):
            raise ValueError(f"{context}: legal_effects is required")
        if not isinstance(legal_effects.get("public_holiday"), bool):
            raise ValueError(
                f"{context}: legal_effects.public_holiday must be boolean"
            )
        worker_rule = legal_effects.get("worker_paid_holiday")
        if worker_rule not in {
            "DIRECT_STATUTORY",
            "LABOR_STANDARDS_ACT",
            "NOT_APPLICABLE",
        }:
            raise ValueError(
                f"{context}: invalid legal_effects.worker_paid_holiday rule"
            )
        if (
            policy.get("day_treatment") is not None
            and policy["day_treatment"] not in DAY_TREATMENTS
        ):
            raise ValueError(f"{context}: invalid day_treatment")

    return data


def load_national_calendar_policy(path: Path | str) -> dict[str, Any]:
    return validate_national_calendar_policy(_load_json(path))


def find_effective_national_policy(
    policies: list[dict[str, Any]],
    event_id: str,
    target_date: date,
) -> dict[str, Any] | None:
    matches = []
    for policy in policies:
        if policy["event_id"] != event_id:
            continue
        start = date.fromisoformat(str(policy["effective_from"]))
        end = (
            date.fromisoformat(str(policy["effective_to"]))
            if policy.get("effective_to") is not None
            else None
        )
        if start <= target_date and (end is None or target_date <= end):
            matches.append(policy)

    if len(matches) > 1:
        raise ValueError(
            f"overlapping national calendar policies: event_id={event_id}, "
            f"target_date={target_date}"
        )
    return matches[0] if matches else None
