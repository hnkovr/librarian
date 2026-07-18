"""librarian.organize — turn an inventory into a move plan, then apply it.

Rules (in order):
  1. exact-content dedupe — an incoming file whose sha256 already exists (in data/
     or earlier in the batch) is skipped, not moved (``skip-duplicate``);
  2. category routing — data/<category>/<normalized name>;
  3. version stacks — per (category, stack-base) the highest version (then newest
     mtime) is the *current* file at the category root; every other member goes to
     ``<category>/.history/``; an existing current beaten by an incoming higher
     version is demoted into ``.history`` (``demote``).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from loguru import logger as log

from . import settings
from .dedupe import pick_canonical
from .scan import Record
from .utils import move_file, normalize_name


def _rank(r: Record) -> tuple:
    return (tuple(r.version), r.mtime, -r.copy)


def _dst(data_root: Path, r: Record, history: bool) -> Path:
    hist = settings.get("history_dirname")
    base = data_root / r.category
    return (base / hist / normalize_name(r.name)) if history else (base / normalize_name(r.name))


def plan_moves(incoming: list[Record], existing: list[Record], data_root: Path) -> list[dict]:
    """Compute the ordered action list; pure — no filesystem writes."""
    # 1. dedupe: existing content always wins; within incoming, canonical pick wins.
    seen: dict[str, Record] = {r.sha256: r for r in existing}
    kept: list[Record] = []
    actions: list[dict] = []
    by_hash: dict[str, list[Record]] = defaultdict(list)
    for r in incoming:
        by_hash[r.sha256].append(r)
    for sha, group in by_hash.items():
        canonical = pick_canonical(group)
        losers = [r for r in group if r is not canonical]
        if sha in seen:
            losers.append(canonical)
        else:
            kept.append(canonical)
        for r in losers:
            actions.append(
                {"action": "skip-duplicate", "src": r.path, "dst": None,
                 "category": r.category, "stack": r.stack,
                 "reason": f"content already kept as sha256={sha[:10]}…"}
            )

    # 2+3. stacks over kept incoming + existing (existing participate in ranking).
    stacks: dict[tuple[str, str], list[tuple[str, Record]]] = defaultdict(list)
    for r in kept:
        stacks[(r.category, normalize_name(r.stack).casefold())].append(("in", r))
    for r in existing:
        stacks[(r.category, normalize_name(r.stack).casefold())].append(("ex", r))

    for (_cat, _key), members in sorted(stacks.items()):
        members.sort(key=lambda t: _rank(t[1]))
        current_kind, current = members[-1]
        for kind, r in members[:-1]:
            if kind == "in":
                actions.append(
                    {"action": "move", "src": r.path, "dst": str(_dst(data_root, r, history=True)),
                     "category": r.category, "stack": r.stack, "reason": "older version → .history"}
                )
            elif len(members) > 1 and current_kind == "in":
                actions.append(
                    {"action": "demote", "src": r.path, "dst": str(_dst(data_root, r, history=True)),
                     "category": r.category, "stack": r.stack,
                     "reason": f"superseded by incoming {Path(current.path).name}"}
                )
        if current_kind == "in":
            actions.append(
                {"action": "move", "src": current.path, "dst": str(_dst(data_root, current, history=False)),
                 "category": current.category, "stack": current.stack, "reason": "current version"}
            )

    # collision guard: two different-content files may normalize to one dst
    taken: dict[str, str] = {}
    for a in actions:
        if not a["dst"]:
            continue
        if a["dst"] in taken:
            p = Path(a["dst"])
            a["dst"] = str(p.with_name(f"{p.stem}-2{p.suffix}"))
        taken[a["dst"]] = a["src"]
    log.info("planned {} actions ({} moves)", len(actions),
             sum(1 for a in actions if a["action"] in ("move", "demote")))
    return actions


def apply_plan(actions: list[dict], dry: bool) -> None:
    for a in actions:
        if a["action"] in ("move", "demote"):
            src, dst = Path(a["src"]), Path(a["dst"])
            if not src.exists():
                raise FileNotFoundError(f"planned source vanished: {src}")
            move_file(src, dst, dry=dry)
        else:
            log.debug("skip-duplicate: {} ({})", a["src"], a["reason"])
