"""Structured logging and the tamper-evident audit record (spec §29).

Two facilities:

* :class:`Logger`, lightweight leveled logging to stderr and a log file.
* :class:`AuditLog`, append-only JSON-lines record of every command, tool call,
  approval decision, safety event and physical action. This is the auditable
  history required by the specification. Private LLM reasoning is deliberately
  *not* recorded; the structured request, decision and external action are.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}


class Logger:
    def __init__(self, name: str, log_file: Path | None = None, level: str = "info") -> None:
        self.name = name
        self.level = LEVELS.get(level, 20)
        self.log_file = log_file
        self._quiet = False

    def set_quiet(self, quiet: bool) -> None:
        self._quiet = quiet

    def _emit(self, level: str, msg: str) -> None:
        if LEVELS[level] < self.level:
            return
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        line = f"{stamp} [{level.upper():5}] {self.name}: {msg}"
        if not self._quiet:
            print(line, file=sys.stderr)
        if self.log_file is not None:
            try:
                with open(self.log_file, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass

    def debug(self, msg: str) -> None:
        self._emit("debug", msg)

    def info(self, msg: str) -> None:
        self._emit("info", msg)

    def warn(self, msg: str) -> None:
        self._emit("warn", msg)

    def error(self, msg: str) -> None:
        self._emit("error", msg)


@dataclass
class AuditRecord:
    """One auditable event (spec §29). Not every field applies to every event."""

    kind: str  # command | tool_call | approval | safety | task | update | auth
    stamp: float = field(default_factory=time.time)
    user: str | None = None
    request_text: str | None = None  # original natural-language request
    intent: str | None = None  # parsed structured intent name
    arguments: dict[str, Any] | None = None
    approval: str | None = None  # approved | rejected | confirmation_required
    reason: str | None = None
    task_id: str | None = None
    outcome: str | None = None  # started | completed | failed | cancelled
    safety_state: str | None = None
    detail: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class AuditLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.records: list[AuditRecord] = []

    def record(self, rec: AuditRecord) -> AuditRecord:
        self.records.append(rec)
        if self.path is not None:
            try:
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec.to_dict()) + "\n")
            except OSError:
                pass
        return rec

    def emit(self, kind: str, **fields: Any) -> AuditRecord:
        return self.record(AuditRecord(kind=kind, **fields))

    def recent(self, limit: int = 50, kind: str | None = None) -> list[AuditRecord]:
        items = [r for r in self.records if kind is None or r.kind == kind]
        return items[-limit:]

    def load_history(self, limit: int = 500) -> list[dict[str, Any]]:
        """Read persisted audit history (spec: fault/command history is stored)."""
        if self.path is None or not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        out.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            return out
        return out[-limit:]
