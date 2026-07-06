# DroidOS safety controller firmware

Firmware for the **independent safety microcontroller** (spec §24). This is the
hardware trust root for the DroidOS safety story: it owns the motor-power
contactor and enforces the fast limits. Nothing on the Linux host, and certainly
not the LLM, can override it.

The reference brain models this device in software
(`src/droidos/backends/safety_controller.py`); this firmware is the real thing it
stands in for. It is portable C over a small HAL (`hal_*` functions), so it builds
for STM32, RP2040, AVR, etc. once the HAL is implemented for your board.

## Responsibilities (spec §24)

- Own the **motor-power contactor**; it defaults **open** (power off) at reset.
- Pet the **hardware watchdog**; enter the safe state if the host stops talking.
- Read the physical **emergency-stop** input; latch it.
- Enforce **joint limits** and **thermal limits** reported by the controllers.
- Speak a tiny, framed **serial protocol** to `droid-safety-gateway` on the host.
- On any fault, invalid command, or host silence → **remove motor power**.

## Safe state

Power contactor **open**, a fault code latched, status still reported to the host.
The controller only *permits* power when: not e-stopped, no active faults, the host
heartbeat is fresh, and the host has explicitly requested enable.

## Protocol

Length-prefixed frames over UART (see `src/protocol.h`). Host → controller:
`HEARTBEAT`, `ENABLE_POWER`, `DISABLE_POWER`, `CLEAR_FAULT`, `REPORT_FAULT`.
Controller → host: `STATE` (alive, estop, power, watchdog, faults) at 50 Hz.

## Build

```
# PlatformIO (recommended)
pio run -e safety-stm32
pio run -e safety-stm32 -t upload

# or bare make with your toolchain after implementing hal_*.c
make
```

The host keyring / signing is unrelated to this firmware; the safety controller is
deliberately simple and auditable.
