"""``droid-hardware`` (spec §12.4).

Presents the body's hardware as named abstractions, motors, encoders, IMUs,
cameras, foot-pressure sensors, lidar, bump sensors, battery, fans, temperature
sensors, speakers, microphones and lights, over the active backend. Actuators and
sensors delegate to the backend's standard interfaces; auxiliary devices (cooling
fans and status lights) that the physics model does not carry are modelled here so
the rest of the system has a single hardware surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core.models import DiagnosticLevel, DiagnosticStatus
from .lifecycle import ManagedService

if TYPE_CHECKING:
    from ..system import Runtime


class Hardware(ManagedService):
    requires = ("safety_gateway",)

    def __init__(self, rt: "Runtime") -> None:
        super().__init__("hardware", rt)
        self.fan_speed = 0.0  # 0.0 - 1.0
        self.lights: dict[str, bool] = {"status": True, "signal": False}

    # inventory ------------------------------------------------------------ #
    def inventory(self) -> dict[str, Any]:
        backend = self.rt.backend
        body = self.rt.body
        sensors_by_type: dict[str, list[str]] = {}
        for s in (body.sensors if body else []):
            sensors_by_type.setdefault(s.type, []).append(s.id)
        return {
            "actuators": backend.actuator_names() if backend else [],
            "sensors": sensors_by_type,
            "battery": bool(body and any(s.type == "battery" for s in body.sensors)),
            "fans": ["main"],
            "lights": list(self.lights.keys()),
            "speakers": ["main"],
            "microphones": [s.id for s in (body.sensors if body else []) if s.type == "microphone"],
        }

    # passthrough reads ---------------------------------------------------- #
    def actuator(self, name: str):
        return self.rt.backend.read_actuator(name)

    def sensor(self, sensor_id: str):
        return self.rt.backend.read_sensor(sensor_id)

    def battery(self):
        return self.rt.backend.battery()

    # auxiliary devices ---------------------------------------------------- #
    def set_fan(self, speed: float) -> None:
        self.fan_speed = max(0.0, min(1.0, speed))

    def set_light(self, name: str, on: bool) -> None:
        self.lights[name] = bool(on)

    def _auto_cooling(self) -> None:
        """Simple thermostatic fan control from the hottest actuator (spec §12.4)."""
        backend = self.rt.backend
        body = self.rt.body
        if backend is None or body is None:
            return
        acts = backend.read_all_actuators()
        if not acts:
            return
        hottest = max(a.temperature_c for a in acts.values())
        warn = body.limits.motor_warn_temp()
        # ramp fan from off (well below warn) to full (at warn)
        self.fan_speed = max(0.0, min(1.0, (hottest - (warn - 20)) / 20.0))

    # diagnostics ---------------------------------------------------------- #
    def diagnostics(self) -> list[DiagnosticStatus]:
        self._auto_cooling()
        inv = self.inventory()
        return [
            DiagnosticStatus(
                name="hardware/inventory",
                level=DiagnosticLevel.OK,
                message=f"{len(inv['actuators'])} actuators, "
                        f"{sum(len(v) for v in inv['sensors'].values())} sensors",
                values=inv,
            ),
            DiagnosticStatus(
                name="hardware/cooling",
                level=DiagnosticLevel.OK,
                message=f"fan at {self.fan_speed * 100:.0f}%",
                values={"fan_speed": round(self.fan_speed, 2), "lights": self.lights},
            ),
        ]
