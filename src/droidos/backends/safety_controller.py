"""Simulated independent safety controller (spec §24).

On real hardware this is a *separate microcontroller* that owns the fastest
control loops and, crucially, the motor-power contactor. It remains authoritative
for electrical motor shutdown and is not reachable by the LLM. If the Linux host
stops communicating, the controller enters its safe state (power removed).

This class models that device so the reference brain can exercise every safety
path. The rest of DroidOS reaches it only through :class:`droid-safety-gateway`
and never bypasses it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SafetyControllerState:
    alive: bool = True
    estop_engaged: bool = False
    power_enabled: bool = False  # motor-power contactor, defaults OFF (spec §8, §40)
    watchdog_ok: bool = True
    faults: list[str] = field(default_factory=list)
    last_host_contact_age_s: float = 0.0

    def movement_permitted(self) -> bool:
        return (
            self.alive
            and self.watchdog_ok
            and not self.estop_engaged
            and not self.faults
            and self.power_enabled
        )

    def healthy(self) -> bool:
        """Healthy = safe to *enable* power (but power may still be off)."""
        return self.alive and self.watchdog_ok and not self.estop_engaged and not self.faults

    def to_dict(self) -> dict[str, Any]:
        return {
            "alive": self.alive,
            "estop_engaged": self.estop_engaged,
            "power_enabled": self.power_enabled,
            "watchdog_ok": self.watchdog_ok,
            "faults": list(self.faults),
            "movement_permitted": self.movement_permitted(),
            "last_host_contact_age_s": round(self.last_host_contact_age_s, 3),
        }


class SimulatedSafetyController:
    def __init__(self, watchdog_timeout_s: float = 1.0) -> None:
        self._alive = True
        self._estop = False
        self._power = False
        self._faults: set[str] = set()
        self._watchdog_timeout = watchdog_timeout_s
        self._last_contact = time.time()
        self._link_up = True  # simulated comms link to the host

    # host liveness -------------------------------------------------------- #
    def heartbeat(self) -> None:
        """Called periodically by the safety gateway to prove the host is alive."""
        self._last_contact = time.time()

    def check_watchdog(self, now: float | None = None) -> None:
        now = now or time.time()
        age = now - self._last_contact
        if not self._link_up or age > self._watchdog_timeout:
            # Safe state: remove motor power if the host is not talking to us.
            self._power = False

    # link simulation (for safety_link_loss fault, spec §26/§39) ----------- #
    def set_link(self, up: bool) -> None:
        self._link_up = up
        if not up:
            self._power = False

    def link_up(self) -> bool:
        return self._link_up

    # emergency stop ------------------------------------------------------- #
    def engage_estop(self, reason: str = "") -> None:
        """Immediate motor-power removal. Never requires confirmation (spec §18)."""
        self._estop = True
        self._power = False
        if reason:
            self._faults.add(f"estop:{reason}")

    def reset_estop(self) -> None:
        """Clear the latch. Callers must have completed the recovery process."""
        self._estop = False
        self._faults = {f for f in self._faults if not f.startswith("estop:")}

    # power contactor ------------------------------------------------------ #
    def request_power_enable(self) -> bool:
        """Enable motor power only if the controller considers itself healthy."""
        if self._estop or not self._alive or self._faults or not self._link_up:
            return False
        self._power = True
        return True

    def disable_power(self) -> None:
        self._power = False

    def power_enabled(self) -> bool:
        return self._power

    # fault reporting ------------------------------------------------------ #
    def report_fault(self, name: str) -> None:
        self._faults.add(name)
        self._power = False  # any hard fault removes power

    def clear_fault(self, name: str) -> None:
        self._faults.discard(name)

    def clear_all_faults(self) -> None:
        self._faults = {f for f in self._faults if f.startswith("estop:")}

    # status --------------------------------------------------------------- #
    def status(self, now: float | None = None) -> SafetyControllerState:
        now = now or time.time()
        self.check_watchdog(now)
        return SafetyControllerState(
            alive=self._alive and self._link_up,
            estop_engaged=self._estop,
            power_enabled=self._power,
            watchdog_ok=(now - self._last_contact) <= self._watchdog_timeout and self._link_up,
            faults=sorted(self._faults),
            last_host_contact_age_s=now - self._last_contact,
        )
