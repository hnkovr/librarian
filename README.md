# librarian

Course-material librarian: **dedupe → categorize → version-stack → catalog**.
Designed to run as a git submodule at `src/librarian` of a host repo (same pattern
as [hnkovr/preza_gen](https://github.com/hnkovr/preza_gen)).

## What it does

1. **inventory** — walks source roots into records (sha256, category, version-stack key).
2. **plan** — computes a move plan against the host `data/`:
   - exact-content duplicates are skipped (`skip-duplicate`);
   - files route to `data/<category>/` (decks / docs / media / archives / code / templates / misc);
   - per version stack the latest version stays current, the rest goes to `<category>/.history/`;
     an existing current beaten by an incoming version is demoted.
3. **apply** — executes the plan (`--execute`; dry-run by default).
4. **docprops** — deterministic per-document properties: slides/pages/paragraphs,
   pictures, code blocks, word totals + avg/median per slide, speaker-notes stats, core metadata.
5. **catalog** — renders `data/CATALOG.md` (tables per category + curated reviews
   merged from `data/reviews.yml`).

## Usage (from the host repo root)

```bash
PYTHONPATH=src python3 -m librarian.cli inventory "<source-root>"
PYTHONPATH=src python3 -m librarian.cli plan "<source-root>" [...]
PYTHONPATH=src python3 -m librarian.cli apply            # dry-run
PYTHONPATH=src python3 -m librarian.cli apply --execute  # move files
PYTHONPATH=src python3 -m librarian.cli catalog
```

All scalars (categories, patterns, paths, LFS globs) live in `settings.yml` —
scripts fail loudly on missing keys, никаких inline-defaults.

## State files (host repo)

| file | purpose |
|---|---|
| `data/.state/librarian-inventory.yml` | last scan records |
| `data/.state/librarian-plan.yml` | reviewed move plan |
| `data/.state/librarian-docprops.yml` | docprops cache behind CATALOG.md |
| `data/reviews.yml` | curated per-file reviews (summary/SWOT/recommendations) |
| `data/CATALOG.md` | generated catalog |
