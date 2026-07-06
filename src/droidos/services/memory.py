"""``droid-memory`` (spec §12.13).

Stores permitted long-term information: names, places, preferences, repeated
tasks, defined room names, known objects, maintenance events and conversation
summaries.

Safety rules and hardware limits must NEVER be stored as editable conversational
memory (spec §12.13). :meth:`remember` refuses categories that would let the LLM
or a user rewrite safety behaviour.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from ..core.errors import DroidError
from ..core.models import DiagnosticLevel, DiagnosticStatus
from .lifecycle import ManagedService

if TYPE_CHECKING:
    from ..system import Runtime

ALLOWED_CATEGORIES = {"fact", "place", "preference", "person", "task", "maintenance", "summary"}
FORBIDDEN_CATEGORIES = {"safety", "limit", "authorization", "capability"}


class Memory(ManagedService):
    def __init__(self, rt: "Runtime") -> None:
        super().__init__("memory", rt)
        self.entries: list[dict[str, Any]] = []

    def _on_configure(self) -> bool:
        self._load()
        return True

    # api ------------------------------------------------------------------ #
    def remember(self, text: str, category: str = "fact", meta: dict[str, Any] | None = None) -> dict[str, Any]:
        category = category.lower()
        if category in FORBIDDEN_CATEGORIES:
            raise DroidError(
                f"refusing to store {category!r} in conversational memory; "
                "safety rules and hardware limits are not editable memory"
            )
        if category not in ALLOWED_CATEGORIES:
            category = "fact"
        entry = {
            "text": text.strip(),
            "category": category,
            "meta": meta or {},
            "stamp": time.time(),
        }
        self.entries.append(entry)
        self._save()
        return entry

    def recall(self, query: str = "", limit: int = 20) -> list[dict[str, Any]]:
        q = query.strip().lower()
        items = self.entries if not q else [e for e in self.entries if q in e["text"].lower()]
        return items[-limit:]

    def forget(self, query: str) -> int:
        q = query.strip().lower()
        before = len(self.entries)
        self.entries = [e for e in self.entries if q not in e["text"].lower()]
        removed = before - len(self.entries)
        if removed:
            self._save()
        return removed

    def count(self) -> int:
        return len(self.entries)

    # diagnostics ---------------------------------------------------------- #
    def diagnostics(self) -> list[DiagnosticStatus]:
        return [
            DiagnosticStatus(
                name="memory/store",
                level=DiagnosticLevel.OK,
                message=f"{len(self.entries)} remembered items",
                values={"count": len(self.entries)},
            )
        ]

    # persistence ---------------------------------------------------------- #
    def _load(self) -> None:
        path = self.rt.paths.memory_file
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    self.entries = loaded
            except (OSError, json.JSONDecodeError):
                pass

    def _save(self) -> None:
        try:
            self.rt.paths.memory_file.write_text(
                json.dumps(self.entries, indent=2), encoding="utf-8"
            )
        except OSError:
            pass
