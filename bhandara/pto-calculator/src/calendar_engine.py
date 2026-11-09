"""Deterministic calendar date resolution.

This module resolves date rules that require no external calendar conversion.
Lunar rules deliberately require an injected converter so the workflow never
silently approximates lunar dates.
"""

from calendar import monthrange
import hashlib
import json
from datetime import datetime
from pathlib import Path
from datetime import date, timedelta
from typing import Callable

from .lunar_adapter import lunar_to_solar


WEEKDAY_INDEX = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6,
}


def _resolve_nth_weekday(year: int, rule: dict) -> date:
    month = rule["month"]
    target_weekday = WEEKDAY_INDEX[rule["weekday"]]
    first = date(year, month, 1)
    day = 1 + (target_weekday - first.weekday()) % 7 + 7 * (rule["nth"] - 1)
    last_day = monthrange(year, month)[1]
    if day > last_day:
        raise ValueError(
            f"NTH_WEEKDAY does not exist: {year}-{month:02d} "
            f"{rule['nth']} {rule['weekday']}"
        )
    return date(year, month, day)


def resolve_event_date(
    event: dict,
    year: int,
    *,
    lunar_converter: Callable[[int, int, int, bool], date] = lunar_to_solar,
) -> date:
    """Resolve an event's base date for a target Gregorian year."""

    rule = event["date_rule"]
    rule_type = rule["type"]

    if rule_type == "FIXED_SOLAR":
        return date(year, rule["month"], rule["day"])

    if rule_type == "NTH_WEEKDAY":
        return _resolve_nth_weekday(year, rule)

    if rule_type == "ONE_OFF":
        resolved = date.fromisoformat(rule["date"])
        if resolved.year != year:
            raise ValueError(
                f"ONE_OFF event {event['id']} does not occur in {year}"
            )
        return resolved

    if rule_type == "FIXED_LUNAR":
        return lunar_converter(
            year,
            rule["month"],
            rule["day"],
            rule.get("intercalation", False),
        )

    raise ValueError(f"unsupported date rule type: {rule_type}")


def expand_event_dates(base_date: date, event: dict) -> list[date]:
    """Expand an event base date using optional days_before/days_after span."""

    span = event.get("span") or {}
    days_before = span.get("days_before", 0)
    days_after = span.get("days_after", 0)

    if (
        not isinstance(days_before, int)
        or isinstance(days_before, bool)
        or days_before < 0
    ):
        raise ValueError("span.days_before must be a non-negative integer")
    if (
        not isinstance(days_after, int)
        or isinstance(days_after, bool)
        or days_after < 0
    ):
        raise ValueError("span.days_after must be a non-negative integer")

    return [
        base_date + timedelta(days=offset)
        for offset in range(-days_before, days_after + 1)
    ]


def build_resolved_records(
    events: list[dict],
    policies: list[dict],
    year: int,
    *,
    lunar_converter: Callable[[int, int, int, bool], date] = lunar_to_solar,
) -> list[dict]:
    """Build resolved calendar records for events resolvable for a target year.

    Substitute holidays are intentionally not generated here yet.
    """

    from .calendar_contract import find_effective_national_policy

    records = []
    for event in events:
        try:
            base_date = resolve_event_date(
                event, year, lunar_converter=lunar_converter
            )
        except ValueError as exc:
            if event["date_rule"]["type"] == "ONE_OFF" and "does not occur" in str(exc):
                continue
            raise

        for resolved_date in expand_event_dates(base_date, event):
            policy = find_effective_national_policy(
                policies, event["id"], resolved_date
            )
            if policy is None:
                raise ValueError(
                    f"no effective policy for {event['id']} on {resolved_date}"
                )

            records.append(
                {
                    "date": resolved_date.isoformat(),
                    "event_id": event["id"],
                    "name": event["name"],
                    "source": "NATIONAL",
                    "category": event.get("category"),
                    "day_treatment": policy.get("day_treatment"),
                    "legal_effects": dict(policy["legal_effects"]),
                    "substitute_holiday_rule": policy.get("substitute_holiday"),
                    "derived_from": {
                        "calendar": "national-calendar.json",
                        "policy": "national-calendar-policy.json",
                    },
                }
            )

    return sorted(records, key=lambda row: (row["date"], row["event_id"]))



ARTICLE_3_WEEKEND_EVENTS = {
    "INDEPENDENCE_MOVEMENT_DAY",
    "BUDDHAS_BIRTHDAY",
    "LABOR_DAY",
    "CHILDRENS_DAY",
    "CONSTITUTION_DAY",
    "LIBERATION_DAY",
    "NATIONAL_FOUNDATION_DAY",
    "HANGEUL_DAY",
    "CHRISTMAS_DAY",
}
ARTICLE_3_SUNDAY_ONLY_EVENTS = {
    "LUNAR_NEW_YEAR",
    "CHUSEOK",
}


def _is_public_holiday_record(record: dict) -> bool:
    return bool(record.get("legal_effects", {}).get("public_holiday"))


