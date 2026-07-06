"""Shared value types used across services (the runtime side of ``interfaces/``).

These mirror the ROS-style messages defined under ``interfaces/droid_interfaces``
(spec §37) but as plain dataclasses so the reference brain needs no ROS install.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class DiagnosticLevel(IntEnum):
    """Matches ``diagnostic_msgs/DiagnosticStatus`` severity ordering (spec §28)."""

    OK = 0
    WARN = 1
    ERROR = 2
    STALE = 3

    @property
    def label(self) -> str:
        return self.name


@dataclass
class DiagnosticStatus:
    name: str
    level: DiagnosticLevel
    message: str
    hardware_id: str = ""
    values: dict[str, Any] = field(default_factory=dict)
    stamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "level": self.level.label,
            "message": self.message,
            "hardware_id": self.hardware_id,
            "values": self.values,
        }


@dataclass
class BodyVelocity:
    """A body-level velocity command (spec §23). The LLM never produces joint targets."""

    linear_x: float = 0.0  # m/s forward
    linear_y: float = 0.0  # m/s lateral (omni bodies only)
    angular_z: float = 0.0  # rad/s yaw

    def is_zero(self) -> bool:
        return self.linear_x == 0.0 and self.linear_y == 0.0 and self.angular_z == 0.0

    def to_dict(self) -> dict[str, float]:
        return {"linear_x": self.linear_x, "linear_y": self.linear_y, "angular_z": self.angular_z}


@dataclass
class MotionPermission:
    """The movement-permission token issued by the safety gateway (spec §12.2)."""

    granted: bool
    reason: str = ""
    token: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"granted": self.granted, "reason": self.reason, "token": self.token}
