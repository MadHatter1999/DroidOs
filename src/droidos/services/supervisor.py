"""``droid-supervisor`` (spec §12.1) and the boot sequence (spec §8).

The highest non-hardware authority. It manages the DroidOS state machine, starts
and validates subsystems in dependency order, enforces startup dependencies,
detects failed services, and, crucially, refuses to permit movement until every
required check passes. A successful Linux boot does not by itself enable movement
(spec §8, §40). The supervisor does not directly operate motors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..core.states import DroidState
from .lifecycle import LifecycleState, ManagedService

if TYPE_CHECKING:
    from ..system import Runtime


@dataclass
class BootStep:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Readiness:
    state: DroidState
    inhibit_reasons: list[str]
    degraded_reasons: list[str]


# The order services are brought up, honouring dependencies (spec §8 steps 11-18).
_ACTIVATION_ORDER = [
    "safety_gateway",
    "hardware",
    "diagnostics",
    "state_estimator",
    "world_model",
    "memory",
    "perception",
    "navigation",
    "motion",
    "update",
    "executive",
    "voice",
    "language",
]

# Services whose failure to activate blocks motion (but not conversation).
_MOTION_CRITICAL = {"safety_gateway", "state_estimator", "motion", "navigation"}


class Supervisor:
    def __init__(self, rt: "Runtime") -> None:
        self.rt = rt
        self.boot_report: list[BootStep] = []
        self.readiness = Readiness(DroidState.POWERED_OFF, [], [])
        self.failed_services: list[str] = []

    # ---------------------------------------------------------------------- #
    def boot(self) -> Readiness:
        """Run the full boot sequence and settle into the resulting state."""
        rt = self.rt
        rep = self.boot_report = []
        state = rt.state

        state.transition(DroidState.BOOTING, "boot start")
        rep.append(BootStep("verify_os_image", True, "signature verification (stub in reference)"))
        rep.append(BootStep("start_kernel", True))
        rep.append(BootStep("mount_readonly_rootfs", True))
        rep.append(BootStep("start_logging", True))

        # 5. hardware watchdog / 7. contact safety controller
        safety = rt.safety
        if safety is None:
            rep.append(BootStep("contact_safety_controller", False, "no safety gateway"))
            state.transition(DroidState.HARDWARE_CHECK)
            state.transition(DroidState.MOTION_INHIBITED, "safety gateway missing")
            self.readiness = Readiness(DroidState.MOTION_INHIBITED, ["safety gateway missing"], [])
            return self.readiness
        safety_ok = safety.activate()
        rep.append(BootStep("start_watchdog", safety_ok))
        rep.append(BootStep("contact_safety_controller", safety_ok,
                            "" if safety_ok else safety.last_error))

        # 8. confirm actuator power disabled
        power_off = rt.backend is None or not rt.backend.power_enabled()
        rep.append(BootStep("confirm_power_disabled", power_off,
                            "" if power_off else "power was unexpectedly enabled"))

        state.transition(DroidState.HARDWARE_CHECK, "safety contacted")

        # 9. load body manifest (already loaded by DroidSystem) / 10. validate
        body = rt.body
        if body is None:
            rep.append(BootStep("load_body_manifest", False, "no body loaded"))
        else:
            fatal = [i for i in body.issues if "placeholder" not in i]
            rep.append(BootStep("load_body_manifest", True, f"{body.body_id}"))
            rep.append(BootStep("validate_body", not fatal,
                                "; ".join(fatal) if fatal else "ok"))

        # 11. start device drivers (connect backend)
        if rt.backend is not None:
            try:
                rt.backend.connect()
                rep.append(BootStep("start_device_drivers", True, rt.backend.kind))
            except Exception as exc:  # noqa: BLE001
                rep.append(BootStep("start_device_drivers", False, str(exc)))

        # 12-18. bring up the remaining services in dependency order
        for name in _ACTIVATION_ORDER:
            if name == "safety_gateway" or not rt.has(name):
                continue
            svc = rt.service(name)
            ok = self._activate_with_deps(svc)
            rep.append(BootStep(f"start_{name}", ok, "" if ok else svc.last_error))
            if not ok:
                self.failed_services.append(name)

        # 19. enter SAFE_IDLE
        state.transition(DroidState.SAFE_IDLE, "boot checks complete")
        rep.append(BootStep("enter_safe_idle", True))

        # 20. permit movement only after all required checks pass
        self.readiness = self.assess_readiness()
        self._settle(self.readiness.state)
        rep.append(BootStep("assess_readiness", True, self.readiness.state.value))
        return self.readiness

    def _activate_with_deps(self, svc: ManagedService) -> bool:
        for dep in svc.requires:
            if self.rt.has(dep):
                self._activate_with_deps(self.rt.service(dep))
        return svc.activate()

    # ---------------------------------------------------------------------- #
    def assess_readiness(self) -> Readiness:
        """Decide whether motion is permitted, and why not if it is not."""
        rt = self.rt
        inhibit: list[str] = []
        degraded: list[str] = []

        # Emergency stop short-circuits everything (spec §9).
        if rt.safety is not None and rt.safety.estop_engaged():
            return Readiness(DroidState.EMERGENCY_STOPPED, ["emergency stop engaged"], [])

        if rt.safety is None or not rt.safety.healthy():
            inhibit.append("safety controller is not healthy")

        # motion-critical services that failed to activate
        for name in _MOTION_CRITICAL:
            if rt.has(name) and rt.service(name).state != LifecycleState.ACTIVE:
                inhibit.append(f"{name} service is not active")

        body = rt.body
        backend = rt.backend
        if body is not None:
            # fatal body issues (missing required sensor declaration, bad gait policy)
            for issue in body.issues:
                if "placeholder" not in issue:
                    inhibit.append(issue)

            if backend is not None:
                # battery
                pct = backend.battery().percent
                if pct < body.limits.battery_motion_minimum():
                    inhibit.append(
                        f"battery {pct:.0f}% is below the motion minimum "
                        f"{body.limits.battery_motion_minimum():.0f}%"
                    )
                # required actuators present
                have_act = set(backend.actuator_names())
                for act in body.manifest.required_actuators:
                    if act not in have_act:
                        inhibit.append(f"required actuator {act!r} not detected")
                # required sensors responding
                for sid in body.manifest.required_sensors:
                    if not backend.read_sensor(sid).ok:
                        inhibit.append(f"required sensor {sid!r} not responding")
                # thermal faults
                for a in backend.read_all_actuators().values():
                    if a.fault_code:
                        inhibit.append(f"actuator {a.name} fault: {a.fault_code}")
                # non-required sensors that failed -> degraded (spec §9 DEGRADED)
                required = set(body.manifest.required_sensors)
                for s in body.sensors:
                    if s.id not in required and not backend.read_sensor(s.id).ok:
                        degraded.append(f"optional sensor {s.id} unavailable")
                # physical bus health
                if hasattr(backend, "bus_online") and not backend.bus_online():
                    inhibit.append("physical hardware bus is offline")

        # A stationary body simply has no motion to permit; that is not a fault and
        # is handled by the capability check in the command broker, not here.

        if inhibit:
            return Readiness(DroidState.MOTION_INHIBITED, inhibit, degraded)
        if degraded:
            return Readiness(DroidState.DEGRADED, [], degraded)
        return Readiness(DroidState.READY, [], degraded)

    def _settle(self, target: DroidState) -> None:
        st = self.rt.state
        if st.state == target:
            return
        if st.can_transition(target):
            st.transition(target, "readiness settle")
        else:
            st.force(target, "readiness settle")

    # ---------------------------------------------------------------------- #
    def refresh(self) -> Readiness:
        """Re-evaluate readiness (e.g. after a fault) without a full reboot."""
        self.readiness = self.assess_readiness()
        self._settle(self.readiness.state)
        return self.readiness

    def request_shutdown(self) -> None:
        st = self.rt.state
        if st.state != DroidState.SHUTTING_DOWN:
            st.force(DroidState.SHUTTING_DOWN, "shutdown requested")
        for svc in reversed(self.rt.all_services()):
            svc.shutdown()
        if self.rt.backend is not None:
            self.rt.backend.shutdown()
        st.force(DroidState.POWERED_OFF, "shutdown complete")

    def restart_failed(self) -> list[str]:
        restarted = []
        for name in list(self.failed_services):
            if self.rt.service(name).restart():
                self.failed_services.remove(name)
                restarted.append(name)
        return restarted
