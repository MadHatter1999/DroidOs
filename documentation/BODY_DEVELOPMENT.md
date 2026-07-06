# Body development guide

DroidOS is body-independent (spec §20). Adding a robot means adding a **body
package** and a **hardware backend**, not changing the brain. This guide walks
through authoring a new body.

## Anatomy of a body package

A body package is a directory under `bodies/<body_id>/` (installed to
`/usr/lib/droidos/bodies/<body_id>/`) containing:

```
manifest.yaml          # identity, locomotion type, required hardware, gait policy, signature
robot.urdf.xacro       # kinematic description + <ros2_control> block
controllers.yaml       # ros2_control controller configuration
sensors.yaml           # sensor manifest (id/type/topic/rate/required)
limits.yaml            # battery, thermal, velocity, payload, per-joint limits
capabilities.yaml      # published capabilities (spec §21)
simulation.yaml        # simulated backend + fault-injection config
diagnostic-rules.yaml  # thresholds for deriving OK/WARN/ERROR
hardware-plugin.so     # (production) ros2_control hardware plugin
locomotion-plugin.so   # (production) controller plugin
gait-policy.onnx       # (walking bodies) trained locomotion policy
```

Study the two worked examples: [`bodies/ig-mk1/`](../bodies/ig-mk1/) (biped) and
[`bodies/r2-mk1/`](../bodies/r2-mk1/) (wheeled).

## Step by step

1. **Pick a `body_id` and `locomotion_type`** (`biped`, `differential`, `omni`,
   `tracked`, `stationary`, `manipulator`). The motion service selects a controller
   from this.
2. **Declare hardware.** List `required_sensors` and `required_actuators` in the
   manifest; every required sensor must also appear in `sensors.yaml`, or the body
   is rejected. Missing required hardware at boot → `MOTION_INHIBITED`.
3. **Publish capabilities.** Set `walk`/`roll`/`stairs`/… truthfully. Use
   `experimental` for not-yet-safe modes, the brain treats experimental as *not
   supported* for permission purposes but will say so honestly.
4. **Set limits.** Battery motion minimum, thermal warn/fault, velocity caps,
   per-joint limits. These are enforced independently of the LLM.
5. **Provide a simulation model** so the body can be validated before any physical
   activation (spec §26). Every body must pass in simulation first.
6. **(Walking bodies) provide a gait policy** with checksum, supported body
   revision, observation/action definitions and `approved_for_physical`. The brain
   rejects a mismatched, unchecksummed, or unapproved policy (spec §25).
7. **Sign the package.** Production activation verifies the signature against the
   fleet signing key (spec §20, §40). A placeholder signature is flagged and blocks
   physical activation.

## Validate

```bash
DROIDOS_BODIES=./bodies droidctl body list
droidctl body set <body_id> --backend simulation
droidctl body validate            # lists issues; FATAL issues block activation
droid "what can you do"           # capabilities-aware
```

Run the body through the reference brain and the test harness before touching
hardware. `droidctl body validate` reports:
- required sensor not declared → **FATAL**
- capability/locomotion mismatch (e.g. biped with `walk: false`) → **FATAL**
- biped gait policy missing/mismatched/unapproved → **FATAL**
- placeholder signature → **warning** (blocks physical, allows simulation)

## Writing the hardware backend

For simulation you get the built-in [`SimulationBackend`](../src/droidos/backends/simulation.py)
for free. For physical hardware, implement the
[`HardwareBackend`](../src/droidos/backends/base.py) interface (or, in production,
a `ros2_control` hardware plugin) translating the standard interfaces (position,
velocity, effort, current, temperature, battery) into your bus frames (CAN-FD,
EtherCAT, serial). Because every service talks to the standard interface, no core
code changes.
