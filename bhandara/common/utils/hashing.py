"""Streaming source hashes; does not modify or load source files into memory."""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()
