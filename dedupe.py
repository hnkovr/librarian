"""librarian.dedupe — exact-content duplicate detection over inventory records.

Canonical pick per sha256 group: shortest name without a copy marker, then the
newest mtime — deterministic for identical inputs.
"""

from __future__ import annotations

from collections import defaultdict

from .scan import Record


def group_by_hash(records: list[Record]) -> dict[str, list[Record]]:
    groups: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        groups[r.sha256].append(r)
    return dict(groups)


def pick_canonical(group: list[Record]) -> Record:
    return sorted(group, key=lambda r: (r.copy, len(r.name), -r.mtime, r.path))[0]


def split_duplicates(records: list[Record]) -> tuple[list[Record], list[Record]]:
    """Return (keep, duplicates): one canonical record per distinct content hash."""
    keep: list[Record] = []
    dupes: list[Record] = []
    for group in group_by_hash(records).values():
        canonical = pick_canonical(group)
        keep.append(canonical)
        dupes += [r for r in group if r is not canonical]
    return keep, dupes
