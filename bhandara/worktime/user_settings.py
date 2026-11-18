"""Tool-local, user-editable defaults. External JSON may override each key.

These are *detection* windows and recording tolerances, not legal conclusions,
company approval rules, overtime pay rates, or permanent HR policy.
"""
from __future__ import annotations

ATTENDANCE_DETECTION_DEFAULTS = {
    "late_grace_min": 0,
    "early_leave_grace_min": 0,
    "outside_schedule_grace_min": 0,
    "night_start": "22:00",
    "night_end": "06:00",
}
