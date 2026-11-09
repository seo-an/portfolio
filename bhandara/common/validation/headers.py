"""Exact required-header matching; unrelated Excel columns are ignored."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


class HeaderContractError(ValueError):
    """The entire worksheet cannot be mapped unambiguously."""


@dataclass(frozen=True, slots=True)
class HeaderMap:
    required: tuple[str, ...]
    positions: tuple[int, ...]  # zero-based Excel columns

    def project(self, row: Sequence[object]) -> dict[str, object]:
        return {
            name: row[position] if position < len(row) else None
            for name, position in zip(self.required, self.positions)
        }


def parse_headers(header: Sequence[object], required: Sequence[str]) -> HeaderMap:
    """Allow blank/duplicate *extra* headers, but never duplicate required headers."""
    if not required or any(not isinstance(x, str) or not x.strip() for x in required):
        raise HeaderContractError("required headers must be nonempty strings")
    names = tuple(x.strip() for x in required)
    if len(set(names)) != len(names):
        raise HeaderContractError("required contract declares duplicate headers")
    cells = [cell.strip() if isinstance(cell, str) else None for cell in header]
    positions: list[int] = []
    for name in names:
        found = [index for index, cell in enumerate(cells) if cell == name]
        if not found:
            raise HeaderContractError(f"missing required header: {name}")
        if len(found) != 1:
            raise HeaderContractError(f"ambiguous duplicate required header: {name}")
        positions.append(found[0])
    return HeaderMap(required=names, positions=tuple(positions))


def is_blank(value: object) -> bool:
    """Zero and False are valid facts, not blank cells."""
    return value is None or (isinstance(value, str) and not value.strip())
