# DroidOS delivery roadmap

The specification describes an end state. This roadmap breaks it into milestones
that each leave something demonstrable, ordered so risk is retired early. It is
honest about what needs hardware, vendor BSPs or a build farm.

## Where we are

**M0, Reference brain (DONE in this repository).** Runnable, zero-dependency
Python implementation of the interaction, executive, robot-service and
body/hardware-abstraction layers against a simulated backend. `droid`/`droidctl`
CLIs, command broker, tool registry, LLM provider interface with offline fallback,
body loader, capability enforcement, simulated safety controller, diagnostics, task
executive, roles and audit. 48 automated tests pass.

## Next milestones

### M1, ROS 2 node split
Split the in-process services into ROS 2 lifecycle nodes behind
[`interfaces/`](../interfaces/). Bring up `ros2_control`, Nav2 (with the collision
monitor) and the diagnostics stack. Deliverable: the same commands running over
real ROS 2 middleware. *Needs: ROS 2 Lyrical install.*

### M2, Yocto image (Raspberry Pi 5)
Wire up [`meta-droidos`](../meta-droidos/) + [`meta-droidos-rpi`](../meta-droidos-rpi/)
to produce a signed, read-only-rootfs image that boots to `SAFE_IDLE` and runs the
brain. Deliverable: `droidos-rpi5-production.wic`. *Needs: Yocto build host.*

### M3, Independent safety controller (firmware)
Real firmware for the safety microcontroller: heartbeat, e-stop, contactor,
watchdog, joint/thermal limits, safe response to host silence. Replace the
simulated controller behind the same gateway. Deliverable: motor power that
defaults off and is removed on host silence, in hardware. *Needs: MCU + power stage.*

### M4, A/B updates + recovery
RAUC signed bundles, A/B slots, boot-health confirmation, automatic rollback, and
the recovery image. Deliverable: `droidos-update.raucb`, verified rollback. *Needs:
partitioned storage, signing keys.*

### M5, Physical body bring-up (one body)
Implement a real `HardwareBackend` (CAN-FD) for one body, `ros2_control` hardware
plugin, sensor drivers, calibration. Validate in sim first (spec §26), then enable
physical activation gated on an approved gait policy. Deliverable: a body that
rolls/walks under DroidOS. *Needs: a physical robot.*

### M6, Perception & navigation on device
Camera pipeline, object/person detection, mapping/localization backend, named
places, docking. Deliverable: "go to X and inspect Y" on hardware. *Needs: cameras,
optionally lidar.*

### M7, Walking policy (biped)
Train a locomotion policy on a separate machine, export to ONNX with the motion
package metadata (spec §25), run inference on device with the safety envelope.
Deliverable: a validated, versioned gait policy. *Needs: training compute + biped.*

### M8, Jetson Orin target
Bring up [`meta-droidos-tegra`](../meta-droidos-tegra/) with a pinned vendor BSP,
CUDA/TensorRT, local LLM and VLM inference. Deliverable: `droidos-orin-production.img`.
*Needs: pinned NVIDIA BSP + Orin.*

### M9, Local LLM + voice
`llama.cpp` provider over a Unix socket, wake word, ASR, TTS, speaker ID, emergency
command detection. Deliverable: fully spoken interaction, offline. *Needs: models,
audio hardware.*

### M10, Hardening & release
Security threat-model closure (see [SECURITY_THREAT_MODEL.md](SECURITY_THREAT_MODEL.md)),
per-service sandboxing verification, reproducible builds, full deliverable set
(spec §35, §41), documentation completion.

## Dependency notes

- M2 depends on M1 (recipes install the runtime; ROS split clarifies packaging).
- M3 is independent of M1/M2 and can proceed in parallel (firmware track).
- M5 requires M3 (no physical motion without the real safety controller).
- M7 requires M5 + M6 (a biped with sensing).
- M8 can follow M2's pattern once a pinned BSP is chosen.

## Biggest risks

1. **Safety controller firmware (M3)**, the whole safety story depends on it.
   Prototype early on a bench rig.
2. **Vendor BSP pinning (M8)**, Jetson BSP + Yocto + kernel + GPU libs must be one
   tested set; drift breaks builds.
3. **Walking policy sim-to-real (M7)**, budget for iteration; keep the safety
   envelope conservative.
