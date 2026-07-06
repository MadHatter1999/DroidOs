"""The DroidOS system state machine (spec §9).

A single authoritative state machine governs the whole droid. Movement is only
permitted from :data:`DroidState.READY` / :data:`DroidState.ACTIVE`, and only
after every startup check has passed (spec §8, §40).
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable


class DroidState(str, Enum):
    POWERED_OFF = "POWERED_OFF"
    BOOTING = "BOOTING"
    HARDWARE_CHECK = "HARDWARE_CHECK"
    SAFE_IDLE = "SAFE_IDLE"
    READY = "READY"
    ACTIVE = "ACTIVE"
    # Fault / transitional states
    DEGRADED = "DEGRADED"
    MOTION_INHIBITED = "MOTION_INHIBITED"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"
    RECOVERY = "RECOVERY"
    SHUTTING_DOWN = "SHUTTING_DOWN"


# States in which the droid conducts conversation and diagnostics.
CONVERSATIONAL = {
    DroidState.SAFE_IDLE,
    DroidState.READY,
    DroidState.ACTIVE,
    DroidState.DEGRADED,
    DroidState.MOTION_INHIBITED,
}

# States from which a *new* physical motion may begin.
MOTION_ALLOWED_FROM = {DroidState.READY, DroidState.DEGRADED, DroidState.ACTIVE}

# States where motion is explicitly forbidden regardless of anything else.
MOTION_FORBIDDEN = {
    DroidState.POWERED_OFF,
    DroidState.BOOTING,
    DroidState.HARDWARE_CHECK,
    DroidState.SAFE_IDLE,
    DroidState.MOTION_INHIBITED,
    DroidState.EMERGENCY_STOPPED,
    DroidState.RECOVERY,
    DroidState.SHUTTING_DOWN,
}

# Allowed transitions. The value is the set of states reachable from the key.
_TRANSITIONS: dict[DroidState, set[DroidState]] = {
    DroidState.POWERED_OFF: {DroidState.BOOTING},
    DroidState.BOOTING: {DroidState.HARDWARE_CHECK, DroidState.RECOVERY, DroidState.SHUTTING_DOWN},
    DroidState.HARDWARE_CHECK: {
        DroidState.SAFE_IDLE,
        DroidState.MOTION_INHIBITED,
        DroidState.EMERGENCY_STOPPED,
        DroidState.RECOVERY,
    },
    DroidState.SAFE_IDLE: {
        DroidState.READY,
        DroidState.MOTION_INHIBITED,
        DroidState.EMERGENCY_STOPPED,
        DroidState.SHUTTING_DOWN,
        DroidState.DEGRADED,
    },
    DroidState.READY: {
        DroidState.ACTIVE,
        DroidState.SAFE_IDLE,
        DroidState.DEGRADED,
        DroidState.MOTION_INHIBITED,
        DroidState.EMERGENCY_STOPPED,
        DroidState.SHUTTING_DOWN,
    },
    DroidState.ACTIVE: {
        DroidState.READY,
        DroidState.DEGRADED,
        DroidState.MOTION_INHIBITED,
        DroidState.EMERGENCY_STOPPED,
        DroidState.SHUTTING_DOWN,
    },
    DroidState.DEGRADED: {
        DroidState.READY,
        DroidState.ACTIVE,
        DroidState.SAFE_IDLE,
        DroidState.MOTION_INHIBITED,
        DroidState.EMERGENCY_STOPPED,
        DroidState.SHUTTING_DOWN,
    },
    DroidState.MOTION_INHIBITED: {
        DroidState.SAFE_IDLE,
        DroidState.READY,
        DroidState.EMERGENCY_STOPPED,
        DroidState.SHUTTING_DOWN,
    },
    DroidState.EMERGENCY_STOPPED: {DroidState.RECOVERY, DroidState.SHUTTING_DOWN},
    DroidState.RECOVERY: {DroidState.SAFE_IDLE, DroidState.SHUTTING_DOWN, DroidState.POWERED_OFF},
    DroidState.SHUTTING_DOWN: {DroidState.POWERED_OFF},
}


class InvalidTransition(RuntimeError):
    def __init__(self, src: DroidState, dst: DroidState) -> None:
        super().__init__(f"illegal state transition {src.value} -> {dst.value}")
        self.src = src
        self.dst = dst


class StateMachine:
    """Enforces the legal transition graph and records history."""

    def __init__(self, initial: DroidState = DroidState.POWERED_OFF) -> None:
        self._state = initial
        self.history: list[tuple[DroidState, DroidState, str]] = []

    @property
    def state(self) -> DroidState:
        return self._state

    def can_transition(self, dst: DroidState) -> bool:
        return dst in _TRANSITIONS.get(self._state, set())

    def transition(self, dst: DroidState, reason: str = "") -> DroidState:
        if dst == self._state:
            return self._state
        if not self.can_transition(dst):
            raise InvalidTransition(self._state, dst)
        self.history.append((self._state, dst, reason))
        self._state = dst
        return self._state

    def force(self, dst: DroidState, reason: str) -> DroidState:
        """Unconditional transition, used only for emergency-stop paths (spec §18)."""
        self.history.append((self._state, dst, f"FORCED: {reason}"))
        self._state = dst
        return self._state

    def motion_permitted(self) -> bool:
        return self._state in MOTION_ALLOWED_FROM

    def is_conversational(self) -> bool:
        return self._state in CONVERSATIONAL


def reachable(src: DroidState) -> Iterable[DroidState]:
    return _TRANSITIONS.get(src, set())
