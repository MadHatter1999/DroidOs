"""DroidOS exception hierarchy.

Errors are typed so the command broker and CLIs can distinguish *why* an action
was refused (spec §14) and so refusals never masquerade as success (spec §39).
"""

from __future__ import annotations


class DroidError(Exception):
    """Base class for all DroidOS runtime errors."""


class ConfigError(DroidError):
    """Configuration is missing or invalid."""


class BodyError(DroidError):
    """A body package is missing, malformed, or incompatible (spec §20, §25)."""


class BackendError(DroidError):
    """The hardware/simulation backend failed to respond."""


class SafetyError(DroidError):
    """A safety precondition was not met (spec §24). Motion is refused."""


class CapabilityError(DroidError):
    """The active body cannot perform the requested action (spec §21)."""


class AuthorizationError(DroidError):
    """The current user is not permitted to perform the action (spec §32)."""


class ConfirmationRequired(DroidError):
    """The action is valid but requires explicit confirmation (spec §18)."""

    def __init__(self, message: str, risk: str) -> None:
        super().__init__(message)
        self.risk = risk


class UnknownIntentError(DroidError):
    """The requested intent is not in the tool registry (spec §17)."""


class ProviderError(DroidError):
    """The LLM provider failed or is unavailable (spec §16)."""
