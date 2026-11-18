"""Attendance Verification — biometric reader evidence vs attendance ledger.

Import with importlib.import_module("bhandara.worktime.attendance-verification")
to support the stable public directory name.
"""
from .calculation import AttendanceVerificationInputError, verify_attendance

__all__ = ["AttendanceVerificationInputError", "verify_attendance"]
