"""librarian unit tests — parsing, dedupe, planning, docprops, catalog smoke."""

from pathlib import Path

import pytest

from librarian.dedupe import split_duplicates
from librarian.docprops import md_props, props_for
from librarian.organize import plan_moves
from librarian.scan import Record, scan_roots
from librarian.utils import categorize, normalize_name, parse_stack, word_stats


def _rec(**kw) -> Record:
    base = dict(path="/s/a.pptx", root="/s", rel="a.pptx", name="a.pptx", ext="pptx",
                bytes=1, mtime=100, sha256="h1", category="decks", stack="a", version=[], copy=0)
    base.update(kw)
    return Record(**base)


# ── parse_stack ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("stem,base,ver,copy_n", [
    ("MLInside_dbt-HSU-final-v3", "MLInside_dbt-HSU-final", (3,), 0),
    ("MLInside_Введение-в-dbt_v3.10", "MLInside_Введение-в-dbt", (3, 10), 0),
    ("MLInside_Введение-в-dbt_v2 (1)", "MLInside_Введение-в-dbt", (2,), 1),
    ("Просто документ", "Просто документ", (), 0),
    ("deck v1.0", "deck", (1, 0), 0),
])
def test_parse_stack(stem, base, ver, copy_n):
    assert parse_stack(stem) == (base, ver, copy_n)


def test_version_ordering():
    assert (3, 10) > (3, 9) > (3,) > ()


# ── categorize / normalize ────────────────────────────────────────────────────
@pytest.mark.parametrize("name,cat", [
    ("deck.pptx", "decks"), ("doc.pdf", "docs"), ("v.mp4", "media"),
    ("z.zip", "archives"), ("q.sql", "code"), ("weird.xyz", "misc"),
    ("MLinside шаблон презентаций.pptx", "templates"),
    ("MLinside-template.pptx", "templates"),
])
def test_categorize(name, cat):
    assert categorize(Path(name)) == cat


def test_normalize_name():
    assert " " not in normalize_name("a b c.pptx")


# ── dedupe ────────────────────────────────────────────────────────────────────
def test_split_duplicates_prefers_non_copy_shortest():
    a = _rec(path="/s/x (1).pptx", name="x (1).pptx", copy=1)
    b = _rec(path="/s/x.pptx", name="x.pptx")
    keep, dupes = split_duplicates([a, b])
    assert [r.path for r in keep] == ["/s/x.pptx"]
    assert [r.path for r in dupes] == ["/s/x (1).pptx"]


# ── plan_moves ────────────────────────────────────────────────────────────────
def test_plan_version_stack_and_dupes(tmp_path):
    data_root = tmp_path / "data"
    v1 = _rec(path="/s/d-v1.pptx", name="d-v1.pptx", stack="d", version=[1], sha256="h1")
    v2 = _rec(path="/s/d-v2.pptx", name="d-v2.pptx", stack="d", version=[2], sha256="h2")
    dup = _rec(path="/s/copy of d-v2.pptx", name="d-v2 (1).pptx", stack="d", version=[2], sha256="h2", copy=1)
    actions = plan_moves([v1, v2, dup], existing=[], data_root=data_root)
    by = {a["src"]: a for a in actions}
    assert by["/s/copy of d-v2.pptx"]["action"] == "skip-duplicate"
    assert by["/s/d-v1.pptx"]["action"] == "move" and "/.history/" in by["/s/d-v1.pptx"]["dst"]
    assert by["/s/d-v2.pptx"]["dst"].endswith("data/decks/d-v2.pptx")


def test_plan_demotes_existing_current(tmp_path):
    data_root = tmp_path / "data"
    existing = _rec(path=str(data_root / "decks/d-v4.pptx"), name="d-v4.pptx",
                    stack="d", version=[4], sha256="e1")
    incoming = _rec(path="/s/d-v6.pptx", name="d-v6.pptx", stack="d", version=[6], sha256="i1")
    actions = plan_moves([incoming], existing=[existing], data_root=data_root)
    by = {a["src"]: a for a in actions}
    assert by[str(data_root / "decks/d-v4.pptx")]["action"] == "demote"
    assert by["/s/d-v6.pptx"]["reason"] == "current version"


def test_plan_existing_content_wins(tmp_path):
    existing = _rec(path="/data/decks/d.pptx", sha256="same")
    incoming = _rec(path="/s/d.pptx", sha256="same")
    actions = plan_moves([incoming], existing=[existing], data_root=tmp_path / "data")
    assert [a["action"] for a in actions if a["src"] == "/s/d.pptx"] == ["skip-duplicate"]


# ── scan skips junk ───────────────────────────────────────────────────────────
def test_scan_skips_locks_and_ds_store(tmp_path):
    (tmp_path / "ok.md").write_text("hello world")
    (tmp_path / "~$lock.pptx").write_text("x")
    (tmp_path / ".DS_Store").write_text("x")
    records = scan_roots([tmp_path])
    assert [r.name for r in records] == ["ok.md"]


# ── docprops ──────────────────────────────────────────────────────────────────
def test_md_props(tmp_path):
    f = tmp_path / "note.md"
    f.write_text("# Title\n\nsome words here\n\n```sql\nselect 1\n```\n![img](a.png)\n")
    p = md_props(f)
    assert p["code_blocks"] == 1 and p["pictures"] == 1 and p["words"] >= 4


def test_props_for_unknown(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"12")
    assert props_for(f)["format"] == "bin"


def test_word_stats_empty():
    assert word_stats([]) == {"total": 0, "avg": 0, "median": 0}
