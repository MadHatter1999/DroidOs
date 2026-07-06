# DroidOS architecture (reference implementation)

This document maps the runnable reference brain in [`src/droidos/`](../src/droidos/)
onto the specification ([SPEC.md](SPEC.md)). The full end-state system spans an
embedded Linux distribution; the reference brain implements the top four
architectural layers in software against a simulated hardware/safety backend, and
the OS layer is provided as Yocto build scaffolding.

## Layer map (spec §4)

| Spec layer | Reference modules |
|-----------|-------------------|
| Droid interaction | [`language/`](../src/droidos/language/), providers, offline parser, broker, tools, auth, personality, service |
| Droid executive | [`executive/`](../src/droidos/executive/), tasks, behaviour trees, executive |
| Robot services | [`services/`](../src/droidos/services/), supervisor, safety gateway, diagnostics, perception, world model, navigation, motion, state estimator, memory |
| Body / HW abstraction | [`body/`](../src/droidos/body/) + [`backends/`](../src/droidos/backends/), manifest, capabilities, loader; HAL, simulation, physical mock, safety controller |
| DroidOS Linux | [`meta-droidos*`](../meta-droidos/), [`systemd/`](../systemd/), [`config/`](../config/), Yocto scaffolding (build-host gated) |

## Request flow (spec §14, §38)

```
English (droid CLI / voice)
  -> LanguageService.process
     -> ProviderChain.generate_structured_intent   (LLM or offline parser)
     -> CommandBroker.validate                      (register/auth/capability/
                                                      destination/motion/confirm)
     -> Executive.run_intent                        (behaviour tree over services)
        -> SafetyGateway.request_motion_permission  (independent controller)
        -> Motion / Navigation / Perception / ...
     -> Renderer                                    (facts -> English)
```

The broker is the single gate; the LLM only ever *proposes*. Basic commands work
with no LLM via the offline parser (spec §16), and the safety controller is never
reachable by the language layer (spec §24).

## Spec section → code index

| Spec | Where |
|------|-------|
| §8 boot sequence | `services/supervisor.py::Supervisor.boot` |
| §9 state machine | `core/states.py` |
| §11 managed lifecycle | `services/lifecycle.py` |
| §12.1 supervisor | `services/supervisor.py` |
| §12.2 safety gateway | `services/safety_gateway.py` |
| §12.3 body manager | `body/loader.py` |
| §12.4 hardware | `services/hardware.py` |
| §12.5-12.14 services | `services/*.py` |
| §12.12 voice | `services/voice.py` (+ `voice_engines.py`) |
| §12.15 update | `services/update.py` |
| §14 command broker | `language/broker.py` |
| §15 LLM providers | `language/providers.py` |
| §16 offline operation | `language/offline_parser.py` |
| §17 tool registry | `language/tools.py` |
| §18 confirmation rules | `language/broker.py::_needs_confirmation` |
| §19 personality | `language/personality.py` |
| §20-21 body package / capabilities | `bodies/`, `body/manifest.py`, `body/capabilities.py` |
| §22 hardware abstraction | `backends/base.py` (physical: `backends/canfd_hardware.py`) |
| §23-24 locomotion / independent control | `services/motion.py`, `backends/safety_controller.py`, `firmware/safety-controller/` |
| §25 walking policy validation + inference | `body/loader.py::_static_validate`, `gait/policy.py` |
| ROS 2 bridge (roadmap M1) | `ros2/droid_nodes/`, `ros2/droid_bringup/` |
| §26 simulation | `backends/simulation.py` |
| §28 diagnostics | `services/diagnostics.py` |
| §29 audit log | `core/logging.py` |
| §32 users / roles | `language/auth.py`, `config/users.yaml` |
| §37 interfaces | `interfaces/droid_interfaces/` |
| §38 example flow | `executive/executive.py::_h_inspect` |
| §39 failure behaviour | `executive/executive.py::_drive_to`, `services/perception.py` |

## Process model

The specification describes independent ROS 2 nodes. The reference brain runs the
same responsibilities as objects in a single process, communicating over an
in-process `EventBus` that mirrors the topic model, so the logic and the safety
gates are faithful and fully testable without a ROS install. A production build
splits these into ROS 2 lifecycle nodes behind the interfaces in
[`interfaces/`](../interfaces/); the boundaries are already drawn along those lines.
