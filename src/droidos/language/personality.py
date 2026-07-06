"""Personality and identity (spec §19).

Personality controls wording, tone, humour and response length. It must NOT alter
safety thresholds, physical limits, authorization, sensor truth, diagnostic
severity or command permissions. The droid may be sarcastic about an overheated
motor; it may not ignore the overheated motor.

Accordingly, this module only ever *decorates* text that has already been produced
from verified facts. It never sees or changes the facts themselves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.config import Config


_FLAVOR = {
    "dry_literal": {
        "ack": "",
        "refuse_prefix": "",
        "greeting": "Ready.",
        "tone": "dry",
    },
    "cheerful": {
        "ack": "On it!",
        "refuse_prefix": "Sorry, ",
        "greeting": "Hello! Standing by.",
        "tone": "warm",
    },
    "formal": {
        "ack": "Acknowledged.",
        "refuse_prefix": "Regretfully, ",
        "greeting": "At your service.",
        "tone": "formal",
    },
    "terse": {
        "ack": "",
        "refuse_prefix": "",
        "greeting": "Ready.",
        "tone": "terse",
    },
}


class Personality:
    def __init__(self, config: "Config") -> None:
        ident = config.identity
        self.name = ident.get("name", "droid")
        self.model_family = ident.get("model_family", "droid")
        self.profile = ident.get("personality_profile", "dry_literal")
        self.verbosity = ident.get("verbosity", "concise")
        self.wake_names = ident.get("wake_names", [self.name])
        self._flavor = _FLAVOR.get(self.profile, _FLAVOR["dry_literal"])

    def greeting(self) -> str:
        return self._flavor["greeting"]

    def acknowledge(self, text: str) -> str:
        ack = self._flavor["ack"]
        return f"{ack} {text}".strip() if ack else text

    def refuse(self, reason: str) -> str:
        """Wrap a refusal. The *reason* is factual and passes through unchanged."""
        prefix = self._flavor["refuse_prefix"]
        return f"{prefix}{reason}" if prefix else reason

    def trim(self, text: str) -> str:
        """Apply verbosity preference. Never removes safety-relevant content; the
        caller is responsible for keeping such content in the first sentence."""
        if self.verbosity == "verbose":
            return text
        if self.verbosity == "terse":
            # keep only the first sentence/line
            first = text.strip().split("\n", 1)[0]
            return first.split(". ", 1)[0].rstrip(".") + ("." if first else "")
        return text
