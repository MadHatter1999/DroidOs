"""The tool / intent registry (spec §17).

The LLM can only request *registered* tools; it never receives a general shell and
cannot execute arbitrary commands. Administrative actions are specific, validated
tools (e.g. ``system.request_reboot``), never "run this string".

Every registered intent carries the metadata the command broker needs: its risk
class, whether it requires motion, any required body capability, its confirmation
rule (spec §18) and the minimum authenticated role (spec §32).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Risk(str, Enum):
    NONE = "none"
    MOTION = "motion"
    DATA_WRITE = "data_write"
    ADMINISTRATIVE = "administrative"


class Confirm(str, Enum):
    NONE = "none"
    CONDITIONAL = "conditional"
    REQUIRED = "required"


@dataclass
class ToolSpec:
    name: str
    risk: Risk = Risk.NONE
    requires_motion: bool = False
    required_capability: str | None = None  # e.g. "locomotion", "front_camera"
    confirmation: Confirm = Confirm.NONE
    min_role_rank: int = 0  # 0 guest, 1 operator, 2 technician, 3 owner
    always_available: bool = False  # works even without LLM / in any state (spec §16)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "risk": self.risk.value,
            "requires_motion": self.requires_motion,
            "required_capability": self.required_capability,
            "confirmation": self.confirmation.value,
            "min_role_rank": self.min_role_rank,
            "always_available": self.always_available,
        }


# Role ranks (kept here so tools.py has no import cycle with auth.py).
RANK_GUEST = 0
RANK_OPERATOR = 1
RANK_TECHNICIAN = 2
RANK_OWNER = 3


def _default_tools() -> list[ToolSpec]:
    return [
        # --- information / conversation (no confirmation, work for everyone) --- #
        ToolSpec("robot.get_status", Risk.NONE, description="report overall status"),
        ToolSpec("robot.get_battery", Risk.NONE, description="report battery level"),
        ToolSpec("robot.get_temperature", Risk.NONE, description="report motor temperatures"),
        ToolSpec("diagnostics.summary", Risk.NONE, description="summarise health / what is wrong"),
        ToolSpec("robot.explain", Risk.NONE, description="explain last task or why motion is disabled"),
        ToolSpec("perception.describe_scene", Risk.NONE, required_capability="front_camera",
                 description="describe what the camera sees"),
        ToolSpec("navigation.list_places", Risk.NONE, description="list known destinations"),
        ToolSpec("help", Risk.NONE, always_available=True, description="list available commands"),

        # --- always-available safety commands (spec §16, §17) ----------------- #
        ToolSpec("motion.stop", Risk.NONE, always_available=True, description="stop immediately"),
        ToolSpec("motion.emergency_stop", Risk.NONE, always_available=True,
                 description="remove motor power immediately"),
        ToolSpec("task.cancel", Risk.NONE, always_available=True, description="cancel the active task"),
        ToolSpec("voice.silence", Risk.NONE, always_available=True, description="stop speaking"),
        ToolSpec("robot.return_safe_idle", Risk.NONE, description="return to safe idle"),

        # --- motion (operator+, needs locomotion capability) ------------------ #
        ToolSpec("navigation.navigate_to", Risk.MOTION, requires_motion=True,
                 required_capability="locomotion", confirmation=Confirm.CONDITIONAL,
                 min_role_rank=RANK_OPERATOR, description="navigate to a named place"),
        ToolSpec("navigation.go_charge", Risk.MOTION, requires_motion=True,
                 required_capability="locomotion", min_role_rank=RANK_OPERATOR,
                 description="return to the charging station"),
        ToolSpec("inspect.named_target", Risk.MOTION, requires_motion=True,
                 required_capability="locomotion", confirmation=Confirm.CONDITIONAL,
                 min_role_rank=RANK_OPERATOR, description="go to a place and inspect a target"),

        # --- data write (operator+, conditional/required confirmation) -------- #
        ToolSpec("memory.remember", Risk.DATA_WRITE, confirmation=Confirm.CONDITIONAL,
                 min_role_rank=RANK_OPERATOR, description="remember a fact"),
        ToolSpec("memory.store_place", Risk.DATA_WRITE, confirmation=Confirm.CONDITIONAL,
                 min_role_rank=RANK_OPERATOR, description="remember a named place"),
        ToolSpec("memory.forget", Risk.DATA_WRITE, confirmation=Confirm.REQUIRED,
                 min_role_rank=RANK_OPERATOR, description="delete a memory"),

        # --- administrative (owner, explicit confirmation) -------------------- #
        ToolSpec("system.set_body", Risk.ADMINISTRATIVE, confirmation=Confirm.REQUIRED,
                 min_role_rank=RANK_OWNER, description="activate a different body package"),
        ToolSpec("system.install_update", Risk.ADMINISTRATIVE, confirmation=Confirm.REQUIRED,
                 min_role_rank=RANK_OWNER, description="install a signed update"),
        ToolSpec("system.request_reboot", Risk.ADMINISTRATIVE, confirmation=Confirm.REQUIRED,
                 min_role_rank=RANK_OWNER, description="reboot the droid"),
        ToolSpec("system.shutdown", Risk.ADMINISTRATIVE, confirmation=Confirm.REQUIRED,
                 min_role_rank=RANK_OWNER, description="shut down the droid"),
    ]


class ToolRegistry:
    def __init__(self, tools: list[ToolSpec] | None = None) -> None:
        self._tools: dict[str, ToolSpec] = {}
        for t in (tools if tools is not None else _default_tools()):
            self._tools[t.name] = t

    def register(self, tool: ToolSpec) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def is_registered(self, name: str) -> bool:
        return name in self._tools

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def always_available(self) -> list[ToolSpec]:
        return [t for t in self._tools.values() if t.always_available]

    def to_catalog(self) -> list[dict[str, Any]]:
        """The catalog exposed to the LLM (names + metadata only, no code)."""
        return [t.to_dict() for t in self._tools.values()]
