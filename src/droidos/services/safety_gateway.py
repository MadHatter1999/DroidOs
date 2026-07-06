"""``droid-safety-gateway`` (spec §12.2).

Communicates with the independent safety microcontroller (here, the simulated
controller). Provides the safety heartbeat, emergency-stop status, motor-power
contactor state, hardware-watchdog state, fault reporting, the movement-permission
token, and safety-event logging.

The safety microcontroller, never this gateway, and never the LLM, remains
authoritative for electrical motor shutdown (spec §24). The e-stop latch is
persisted so it survives across process invocations, exactly as a hardware latch
survives a reboot until the defined recovery process clears it (spec §9).
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from ..backends.safety_controller import SimulatedSafetyController
from ..core.models import DiagnosticLevel, DiagnosticStatus, MotionPermission
from ..core.states import DroidState
from .lifecycle import ManagedService

if TYPE_CHECKING:
    from ..system import Runtime


class SafetyGateway(ManagedService):
    def __init__(self, rt: "Runtime") -> None:
        super().__init__("safety_gateway", rt)
        self.controller = SimulatedSafetyController()
        self._token: str = ""

    # lifecycle ------------------------------------------------------------ #
    def _on_configure(self) -> bool:
        self._load_latch()
        self.controller.heartbeat()
        return True

    def _on_activate(self) -> bool:
        self.controller.heartbeat()
        # Boot sequence step: confirm actuator power is disabled (spec §8 step 8).
        self.controller.disable_power()
        if self.rt.backend is not None:
            self.rt.backend.set_power(False)
        return True

    # heartbeat ------------------------------------------------------------ #
    def heartbeat(self) -> None:
        self.controller.heartbeat()

    # status --------------------------------------------------------------- #
    def status(self) -> dict[str, Any]:
        self.controller.heartbeat()  # a live host is contacting the controller now
        st = self.controller.status()
        return st.to_dict()

    def healthy(self) -> bool:
        self.controller.heartbeat()
        return self.controller.status().healthy()

    def link_up(self) -> bool:
        return self.controller.link_up()

    # emergency stop (never requires confirmation, works without the LLM) --- #
    def engage_estop(self, reason: str = "operator_command") -> None:
        self.controller.engage_estop(reason)
        if self.rt.backend is not None:
            self.rt.backend.set_power(False)
        self._save_latch(estop=True, reason=reason)
        self._log_safety_event("emergency_stop", reason)
        try:
            self.rt.state.force(DroidState.EMERGENCY_STOPPED, f"estop: {reason}")
        except Exception:  # state machine is best-effort here; safety already acted
            pass

    def reset_estop(self) -> bool:
        """Clear the latch. The caller must have completed the recovery process."""
        self.controller.reset_estop()
        self._save_latch(estop=False, reason="")
        self._log_safety_event("estop_reset", "recovery_complete")
        return True

    def estop_engaged(self) -> bool:
        return self.controller.status().estop_engaged

    # motion permission token (spec §12.2) --------------------------------- #
    def request_motion_permission(self) -> MotionPermission:
        self.controller.heartbeat()
        st = self.controller.status()
        if not st.healthy():
            reasons = []
            if st.estop_engaged:
                reasons.append("emergency stop engaged")
            if not st.alive or not st.watchdog_ok:
                reasons.append("safety controller link unhealthy")
            if st.faults:
                reasons.append("active safety faults: " + ", ".join(st.faults))
            return MotionPermission(False, "; ".join(reasons) or "safety controller not healthy")
        if not self.controller.request_power_enable():
            return MotionPermission(False, "safety controller refused to enable motor power")
        if self.rt.backend is not None:
            self.rt.backend.set_power(True)
        self._token = f"mp-{int(time.time() * 1000)}"
        self._log_safety_event("motion_permission_granted", self._token)
        return MotionPermission(True, "granted", self._token)

    def release_motion_permission(self) -> None:
        self.controller.disable_power()
        if self.rt.backend is not None:
            self.rt.backend.set_power(False)
        if self._token:
            self._log_safety_event("motion_permission_released", self._token)
        self._token = ""

    def report_fault(self, name: str) -> None:
        self.controller.report_fault(name)
        if self.rt.backend is not None:
            self.rt.backend.set_power(False)
        self._log_safety_event("fault_reported", name)

    # fault-link simulation (used by failure tests, spec §26/§39) ---------- #
    def set_safety_link(self, up: bool) -> None:
        self.controller.set_link(up)
        if not up:
            self._log_safety_event("safety_link_lost", "")

    # diagnostics ---------------------------------------------------------- #
    def diagnostics(self) -> list[DiagnosticStatus]:
        st = self.controller.status()
        level = DiagnosticLevel.OK
        msg = "safety controller healthy"
        if st.estop_engaged:
            level, msg = DiagnosticLevel.ERROR, "EMERGENCY STOP engaged"
        elif st.faults:
            level, msg = DiagnosticLevel.ERROR, "safety faults: " + ", ".join(st.faults)
        elif not st.alive or not st.watchdog_ok:
            level, msg = DiagnosticLevel.ERROR, "safety controller link unhealthy"
        return [
            DiagnosticStatus(
                name="safety/controller",
                level=level,
                message=msg,
                hardware_id="safety-mcu",
                values=st.to_dict(),
            )
        ]

    # persistence ---------------------------------------------------------- #
    def _load_latch(self) -> None:
        path = self.rt.paths.safety_latch_file
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if data.get("estop_engaged"):
            self.controller.engage_estop(data.get("reason", "persisted_latch"))

    def _save_latch(self, estop: bool, reason: str) -> None:
        path = self.rt.paths.safety_latch_file
        try:
            path.write_text(
                json.dumps({"estop_engaged": estop, "reason": reason, "stamp": time.time()}),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _log_safety_event(self, event: str, detail: str) -> None:
        self.rt.audit.emit(
            "safety",
            reason=event,
            detail={"detail": detail},
            safety_state="EMERGENCY_STOPPED" if self.controller.status().estop_engaged else "ok",
        )
        self.rt.bus.publish("safety/event", {"event": event, "detail": detail}, source=self.name)
