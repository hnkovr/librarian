"""librarian.scan — walk source roots into an inventory of file records.

A record carries everything downstream stages need: identity (sha256), category,
version-stack key, and provenance (source root + relative path).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from loguru import logger as log

from .utils import categorize, is_skipped, parse_stack, sha256_of


@dataclass
class Record:
    path: str          # absolute source path
    root: str          # source root it was found under
    rel: str           # path relative to root
    name: str
    ext: str
    bytes: int
    mtime: int
    sha256: str
    category: str
    stack: str         # version-stack base (stem without version/copy suffix)
    version: list[int]
    copy: int


def scan_roots(roots: list[Path]) -> list[Record]:
    records: list[Record] = []
    for root in roots:
        root = root.expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"source root does not exist: {root}")
        files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for p in files:
            if is_skipped(p):
                continue
            stack, version, copy_n = parse_stack(p.stem)
            st = p.stat()
            records.append(
                Record(
                    path=str(p),
                    root=str(root),
                    rel=str(p.relative_to(root if root.is_dir() else root.parent)),
                    name=p.name,
                    ext=p.suffix.lower().lstrip("."),
                    bytes=st.st_size,
                    mtime=int(st.st_mtime),
                    sha256=sha256_of(p),
                    category=categorize(p),
                    stack=stack,
                    version=list(version),
                    copy=copy_n,
                )
            )
    log.info("scanned {} files across {} roots", len(records), len(roots))
    return records


def to_dicts(records: list[Record]) -> list[dict]:
    return [asdict(r) for r in records]
