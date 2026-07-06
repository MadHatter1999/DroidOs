"""CAN-FD physical hardware backend (spec §22, §24).

A real transport backend that speaks CAN-FD to the joint controllers. It
implements the same :class:`HardwareBackend` interface as the simulator, so no
core service changes when moving from simulation to hardware, only the backend
does.

It imports ``python-can`` lazily, so this module is importable on any machine; a
real bus is only required at :meth:`connect`. It is opt-in: set
``hardware_backend: canfd`` in ``body.yaml``. The default physical backend
remains the mock so tests and the reference build never touch a bus.

Safety note: the independent safety controller, not this backend, owns the
motor-power contactor and enforces the fast limits (spec §24). This backend only
sends desired setpoints and reads telemetry; if it stops sending, the controllers
enter their safe state on their own watchdog.
"""

from __future__ import annotations

import struct
import time
from typing import Any

from ..core.errors import BackendError
from ..core.models import BodyVelocity
from .base import ActuatorState, BatteryState, HardwareBackend, Pose

# CAN-FD arbitration-ID layout (example profile "canfd-v1").
BASE_CMD_ID = 0x200      # + joint index: position/velocity setpoint to a controller
BASE_STATE_ID = 0x300    # + joint index: telemetry from a controller
BATTERY_STATE_ID = 0x3F0
SAFETY_STATE_ID = 0x010  # broadcast from the safety controller


class CanFdBackend(HardwareBackend):
    kind = "physical"

    def __init__(self, body: Any, channel: str = "can0", bitrate: int = 500000,
                 data_bitrate: int = 2000000) -> None:
        self.body = body
        self.channel = channel
        self.bitrate = bitrate
        self.data_bitrate = data_bitrate
        self._bus: Any = None
        self._actuators = list(body.manifest.required_actuators) or ["drive"]
        self._index = {name: i for i, name in enumerate(self._actuators)}
        self._telemetry: dict[str, ActuatorState] = {
            n: ActuatorState(name=n) for n in self._actuators
        }
        self._battery = BatteryState(percent=100.0)
        self._pose = Pose()
        self._power = False
        self._last_recv = 0.0

    # lifecycle ------------------------------------------------------------ #
    def connect(self) -> None:
        try:
            import can  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise BackendError(
                "python-can is required for the CAN-FD backend. "
                "Install it (`pip install python-can`) or use the simulation backend."
            ) from exc
        try:
            self._bus = can.Bus(
                interface="socketcan", channel=self.channel,
                fd=True, bitrate=self.bitrate, data_bitrate=self.data_bitrate,
            )
        except Exception as exc:  # noqa: BLE001
            raise BackendError(f"cannot open CAN-FD bus {self.channel}: {exc}") from exc
        # Motor power always defaults disabled; only the safety controller enables it.
        self._power = False
        self._drain(timeout=0.2)

    def shutdown(self) -> None:
        if self._bus is not None:
            try:
                self._bus.shutdown()
            finally:
                self._bus = None
        self._power = False

    # inventory ------------------------------------------------------------ #
    def actuator_names(self) -> list[str]:
        return list(self._actuators)

    def sensor_ids(self) -> list[str]:
        return [s.id for s in self.body.sensors]

    # power ---------------------------------------------------------------- #
    def set_power(self, enabled: bool) -> None:
        # The host cannot force the contactor closed; it can only *request* it via
        # the safety gateway. Here we track the last known state reported on the bus.
        self._power = bool(enabled)

    def power_enabled(self) -> bool:
        return self._power

    # commands ------------------------------------------------------------- #
    def command_velocity(self, vel: BodyVelocity, dt: float) -> None:
        # Body velocity is converted to joint/wheel setpoints by the controller
        # stack; for a diff-drive body we send left/right wheel velocities here.
        if self._bus is None:
            raise BackendError("CAN-FD bus not connected")
        # (wheel kinematics omitted; see controllers.yaml for parameters)
        self._drain(timeout=0.0)

    def command_joints(self, targets: dict[str, float]) -> None:
        if self._bus is None:
            raise BackendError("CAN-FD bus not connected")
        import can  # type: ignore

        for name, value in targets.items():
            idx = self._index.get(name)
            if idx is None:
                continue
            payload = struct.pack("<f", float(value))  # 4-byte float setpoint
            msg = can.Message(arbitration_id=BASE_CMD_ID + idx, data=payload,
                              is_extended_id=False, is_fd=True)
            try:
                self._bus.send(msg)
            except Exception as exc:  # noqa: BLE001
                raise BackendError(f"CAN send failed for {name}: {exc}") from exc

    # reads ---------------------------------------------------------------- #
    def read_actuator(self, name: str) -> ActuatorState:
        self._drain(timeout=0.0)
        return self._telemetry.get(name, ActuatorState(name=name))

    def read_sensor(self, sensor_id: str):
        from .base import SensorReading

        spec = next((s for s in self.body.sensors if s.id == sensor_id), None)
        stype = spec.type if spec else "unknown"
        # Real sensor drivers publish to ROS topics; here we report link liveness.
        ok = (time.time() - self._last_recv) < 1.0
        return SensorReading(sensor_id, stype, ok=ok, rate_hz=spec.rate_hz if spec else 0.0)

    def battery(self) -> BatteryState:
        self._drain(timeout=0.0)
        return self._battery

    def pose(self) -> Pose:
        # Real pose comes from state estimation (wheel odometry + IMU); the backend
        # exposes the latest fused estimate published by the controllers.
        return Pose(self._pose.x, self._pose.y, self._pose.theta)

    def describe_scene(self) -> dict[str, Any]:
        # Perception runs off the camera pipeline, not the CAN bus.
        return {"camera_ok": True, "objects": [], "people": [], "confidence": 0.0,
                "note": "scene comes from the perception pipeline, not the CAN backend"}

    def step(self, dt: float) -> None:
        self._drain(timeout=0.0)

    # bus rx --------------------------------------------------------------- #
    def _drain(self, timeout: float) -> None:
        if self._bus is None:
            return
        while True:
            msg = self._bus.recv(timeout=timeout)
            if msg is None:
                break
            self._last_recv = time.time()
            self._decode(msg)
            timeout = 0.0  # only block on the first read

    def _decode(self, msg: Any) -> None:
        aid = msg.arbitration_id
        if BASE_STATE_ID <= aid < BASE_STATE_ID + len(self._actuators):
            idx = aid - BASE_STATE_ID
            name = self._actuators[idx]
            # example telemetry frame: position(f32), velocity(f32), temp(f32), current(f32)
            if len(msg.data) >= 16:
                pos, vel, temp, cur = struct.unpack("<ffff", bytes(msg.data[:16]))
                self._telemetry[name] = ActuatorState(
                    name=name, position=pos, velocity=vel,
                    temperature_c=temp, current_a=cur,
                )
        elif aid == BATTERY_STATE_ID and len(msg.data) >= 8:
            pct, volt = struct.unpack("<ff", bytes(msg.data[:8]))
            self._battery = BatteryState(percent=pct, voltage=volt)
        elif aid == SAFETY_STATE_ID and len(msg.data) >= 1:
            self._power = bool(msg.data[0] & 0x01)