def _next_substitute_date(start_date: date, occupied_dates: set[date]) -> date:
    candidate = start_date + timedelta(days=1)
    while (
        candidate in occupied_dates
        or candidate.weekday() == 6
        or candidate.weekday() == 5
    ):
        candidate += timedelta(days=1)
    return candidate


def generate_substitute_holiday_records(records: list[dict]) -> list[dict]:
    """Generate substitute holidays under Article 3 of the holiday regulation.

    The input must already contain effective-dated national holiday policy.
    Each multi-day holiday event is treated as one occurrence, so Lunar New
    Year and Chuseok generate at most one substitute holiday per occurrence.
    """

    public_records = [row for row in records if _is_public_holiday_record(row)]
    occupied_dates = {date.fromisoformat(row["date"]) for row in public_records}

    records_by_event: dict[str, list[dict]] = {}
    for row in public_records:
        if row.get("substitute_holiday_rule") != "REGULATION_ARTICLE_3":
            continue
        records_by_event.setdefault(row["event_id"], []).append(row)

    date_to_event_ids: dict[date, set[str]] = {}
    for row in public_records:
        resolved_date = date.fromisoformat(row["date"])
        date_to_event_ids.setdefault(resolved_date, set()).add(row["event_id"])

    generated = []
    reserved_substitute_dates: set[date] = set()

    for event_id, event_rows in sorted(records_by_event.items()):
        event_dates = sorted(date.fromisoformat(row["date"]) for row in event_rows)

        weekend_trigger = False
        if event_id in ARTICLE_3_WEEKEND_EVENTS:
            weekend_trigger = any(day.weekday() in {5, 6} for day in event_dates)
        elif event_id in ARTICLE_3_SUNDAY_ONLY_EVENTS:
            weekend_trigger = any(day.weekday() == 6 for day in event_dates)

        overlap_trigger = any(
            day.weekday() not in {5, 6}
            and any(other_id != event_id for other_id in date_to_event_ids[day])
            for day in event_dates
        )

        if not weekend_trigger and not overlap_trigger:
            continue

        source = event_rows[0]
        substitute_date = _next_substitute_date(
            max(event_dates),
            occupied_dates | reserved_substitute_dates,
        )
        reserved_substitute_dates.add(substitute_date)

        generated.append(
            {
                "date": substitute_date.isoformat(),
                "event_id": event_id,
                "name": f"{source['name']} 대체공휴일",
                "source": "NATIONAL",
                "category": source.get("category"),
                "day_treatment": source.get("day_treatment"),
                "legal_effects": dict(source["legal_effects"]),
                "substitute_holiday_rule": "REGULATION_ARTICLE_3",
                "occurrence_type": "SUBSTITUTE",
                "substitutes_for": [day.isoformat() for day in event_dates],
                "derived_from": dict(source["derived_from"]),
            }
        )

    return sorted(generated, key=lambda row: (row["date"], row["event_id"]))

def _sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_resolved_calendar_document(
    year: int,
    records: list[dict],
    *,
    generated_at: datetime,
    source_paths: dict[str, str | Path],
) -> dict:
    """Wrap records with generation time and immutable source fingerprints."""

    source_snapshot = {
        name: {
            "file": Path(path).name,
            "sha256": _sha256_file(path),
        }
        for name, path in sorted(source_paths.items())
    }

    return {
        "schema_version": "1.0",
        "jurisdiction": "KR",
        "year": year,
        "artifact_type": "RESOLVED_NATIONAL_CALENDAR",
        "derived": True,
        "source_of_truth": False,
        "generated_at": generated_at.isoformat(),
        "source_snapshot": source_snapshot,
        "records": records,
    }


def materialize_resolved_calendar(
    output_path: str | Path,
    document: dict,
) -> Path:
    """Write stable JSON for a resolved calendar document."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    path.write_text(payload, encoding="utf-8")
    return path


def check_resolved_calendar_freshness(
    document: dict,
    *,
    source_paths: dict[str, str | Path],
) -> dict:
    """Compare a resolved document's source snapshot with current source files."""

    snapshot = document.get("source_snapshot")
    if not isinstance(snapshot, dict):
        return {
            "status": "INVALID",
            "changed_sources": [],
            "reason": "missing source_snapshot",
        }

    changed_sources = []
    for name, path in sorted(source_paths.items()):
        saved = snapshot.get(name)
        if not isinstance(saved, dict) or not saved.get("sha256"):
            return {
                "status": "INVALID",
                "changed_sources": [],
                "reason": f"missing source snapshot: {name}",
            }

        current_hash = _sha256_file(path)
        if current_hash != saved["sha256"]:
            changed_sources.append(name)

    if changed_sources:
        return {
            "status": "STALE",
            "changed_sources": changed_sources,
            "reason": "source fingerprint changed",
        }

    return {
        "status": "CURRENT",
        "changed_sources": [],
        "reason": None,
    }
