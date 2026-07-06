"""The capability registry (spec §21).

The body package publishes what the body can and cannot do. The English interface
reads this to decide whether a requested action is even possible, and to refuse
honestly when it is not (e.g. an R2 body told to "walk upstairs").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# A capability value may be a bool, a number, or the literal "experimental".
TRISTATE = {True: "supported", False: "unsupported", "experimental": "experimental"}


@dataclass
class Capabilities:
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Capabilities":
        # accept either {"capabilities": {...}} or {...}
        caps = data.get("capabilities", data) if isinstance(data, dict) else {}
        return cls(raw=caps or {})

    def category(self, name: str) -> dict[str, Any]:
        node = self.raw.get(name, {})
        return node if isinstance(node, dict) else {}

    def get(self, category: str, key: str, default: Any = None) -> Any:
        return self.category(category).get(key, default)

    # locomotion helpers --------------------------------------------------- #
    def locomotion_mode(self, mode: str) -> Any:
        """Return True / False / 'experimental' for a locomotion mode."""
        return self.get("locomotion", mode, False)

    def can(self, mode: str) -> bool:
        """True only when a mode is fully supported (not merely experimental)."""
        return self.locomotion_mode(mode) is True

    def is_experimental(self, mode: str) -> bool:
        return self.locomotion_mode(mode) == "experimental"

    def supports_motion(self) -> bool:
        return self.can("walk") or self.can("roll")

    def max_speed(self) -> float:
        return float(self.get("locomotion", "maximum_speed_mps", 0.0) or 0.0)

    # perception helpers --------------------------------------------------- #
    def has_perception(self, key: str) -> bool:
        return bool(self.get("perception", key, False))

    # manipulation helpers ------------------------------------------------- #
    def has_manipulation(self, key: str) -> bool:
        return bool(self.get("manipulation", key, False))

    def max_payload_kg(self) -> float:
        return float(self.get("manipulation", "maximum_payload_kg", 0.0) or 0.0)

    # posture -------------------------------------------------------------- #
    def posture(self, key: str) -> bool:
        return bool(self.get("posture", key, False))

    # summaries ------------------------------------------------------------ #
    def locomotion_summary(self) -> str:
        loco = self.category("locomotion")
        if not loco:
            return "no locomotion"
        modes = [m for m in ("walk", "roll", "reverse", "turn_in_place") if loco.get(m) is True]
        exp = [m for m in loco if loco.get(m) == "experimental"]
        parts = []
        if modes:
            parts.append(", ".join(modes))
        if exp:
            parts.append("experimental: " + ", ".join(exp))
        speed = self.max_speed()
        if speed:
            parts.append(f"up to {speed:.2f} m/s")
        return "; ".join(parts) if parts else "no locomotion"

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw)
