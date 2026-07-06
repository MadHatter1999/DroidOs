"""A minimal in-process event bus.

The reference brain runs in a single process rather than as separate ROS 2
nodes, but services still communicate through published events instead of direct
calls where practical. This mirrors the ROS 2 topic model (spec §10) closely
enough for the reference implementation and keeps services decoupled.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Event:
    topic: str
    payload: Any
    stamp: float = field(default_factory=time.time)
    source: str = ""


Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Subscriber]] = {}
        self._log: list[Event] = []
        self._log_limit = 2000

    def subscribe(self, topic: str, callback: Subscriber) -> None:
        self._subs.setdefault(topic, []).append(callback)

    def publish(self, topic: str, payload: Any, source: str = "") -> Event:
        event = Event(topic=topic, payload=payload, source=source)
        self._log.append(event)
        if len(self._log) > self._log_limit:
            self._log = self._log[-self._log_limit :]
        for cb in self._subs.get(topic, []):
            cb(event)
        # wildcard subscribers
        for cb in self._subs.get("*", []):
            cb(event)
        return event

    def recent(self, topic: str | None = None, limit: int = 50) -> list[Event]:
        items = self._log if topic is None else [e for e in self._log if e.topic == topic]
        return items[-limit:]
