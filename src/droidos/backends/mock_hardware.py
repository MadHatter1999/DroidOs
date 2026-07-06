"""Physical-hardware mock backend.

Stands in for a real body reached over CAN-FD / EtherCAT / serial (spec §22). In
the reference build it reuses the simulation kinematics but identifies as
``physical`` so the rest of the brain exercises the physical code path: physical
activation requires a gait policy approved for physical operation (spec §25) and
a healthy safety controller before power is enabled (spec §24).

On a real target this class is replaced by a transport-specific implementation
that translates the standard interfaces into bus frames; the interface is
identical, so no core service changes.
"""

from __future__ import annotations

from typing import Any

from .simulation import SimulationBackend


class MockHardwareBackend(SimulationBackend):
    kind = "physical"

    def __init__(self, body: Any) -> None:
        super().__init__(body)
        self._bus_online = True

    def connect(self) -> None:
        super().connect()
        # A physical bus can fail to come up; modelled so integration tests can
        # exercise the "hardware did not respond" path (spec §39).
        if self._faults.get("bus_offline"):
            self._bus_online = False

    def bus_online(self) -> bool:
        return self._bus_online

    def inject_fault(self, kind: str, **params: Any) -> None:
        super().inject_fault(kind, **params)
        if kind == "bus_offline":
            self._bus_online = False

    def clear_faults(self) -> None:
        super().clear_faults()
        self._bus_online = True
