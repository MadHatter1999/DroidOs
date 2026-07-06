"""Managed service lifecycle (spec §11).

Mirrors ROS 2 lifecycle nodes: a component moves through known states under
external control, so the supervisor can create and validate a service before it
begins operating and can restart or replace it.

    UNCONFIGURED -> INACTIVE -> ACTIVE -> INACTIVE -> FINALIZED

Concrete services override the ``_on_configure`` / ``_on_activate`` /
``_on_deactivate`` / ``_on_cleanup`` hooks. A hook returns ``True`` on success;
returning ``False`` (or raising) leaves the service in its previous state, and
the supervisor refuses to bring the system up (spec §11, §12.1).
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from ..core.models import DiagnosticLevel, DiagnosticStatus

if TYPE_CHECKING:  # avoid import cycle; Runtime is defined in droidos.system
    from ..system import Runtime


class LifecycleState(str, Enum):
    UNCONFIGURED = "UNCONFIGURED"
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    FINALIZED = "FINALIZED"


class ManagedService:
    #: Services this one requires to be ACTIVE before it can activate (spec §11).
    requires: tuple[str, ...] = ()

    def __init__(self, name: str, rt: "Runtime") -> None:
        self.name = name
        self.rt = rt
        self.state = LifecycleState.UNCONFIGURED
        self.restart_count = 0
        self.last_error: str = ""

    # transitions ---------------------------------------------------------- #
    def configure(self) -> bool:
        if self.state not in (LifecycleState.UNCONFIGURED, LifecycleState.INACTIVE):
            return self.state == LifecycleState.INACTIVE
        ok = self._guard(self._on_configure)
        if ok:
            self.state = LifecycleState.INACTIVE
        return ok

    def activate(self) -> bool:
        if self.state == LifecycleState.ACTIVE:
            return True
        if self.state != LifecycleState.INACTIVE:
            if not self.configure():
                return False
        ok = self._guard(self._on_activate)
        if ok:
            self.state = LifecycleState.ACTIVE
        return ok

    def deactivate(self) -> bool:
        if self.state != LifecycleState.ACTIVE:
            return True
        ok = self._guard(self._on_deactivate)
        if ok:
            self.state = LifecycleState.INACTIVE
        return ok

    def cleanup(self) -> bool:
        self._guard(self._on_cleanup)
        self.state = LifecycleState.UNCONFIGURED
        return True

    def shutdown(self) -> None:
        try:
            if self.state == LifecycleState.ACTIVE:
                self.deactivate()
            self._on_cleanup()
        finally:
            self.state = LifecycleState.FINALIZED

    def restart(self) -> bool:
        """Recover a failed service (spec §12.1, §28 restart count)."""
        self.restart_count += 1
        self.cleanup()
        return self.activate()

    # hooks (override in subclasses) --------------------------------------- #
    def _on_configure(self) -> bool:
        return True

    def _on_activate(self) -> bool:
        return True

    def _on_deactivate(self) -> bool:
        return True

    def _on_cleanup(self) -> bool:
        return True

    # diagnostics ---------------------------------------------------------- #
    def diagnostics(self) -> list[DiagnosticStatus]:
        level = DiagnosticLevel.OK if self.state == LifecycleState.ACTIVE else DiagnosticLevel.WARN
        msg = self.state.value + (f" ({self.last_error})" if self.last_error else "")
        return [
            DiagnosticStatus(
                name=f"service/{self.name}",
                level=level if self.state != LifecycleState.UNCONFIGURED else DiagnosticLevel.WARN,
                message=msg,
                values={"state": self.state.value, "restart_count": self.restart_count},
            )
        ]

    # internal ------------------------------------------------------------- #
    def _guard(self, fn: Any) -> bool:
        try:
            result = fn()
            self.last_error = ""
            return bool(result)
        except Exception as exc:  # noqa: BLE001 - services must not crash the supervisor
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.rt.log.error(f"{self.name}: {self.last_error}")
            return False

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name} {self.state.value}>"
