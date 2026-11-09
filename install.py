#!/usr/bin/env python3
"""Non-destructive Phase 1 bootstrap environment check (not an installer yet)."""
from __future__ import annotations

import argparse
import sys

MIN_PYTHON = (3, 12)


def check_python(version: tuple[int, ...] | None = None) -> tuple[bool, str]:
    """Check a minimum syntax floor without claiming a runtime compatibility test."""
    detected = tuple(sys.version_info[:3] if version is None else version)
    supported = detected >= MIN_PYTHON
    details = ".".join(map(str, detected))
    return supported, details


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check Bhandara bootstrap prerequisites (no changes made)."
    )
    parser.add_argument(
        "--check", action="store_true", help="Check prerequisites without installing anything"
    )
    parser.parse_args(argv)

    supported, detected = check_python()
    if not supported:
        print(f"INCOMPATIBLE: Python {detected}; bootstrap requires Python 3.12+", file=sys.stderr)
        return 2
    print(f"BOOTSTRAP_CHECK_OK: Python {detected}")
    print("Phase 1 bootstrap has no external package dependencies.")
    print("No packages were installed or changed. Calculator modules are not yet released.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
