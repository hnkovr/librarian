"""librarian.cli — click entry points. Run from the HOST repo root.

Pipeline: inventory → plan → apply (dry by default) → catalog.
    PYTHONPATH=src python3 -m librarian.cli plan <src-root>...
    PYTHONPATH=src python3 -m librarian.cli apply --execute
"""

from __future__ import annotations

from pathlib import Path

import click

from . import settings
from .catalog import build_catalog
from .docprops import props_for
from .organize import apply_plan, plan_moves
from .scan import scan_roots, to_dicts
from .utils import dump_yaml, load_yaml


@click.group()
def main() -> None:
    """librarian — dedupe, categorize, version and catalog course materials."""


@main.command()
@click.argument("roots", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
def inventory(roots: tuple[Path, ...]) -> None:
    """Scan ROOTS and write the inventory state file."""
    records = scan_roots(list(roots))
    out = Path(settings.get("inventory_file"))
    dump_yaml(to_dicts(records), out)
    click.echo(f"{len(records)} records → {out}")


@main.command()
@click.argument("roots", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
def plan(roots: tuple[Path, ...]) -> None:
    """Scan ROOTS + existing data/, write the move plan (no changes)."""
    incoming = scan_roots(list(roots))
    data_root = Path(settings.get("data_root"))
    existing = scan_roots([data_root]) if data_root.exists() else []
    actions = plan_moves(incoming, existing, data_root)
    out = Path(settings.get("plan_file"))
    dump_yaml(actions, out)
    moves = sum(1 for a in actions if a["action"] in ("move", "demote"))
    dupes = sum(1 for a in actions if a["action"] == "skip-duplicate")
    click.echo(f"{len(actions)} actions ({moves} moves/demotes, {dupes} duplicates) → {out}")


@main.command()
@click.option("--execute", is_flag=True, help="actually move files (default: dry-run)")
def apply(execute: bool) -> None:
    """Apply the previously written plan file."""
    plan_file = Path(settings.get("plan_file"))
    if not plan_file.is_file():
        raise click.ClickException(f"plan file missing — run `plan` first: {plan_file}")
    actions = load_yaml(plan_file)
    apply_plan(actions, dry=not execute)
    click.echo(("applied" if execute else "dry-run over") + f" {len(actions)} actions")


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
def docprops(paths: tuple[Path, ...]) -> None:
    """Print deterministic document properties for PATHS (YAML)."""
    import yaml

    click.echo(yaml.safe_dump([props_for(p) for p in paths], allow_unicode=True, sort_keys=False))


@main.command()
def catalog() -> None:
    """Regenerate data/CATALOG.md from current files + data/reviews.yml."""
    build_catalog(Path.cwd())


if __name__ == "__main__":
    main()
