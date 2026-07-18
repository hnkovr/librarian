"""Make the repo importable as the ``librarian`` package when tests run standalone."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
