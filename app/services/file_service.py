from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol


class GeneratedFileLike(Protocol):
    file_path: str
    content_hash: str | None


class FileIntegrityError(RuntimeError):
    pass


def resolve_verified_file(record: GeneratedFileLike, allowed_root: Path) -> Path | None:
    root = allowed_root.resolve()
    path = Path(record.file_path).resolve()
    if path.parent != root or not path.is_file():
        return None
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if not record.content_hash or actual_hash != record.content_hash:
        raise FileIntegrityError(path.name)
    return path

