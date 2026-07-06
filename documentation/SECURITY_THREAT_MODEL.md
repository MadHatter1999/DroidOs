# DroidOS security threat model

Scope: the DroidOS brain and its boundaries with the LLM, the network, users and
the independent safety controller. This is a living document; it closes out at
milestone M10 (see [ROADMAP.md](ROADMAP.md)).

## Assets

| Asset | Why it matters |
|-------|----------------|
| Motor power / physical motion | A droid that moves can injure people or itself |
| Safety controller + its config | Authoritative for motor shutdown (spec §24) |
| Signing keys (image, update, body) | Trust anchor for what runs |
| User memory & personal data | Privacy (spec §12.13) |
| Audit log | Accountability (spec §29) |
| Network credentials / LLM keys | Lateral movement, data exfiltration |
| Body & gait policy files | Bad ones cause unsafe motion (spec §25) |

## Trust boundaries

1. **LLM ↔ everything else.** The model is treated as *untrusted input*. It may
   only emit a proposed intent naming a registered tool; it never gets a shell,
   device access, or the ability to bypass the broker (spec §17). Enforced in
   `language/broker.py` and `language/tools.py`.
2. **Language service ↔ hardware.** `droid-language` runs sandboxed with
   `PrivateDevices=true`, no motor/kernel/storage/key access
   (`systemd/droid-language.service`, spec §31).
3. **Host ↔ safety controller.** The controller is a separate device; the host
   only sends a heartbeat and requests. Host silence → controller removes power
   (`backends/safety_controller.py::check_watchdog`).
4. **Remote ↔ droid.** Remote access is disabled unless configured (spec §40);
   `IPAddressDeny=any` on the language service, sysctl `ip_forward=0`.

## Threats and mitigations (STRIDE)

### Spoofing / authorization
- *Threat:* a familiar voice issues a high-risk command.
  *Mitigation:* high-risk actions require an authenticated role, not recognition
  (spec §32); `Authorizer` + tool `min_role_rank`. Guests cannot move the droid.

### Tampering
- *Threat:* modified OS/body/gait/update artifacts.
  *Mitigation:* signed, read-only rootfs; signed RAUC bundles; signed body packages
  verified before activation; gait-policy checksum + body-revision + approval checks
  (`body/loader.py`). Kernel module signing enforced (`droidos-hardening.cfg`).
- *Threat:* editing safety limits via conversation/memory.
  *Mitigation:* safety rules and hardware limits are **not** editable memory
  (`services/memory.py` refuses `safety`/`limit`/`authorization`/`capability`
  categories); personality cannot alter thresholds (`language/personality.py`).

### Repudiation
- *Threat:* disputed physical actions.
  *Mitigation:* every command, approval decision, tool call, task outcome and
  safety event is written to an append-only audit record with user, original text,
  parsed intent and result (`core/logging.py`, spec §29). Private LLM reasoning is
  deliberately not required in the record.

### Information disclosure
- *Threat:* LLM leaks secrets or a service reads other users' data.
  *Mitigation:* secrets never appear in manifests or the LLM context; API keys read
  by reference from a protected source (`language/providers.py`). Per-service
  accounts + `ProtectHome`/`ProtectSystem=strict` (spec §31).

### Denial of service
- *Threat:* a crashed/hung service or LLM stalls the droid.
  *Mitigation:* managed lifecycle with supervised restart (`services/lifecycle.py`,
  `supervisor.restart_failed`); offline parser keeps essential commands working when
  the LLM is down (spec §16); hardware watchdog + safety watchdog remove power on
  host silence.

### Elevation of privilege
- *Threat:* language service escalates to motor/root control.
  *Mitigation:* `NoNewPrivileges`, seccomp `SystemCallFilter=@system-service`,
  `RestrictNamespaces`, capability drop, `PrivateDevices` (spec §31). The command
  broker is the only path to actuation and it cannot be bypassed by the LLM.

## Safety-specific invariants (must always hold)

1. Motor power defaults **disabled**; boot does not enable movement (spec §8, §40).
   Verified by `tests/test_safety.py::test_power_defaults_off_at_boot`.
2. Physical motion requires a healthy **independent** safety controller (spec §24).
3. **Emergency stop** works without Linux/LLM and never requires confirmation
   (spec §18); it removes power immediately and latches across reboot.
4. Communication failure with the safety controller **disables movement**
   (`test_safety_link_loss_inhibits_motion`).
5. The LLM cannot override safety, limits or authorization.
6. Invalid body or gait-policy files **prevent activation** (spec §40).
7. Every physical command is **audited** (`test_audit_records_written`).

## Residual risks / open items (for M10)

- Reproducible builds and SBOM generation not yet wired.
- Secure boot chain (verified boot ROM → bootloader → kernel) is board-specific and
  documented but not implemented in this reference.
- Rate-limiting / anomaly detection on the command stream is future work.
- Physical safety-controller firmware (M3) is the trust root for invariants 2-4 and
  must undergo its own dedicated review.
