"""Hardware abstraction layer and backends (spec §22, §24, §26).

Every body supports a *simulated* backend before physical activation, and the
rest of DroidOS operates through the same interfaces regardless of which backend
is active. Only the backend changes.
"""

from .base import (
    ActuatorState,
    BatteryState,
    HardwareBackend,
    Pose,
    SensorReading,
)
from .simulation import SimulationBackend
from .mock_hardware import MockHardwareBackend
from .safety_controller import SimulatedSafetyController, SafetyControllerState

__all__ = [
    "ActuatorState",
    "BatteryState",
    "HardwareBackend",
    "Pose",
    "SensorReading",
    "SimulationBackend",
    "MockHardwareBackend",
    "SimulatedSafetyController",
    "SafetyControllerState",
    "make_backend",
]


def make_backend(body, kind: str, hardware_backend: str | None = None) -> HardwareBackend:
    """Factory: pick the backend implementation for a body selection (spec §20).

    ``kind`` is ``simulation`` or ``physical``. For a physical body,
    ``hardware_backend`` selects the transport: ``canfd`` uses the real CAN-FD
    backend (opt-in, needs python-can + a bus); anything else uses the mock so the
    reference build never touches hardware.
    """
    if kind == "physical":
        if hardware_backend == "canfd":
            from .canfd_hardware import CanFdBackend

            return CanFdBackend(body)
        return MockHardwareBackend(body)
    return SimulationBackend(body)
