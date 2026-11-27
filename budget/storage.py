"""Save the budget to JSON and load it back, without ever crashing."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

from budget.tracker import BudgetTracker


@contextmanager
def atomic_write(path: Path) -> Iterator[TextIO]:
    """Write a file safely: write to a temp file, then swap it in.

    If anything fails half way, the old file is left untouched, so a crash
    or a full disk can never leave you with a half-written budget.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as file:
            yield file
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


class JsonStorage:
    """Reads and writes a BudgetTracker as a JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.warning: str | None = None

    def load(self) -> BudgetTracker:
        """Load the tracker. A missing or broken file gives an empty tracker.

        A broken file is kept as ``<name>.broken`` so no data is thrown away,
        and ``self.warning`` says what happened.
        """
        self.warning = None
        if not self.path.exists():
            return BudgetTracker()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return BudgetTracker.from_dict(data)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            backup = self.path.with_name(self.path.name + ".broken")
            try:
                self.path.replace(backup)
                where = f" It was moved to {backup.name}."
            except OSError:
                where = ""
            self.warning = f"Couldn't read {self.path.name} ({error}).{where}"
            return BudgetTracker()

    def save(self, tracker: BudgetTracker) -> None:
        """Save the tracker as pretty JSON. Raises OSError if the disk fails."""
        with atomic_write(self.path) as file:
            json.dump(tracker.to_dict(), file, indent=2, ensure_ascii=False)
            file.write("\n")
