# DroidOS

**A Linux-based operating system and control brain for intelligent physical droids.**

DroidOS is the common brain for a family of physical droids (biped, wheeled, tracked,
utility, stationary). The same core software, identity, language interface, LLM
integration, memory, diagnostics, mapping, task planning, permissions, safety
enforcement, runs across interchangeable bodies. Only the *body package* and
*hardware backend* change between robots.

The primary user interface is **spoken and typed English**:

```bash
droid "What can you see?"
droid "Walk to the workshop and inspect the server rack."
droidctl status --json
```

---

## What is in this repository

DroidOS spans two very different scales, and this repository is honest about which
parts are runnable software and which parts are hardware/build-farm gated.

| Area | Directory | Status |
|------|-----------|--------|
| **Reference brain runtime** (Python), the runnable DroidOS control stack | [`src/droidos/`](src/droidos/) | **Runnable today** |
| Walking-policy inference runtime (§25) | [`src/droidos/gait/`](src/droidos/gait/) | **Runnable today** |
| Example body packages (biped + wheeled) | [`bodies/`](bodies/) | Runnable in sim |
| Public ROS-style interfaces (msg/srv/action) | [`interfaces/`](interfaces/) | Definitions |
| ROS 2 node bridge (roadmap M1) | [`ros2/`](ros2/) | Source (needs ROS 2) |
| Physical CAN-FD backend (§22) | [`src/droidos/backends/canfd_hardware.py`](src/droidos/backends/canfd_hardware.py) | Source (needs bus) |
| Safety-controller firmware (§24) | [`firmware/`](firmware/) | Embedded C source |
| Simulation backend config | [`simulation/`](simulation/) | Runnable (mock) |
| Automated test suite (60 tests) | [`tests/`](tests/) | Runnable today |
| Yocto distribution layer | [`meta-droidos/`](meta-droidos/) | Build scaffolding |
| Raspberry Pi 5 board layer | [`meta-droidos-rpi/`](meta-droidos-rpi/) | Build scaffolding |
| NVIDIA Jetson Orin board layer | [`meta-droidos-tegra/`](meta-droidos-tegra/) | Build scaffolding |
| systemd service units | [`systemd/`](systemd/) | Deployment files |
| System configuration | [`config/`](config/) | Config files |
| Documentation set | [`documentation/`](documentation/) | Docs |

### Runnable vs. hardware-gated

The **reference brain** (`src/droidos/`) is a complete, testable Python
implementation of the DroidOS control architecture: the `droid`/`droidctl`
CLIs, command broker, tool registry, LLM provider interface with an offline
deterministic fallback, body-package loader, capability enforcement, simulated
safety controller, diagnostics, perception/navigation/motion services, the task
executive, roles/authorization and the audit log. It runs entirely in
simulation with **no robot, no GPU and no network** required.

The **OS-build scaffolding** (`meta-droidos*`, `systemd/`, `config/`) is real
Yocto/systemd content, but producing signed bootable images and running kernel,
ROS 2 C++ nodes and physical motor/safety controllers requires a Yocto build
host, vendor BSPs and target hardware. Those steps are documented, not executed
here. See [`documentation/ROADMAP.md`](documentation/ROADMAP.md).

---

## Quick start (reference brain)

Requires Python 3.10+. No third-party packages are required for the core.

```bash
# From the repository root
python -m pip install -e .

# Deterministic administrative interface
droidctl status
droidctl status --json
droidctl body show
droidctl safety status
droidctl diagnostics list

# Natural-language interface (offline deterministic parser by default)
droid "What is your current status?"
droid "What can you see?"
droid ask "Why is your movement disabled?"
droid do "Walk to the workshop."

# Interactive session
droid
```

Without installing, you can run the same entry points directly:

```bash
python -m droidos.cli.droidctl status
python -m droidos.cli.droid "What can you see?"
```

Run the tests:

```bash
python -m pytest -q          # if pytest is installed
python tests/run_all.py      # zero-dependency test runner
```

---

## Architecture (five layers, spec §4)

```text
┌─────────────────────────────────────────────────────┐
│ DROID INTERACTION   English, voice, personality, LLM │
├─────────────────────────────────────────────────────┤
│ DROID EXECUTIVE     Tasks, permissions, tools, trees │
├─────────────────────────────────────────────────────┤
│ ROBOT SERVICES      Vision, mapping, nav, diagnostics│
├─────────────────────────────────────────────────────┤
│ BODY / HW ABSTRACT. Body profiles, locomotion, HAL   │
├─────────────────────────────────────────────────────┤
│ DROIDOS LINUX       Kernel, systemd, security, update│
└─────────────────────────────────────────────────────┘
```

The reference brain implements the top four layers in software against a
simulated hardware/safety backend. The bottom layer is provided as Yocto
build scaffolding.

## Safety invariants (non-negotiable, spec §16, §24, §40)

- Motor power **defaults to disabled**. A successful Linux boot does **not** enable movement.
- Physical motion requires a healthy **independent safety controller** (modelled by
  `droid-safety-gateway`; real deployments use a separate microcontroller).
- **Emergency stop** and basic commands (stop, status, cancel, return, shutdown) work
  **without the LLM**.
- The LLM can only request **registered tools**, never an arbitrary shell.
- The LLM **cannot override safety**, physical limits or authorization.
- Invalid body or gait-policy files **prevent activation**.
- Every physical command is **audited**.

## License

Apache-2.0. See [LICENSE](LICENSE).

## Documentation

- [HOWTO.md](documentation/HOWTO.md), practical guide: install, run, and drive the droid
- [ROADMAP.md](documentation/ROADMAP.md), phased delivery plan from sim-only CLI to signed OS images
- [ADMINISTRATION.md](documentation/ADMINISTRATION.md), operating and configuring a droid
- [BODY_DEVELOPMENT.md](documentation/BODY_DEVELOPMENT.md), authoring a new body package
- [RECOVERY.md](documentation/RECOVERY.md), recovery mode and rollback
- [SECURITY_THREAT_MODEL.md](documentation/SECURITY_THREAT_MODEL.md), threat model and mitigations
- [ARCHITECTURE.md](documentation/ARCHITECTURE.md), how the reference brain maps to the spec
