"""Normalize human-friendly Korean employee-event labels to workflow codes."""

from __future__ import annotations

import re
import unicodedata


EVENT_TYPE_ALIASES = {
    "ANNUAL_LEAVE": {
        "연차", "연차휴가", "연차유급휴가",
    },
    "PARENTAL_LEAVE": {
        "육아휴직", "육휴",
    },
    "OCCUPATIONAL_INJURY_LEAVE": {
        "업무상재해휴업", "업무상재해휴직", "산재휴업",
    },
    "MATERNITY_PROTECTION_LEAVE": {
        "출산전후휴가", "출산휴가",
    },
    "CHILDCARE_REDUCED_HOURS": {
        "육아기근로시간단축", "육아기단축근무",
    },
    "PREGNANCY_REDUCED_HOURS": {
        "임신기근로시간단축", "임신기단축근무",
    },
    "BEREAVEMENT_LEAVE": {
        "경조휴가", "경조사휴가",
    },
    "SICK_LEAVE": {
        "병가",
    },
    "LEAVE_OF_ABSENCE": {
        "휴직", "일반휴직",
    },
}


def _normalize_label(value: str) -> str:
    """Normalize harmless presentation differences, not semantic differences."""
    value = unicodedata.normalize("NFKC", value).strip()
    value = re.sub(r"[\s_-]+", "", value)
    return value.casefold()


_ALIAS_INDEX: dict[str, str] = {}
for canonical_code, aliases in EVENT_TYPE_ALIASES.items():
    for alias in aliases | {canonical_code}:
        key = _normalize_label(alias)
        previous = _ALIAS_INDEX.get(key)
        if previous is not None and previous != canonical_code:
            raise RuntimeError(
                f"ambiguous employee event alias: {alias!r} -> "
                f"{previous!r}, {canonical_code!r}"
            )
        _ALIAS_INDEX[key] = canonical_code


def normalize_event_type(value: object) -> str | None:
    """Return a canonical event code, or None when the label is unknown."""
    if value is None:
        return None
    label = str(value).strip()
    if not label:
        return None
    return _ALIAS_INDEX.get(_normalize_label(label))


# Detailed labels preserve policy-relevant distinctions while keeping the
# existing normalize_event_type() API backward compatible.
EVENT_DETAIL_ALIASES = {
    ("BEREAVEMENT_LEAVE", "PARENT_DEATH"): {
        "모친상", "부친상", "부모상",
    },
    ("BEREAVEMENT_LEAVE", "PATERNAL_GRANDPARENT_DEATH"): {
        "조모상", "조부상", "조부모상",
    },
    ("BEREAVEMENT_LEAVE", "MATERNAL_GRANDPARENT_DEATH"): {
        "외조모상", "외조부상", "외조부모상",
    },
    ("BEREAVEMENT_LEAVE", "SIBLING_DEATH"): {
        "형제상", "자매상", "형제자매상",
    },
    ("BEREAVEMENT_LEAVE", "SPOUSE_PARENT_DEATH"): {
        "빙부상", "빙모상", "배우자부모상",
    },
    ("BEREAVEMENT_LEAVE", "SPOUSE_DEATH"): {
        "배우자상", "남편상", "아내상",
    },
    ("BEREAVEMENT_LEAVE", "CHILD_DEATH"): {
        "자녀상", "자식상",
    },
    ("BEREAVEMENT_LEAVE", "SELF_MARRIAGE"): {
        "본인결혼", "본인결혼휴가",
    },
    ("BEREAVEMENT_LEAVE", "CHILD_MARRIAGE"): {
        "자녀결혼", "자녀결혼휴가",
    },
}

_DETAIL_ALIAS_INDEX: dict[str, tuple[str, str | None]] = {}
for (event_type, event_subtype), aliases in EVENT_DETAIL_ALIASES.items():
    for alias in aliases:
        key = _normalize_label(alias)
        previous = _DETAIL_ALIAS_INDEX.get(key)
        current = (event_type, event_subtype)
        if previous is not None and previous != current:
            raise RuntimeError(
                f"ambiguous employee event detail alias: {alias!r} -> "
                f"{previous!r}, {current!r}"
            )
        _DETAIL_ALIAS_INDEX[key] = current


def _build_company_alias_index(
    company_aliases: dict[str, dict[str, str | None]] | None,
) -> dict[str, tuple[str, str | None]]:
    index: dict[str, tuple[str, str | None]] = {}
    for raw_label, target in (company_aliases or {}).items():
        event_type = target.get("event_type")
        event_subtype = target.get("event_subtype")
        if not event_type:
            raise ValueError(f"company alias requires event_type: {raw_label!r}")
        index[_normalize_label(raw_label)] = (
            str(event_type).strip().upper(),
            str(event_subtype).strip().upper() if event_subtype else None,
        )
    return index


def normalize_event_detail(
    value: object,
    *,
    company_aliases: dict[str, dict[str, str | None]] | None = None,
) -> dict[str, str | None]:
    """Normalize a human label while preserving its raw representation.

    Company aliases take precedence over built-in aliases. Unknown labels are
    never guessed.
    """
    raw_event_type = None if value is None else str(value).strip()
    if not raw_event_type:
        return {
            "raw_event_type": raw_event_type,
            "event_type": None,
            "event_subtype": None,
        }

    key = _normalize_label(raw_event_type)
    company_target = _build_company_alias_index(company_aliases).get(key)
    if company_target is not None:
        event_type, event_subtype = company_target
    elif key in _DETAIL_ALIAS_INDEX:
        event_type, event_subtype = _DETAIL_ALIAS_INDEX[key]
    else:
        event_type = _ALIAS_INDEX.get(key)
        event_subtype = None

    return {
        "raw_event_type": raw_event_type,
        "event_type": event_type,
        "event_subtype": event_subtype,
    }
