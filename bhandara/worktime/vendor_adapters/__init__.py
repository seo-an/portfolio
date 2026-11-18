"""Vendor-specific raw security Excel adapters with one canonical output contract."""
from .normalizer import (
    VendorSourceError,
    normalize_vendor_excel,
    normalize_vendor_rows,
)
from .profiles import PROFILES, VendorProfile

__all__ = [
    "PROFILES", "VendorProfile", "VendorSourceError",
    "normalize_vendor_rows", "normalize_vendor_excel",
]
