# DroidOS recovery and rollback

Covers the A/B update model (spec §33) and the recovery system (spec §34).
**Recovery mode never enables actuator power.**

## A/B updates (spec §33)

DroidOS runs from one of two root slots. Updates install into the *inactive* slot,
so a failed update never breaks the running system.

```
Boot | Root A (active) | Root B (inactive) | Persistent data | Recovery
```

Update sequence:

1. Verify the update-bundle signature (RAUC, `/etc/rauc/keyring.pem`).
2. Install into the inactive slot (B).
3. Mark B as the next boot target.
4. Reboot.
5. Run boot-health checks (required services must reach `ACTIVE`; the supervisor
   must settle into `SAFE_IDLE` or better).
6. Mark B successful **only after** those checks pass.
7. If B fails, the bootloader automatically returns to A.

Query state:

```bash
droidctl update status
droid "What version are you running?"
droid "Did the previous update succeed?"
droid "Which system slot is active?"
```

## Recovery mode (spec §34)

If the normal OS cannot boot, the recovery image provides:

- network or USB repair access
- filesystem checks
- log export
- factory-image restoration
- configuration backup / restore
- update rollback
- body-package removal
- model removal
- safe shutdown

Recovery mode brings up **no** robot services and **never** enables motor power.
The safety controller remains in its safe state throughout.

## E-stop recovery

An engaged emergency stop is a latch that survives reboot (as a hardware latch
does). Clearing it is a deliberate recovery step:

```bash
droidctl safety status            # confirm the cause is resolved
droidctl safety reset             # clear the latch
# reboot (or re-run droidctl status) to re-arm; the droid returns to SAFE_IDLE
```

The droid will not re-enable motion until the supervisor re-runs its checks and
finds them all passing.

## Manual rollback

```bash
# from a healthy slot or recovery:
rauc status                       # show slots and which booted
rauc status mark-bad              # mark the current slot bad
rauc status mark-active rootfs.0  # force back to slot A
reboot
```
