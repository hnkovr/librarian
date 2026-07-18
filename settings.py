"""librarian.settings — fail-loud loader for settings.yml (the package SSoT).

Every scalar the tool uses lives in settings.yml next to this module; a missing
key raises KeyError naming the key and file instead of guessing a default.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_SETTINGS_FILE = Path(__file__).resolve().parent / "settings.yml"


@lru_cache(maxsize=1)
def _root() -> dict[str, Any]:
    if not _SETTINGS_FILE.is_file():
        raise FileNotFoundError(f"librarian settings file missing: {_SETTINGS_FILE}")
    data = yaml.safe_load(_SETTINGS_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "librarian" not in data:
        raise KeyError(f"top-level key 'librarian' missing in {_SETTINGS_FILE}")
    return data["librarian"]


def get(*keys: str) -> Any:
    """Fetch a (possibly nested) setting; KeyError names the missing path + file."""
    node: Any = _root()
    for i, key in enumerate(keys):
        if not isinstance(node, dict) or key not in node:
            dotted = ".".join(keys[: i + 1])
            raise KeyError(f"setting 'librarian.{dotted}' missing in {_SETTINGS_FILE}")
        node = node[key]
    return node
