"""A minimal behaviour tree (spec §23, §38).

Enough to express the coordinated tasks in the specification (check health →
stand → navigate → locate → orient → observe → analyse → report) with sequences,
selectors (for recovery), conditions and actions. Nodes tick to SUCCESS, FAILURE
or RUNNING; the executive ticks the root until it settles.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable


class Status(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class Node:
    name: str = "node"

    def tick(self) -> Status:  # pragma: no cover - abstract
        raise NotImplementedError


class Action(Node):
    def __init__(self, name: str, fn: Callable[[], Status | bool]) -> None:
        self.name = name
        self._fn = fn

    def tick(self) -> Status:
        result = self._fn()
        if isinstance(result, Status):
            return result
        return Status.SUCCESS if result else Status.FAILURE


class Condition(Action):
    """An action whose truthiness gates a sequence."""


class Sequence(Node):
    """Succeeds only if all children succeed, in order (fails fast)."""

    def __init__(self, name: str, children: list[Node]) -> None:
        self.name = name
        self.children = children
        self.last_failed: str = ""

    def tick(self) -> Status:
        for child in self.children:
            status = child.tick()
            if status == Status.RUNNING:
                return Status.RUNNING
            if status == Status.FAILURE:
                self.last_failed = child.name
                return Status.FAILURE
        return Status.SUCCESS


class Selector(Node):
    """Succeeds if any child succeeds; used for recovery fallbacks (spec §12.10)."""

    def __init__(self, name: str, children: list[Node]) -> None:
        self.name = name
        self.children = children

    def tick(self) -> Status:
        for child in self.children:
            status = child.tick()
            if status in (Status.SUCCESS, Status.RUNNING):
                return status
        return Status.FAILURE


def run(root: Node, max_ticks: int = 10000) -> Status:
    """Tick a tree until it settles or the tick budget is exhausted."""
    for _ in range(max_ticks):
        status = root.tick()
        if status != Status.RUNNING:
            return status
    return Status.FAILURE
