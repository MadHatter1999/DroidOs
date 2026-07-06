"""The language layer (spec §13-§19).

Turns English into a *proposed* structured intent, validates it through the
command broker (permission, capability, safety, confirmation), and renders the
result back into English with personality. The LLM only ever proposes; the broker
decides. Basic commands work with no LLM at all (spec §16).
"""

from .intent import StructuredIntent
from .tools import ToolRegistry, ToolSpec, Risk
from .auth import Authorizer, Role
from .broker import CommandBroker, BrokerDecision

__all__ = [
    "StructuredIntent",
    "ToolRegistry",
    "ToolSpec",
    "Risk",
    "Authorizer",
    "Role",
    "CommandBroker",
    "BrokerDecision",
]
