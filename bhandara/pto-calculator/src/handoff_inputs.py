"""Validate and expose a prepared PTO Tooth handoff to calculator functions."""

from __future__ import annotations

from typing import Any


REQUIRED_DATASETS = {
    "employees",
    "schedule_rows",
    "assignment_rows",
    "monthly_rows",
    "attendance_rows",
    "event_rows",
}


def load_handoff_inputs(handoff: dict[str, Any]) -> dict[str, Any]:
    missing = REQUIRED_DATASETS - set(handoff)
    if missing:
        raise ValueError(f"PTO handoff missing datasets: {sorted(missing)}")

    unexpected = set(handoff) - REQUIRED_DATASETS
    if unexpected:
        raise ValueError(f"PTO handoff has unexpected datasets: {sorted(unexpected)}")

    for name in REQUIRED_DATASETS:
        if not isinstance(handoff[name], list):
            raise TypeError(f"PTO handoff dataset must be a list: {name}")

    return handoff
