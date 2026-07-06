# DroidOS administration guide

How to operate and configure a droid. Humans normally use `droid` (natural
language); scripts and diagnostics use `droidctl` (deterministic, no LLM required).

## Running the reference brain

```bash
python -m pip install -e .        # from the repo root (Python 3.10+)
droidctl status
droid "What can you see?"
droid                             # interactive session
```

Without installing, `python -m droidos.cli.droidctl status` and
`python -m droidos.cli.droid "..."` work identically.

## Filesystem layout (spec §30)

| Path | Purpose |
|------|---------|
| `/etc/droidos/` | configuration (`droidos.yaml`, `body.yaml`, `users.yaml`) |
| `/usr/lib/droidos/bodies/` | installed body packages |
| `/var/lib/droidos/` | mutable state, maps, models, approved memory |
| `/var/log/droidos/` | logs and the audit record (`audit.jsonl`) |
| `/run/droidos/` | runtime sockets |

In a checkout these are redirected under `run-state/` via `DROIDOS_STATE`, and
config is read from `config/`. Override with `DROIDOS_CONFIG`, `DROIDOS_BODIES`,
`DROIDOS_STATE`, `DROIDOS_MODELS`.

## Common tasks

```bash
droidctl status [--json]              # overall state (machine-readable with --json)
droidctl body list                    # installed bodies
droidctl body show                    # active body detail
droidctl body validate                # check the active body package
droidctl body set r2-mk1 --backend simulation   # change body (applies next boot)
droidctl safety status                # safety-controller state
droidctl safety estop                 # engage emergency stop (removes motor power)
droidctl safety reset                 # clear the e-stop latch (recovery)
droidctl diagnostics list [--json]    # every component's health
droidctl services list                # managed-service lifecycle states
droidctl boot-report                  # the last boot sequence result
droidctl task cancel                  # cancel the active task
droidctl update status                # A/B slot / version
```

## Configuring identity and language (spec §15, §19)

Edit `/etc/droidos/droidos.yaml`. Personality controls wording only, it cannot
change safety thresholds, limits, authorization or diagnostics. To use a local
model instead of the offline parser:

```yaml
language:
  primary_provider: local
  fallback_provider: offline        # always keep an offline fallback
  providers:
    local:
      type: llama_cpp
      endpoint: http://127.0.0.1:8080   # OpenAI-compatible server
      model: default
```

Secrets are never placed here; API keys are read from a protected source by
reference (`api_key_ref`), set `DROIDOS_LLM_KEY_<REF>` in the service environment.

## Users and roles (spec §32)

Edit `/etc/droidos/users.yaml`. Roles rank guest < operator < service_technician <
owner. Motion and data-write need operator+; administrative actions (updates, body
change, reboot, shutdown) need owner and explicit confirmation. High-risk actions
require an authenticated role, not merely a recognised voice.

```bash
droid --user owner "install the pending update"     # will still ask to confirm
```

## What always works without the LLM (spec §16)

stop, emergency stop, cancel, status, battery, temperature, help, return to safe
idle, silence, shut down, report faults, report current task. If the model is
unavailable the droid says so and these deterministic commands remain available.
