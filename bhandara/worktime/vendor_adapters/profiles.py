"""Vendor-specific *column meaning*, never vendor-specific output schemas.

Profiles in this file describe only headers observed in the supplied three-sheet
synthetic export, not a comprehensive official ADT/S1/KT vendor specification.
Unrecognized future forms are rejected for explicit profile review.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VendorProfile:
    vendor: str
    employee_number: str
    employee_name: str
    department: str
    device: str
    date_column: str | None = None
    time_column: str | None = None
    timestamp_column: str | None = None
    mode_column: str | None = None
    auth_method_column: str | None = None

    @property
    def required(self) -> tuple[str, ...]:
        return tuple(value for value in (
            self.employee_number, self.employee_name, self.department,
            self.device, self.date_column, self.time_column,
            self.timestamp_column, self.mode_column, self.auth_method_column,
        ) if value)


PROFILES = {
    "CAPS": VendorProfile(
        vendor="CAPS", employee_number="사원번호", employee_name="성명",
        department="부서", device="단말기명", date_column="일자",
        time_column="시간", mode_column="상태",
    ),
    "SECOM": VendorProfile(
        vendor="SECOM", employee_number="사번", employee_name="성명",
        department="부서", device="출입구명", timestamp_column="일시",
        auth_method_column="인증방식",
    ),
    "KT_TELECOP": VendorProfile(
        vendor="KT_TELECOP", employee_number="사번", employee_name="이름",
        department="부서", device="장치명", timestamp_column="일시",
        auth_method_column="인증구분",
    ),
}
