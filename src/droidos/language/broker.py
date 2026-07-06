"""The command broker (spec §14, §18).

The LLM (or offline parser) only ever produces a *proposal*. The broker is the
single gate every proposal must pass before it can reach the task executive. It
checks, in order: intent registration, user authorization, body capability,
destination knowledge, route traversability, current motion permission, and the
confirmation rules. Only an approved action proceeds. The broker cannot be
bypassed by the LLM, and it enforces safety independently of personality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from .auth import User
from .intent import StructuredIntent
from .tools import Confirm, Risk, ToolRegistry, ToolSpec

if TYPE_CHECKING:
    from ..system import Runtime


class Outcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    CONFIRM = "confirmation_required"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class BrokerDecision:
    outcome: Outcome
    intent: StructuredIntent
    tool: ToolSpec | None = None
    reason: str = ""
    confirm_prompt: str = ""
    checks: list[Check] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return self.outcome == Outcome.APPROVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "intent": self.intent.intent,
            "reason": self.reason,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
        }


class CommandBroker:
    def __init__(self, rt: "Runtime", registry: ToolRegistry, authorizer) -> None:
        self.rt = rt
        self.registry = registry
        self.authorizer = authorizer

    def validate(self, intent: StructuredIntent, user: User, confirmed: bool = False) -> BrokerDecision:
        checks: list[Check] = []

        def reject(reason: str, tool: ToolSpec | None = None) -> BrokerDecision:
            return BrokerDecision(Outcome.REJECTED, intent, tool, reason, checks=checks)

        # 1. registered? (spec §17) ---------------------------------------- #
        tool = self.registry.get(intent.intent)
        if tool is None:
            checks.append(Check("registered", False, intent.intent))
            return reject(
                "I do not have a registered action for that request." if intent.intent != "unknown"
                else "I did not understand that request."
            )
        checks.append(Check("registered", True, tool.name))

        # always-available tools bypass the remaining gates (spec §16, §17) - #
        if tool.always_available:
            checks.append(Check("always_available", True))
            return BrokerDecision(Outcome.APPROVED, intent, tool, "approved", checks=checks)

        # 2. authorization (spec §32) -------------------------------------- #
        ok, detail = self.authorizer.authorize(user, tool.min_role_rank)
        checks.append(Check("authorization", ok, detail))
        if not ok:
            return reject(detail, tool)

        # 3. capability (spec §21) ----------------------------------------- #
        cap_ok, cap_reason = self._capability_ok(tool)
        checks.append(Check("capability", cap_ok, cap_reason))
        if not cap_ok:
            return reject(cap_reason, tool)

        # 4. destination knowledge + 5. traversability (spec §12.8, §21) --- #
        if tool.requires_motion:
            dest_ok, dest_reason = self._destination_ok(intent, tool)
            checks.append(Check("destination", dest_ok, dest_reason))
            if not dest_ok:
                return reject(dest_reason, tool)

        # 6. motion permission (spec §9, §24) ------------------------------ #
        if tool.requires_motion:
            move_ok, move_reason = self._motion_permitted()
            checks.append(Check("motion_permitted", move_ok, move_reason))
            if not move_ok:
                return reject(move_reason, tool)

        # 7. confirmation (spec §18) --------------------------------------- #
        need, cprompt = self._needs_confirmation(tool, intent)
        checks.append(Check("confirmation", not need, cprompt if need else "not required"))
        if need and not confirmed:
            return BrokerDecision(Outcome.CONFIRM, intent, tool, "confirmation required",
                                  confirm_prompt=cprompt, checks=checks)

        return BrokerDecision(Outcome.APPROVED, intent, tool, "approved", checks=checks)

    # ---------------------------------------------------------------------- #
    def _capability_ok(self, tool: ToolSpec) -> tuple[bool, str]:
        body = self.rt.body
        if body is None:
            return False, "no body is loaded"
        cap = tool.required_capability
        if cap is None:
            return True, "no capability required"
        if cap == "locomotion":
            if not body.capabilities.supports_motion():
                return False, (
                    f"this body ({body.name}) cannot move; it has no locomotion capability"
                )
            return True, "locomotion available"
        # otherwise treat as a perception / manipulation capability flag
        if body.capabilities.has_perception(cap):
            return True, f"{cap} available"
        if body.capabilities.has_manipulation(cap):
            return True, f"{cap} available"
        return False, f"this body does not have {cap.replace('_', ' ')}"

    def _destination_ok(self, intent: StructuredIntent, tool: ToolSpec) -> tuple[bool, str]:
        nav = self.rt.navigation
        if nav is None:
            return False, "navigation service unavailable"
        if tool.name == "navigation.go_charge":
            dest = "charging station"
        else:
            dest = intent.arguments.get("destination")
        if not dest:
            # inspect-in-place with no destination: nothing to traverse to
            if tool.name == "inspect.named_target":
                return True, "inspect in current position"
            return False, "no destination was specified"
        if nav.resolve(dest) is None:
            known = ", ".join(nav.known_places()) or "none"
            return False, f"{dest!r} is not a known destination. Known places: {known}"
        traversable, reason = nav.traversable(dest)
        if not traversable:
            return False, reason
        return True, f"{dest} is reachable"

    def _motion_permitted(self) -> tuple[bool, str]:
        supervisor = getattr(self.rt, "supervisor", None)
        if supervisor is not None:
            readiness = supervisor.assess_readiness()
            from ..core.states import MOTION_ALLOWED_FROM  # local import avoids cycle
            if readiness.state in MOTION_ALLOWED_FROM:
                return True, "motion permitted"
            reasons = readiness.inhibit_reasons or [f"state is {readiness.state.value}"]
            return False, "; ".join(reasons)
        # fall back to the raw state machine
        if self.rt.state.motion_permitted():
            return True, "motion permitted"
        return False, f"motion not permitted in state {self.rt.state.state.value}"

    def _needs_confirmation(self, tool: ToolSpec, intent: StructuredIntent) -> tuple[bool, str]:
        if tool.confirmation == Confirm.NONE:
            return False, ""
        if tool.confirmation == Confirm.REQUIRED:
            return True, self._confirm_prompt(tool, intent)
        # CONDITIONAL (spec §18): decide from context
        if tool.risk == Risk.MOTION:
            dest = intent.arguments.get("destination", "")
            nav = self.rt.navigation
            near_stairs = "stair" in str(dest).lower()
            newly_discovered = bool(dest) and nav is not None and nav.resolve(dest) is None
            if near_stairs or newly_discovered or intent.requested_speed != "cautious":
                return True, self._confirm_prompt(tool, intent)
            return False, ""
        if tool.name in ("memory.remember", "memory.store_place"):
            text = " ".join(str(v) for v in intent.arguments.values()).lower()
            personal = any(w in text for w in ("my name", "i am ", "person", "phone", "address", "password"))
            if personal:
                return True, self._confirm_prompt(tool, intent)
            return False, ""
        return False, ""

    @staticmethod
    def _confirm_prompt(tool: ToolSpec, intent: StructuredIntent) -> str:
        args = ", ".join(f"{k}={v}" for k, v in intent.arguments.items())
        detail = f" ({args})" if args else ""
        return f"This will {tool.description or tool.name}{detail}. Confirm? [yes/no]"
