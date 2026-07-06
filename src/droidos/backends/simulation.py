"""Simulation backend (spec §26).

A lightweight, deterministic model, not a physics engine, sufficient to drive
the whole DroidOS brain end to end without hardware: kinematic integration of
body velocity, a thermal model that heats motors under load and cools them at
rest, a draining battery, a structured camera scene, 2D lidar, and injectable
faults for failure testing. A production build swaps this for a MuJoCo/Gazebo
bridge behind the identical :class:`HardwareBackend` interface.
"""

from __future__ import annotations

import math
import time
from typing import Any

from ..core.models import BodyVelocity
from .base import ActuatorState, BatteryState, HardwareBackend, Pose, SensorReading

AMBIENT_C = 25.0
MOVING_MOTOR_EQUILIBRIUM_C = 62.0
COOL_RATE = 0.04  # per second toward ambient
HEAT_RATE = 0.08  # per second toward equilibrium under load


class SimulationBackend(HardwareBackend):
    kind = "simulation"

    def __init__(self, body: Any) -> None:
        self.body = body
        self._pose = Pose()
        self._power = False
        self._battery = 78.0  # matches the spec's example ("72 percent" ballpark)
        self._charging = False
        self._actuators = list(body.manifest.required_actuators) or ["drive"]
        self._temps: dict[str, float] = {n: AMBIENT_C for n in self._actuators}
        self._positions: dict[str, float] = {n: 0.0 for n in self._actuators}
        self._last_cmd = BodyVelocity()
        self._time_since_cmd = 999.0
        self._faults: dict[str, Any] = {}
        self._connected = False
        self._boot_time = time.time()

    # lifecycle ------------------------------------------------------------ #
    def connect(self) -> None:
        self._connected = True
        # Motor power ALWAYS defaults to disabled on connect (spec §8, §24, §40).
        self._power = False

    def shutdown(self) -> None:
        self._power = False
        self._connected = False

    # inventory ------------------------------------------------------------ #
    def actuator_names(self) -> list[str]:
        return list(self._actuators)

    def sensor_ids(self) -> list[str]:
        return [s.id for s in self.body.sensors]

    # power ---------------------------------------------------------------- #
    def set_power(self, enabled: bool) -> None:
        self._power = bool(enabled)

    def power_enabled(self) -> bool:
        return self._power

    # commands ------------------------------------------------------------- #
    def command_velocity(self, vel: BodyVelocity, dt: float) -> None:
        # Motion has no physical effect while motor power is disabled (spec §24).
        if not self._power:
            return
        vx, vy, wz = self._clamp(vel)
        self._pose.x += (vx * math.cos(self._pose.theta) - vy * math.sin(self._pose.theta)) * dt
        self._pose.y += (vx * math.sin(self._pose.theta) + vy * math.cos(self._pose.theta)) * dt
        self._pose.theta = _wrap(self._pose.theta + wz * dt)
        self._last_cmd = BodyVelocity(vx, vy, wz)
        self._time_since_cmd = 0.0

    def command_joints(self, targets: dict[str, float]) -> None:
        # In the reference simulator the pose is integrated from body velocity;
        # joint targets from the gait policy are tracked so telemetry/diagnostics
        # reflect real per-joint motion (spec §25, §28).
        if not self._power:
            return
        for joint, value in targets.items():
            if joint in self._positions:
                self._positions[joint] = value

    def _clamp(self, vel: BodyVelocity) -> tuple[float, float, float]:
        max_lin = self.body.limits.max_linear() or self.body.capabilities.max_speed() or 0.3
        max_ang = self.body.limits.max_angular() or 0.8
        vx = max(-max_lin, min(max_lin, vel.linear_x))
        vy = max(-max_lin, min(max_lin, vel.linear_y))
        wz = max(-max_ang, min(max_ang, vel.angular_z))
        return vx, vy, wz

    # simulation step ------------------------------------------------------ #
    def step(self, dt: float) -> None:
        self._time_since_cmd += dt
        moving = self._power and self._time_since_cmd < 0.5 and not self._last_cmd.is_zero()
        for name in self._actuators:
            target = MOVING_MOTOR_EQUILIBRIUM_C if moving else AMBIENT_C
            rate = HEAT_RATE if moving else COOL_RATE
            self._temps[name] += (target - self._temps[name]) * min(1.0, rate * dt)
        # apply an injected overheat fault on a specific joint
        of = self._faults.get("motor_overheat")
        if of:
            joint = of.get("joint", self._actuators[0])
            self._temps[joint] = of.get("temp", 88.0)
        # battery drain
        drain = (0.02 if moving else 0.004) * dt
        if self._charging:
            self._battery = min(100.0, self._battery + 0.5 * dt)
        else:
            self._battery = max(0.0, self._battery - drain)

    # reads ---------------------------------------------------------------- #
    def read_actuator(self, name: str) -> ActuatorState:
        temp = self._temps.get(name, AMBIENT_C)
        # an injected overheat fault is reflected immediately, not only after a step
        of = self._faults.get("motor_overheat")
        if of and of.get("joint", self._actuators[0]) == name:
            temp = of.get("temp", 88.0)
        moving = self._power and self._time_since_cmd < 0.5 and not self._last_cmd.is_zero()
        fault = ""
        if temp >= self.body.limits.motor_fault_temp():
            fault = "OVERTEMP"
        comm_errors = 0
        if self._faults.get("comm_error", {}).get("joint") == name:
            comm_errors = self._faults["comm_error"].get("count", 5)
        return ActuatorState(
            name=name,
            position=self._positions.get(name, 0.0),
            velocity=(self._last_cmd.linear_x if moving else 0.0),
            effort=(8.0 if moving else 0.0),
            current_a=(6.0 if moving else 0.2),
            temperature_c=temp,
            controller_temp_c=temp - 8.0,
            voltage=self.body.limits.battery.get("nominal_voltage", 36.0),
            fault_code=fault,
            comm_errors=comm_errors,
        )

    def read_sensor(self, sensor_id: str) -> SensorReading:
        spec = next((s for s in self.body.sensors if s.id == sensor_id), None)
        stype = spec.type if spec else "unknown"
        rate = spec.rate_hz if spec else 0.0
        dropout = self._faults.get("sensor_dropout", {}).get("sensor")
        if dropout == sensor_id or dropout == "*":
            return SensorReading(sensor_id, stype, ok=False, rate_hz=0.0, age_s=5.0, confidence=0.0)
        age = (1.0 / rate) if rate else 0.05
        values: dict[str, Any] = {}
        if stype == "imu":
            values = {"orientation_yaw": round(self._pose.theta, 3), "acc_z": 9.81}
        elif stype == "battery":
            values = self.battery().to_dict()
        elif stype.startswith("lidar"):
            scan = self.lidar_scan() or []
            values = {"ranges": len(scan), "min_range_m": round(min(scan), 2) if scan else None}
        elif stype == "contact":
            values = {"in_contact": True}
        return SensorReading(sensor_id, stype, ok=True, rate_hz=rate, age_s=age, confidence=0.95, values=values)

    def battery(self) -> BatteryState:
        moving = self._power and self._time_since_cmd < 0.5 and not self._last_cmd.is_zero()
        return BatteryState(
            percent=self._battery,
            voltage=self.body.limits.battery.get("nominal_voltage", 36.0) * (0.9 + self._battery / 1000.0),
            charging=self._charging,
            current_a=(4.0 if moving else 0.3),
        )

    def pose(self) -> Pose:
        return Pose(self._pose.x, self._pose.y, self._pose.theta)

    # perception ----------------------------------------------------------- #
    def describe_scene(self) -> dict[str, Any]:
        """Structured observation used by droid-perception (spec §12.6, §38)."""
        camera_ok = self._faults.get("sensor_dropout", {}).get("sensor") not in (
            "camera/front",
            "*",
        )
        if not camera_ok:
            return {"camera_ok": False, "objects": [], "people": [], "confidence": 0.0}
        objects = [
            {"label": "workbench", "distance_m": 1.2},
            {"label": "two monitors", "distance_m": 1.5},
            {"label": "closed door", "distance_m": 4.1},
            {
                "label": "server rack",
                "distance_m": 2.4,
                "indicators": {"green": 8, "amber": 1, "red": 0},
                "open_cabinet_door": True,
            },
        ]
        return {
            "camera_ok": True,
            "objects": objects,
            "people": [{"distance_m": 3.0}],
            "confidence": 0.87,
        }

    def lidar_scan(self) -> list[float] | None:
        if not any(s.type.startswith("lidar") for s in self.body.sensors):
            return None
        if self._faults.get("sensor_dropout", {}).get("sensor") in ("lidar/2d", "*"):
            return None
        # a flat synthetic scan with one nearby obstacle
        return [4.0] * 180 + [1.1] * 10 + [4.0] * 170

    # faults --------------------------------------------------------------- #
    def inject_fault(self, kind: str, **params: Any) -> None:
        self._faults[kind] = params or {"active": True}

    def clear_faults(self) -> None:
        self._faults.clear()

    def set_charging(self, charging: bool) -> None:
        self._charging = charging


def _wrap(angle: float) -> float:
    return (angle + math.pi) % (2 * math.pi) - math.pi
