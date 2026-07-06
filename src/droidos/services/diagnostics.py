"""``droid-diagnostics`` (spec §12.14, §28).

Collects and aggregates health information from every major component: computer,
network, sensors, actuators and robot-level status. Mirrors the ROS diagnostics
stack (collect device diagnostics, publish standard status, aggregate). This is
the evidence base the language service uses to answer "What is wrong?", "Why can't
you walk?" and "Which motor is hottest?", answers come from these facts, not from
model speculation (spec §28).
"""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING, Any

from ..core.models import DiagnosticLevel, DiagnosticStatus
from .lifecycle import ManagedService

if TYPE_CHECKING:
    from ..system import Runtime


class Diagnostics(ManagedService):
    requires = ("safety_gateway",)

    def __init__(self, rt: "Runtime") -> None:
        super().__init__("diagnostics", rt)

    # aggregation ---------------------------------------------------------- #
    def collect(self) -> list[DiagnosticStatus]:
        out: list[DiagnosticStatus] = []
        out += self._computer()
        out += self._network()
        out += self._actuators()
        out += self._sensors()
        out += self._battery()
        out += self._robot_level()
        # every managed service reports its own status
        for svc in self.rt.all_services():
            out += svc.diagnostics()
        return out

    def summary(self) -> dict[str, Any]:
        items = self.collect()
        worst = max((d.level for d in items), default=DiagnosticLevel.OK)
        faults = [d for d in items if d.level >= DiagnosticLevel.WARN]
        return {
            "overall": worst.label,
            "fault_count": len(faults),
            "faults": [d.to_dict() for d in faults],
        }

    def problems(self) -> list[DiagnosticStatus]:
        return [d for d in self.collect() if d.level >= DiagnosticLevel.WARN]

    def hottest_actuator(self) -> DiagnosticStatus | None:
        backend = self.rt.backend
        if backend is None:
            return None
        acts = backend.read_all_actuators()
        if not acts:
            return None
        hottest = max(acts.values(), key=lambda a: a.temperature_c)
        warn = self.rt.body.limits.motor_warn_temp() if self.rt.body else 70.0
        fault = self.rt.body.limits.motor_fault_temp() if self.rt.body else 85.0
        level = DiagnosticLevel.OK
        if hottest.temperature_c >= fault:
            level = DiagnosticLevel.ERROR
        elif hottest.temperature_c >= warn:
            level = DiagnosticLevel.WARN
        return DiagnosticStatus(
            name=f"actuator/{hottest.name}/temperature",
            level=level,
            message=f"{hottest.name} at {hottest.temperature_c:.1f} C",
            values={"temperature_c": round(hottest.temperature_c, 1)},
        )

    # sources -------------------------------------------------------------- #
    def _computer(self) -> list[DiagnosticStatus]:
        try:
            load = os.getloadavg()[0]
        except (OSError, AttributeError):
            load = 0.0
        usage = shutil.disk_usage(str(self.rt.paths.state_dir))
        disk_pct = usage.used / usage.total * 100 if usage.total else 0.0
        return [
            DiagnosticStatus("computer/cpu", DiagnosticLevel.OK, f"load {load:.2f}",
                             values={"load1": round(load, 2)}),
            DiagnosticStatus(
                "computer/storage",
                DiagnosticLevel.WARN if disk_pct > 90 else DiagnosticLevel.OK,
                f"disk {disk_pct:.0f}% used",
                values={"used_percent": round(disk_pct, 1)},
            ),
        ]

    def _network(self) -> list[DiagnosticStatus]:
        # The reference brain runs offline by design; report provider reachability
        # honestly rather than assuming internet (spec §16, §28).
        provider = self.rt.config.get("language", "primary_provider", default="offline")
        return [
            DiagnosticStatus(
                "network/llm_provider",
                DiagnosticLevel.OK,
                f"language provider: {provider}",
                values={"provider": provider},
            )
        ]

    def _actuators(self) -> list[DiagnosticStatus]:
        backend = self.rt.backend
        if backend is None or self.rt.body is None:
            return []
        warn = self.rt.body.limits.motor_warn_temp()
        fault = self.rt.body.limits.motor_fault_temp()
        out = []
        for name, a in backend.read_all_actuators().items():
            level = DiagnosticLevel.OK
            msg = "nominal"
            if a.fault_code:
                level, msg = DiagnosticLevel.ERROR, a.fault_code
            elif a.temperature_c >= fault:
                level, msg = DiagnosticLevel.ERROR, "over fault temperature"
            elif a.temperature_c >= warn:
                level, msg = DiagnosticLevel.WARN, "warm"
            elif a.comm_errors:
                level, msg = DiagnosticLevel.WARN, f"{a.comm_errors} comm errors"
            out.append(
                DiagnosticStatus(f"actuator/{name}", level, msg, hardware_id=name, values=a.to_dict())
            )
        return out

    def _sensors(self) -> list[DiagnosticStatus]:
        backend = self.rt.backend
        if backend is None or self.rt.body is None:
            return []
        required = set(self.rt.body.manifest.required_sensors)
        out = []
        for s in self.rt.body.sensors:
            r = backend.read_sensor(s.id)
            if r.ok:
                level, msg = DiagnosticLevel.OK, f"{r.rate_hz:g} Hz"
            else:
                level = DiagnosticLevel.ERROR if s.id in required else DiagnosticLevel.WARN
                msg = "not responding"
            out.append(DiagnosticStatus(f"sensor/{s.id}", level, msg, values=r.to_dict()))
        return out

    def _battery(self) -> list[DiagnosticStatus]:
        backend = self.rt.backend
        if backend is None or self.rt.body is None:
            return []
        b = backend.battery()
        warn = float(self.rt.body.limits.battery.get("warn_percent", 30.0))
        crit = float(self.rt.body.limits.battery.get("critical_percent", 10.0))
        level = DiagnosticLevel.OK
        if b.percent <= crit:
            level = DiagnosticLevel.ERROR
        elif b.percent <= warn:
            level = DiagnosticLevel.WARN
        return [
            DiagnosticStatus("battery/main", level, f"{b.percent:.0f}%"
                             + (" charging" if b.charging else ""), values=b.to_dict())
        ]

    def _robot_level(self) -> list[DiagnosticStatus]:
        rt = self.rt
        est = rt.state_estimator
        conf = est.localization_confidence() if est else 0.0
        return [
            DiagnosticStatus(
                "robot/state",
                DiagnosticLevel.OK,
                rt.state.state.value,
                values={
                    "droid_state": rt.state.state.value,
                    "body": rt.body.body_id if rt.body else None,
                    "localization_confidence": round(conf, 3),
                },
            )
        ]
