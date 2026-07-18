"""librarian.utils — cross-cutting helpers (hashing, yaml I/O, path rules, moves)."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

import yaml
from loguru import logger as log

from . import settings


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def plain(data: Any) -> Any:
    """Coerce str/int/float subclasses (pypdf TextStringObject etc.) to yaml-safe builtins."""
    if isinstance(data, dict):
        return {plain(k): plain(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [plain(v) for v in data]
    for t in (bool, int, float, str):
        if isinstance(data, t):
            return t(data)
    return data if data is None else str(data)


def dump_yaml(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(plain(data), allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )


def is_skipped(path: Path) -> bool:
    """True when a file must never be inventoried/moved (locks, junk, excluded trees)."""
    if path.name in settings.get("skip_names"):
        return True
    if any(path.name.startswith(p) for p in settings.get("skip_prefixes")):
        return True
    parts = set(path.parts)
    if parts & set(settings.get("skip_dir_names")):
        return True
    posix = path.as_posix()
    return any(frag in posix for frag in settings.get("exclude_dir_fragments"))


def categorize(path: Path) -> str:
    """Category for a file: name_rules first, then extension map, then default."""
    lowered = path.name.casefold()
    for rule in settings.get("name_rules"):
        if any(s.casefold() in lowered for s in rule["contains"]):
            return rule["category"]
    ext = path.suffix.lower().lstrip(".")
    for category, exts in settings.get("categories").items():
        if ext in exts:
            return category
    return settings.get("category_default")


def parse_stack(stem: str) -> tuple[str, tuple[int, ...], int]:
    """Split a filename stem into (stack base, version tuple, copy number).

    'Deck-v3.10' → ('Deck', (3, 10), 0); 'Deck_v2 (1)' → ('Deck', (2,), 1);
    unversioned stems return version () — they rank below any explicit version.
    """
    copy_n = 0
    m = re.match(settings.get("copy_pattern"), stem)
    if m:
        stem, copy_n = m.group("base"), int(m.group("n"))
    m = re.match(settings.get("version_pattern"), stem)
    if not m:
        return stem, (), copy_n
    version = tuple(int(x) for x in m.group("ver").split("."))
    return m.group("base"), version, copy_n


def normalize_name(name: str) -> str:
    return name.replace(" ", settings.get("normalize_space_to"))


def move_file(src: Path, dst: Path, dry: bool) -> None:
    """Move src → dst creating parents; cross-device safe (shutil.move)."""
    log.info("{} {} → {}", "DRY" if dry else "MOVE", src, dst)
    if dry:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise FileExistsError(f"refusing to overwrite existing destination: {dst}")
    shutil.move(str(src), str(dst))


def word_stats(counts: Iterable[int]) -> dict[str, float | int]:
    seq = list(counts)
    if not seq:
        return {"total": 0, "avg": 0, "median": 0}
    return {
        "total": sum(seq),
        "avg": round(mean(seq), 1),
        "median": round(median(seq), 1),
    }
