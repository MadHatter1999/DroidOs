"""Shared test helpers: boot a DroidSystem against an isolated temp state dir."""

from __future__ import annotations

import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(os.path.dirname(_HERE), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _isolate_state() -> str:
    state = tempfile.mkdtemp(prefix="droidos-test-")
    os.environ["DROIDOS_STATE"] = state
    return state


def fresh_system(body: str | None = None, backend: str = "simulation"):
    """Return a freshly booted DroidSystem with clean, isolated state."""
    from droidos.system import DroidSystem

    _isolate_state()
    if body is not None:
        boot = DroidSystem.boot()
        boot.rt.body_manager.set_active(body, backend)
    return DroidSystem.boot()


def ask_confirm(sys_, text: str, user: str = "operator"):
    """Ask, auto-confirming any confirmation prompt (for motion tasks)."""
    resp = sys_.rt.language.process(text, user)
    if resp.needs_confirmation:
        resp = sys_.rt.language.process("yes", user, pending=resp.pending)
    return resp
