"""One-run coordinated filenames with exclusive reservations and atomic file writes.

Each file is published by os.replace; a multi-file batch is NOT an atomic
filesystem transaction. Rollback removes files owned by this batch on failure.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from bhandara.common.utils.hashing import sha256_file


class ArtifactError(ValueError):
    """Invalid output plan or incomplete/unsafe artifact batch."""


def _validate_name(name: str) -> None:
    if (not isinstance(name, str) or not name or name in (".", "..")
            or name.startswith(".") or name.strip() != name
            or "/" in name or "\\" in name or "\x00" in name):
        raise ArtifactError("artifact names must be plain, non-hidden filenames")


def _versioned(name: str, number: int) -> str:
    if number == 0:
        return name
    path = Path(name)
    return f"{path.stem}({number}){path.suffix}"


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("non-finite decimal in artifact")
        return format(value, "f")
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"unsupported JSON type: {type(value).__name__}")


class ArtifactBatch:
    """Reserve a single common suffix across ALL requested output filenames.

    Placeholders are created with O_EXCL so concurrent writers never share a
    filename. File contents are fully staged before publishing. No existing
    output is overwritten. Use as a context manager to clean up on failure.
    """

    def __init__(self, directory: str | Path, names: Iterable[str]) -> None:
        self.directory = Path(directory)
        self.names = tuple(names)
        if not self.names or len(set(self.names)) != len(self.names):
            raise ArtifactError("a nonempty set of unique artifact names is required")
        for name in self.names:
            _validate_name(name)
        self._reserved: dict[str, tuple[Path, int]] = {}
        self._stage: Path | None = None
        self._staged: set[str] = set()
        self._published: set[str] = set()
        self._finished = False
        self.suffix_number: int | None = None

    def __enter__(self) -> ArtifactBatch:
        if self._stage is not None or self._finished:
            raise ArtifactError("artifact batch is single-use")
        if self.directory.is_symlink():
            raise ArtifactError("output directory must not be a symlink")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not self.directory.is_dir():
            raise ArtifactError("output directory is not a directory")
        for number in range(10001):
            allocated = {}
            try:
                for name in self.names:
                    path = self.directory / _versioned(name, number)
                    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    try:
                        inode = os.fstat(descriptor).st_ino
                    finally:
                        os.close(descriptor)
                    allocated[name] = (path, inode)
            except FileExistsError:
                for path, inode in allocated.values():
                    self._remove_if_owned(path, inode)
                continue
            except BaseException:
                for path, inode in allocated.values():
                    self._remove_if_owned(path, inode)
                raise
            self._reserved = allocated
            self.suffix_number = number
            break
        else:
            raise ArtifactError("no free artifact suffix among 0..10000")
        try:
            self._stage = Path(tempfile.mkdtemp(prefix=".bhandara-stage-", dir=self.directory))
            os.chmod(self._stage, 0o700)
        except BaseException:
            self._rollback()
            raise
        return self

    @staticmethod
    def _remove_if_owned(path: Path, inode: int) -> None:
        try:
            if path.lstat().st_ino == inode:
                path.unlink()
        except FileNotFoundError:
            pass

    def _staging_path(self, name: str) -> Path:
        if self._stage is None or self._finished:
            raise ArtifactError("artifact batch is not active")
        if name not in self._reserved:
            raise ArtifactError("artifact name was not reserved")
        if name in self._staged:
            raise ArtifactError("artifact was already staged")
        return self._stage / _versioned(name, self.suffix_number or 0)

    def write_json(self, name: str, payload: Any) -> None:
        target = self._staging_path(name)
        try:
            with target.open("x", encoding="utf-8") as handle:
                os.chmod(target, 0o600)
                json.dump(payload, handle, ensure_ascii=False, indent=2,
                          sort_keys=True, allow_nan=False, default=_json_default)
                handle.write("\n")
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        self._staged.add(name)

    def write_bytes(self, name: str, payload: bytes) -> None:
        if not isinstance(payload, bytes):
            raise TypeError("binary artifact requires bytes")
        target = self._staging_path(name)
        with target.open("xb") as handle:
            os.chmod(target, 0o600)
            handle.write(payload)
        self._staged.add(name)

    def copy_file(self, name: str, source: str | Path) -> None:
        """Copy bytes; never change the caller's input file."""
        target = self._staging_path(name)
        try:
            with Path(source).open("rb") as reader, target.open("xb") as writer:
                os.chmod(target, 0o600)
                shutil.copyfileobj(reader, writer, length=1024 * 1024)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        self._staged.add(name)

    def staged_hashes(self) -> dict[str, str]:
        if self._stage is None or self._finished:
            raise ArtifactError("artifact batch is not active")
        return {
            _versioned(name, self.suffix_number or 0): sha256_file(
                self._stage / _versioned(name, self.suffix_number or 0)
            )
            for name in self.names if name in self._staged
        }

    def commit(self) -> dict[str, Path]:
        if self._stage is None or self._finished:
            raise ArtifactError("artifact batch is not active")
        if self._staged != set(self.names):
            raise ArtifactError("all reserved output files must be staged before commit")
        try:
            for name in self.names:
                path, inode = self._reserved[name]
                if path.is_symlink() or path.lstat().st_ino != inode:
                    raise ArtifactError("reserved output file changed externally")
                os.replace(self._stage / path.name, path)
                self._published.add(name)
            result = {name: path for name, (path, _) in self._reserved.items()}
            self._finished = True
            self._cleanup_stage()
            return result
        except BaseException:
            self._rollback()
            raise

    def _cleanup_stage(self) -> None:
        if self._stage is not None:
            shutil.rmtree(self._stage)
            self._stage = None

    def _rollback(self) -> None:
        for name, (path, inode) in self._reserved.items():
            if name in self._published:
                # File was created by this batch, never a pre-existing file.
                path.unlink(missing_ok=True)
            else:
                self._remove_if_owned(path, inode)
        self._cleanup_stage()
        self._finished = True

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._finished:
            self._rollback()
