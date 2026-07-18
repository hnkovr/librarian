"""librarian.catalog — render data/CATALOG.md from docprops + curated reviews.

Deterministic layer: file table per category (current versions only — .history is
listed as a count), doc properties. Curated layer: data/reviews.yml entries keyed
by repo-relative path (summary / swot / mistakes / controversial / recommendations)
are merged in verbatim when present.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger as log

from . import settings
from .utils import dump_yaml, is_skipped, load_yaml
from .docprops import props_for


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def collect(data_root: Path) -> dict[str, list[dict]]:
    """Docprops for every *current* file, grouped by category dir; sorted for determinism."""
    hist = settings.get("history_dirname")
    by_cat: dict[str, list[dict]] = {}
    for cat_dir in sorted(p for p in data_root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        rows = []
        for f in sorted(cat_dir.rglob("*")):
            if not f.is_file() or is_skipped(f) or hist in f.parts:
                continue
            row = props_for(f)
            row["rel"] = f.relative_to(data_root.parent).as_posix()
            row["history_versions"] = _history_count(f, hist)
            rows.append(row)
        if rows:
            by_cat[cat_dir.name] = rows
    return by_cat


def _history_count(current: Path, hist: str) -> int:
    hdir = current.parent / hist
    if not hdir.is_dir():
        return 0
    from .utils import parse_stack

    stack, _, _ = parse_stack(current.stem)
    return sum(1 for f in hdir.iterdir()
               if f.is_file() and not is_skipped(f) and parse_stack(f.stem)[0].casefold() == stack.casefold())


def _fmt_stats(s: dict | None) -> str:
    return f"{s['total']} (avg {s['avg']} / med {s['median']})" if s else "—"


def _row_props(r: dict) -> str:
    bits = []
    for key, label in (("slides", "slides"), ("pages", "pages"), ("paragraphs", "paras"),
                       ("pictures", "pics"), ("code_blocks", "code")):
        if r.get(key) is not None:
            bits.append(f"{r[key]} {label}")
    return ", ".join(bits) or "—"


def render(by_cat: dict[str, list[dict]], reviews: dict) -> str:
    out = [settings.get("catalog", "title"), "", settings.get("catalog", "generated_note"), ""]
    total = sum(len(v) for v in by_cat.values())
    out += [f"**{total} current files** across {len(by_cat)} categories "
            f"(older versions live in `.history/` next to each current file).", ""]
    for cat, rows in by_cat.items():
        out += [f"## {cat}/", "",
                "| file | size | props | words | notes words | modified | author | hist |",
                "|---|---|---|---|---|---|---|---|"]
        for r in rows:
            words = r.get("words_per_slide") or r.get("words_per_page") or r.get("words_per_paragraph")
            words_cell = _fmt_stats(words) if words else (str(r.get("words", "—")))
            out.append(
                f"| [{Path(r['rel']).name}]({r['rel'].replace(' ', '%20')}) | {_human(r['bytes'])} "
                f"| {_row_props(r)} | {words_cell} | {_fmt_stats(r.get('notes_words_per_slide'))} "
                f"| {(r.get('modified') or '—')[:10]} | {r.get('author') or '—'} | {r['history_versions']} |"
            )
        out.append("")
        for r in rows:
            rev = reviews.get(r["rel"])
            if not rev:
                continue
            out += [f"### {Path(r['rel']).name}", ""]
            for key, title in (("summary", "Summary"), ("detailing", "Detailing"), ("swot", "SWOT"),
                               ("mistakes", "Mistakes"), ("controversial", "Controversial points"),
                               ("recommendations", "Recommendations")):
                if rev.get(key):
                    out += [f"**{title}:**", str(rev[key]).rstrip(), ""]
    return "\n".join(out) + "\n"


def build_catalog(repo_root: Path) -> Path:
    data_root = repo_root / settings.get("data_root")
    reviews_file = repo_root / settings.get("reviews_file")
    reviews = load_yaml(reviews_file) or {} if reviews_file.is_file() else {}
    by_cat = collect(data_root)
    dump_yaml(by_cat, repo_root / settings.get("docprops_file"))
    catalog = repo_root / settings.get("catalog_file")
    catalog.write_text(render(by_cat, reviews), encoding="utf-8")
    log.info("catalog written: {} ({} categories)", catalog, len(by_cat))
    return catalog
