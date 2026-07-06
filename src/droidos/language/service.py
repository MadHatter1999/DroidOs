"""``droid-language`` (spec §12.11).

The interaction service: English in, English out. It obtains a *proposed*
structured intent from the active provider (LLM or offline parser), passes it
through the command broker, runs approved actions on the executive, and renders
the structured result into English. Facts come from the services; personality
only decorates wording (spec §19). When the model is unavailable it says so and
falls back to deterministic commands (spec §16, §39).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..core.errors import DroidError
from .auth import Authorizer
from .broker import BrokerDecision, CommandBroker, Outcome
from .intent import StructuredIntent
from . import offline_parser
from .personality import Personality
from .providers import ProviderChain, build_provider
from .tools import ToolRegistry

if TYPE_CHECKING:
    from ..system import Runtime
    from ..executive.tasks import TaskResult


@dataclass
class Response:
    text: str
    outcome: str = "approved"
    needs_confirmation: bool = False
    pending: StructuredIntent | None = None
    degraded: bool = False
    decision: BrokerDecision | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "outcome": self.outcome, "degraded": self.degraded}


class LanguageService:
    def __init__(self, rt: "Runtime") -> None:
        self.rt = rt
        self.registry = ToolRegistry()
        self.authorizer = Authorizer(rt.config)
        self.personality = Personality(rt.config)
        self.broker = CommandBroker(rt, self.registry, self.authorizer)
        self.chain = self._build_chain()
        self.renderer = Renderer(self.personality)
        # expose to the runtime for the executive help handler / diagnostics
        rt.tool_registry = self.registry  # type: ignore[attr-defined]
        rt.language_degraded = self.chain.degraded()  # type: ignore[attr-defined]

    def _build_chain(self):
        lang = self.rt.config.language
        providers = lang.get("providers", {})
        order = []
        for key in ("primary_provider", "fallback_provider"):
            name = lang.get(key)
            if name and name in providers:
                order.append(build_provider(name, providers[name]))
        return ProviderChain(order)

    # main entry ----------------------------------------------------------- #
    def process(self, text: str, user_name: str | None = None, confirmed: bool = False,
                pending: StructuredIntent | None = None) -> Response:
        user = self.authorizer.resolve(user_name)
        degraded = self.chain.degraded()

        # confirmation round-trip in interactive mode
        if pending is not None:
            if offline_parser.is_affirmative(text):
                return self._dispatch(pending, user, confirmed=True, degraded=degraded)
            if offline_parser.is_negative(text):
                return Response("Understood, cancelled.", outcome="cancelled", degraded=degraded)
            # anything else: treat as a fresh command

        intent = self.chain.generate_structured_intent(text, self.registry.to_catalog(), {})
        self.rt.audit.emit("command", user=user.name, request_text=text, intent=intent.intent,
                           arguments=intent.arguments, detail={"source": intent.source})
        return self._dispatch(intent, user, confirmed=confirmed, degraded=degraded)

    def _dispatch(self, intent: StructuredIntent, user, confirmed: bool, degraded: bool) -> Response:
        decision = self.broker.validate(intent, user, confirmed=confirmed)
        self.rt.audit.emit("approval", user=user.name, intent=intent.intent,
                           approval=decision.outcome.value, reason=decision.reason)

        if decision.outcome == Outcome.CONFIRM:
            return Response(self.personality.refuse(decision.confirm_prompt),
                            outcome="confirmation_required", needs_confirmation=True,
                            pending=intent, degraded=degraded, decision=decision)

        if decision.outcome == Outcome.REJECTED:
            text = self.personality.refuse(decision.reason)
            if intent.intent == "unknown" and degraded:
                text = ("My advanced language service is unavailable. Basic status, stop, cancel, "
                        "return and shutdown commands remain available.")
            return Response(text, outcome="rejected", degraded=degraded, decision=decision)

        # approved -> execute
        executive = self.rt.executive
        if executive is None:
            return Response("Executive service is unavailable.", outcome="error", degraded=degraded)
        try:
            result = executive.run_intent(decision, user.name)
        except DroidError as exc:
            return Response(self.personality.refuse(str(exc)), outcome="error", degraded=degraded)
        return Response(self.renderer.render(result, self.rt), outcome="approved" if result.ok else "failed",
                        degraded=degraded, decision=decision)

    # helpers for CLI ------------------------------------------------------ #
    def active_provider_name(self) -> str:
        return self.chain.active().name

    def is_degraded(self) -> bool:
        return self.chain.degraded()


class Renderer:
    """Renders a structured :class:`TaskResult` into English from verified facts."""

    def __init__(self, personality: Personality) -> None:
        self.p = personality

    def render(self, result: "TaskResult", rt: "Runtime") -> str:
        fn = getattr(self, f"_r_{result.kind.replace('.', '_')}", None)
        if fn is None:
            text = self._fallback(result)
        else:
            text = fn(result)
        return self.p.trim(text)

    # -- information ------------------------------------------------------- #
    def _r_robot_get_status(self, r) -> str:
        d = r.data
        lines = [f"I am {d.get('name','the droid')}. Current state: {d.get('state')}."]
        b = d.get("battery_percent")
        if b is not None:
            lines.append(f"Battery charge is {b:.0f} percent.")
        if d.get("motion_permitted"):
            lines.append("All required systems are responding; I am currently safe to move.")
        else:
            reasons = d.get("inhibit_reasons") or []
            if reasons:
                lines.append("Movement is disabled: " + "; ".join(reasons) + ".")
            else:
                lines.append("Movement is not currently permitted.")
        hm = d.get("hottest_motor")
        if hm and hm.get("level") != "OK":
            lines.append(f"Note: {hm.get('message')}.")
        return " ".join(lines)

    def _r_robot_get_battery(self, r) -> str:
        d = r.data
        s = f"Battery charge is {d['percent']:.0f} percent"
        s += " and charging." if d.get("charging") else "."
        if not d.get("safe_to_move"):
            s += f" That is below the {d['motion_minimum']:.0f} percent motion minimum, so movement is inhibited."
        return s

    def _r_robot_get_temperature(self, r) -> str:
        d = r.data
        hot = d.get("hottest")
        if not hot:
            return "I have no motor temperature readings."
        s = f"The warmest joint is {hot['name']} at {hot['temp_c']:.1f} C"
        s += f" (warning at {d['warn_c']:.0f} C, fault at {d['fault_c']:.0f} C)."
        if hot["temp_c"] >= d["fault_c"]:
            s += " It has exceeded its fault threshold."
        elif hot["temp_c"] >= d["warn_c"]:
            s += " It is warmer than normal but below the warning threshold."
        return s

    def _r_diagnostics_summary(self, r) -> str:
        d = r.data
        if d.get("fault_count", 0) == 0:
            return "All monitored systems are nominal. Nothing is wrong."
        lines = [f"I have {d['fault_count']} issue(s):"]
        for f in d.get("faults", []):
            lines.append(f"  - {f['name']} [{f['level']}]: {f['message']}")
        return "\n".join(lines)

    def _r_robot_explain(self, r) -> str:
        d = r.data
        if d.get("topic") == "current_task":
            lt = d.get("last_task")
            if not lt:
                return "I have not performed any task yet."
            return f"My last task was {lt['intent']} ({lt['state']}); steps: {', '.join(lt['steps']) or 'none'}."
        if d.get("estop"):
            return "Movement is disabled because an emergency stop is engaged. Motor power has been removed."
        reasons = d.get("inhibit_reasons") or []
        if reasons:
            return "Movement is disabled because: " + "; ".join(reasons) + "."
        return "Movement is currently permitted; there is nothing preventing me from moving."

    def _r_perception_describe_scene(self, r) -> str:
        d = r.data
        if not d.get("camera_ok", False):
            return d.get("summary", "My camera is not available, so I cannot describe the scene.")
        conf = d.get("confidence", 0.0)
        return f"I can see {d.get('summary')}. (visual confidence {conf:.2f})"

    def _r_navigation_list_places(self, r) -> str:
        places = r.data.get("places", [])
        if not places:
            return "I do not have any named destinations yet."
        return "I know these places: " + ", ".join(places) + "."

    def _r_help(self, r) -> str:
        lines = ["I understand commands such as:"]
        for t in r.data.get("tools", []):
            lines.append(f"  - {t['name']}: {t['description']} [{t['risk']}]")
        return "\n".join(lines)

    # -- control ----------------------------------------------------------- #
    def _r_motion_stop(self, r) -> str:
        return "Stopped."

    def _r_motion_emergency_stop(self, r) -> str:
        return "Emergency stop engaged. Motor power has been removed."

    def _r_task_cancel(self, r) -> str:
        return "The active task has been cancelled and I have stopped."

    def _r_voice_silence(self, r) -> str:
        return ""

    def _r_robot_return_safe_idle(self, r) -> str:
        return f"Returning to safe idle. State is now {r.data.get('state')}."

    # -- motion tasks ------------------------------------------------------ #
    def _r_navigation_navigate_to(self, r) -> str:
        if r.ok:
            return f"I have arrived at {r.data.get('destination')}."
        return self.p.refuse(r.error or "I could not reach the destination.")

    def _r_navigation_go_charge(self, r) -> str:
        if r.ok:
            return "I have returned to the charging station and started docking."
        return self.p.refuse(r.error or "I could not return to the charging station.")

    def _r_inspect_named_target(self, r) -> str:
        if not r.ok:
            return self.p.refuse(r.error or "I could not complete the inspection.")
        d = r.data
        if not d.get("found", False):
            return f"I did not see {d.get('target', 'the target')} from here. ({d.get('note','')})".strip()
        parts = [f"I inspected the {d.get('target')}."]
        ind = d.get("indicators")
        if ind:
            parts.append(
                f"I found {ind.get('amber',0)} amber and {ind.get('red',0)} red indicators, "
                f"with {ind.get('green',0)} green."
            )
        if d.get("open_cabinet_door"):
            parts.append("The cabinet door is open.")
        parts.append(f"(observation only; visual confidence {d.get('confidence',0):.2f}). "
                     "I can report what I see but not diagnose the cause without a reference.")
        return " ".join(parts)

    # -- memory / admin ---------------------------------------------------- #
    def _r_memory_remember(self, r) -> str:
        return f'Noted: "{r.data.get("remembered")}".' if r.ok else self.p.refuse(r.error)

    def _r_memory_store_place(self, r) -> str:
        return f"I have remembered {r.data.get('place')} at ({r.data.get('x'):.1f}, {r.data.get('y'):.1f})."

    def _r_memory_forget(self, r) -> str:
        n = r.data.get("removed", 0)
        return f"I removed {n} remembered item(s)." if n else "I had nothing matching to forget."

    def _r_system_set_body(self, r) -> str:
        if not r.ok:
            return self.p.refuse(r.error)
        sel = r.data.get("selection", {})
        return f"Body {sel.get('body_id')} ({sel.get('backend')}) will activate on next boot."

    def _r_system_install_update(self, r) -> str:
        return r.data.get("note", "Update handled.")

    def _r_system_request_reboot(self, r) -> str:
        return "Reboot requested."

    def _r_system_shutdown(self, r) -> str:
        return "Shutting down."

    def _fallback(self, r) -> str:
        if r.ok:
            return "Done."
        return self.p.refuse(r.error or "The task did not succeed.")
