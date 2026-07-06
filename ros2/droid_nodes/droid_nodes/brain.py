"""Shared DroidSystem instance for the ROS 2 bridge nodes.

During M1 the nodes share one booted brain so the interfaces can stabilise before
the full per-process split. Later milestones give each service its own node/process.
"""

from __future__ import annotations

from droidos.system import DroidSystem

_BRAIN = None


def get_brain() -> DroidSystem:
    global _BRAIN
    if _BRAIN is None:
        _BRAIN = DroidSystem.boot()
    return _BRAIN
