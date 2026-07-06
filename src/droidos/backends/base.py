"""The hardware backend interface (spec §22).

``ros2_control`` on a real target loads hardware components (actuators, sensors,
systems) as plugins so controllers work through standard interfaces rather than
being tied to one device brand. The reference brain models the same contract:
the backend exposes standard state interfaces (position, velocity, effort,
current, temperature, encoder, battery, …) and accepts standard commands, while
hiding the transport (CAN-FD, EtherCAT, serial, simulation).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from ..core.models import BodyVelocity


@dataclass
class ActuatorState:
    name: str
    position: float = 0.0
    velocity: float = 0.0
    effort: float = 0.0
    current_a: float = 0.0
    temperature_c: float = 25.0
    controller_temp_c: float = 25.0
    voltage: float = 0.0
    limit_state: str = "ok"  # ok | min | max
    fault_code: str = ""
    comm_errors: int = 0
    encoder_ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "position": round(self.position, 4),
            "velocity": round(self.velocity, 4),
            "effort": round(self.effort, 3),
            "current_a": round(self.current_a, 3),
            "temperature_c": round(self.temperature_c, 2),
            "controller_temp_c": round(self.controller_temp_c, 2),
            "limit_state": self.limit_state,
            "fault_code": self.fault_code,
            "comm_errors": self.comm_errors,
            "encoder_ok": self.encoder_ok,
        }


@dataclass
class SensorReading:
    sensor_id: str
    type: str
    ok: bool = True
    rate_hz: float = 0.0
    age_s: float = 0.0
    confidence: float = 1.0
    values: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "type": self.type,
            "ok": self.ok,
            "rate_hz": self.rate_hz,
            "age_s": round(self.age_s, 3),
            "confidence": round(self.confidence, 3),
            "values": self.values,
        }


@dataclass
class BatteryState:
    percent: float = 100.0
    voltage: float = 0.0
    charging: bool = False
    current_a: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "percent": round(self.percent, 1),
            "voltage": round(self.voltage, 2),
            "charging": self.charging,
            "current_a": round(self.current_a, 2),
        }


@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {"x": round(self.x, 3), "y": round(self.y, 3), "theta": round(self.theta, 4)}


class HardwareBackend(abc.ABC):
    """Abstract standard hardware interface shared by simulation and physical."""

    kind: str = "abstract"

    @abc.abstractmethod
    def connect(self) -> None:
        """Establish communication with the body (or start the simulator)."""

    @abc.abstractmethod
    def shutdown(self) -> None:
        ...

    @abc.abstractmethod
    def actuator_names(self) -> list[str]:
        ...

    @abc.abstractmethod
    def sensor_ids(self) -> list[str]:
        ...

    @abc.abstractmethod
    def read_actuator(self, name: str) -> ActuatorState:
        ...

    def read_all_actuators(self) -> dict[str, ActuatorState]:
        return {n: self.read_actuator(n) for n in self.actuator_names()}

    @abc.abstractmethod
    def read_sensor(self, sensor_id: str) -> SensorReading:
        ...

    @abc.abstractmethod
    def battery(self) -> BatteryState:
        ...

    @abc.abstractmethod
    def pose(self) -> Pose:
        ...

    # motor power contactor. Only the safety controller should enable this; the
    # backend enforces that motion has no effect while power is disabled (spec §24).
    @abc.abstractmethod
    def set_power(self, enabled: bool) -> None:
        ...

    @abc.abstractmethod
    def power_enabled(self) -> bool:
        ...

    @abc.abstractmethod
    def command_velocity(self, vel: BodyVelocity, dt: float) -> None:
        ...

    def command_joints(self, targets: dict[str, float]) -> None:
        """Apply joint-position targets from a gait controller (spec §23, §25).

        Optional: wheeled bodies drive through :meth:`command_velocity` only.
        The independent joint controllers enforce the actual limits (spec §24)."""
        return None

    @abc.abstractmethod
    def describe_scene(self) -> dict[str, Any]:
        """Return a structured observation from the primary camera (spec §12.6)."""

    def lidar_scan(self) -> list[float] | None:
        return None

    # fault injection for failure testing (spec §26)
    def inject_fault(self, kind: str, **params: Any) -> None:
        raise NotImplementedError(f"backend {self.kind} does not support fault injection")

    def clear_faults(self) -> None:
        pass

    @abc.abstractmethod
    def step(self, dt: float) -> None:
        """Advance internal thermal/battery/kinematic models by *dt* seconds."""
