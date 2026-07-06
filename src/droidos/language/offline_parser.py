"""Deterministic offline command parser (spec §16).

A small, dependency-free rule-based parser that maps English to a structured
intent for the essential commands, so the droid remains operable when the LLM is
unavailable: stop, emergency stop, cancel, status, battery, temperature, help,
return to safe idle, silence, shut down, report faults, report current task, plus
basic navigation, description, memory and place queries.

Walking, stopping, balance and safety must never depend on an external LLM, so
this parser is always present and is the fallback provider.
"""

from __future__ import annotations

import re

from .intent import StructuredIntent

_AFFIRM = {"yes", "y", "confirm", "confirmed", "do it", "go ahead", "affirmative", "proceed"}
_NEGATIVE = {"no", "n", "cancel", "cancel that", "stop", "negative", "abort", "don't", "dont"}


def is_affirmative(text: str) -> bool:
    return text.strip().lower().rstrip(".!") in _AFFIRM


def is_negative(text: str) -> bool:
    return text.strip().lower().rstrip(".!") in _NEGATIVE


def _cautious(t: str) -> str:
    return "cautious" if any(w in t for w in ("careful", "carefully", "slow", "slowly", "cautious")) else "normal"


def _clean(s: str) -> str:
    """Strip surrounding whitespace, articles and trailing punctuation from a slot."""
    s = s.strip().rstrip(" .?!,").strip()
    for article in ("the ", "a ", "an "):
        if s.lower().startswith(article):
            s = s[len(article):]
            break
    return s


def parse(text: str) -> StructuredIntent:
    raw = text.strip()
    t = " ".join(raw.lower().split())

    def si(intent, **kw):
        kw.setdefault("raw_text", raw)
        kw.setdefault("source", "offline")
        return StructuredIntent(intent=intent, **kw)

    # --- always-available safety commands (checked first) ----------------- #
    if "emergency stop" in t or t in ("e-stop", "estop", "kill power"):
        return si("motion.emergency_stop")
    if re.search(r"\b(silence|be quiet|stop talking|shush)\b", t):
        return si("voice.silence")
    if re.fullmatch(r"(stop|halt|freeze|stop moving|stop now)\.?", t):
        return si("motion.stop")
    if re.search(r"\b(cancel|abort)\b.*\b(task|it|that|action)?\b", t) and "don't" not in t:
        return si("task.cancel")
    if re.search(r"\b(shut ?down|power off|turn off)\b", t):
        return si("system.shutdown", requires_motion=False)
    if re.search(r"\b(reboot|restart)\b", t):
        return si("system.request_reboot")
    if re.search(r"\b(safe idle|stand down|return to idle|safe mode)\b", t):
        return si("robot.return_safe_idle")

    # --- information / conversation --------------------------------------- #
    if re.search(r"\b(battery|charge level|power level|how much (power|charge))\b", t):
        return si("robot.get_battery")
    if re.search(r"\b(temperature|how hot|motor temp|too hot|overheat)\b", t):
        return si("robot.get_temperature")
    if re.search(r"\b(what('| i)?s wrong|any (faults|problems)|report (active )?faults|diagnostics?|health)\b", t):
        return si("diagnostics.summary")
    if re.search(r"\b(current task|what are you doing|report (current )?task)\b", t):
        return si("robot.explain", arguments={"topic": "current_task"})
    if re.search(r"\bwhy\b", t) and re.search(r"\b(can'?t|cannot|stop|stopped|disabled|inhibit|fail)", t):
        return si("robot.explain", arguments={"topic": "why"})
    if re.search(r"\b(help|what can you do|commands)\b", t):
        return si("help")
    if re.search(r"\b(what (can|do) you see|describe (the )?(scene|room|surroundings)|look around)\b", t):
        return si("perception.describe_scene")
    if re.search(r"\b(list|known|what) (places|destinations|rooms)\b", t) or "where can you go" in t:
        return si("navigation.list_places")
    if re.search(r"\b(status|how are you|report status|are you (ok|safe))\b", t):
        return si("robot.get_status")

    # --- memory ----------------------------------------------------------- #
    m = re.match(r"(?:please )?forget (?:about )?(.+)", t)
    if m:
        return si("memory.forget", arguments={"query": _clean(m.group(1))})
    m = re.match(r"(?:please )?remember (?:that )?(.+)", raw, re.IGNORECASE)
    if m:
        return si("memory.remember", arguments={"text": m.group(1).strip().rstrip(" .")})

    # --- inspection: "go to X and inspect Y" / "inspect Y" ---------------- #
    m = re.search(r"(?:go to|navigate to|walk to|drive to) (?:the )?(.+?) and (?:inspect|look at|check) (?:the )?(.+)", t)
    if m:
        return si("inspect.named_target", requires_motion=True, requested_speed=_cautious(t),
                  arguments={"destination": _clean(m.group(1)), "target": _clean(m.group(2))},
                  requested_output="spoken summary")
    m = re.match(r"(?:inspect|look at|check) (?:the )?(.+)", t)
    if m:
        return si("inspect.named_target", requires_motion=True, requested_speed=_cautious(t),
                  arguments={"target": _clean(m.group(1))}, requested_output="spoken summary")

    # --- navigation / charging ------------------------------------------- #
    if re.search(r"\b(charg(e|ing)|dock)\b", t) and re.search(r"\b(go|return|navigate|to)\b", t):
        return si("navigation.go_charge", requires_motion=True, requested_speed=_cautious(t))
    if re.search(r"\b(walk|climb)\b.*\b(stairs|upstairs)\b", t):
        return si("navigation.navigate_to", requires_motion=True,
                  arguments={"destination": "stairs"})
    m = re.match(r"(?:please )?(?:go|navigate|walk|drive|move|proceed|head)(?: to| toward| towards| back to)? (?:the )?(.+)", t)
    if m:
        return si("navigation.navigate_to", requires_motion=True, requested_speed=_cautious(t),
                  arguments={"destination": _clean(m.group(1))})

    return si("unknown", arguments={"text": raw}, confidence=0.0)
