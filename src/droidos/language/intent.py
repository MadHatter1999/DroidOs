"""The structured intent (spec §14).

Natural language becomes a *proposal*, never a direct action. The broker validates
it before anything physical happens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StructuredIntent:
    intent: str
    arguments: dict[str, Any] = field(default_factory=dict)
    requires_motion: bool = False
    requested_speed: str = "normal"  # cautious | normal
    requested_output: str = "text"  # text | spoken summary
    raw_text: str = ""
    source: str = "offline"  # offline | llm
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "arguments": self.arguments,
            "requires_motion": self.requires_motion,
            "requested_speed": self.requested_speed,
            "requested_output": self.requested_output,
            "source": self.source,
            "confidence": round(self.confidence, 3),
        }
