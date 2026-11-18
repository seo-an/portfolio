"""Attendance Detection — candidate events, never automatic HR/payroll approval.

Use importlib.import_module("bhandara.worktime.attendance-detection") for the
canonical public kebab-case Module path.
"""
from .calculation import DetectionInputError, detect_attendance
from .handoff import detect_attendance_xlsx

__all__ = ["DetectionInputError", "detect_attendance", "detect_attendance_xlsx"]
