"""Task and task-result types (spec §12.10, §29)."""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


_counter = itertools.count(1)


@dataclass
class Task:
    intent: str
    user: str
    arguments: dict[str, Any] = field(default_factory=dict)
    task_id: str = ""
    state: TaskState = TaskState.CREATED
    started: float = 0.0
    finished: float = 0.0
    steps: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.task_id:
            self.task_id = f"task-{next(_counter):04d}"

    def start(self) -> None:
        self.state = TaskState.RUNNING
        self.started = time.time()

    def step(self, label: str) -> None:
        self.steps.append(label)

    def finish(self, state: TaskState) -> None:
        self.state = state
        self.finished = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "intent": self.intent,
            "user": self.user,
            "arguments": self.arguments,
            "state": self.state.value,
            "steps": self.steps,
        }


@dataclass
class TaskResult:
    """The structured outcome of a task. The language service renders this into
    English; keeping facts and phrasing separate lets the droid distinguish
    observation from interpretation (spec §38)."""

    ok: bool
    kind: str  # mirrors the intent, used to pick a renderer
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    task_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "kind": self.kind,
            "data": self.data,
            "error": self.error,
            "task_id": self.task_id,
        }
