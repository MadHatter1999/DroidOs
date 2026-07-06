# DroidOS 1.0

## Complete product vision and engineering specification

**Project:** DroidOS
**Purpose:** A complete Linux-based operating system for intelligent physical droids
**Primary user interface:** Spoken and typed English
**Supported body types:** Biped, wheeled, tracked, utility, stationary, and future custom bodies
**Initial computing targets:** Raspberry Pi 5 and NVIDIA Jetson Orin family
**Primary robotics framework:** ROS 2
**Primary operating-system build framework:** Yocto Project

---

# 1. Purpose of this document

This document describes the complete intended DroidOS system.

It is not a temporary demonstration, proof of concept, or simplified prototype specification. It describes what must exist for DroidOS to be considered a complete, usable robot operating system.

DroidOS must provide:

* A bootable Linux operating system
* A natural-language interface
* An LLM integration layer
* Voice interaction
* Camera and sensor processing
* Mapping and navigation
* Body-independent task execution
* Walking or wheeled locomotion integration
* Diagnostics
* Safety enforcement
* Software updates and recovery
* Support for multiple interchangeable droid bodies
* Simulation and physical-hardware backends
* A secure command architecture
* Offline operation for essential functions

This is an end-state specification. It does not claim the software has already been written.

---

# 2. The central vision

DroidOS is the common brain for a family of physical droids.

The software must not be permanently tied to one robot design. A B1-style battle droid, an assassin-droid-style biped, a Gonk-style utility droid, and an R2/R3-style astromech must all be capable of using the same core operating system.

Each body may have different:

* Motors
* Sensors
* Dimensions
* Joint arrangements
* Locomotion methods
* Power systems
* Physical capabilities
* Safety limits

However, they should share the same:

* Identity system
* Personality
* English-language interface
* LLM integration
* Voice
* Memory
* Diagnostics
* Mapping
* Task planning
* Permission system
* Logging
* Update system
* User accounts
* Networking
* Security architecture

The completed system should allow a user to move the brain between compatible bodies without rewriting the core software.

Only the body description, hardware drivers, controller configuration, sensor configuration, and locomotion implementation should change.

---

# 3. Intended user experience

A powered DroidOS machine should feel like interacting with a droid rather than administering a generic Linux computer.

The user must be able to speak naturally:

> What can you see?

> Walk to the workshop.

> Inspect the server rack and tell me whether any warning lights are active.

> Why did you stop?

> How hot are your motors?

> Remember that this room is the electronics workshop.

> Return to your charging station.

The same interaction must be available through a terminal:

```text
$ droid
DROID> What can you see?

I can see a workbench, two monitors, a closed door, and a person
approximately three metres ahead.
```

The user must also be able to issue a single English command without entering an interactive session:

```bash
droid "Tell me your current battery level and whether you are safe to move."
```

Example response:

```text
Battery charge is 72 percent.

All required locomotion systems are responding. The left ankle motor is
warmer than the other joints but remains below its warning threshold.

I am currently safe to move.
```

The operating system must retain ordinary technical interfaces for administrators, but the normal user experience must be through the droid.

---

# 4. Product definition

DroidOS is a custom embedded Linux distribution containing a complete robotics runtime.

It consists of five major layers:

```text
┌─────────────────────────────────────────────────────┐
│ DROID INTERACTION                                   │
│ English text, voice, personality, memory and LLM    │
├─────────────────────────────────────────────────────┤
│ DROID EXECUTIVE                                     │
│ Tasks, permissions, tools and behaviour trees       │
├─────────────────────────────────────────────────────┤
│ ROBOT SERVICES                                      │
│ Vision, mapping, navigation, diagnostics and state  │
├─────────────────────────────────────────────────────┤
│ BODY AND HARDWARE ABSTRACTION                       │
│ Body profiles, locomotion, sensors and actuators    │
├─────────────────────────────────────────────────────┤
│ DROIDOS LINUX                                       │
│ Kernel, drivers, systemd, security and updates      │
└─────────────────────────────────────────────────────┘
```

DroidOS is not merely a renamed Ubuntu installation.

It must be built as a controlled operating-system image with:

* Known package versions
* Known kernel configuration
* Reproducible builds
* Signed software images
* Defined disk partitions
* Read-only operating-system partitions
* Recovery support
* Hardware-specific builds
* Automated testing

The Yocto Project is suitable because it is specifically designed for building custom embedded Linux distributions. Its documentation describes creating a separate distribution layer, distribution configuration, and metadata for the finished product.

---

# 5. DroidOS is based on Linux

The Linux kernel will not be rewritten from zero.

A complete kernel rewrite would require recreating:

* Memory management
* Process scheduling
* Filesystems
* Networking
* USB
* Camera drivers
* Storage drivers
* Security boundaries
* Power management
* Thermal management
* Hardware discovery
* Device trees
* GPU drivers
* Wireless networking
* Bluetooth
* Debugging infrastructure

Instead, DroidOS will use the appropriate supported Linux kernel for each board and apply a controlled DroidOS configuration.

The final kernel may be branded:

```text
Linux 6.x.x-droidos
```

DroidOS kernel work includes:

* Kernel configuration
* Robotics-specific patches
* Hardware drivers
* Device-tree changes
* Watchdog configuration
* CAN and CAN-FD support
* Camera support
* GPIO, SPI and I²C support
* Thermal monitoring
* Real-time scheduling configuration
* Security hardening
* Removal of unnecessary drivers and features

Where supported by the selected board kernel, DroidOS should use `PREEMPT_RT`. PREEMPT_RT changes important locking and interrupt behaviour to make Linux substantially more preemptible and predictable for time-sensitive workloads.

PREEMPT_RT does not replace independent motor controllers.

Linux remains responsible for high-level robotics processing. Dedicated microcontrollers remain responsible for immediate electrical and mechanical safety.

---

# 6. Operating-system build system

DroidOS should be built with Yocto rather than manually modifying an installed Linux system.

At the time of this specification, Yocto 5.0 Scarthgap is a supported long-term-support release. Yocto documents Scarthgap support through April 2028. The final product must pin exact release tags and commit hashes rather than following changing branches.

The repository should use separate layers:

```text
droidos/
├── poky/
├── meta-openembedded/
├── meta-ros/
├── meta-droidos/
├── meta-droidos-rpi/
├── meta-droidos-tegra/
├── applications/
├── interfaces/
├── bodies/
├── simulation/
├── models/
├── tests/
├── tools/
└── documentation/
```

## 6.1 Shared distribution layer

`meta-droidos` contains everything common to all droids:

```text
meta-droidos/
├── conf/
│   └── distro/
│       └── droidos.conf
├── recipes-core/
├── recipes-kernel/
├── recipes-security/
├── recipes-robotics/
├── recipes-droid/
├── recipes-ai/
├── recipes-update/
└── recipes-support/
```

## 6.2 Raspberry Pi layer

`meta-droidos-rpi` contains:

* Raspberry Pi machine configuration
* Pi-specific kernel fragments
* Pi camera configuration
* Pi boot configuration
* Pi-specific device-tree overlays
* Pi cooling and fan control
* Pi hardware tests

## 6.3 NVIDIA layer

`meta-droidos-tegra` contains:

* NVIDIA Jetson board configuration
* Jetson Linux integration
* CUDA and TensorRT packages
* Jetson camera support
* GPU monitoring
* Jetson power profiles
* NVIDIA-specific device trees
* Jetson-specific hardware tests

The NVIDIA build must use a compatible vendor board-support package. The selected BSP, Yocto release, GPU libraries, and kernel must be pinned as a tested set.

---

# 7. Supported computer architecture

DroidOS should support at least two compute levels.

## 7.1 Raspberry Pi 5

The Raspberry Pi build is suitable for:

* One or more basic cameras
* ROS 2
* Diagnostics
* Voice input
* Text-to-speech
* Remote or lightweight local LLM access
* Task planning
* Navigation
* Walking-policy inference
* Hardware communication
* General droid coordination

## 7.2 NVIDIA Jetson Orin

The Jetson build is suitable for more demanding combinations of:

* Multiple cameras
* Continuous object detection
* Depth-camera processing
* Three-dimensional perception
* Local speech recognition
* Local text-to-speech
* Local LLM inference
* Vision-language models
* Semantic mapping
* Walking-policy inference
* Sensor recording

The software architecture must not assume that a GPU is available.

Every accelerated service must have:

* A hardware-accelerated implementation
* A CPU-compatible fallback where practical
* A declared minimum hardware requirement
* A health and performance status

---

# 8. Boot process

DroidOS must use a controlled boot sequence.

```text
Boot ROM
   ↓
Bootloader
   ↓
Verified kernel and device tree
   ↓
Initial RAM filesystem
   ↓
Read-only DroidOS root filesystem
   ↓
systemd
   ↓
Safety and hardware services
   ↓
ROS 2 runtime
   ↓
Droid executive
   ↓
English and voice interface
```

A successful Linux boot must not automatically enable movement.

The completed boot sequence should be:

1. Verify the operating-system image.
2. Start the kernel.
3. Mount the active read-only root filesystem.
4. Start system logging.
5. Start the hardware watchdog.
6. Start the DroidOS supervisor.
7. Contact the independent safety controller.
8. Confirm that actuator power is disabled.
9. Load the active body manifest.
10. Validate expected sensors and actuators.
11. Start device drivers.
12. Start diagnostics.
13. Start state estimation.
14. Start perception.
15. Start navigation.
16. Start the body controller.
17. Start the task executive.
18. Start the language and voice services.
19. Enter `SAFE_IDLE`.
20. Permit movement only after all required checks pass.

---

# 9. System states

The entire droid must have a defined state machine.

```text
POWERED_OFF
     ↓
BOOTING
     ↓
HARDWARE_CHECK
     ↓
SAFE_IDLE
     ↓
READY
     ↓
ACTIVE
```

Fault transitions may lead to:

```text
DEGRADED
MOTION_INHIBITED
EMERGENCY_STOPPED
RECOVERY
SHUTTING_DOWN
```

## State meanings

### `SAFE_IDLE`

* Linux is running.
* Actuator power remains disabled or inhibited.
* English interaction is available.
* Diagnostics are available.
* No movement is permitted.

### `READY`

* Required hardware is responding.
* Safety controller is healthy.
* Body configuration is valid.
* Actuators may be enabled.
* No motion command is currently executing.

### `ACTIVE`

* The droid is executing an approved physical task.

### `DEGRADED`

* Some noncritical capability is unavailable.
* The droid may continue with reduced functionality.

Example:

```text
Rear camera unavailable.
Forward navigation remains available.
```

### `MOTION_INHIBITED`

* Conversation and diagnostics remain available.
* Physical motion is disabled.

Example causes:

* Motor overheating
* Missing foot sensor
* Invalid body configuration
* Low battery
* Safety-controller communication failure

### `EMERGENCY_STOPPED`

* Motor power is removed.
* New movement commands are rejected.
* Reset requires the defined physical and software recovery process.

---

# 10. ROS 2 runtime

DroidOS should use the current ROS 2 long-term-support release that is validated with the selected Yocto and hardware BSP.

As of July 2026, ROS 2 Lyrical Luth is the current LTS release, released in May 2026 with support scheduled through May 2031.

ROS 2 provides communication between independent robot processes.

DroidOS services communicate through:

* Topics
* Services
* Actions
* Parameters
* Lifecycle transitions
* Standard message types
* Custom DroidOS interfaces

ROS 2 is middleware running on DroidOS Linux. It is not a replacement for Linux.

---

# 11. Managed service lifecycle

Important robot services must use managed lifecycle states.

A managed component can be:

```text
UNCONFIGURED
INACTIVE
ACTIVE
FINALIZED
```

This allows DroidOS to create and validate a service before allowing it to begin operating. ROS 2 lifecycle nodes were designed to provide known states and externally controlled transitions, including the ability to restart or replace components.

For example, the locomotion service must not become active until:

* The body description loads
* Joint definitions validate
* Hardware responds
* Sensor calibration is available
* The safety controller permits activation
* The walking policy passes integrity checks

---

# 12. Core DroidOS services

A complete DroidOS installation should contain the following services.

## 12.1 `droid-supervisor`

The highest non-hardware authority in the operating system.

Responsibilities:

* Manage DroidOS state
* Start and stop subsystems
* Control lifecycle transitions
* Detect failed services
* Request safe shutdown
* Enforce startup dependencies
* Maintain the authoritative system state
* Refuse activation when requirements are missing

The supervisor does not directly operate motors.

## 12.2 `droid-safety-gateway`

Communicates with the independent safety microcontroller.

Responsibilities:

* Safety-controller heartbeat
* Emergency-stop status
* Motor-power contactor state
* Hardware watchdog state
* Joint-limit fault reporting
* Thermal fault reporting
* Movement-permission token
* Safety-event logging

The safety microcontroller remains authoritative for electrical motor shutdown.

## 12.3 `droid-body-manager`

Loads and validates the installed body.

Responsibilities:

* Read the body manifest
* Load the robot description
* Verify required hardware
* Load body-specific controllers
* Publish capabilities
* Publish physical limits
* Select simulation or physical backend
* Reject incompatible hardware configurations

## 12.4 `droid-hardware`

Provides hardware abstractions for:

* Motors
* Encoders
* IMUs
* Cameras
* Foot-pressure sensors
* Lidar
* Bump sensors
* Battery systems
* Fans
* Temperature sensors
* Speakers
* Microphones
* Lights

## 12.5 `droid-state-estimator`

Combines sensor measurements to estimate:

* Position
* Orientation
* Velocity
* Angular velocity
* Joint state
* Support foot
* Body stability
* Localization confidence

## 12.6 `droid-perception`

Processes the droid’s sensors.

Responsibilities may include:

* Camera acquisition
* Image correction
* Object detection
* Person detection
* Depth processing
* Motion detection
* Landmark recognition
* QR and fiducial-marker recognition
* Environmental scene descriptions
* Sensor confidence reporting

## 12.7 `droid-world-model`

Maintains the droid’s current understanding of the world.

It stores:

* Known rooms
* Named destinations
* Fixed objects
* Temporary obstacles
* Charging locations
* Restricted areas
* Last-seen object locations
* People recognized with permission
* Confidence and timestamps

## 12.8 `droid-navigation`

Responsibilities:

* Localization
* Route planning
* Obstacle avoidance
* Route recovery
* Destination management
* Docking coordination
* Body-specific traversability checks

Nav2 provides ROS 2 navigation components, behaviour-tree navigation, mapping integration, and collision-monitoring functions. Its collision monitor can independently observe incoming sensor data and apply collision-related responses outside the normal planner path.

## 12.9 `droid-motion`

Provides the standard locomotion interface.

Depending on the body, it may load:

* Biped gait controller
* Differential-drive controller
* Omnidirectional wheel controller
* Track controller
* Stationary-body controller
* Manipulator controller

## 12.10 `droid-executive`

Executes complete tasks.

Responsibilities:

* Receive approved intents
* Build or select behaviour trees
* Coordinate subsystems
* Monitor task progress
* Perform recovery actions
* Cancel tasks
* Report results
* Preserve an auditable task history

## 12.11 `droid-language`

Provides:

* English text input
* Conversation management
* LLM access
* Tool selection
* Intent generation
* Response generation
* Personality
* Diagnostic explanations

## 12.12 `droid-voice`

Provides:

* Wake-word detection
* Speech recognition
* Speaker identification where enabled
* Text-to-speech
* Audio output
* Interruptible speech
* Emergency command detection

## 12.13 `droid-memory`

Stores permitted long-term information.

Examples:

* Names
* Places
* User preferences
* Repeated tasks
* Defined room names
* Known objects
* Previous maintenance events
* Conversation summaries

Safety rules and hardware limits must not be stored as editable conversational memory.

## 12.14 `droid-diagnostics`

Collects and aggregates health information.

ROS diagnostic packages support collecting diagnostic data from device drivers and publishing it through standard diagnostic messages for aggregation and monitoring.

## 12.15 `droid-update`

Responsibilities:

* Validate signed update bundles
* Install updates to the inactive system slot
* Request reboot
* Verify successful boot
* Roll back failed updates
* Report installed versions

---

# 13. The English-language command interface

DroidOS must provide two command interfaces.

## 13.1 `droid`

`droid` is the natural-language interface.

It accepts ordinary English and returns an English response.

Examples:

```bash
droid "What can you see?"
```

```bash
droid "Why is your movement disabled?"
```

```bash
droid "Go to the charging station."
```

```bash
droid "Remember that the room beside the stairs is the electronics workshop."
```

Running it without arguments opens an interactive conversation:

```text
$ droid

DroidOS interactive interface
Body: B1-MK1
State: READY
Language service: local
Motion permission: available

DROID> 
```

The command should also support explicit modes:

```bash
droid ask "What is your current status?"
droid do "Walk to the workshop."
droid explain "Why did the previous task fail?"
droid remember "This shelf contains networking equipment."
droid forget "Forget the temporary storage location."
```

These modes help distinguish conversation from requested physical action.

## 13.2 `droidctl`

`droidctl` is the deterministic administrative interface.

It does not require an LLM.

Examples:

```bash
droidctl status
droidctl status --json
droidctl body show
droidctl body validate
droidctl safety status
droidctl diagnostics list
droidctl task cancel
droidctl update status
droidctl services list
```

Scripts and automated tests use `droidctl`.

Humans normally use `droid`.

The LLM interface must not be the only way to operate or diagnose the machine.

---

# 14. Language-processing architecture

Natural-language input follows this path:

```text
Typed or spoken English
          ↓
Language service
          ↓
Intent and requested outcome
          ↓
Structured action proposal
          ↓
Command broker
          ↓
Permission and capability checks
          ↓
Safety and state checks
          ↓
Task executive
          ↓
Robot services
```

For example, the user says:

> Go to the workshop and inspect the server rack.

The LLM may produce:

```json
{
  "intent": "navigate_and_inspect",
  "arguments": {
    "destination": "workshop",
    "inspection_target": "server rack"
  },
  "requested_speed": "cautious",
  "requires_motion": true
}
```

This is only a proposal.

The command broker checks:

* Is the intent registered?
* Does the current user have permission?
* Does the body support movement?
* Is the destination known?
* Can this body traverse the route?
* Is movement currently permitted?
* Is the battery sufficient?
* Are required sensors available?
* Is the safety controller healthy?
* Does the task require confirmation?

Only an approved action reaches the task executive.

---

# 15. LLM provider interface

DroidOS must not be tied to one model or vendor.

The language service should define a provider interface supporting:

* Local models
* A local network model server
* Remote hosted models
* Multiple fallback providers
* Disabled-LLM operation

Example internal provider interface:

```text
generate_response()
generate_structured_intent()
select_registered_tool()
summarize_diagnostics()
summarize_visual_observation()
```

A local provider may use an embedded inference engine such as `llama.cpp`. Its server provides a lightweight HTTP service and an OpenAI-compatible chat endpoint, making it possible to keep DroidOS provider-neutral.

The model provider is configuration, not core architecture.

Example:

```yaml
language:
  primary_provider: local
  fallback_provider: home_server

  providers:
    local:
      type: llama_cpp
      endpoint: unix:///run/droidos/llm.sock
      model: /var/lib/droidos/models/default.gguf

    home_server:
      type: compatible_http
      endpoint: https://droid-brain.local/v1
```

Secrets must not be stored in the body manifest or exposed to the LLM context.

---

# 16. Required offline operation

DroidOS must retain essential operation if:

* Internet access fails
* The remote LLM is unavailable
* The local large model crashes
* Wi-Fi disconnects

The following commands must work without an LLM:

* Stop
* Emergency stop
* Cancel
* Status
* Battery status
* Temperature status
* Help
* Return to safe idle
* Silence
* Shut down
* Report active faults
* Report current task

These commands should use a deterministic local parser.

The droid may say:

> My advanced language model is unavailable. Basic commands and diagnostics remain operational.

Walking, stopping, balance, collision avoidance, and safety must never depend on an external LLM.

---

# 17. Tool and command registry

The LLM can only request registered tools.

Example registry:

```yaml
tools:
  - name: robot.get_status
    risk: none

  - name: perception.describe_scene
    risk: none

  - name: navigation.navigate_to
    risk: motion
    required_capability: locomotion

  - name: motion.stop
    risk: none
    always_available: true

  - name: memory.store_place
    risk: data_write
    confirmation: conditional

  - name: system.install_update
    risk: administrative
    confirmation: required
    authorization: administrator
```

The LLM must not receive a general unrestricted shell tool.

It must not be able to freely execute:

```bash
rm
dd
mount
modprobe
systemctl
reboot
chmod
sudo
```

Administrative actions must be implemented as specific, validated tools.

For example, it may request:

```text
system.request_reboot
```

It may not request:

```text
execute arbitrary shell string
```

---

# 18. Confirmation rules

DroidOS should divide actions into risk classes.

## No confirmation normally required

* Answering questions
* Reading diagnostics
* Describing camera input
* Reporting battery state
* Looking toward a target
* Cancelling an active task
* Stopping

## Context-dependent confirmation

* Beginning autonomous movement
* Following a person
* Recording video
* Remembering personal information
* Entering a newly discovered area
* Operating near stairs

## Explicit confirmation required

* Installing updates
* Changing network configuration
* Enabling remote access
* Deleting memories
* Changing safety-related configuration
* Activating a new body package
* Enabling experimental locomotion
* Rebooting during an active task
* Shutting down

Emergency stop must never require confirmation.

---

# 19. Personality and identity

The droid should have a configurable identity.

Example:

```yaml
identity:
  name: IG-12
  model_family: assassin_droid
  voice_profile: mechanical_01
  personality_profile: dry_literal
  verbosity: concise
  wake_names:
    - IG-12
    - droid
```

Personality controls:

* Wording
* Tone
* Humour
* Recurring phrases
* Voice
* Response length
* Conversational behaviour

Personality must not alter:

* Safety thresholds
* Physical limits
* Authorization
* Sensor truth
* Diagnostic severity
* Command permissions

The droid may be sarcastic about an overheated motor. It may not ignore the overheated motor.

---

# 20. Body-independent architecture

The active body is described by a signed body package.

Example locations:

```text
/usr/lib/droidos/bodies/b1-mk1/
/usr/lib/droidos/bodies/gonk-mk1/
/usr/lib/droidos/bodies/r2-mk1/
/usr/lib/droidos/bodies/ig-mk1/
```

Each body package contains:

```text
manifest.yaml
robot.urdf.xacro
controllers.yaml
sensors.yaml
limits.yaml
capabilities.yaml
simulation.yaml
hardware-plugin.so
locomotion-plugin.so
diagnostic-rules.yaml
```

The active body is selected in:

```text
/etc/droidos/body.yaml
```

Example:

```yaml
body_id: ig-mk1
backend: physical
hardware_profile: canfd-v1
```

For simulation:

```yaml
body_id: ig-mk1
backend: simulation
simulation_engine: mujoco
```

The rest of DroidOS must operate through the same interfaces in both cases.

---

# 21. Capability registry

The body package publishes its capabilities.

Example B1-style body:

```yaml
capabilities:
  locomotion:
    walk: true
    roll: false
    reverse: true
    turn_in_place: true
    stairs: experimental
    maximum_speed_mps: 0.35

  perception:
    front_camera: true
    rear_camera: false
    lidar_2d: false
    lidar_3d: false
    microphones: true

  manipulation:
    left_arm: true
    right_arm: true
    grippers: false
    maximum_payload_kg: 1.0

  posture:
    stand: true
    crouch: true
    self_right: false
```

Example R2-style body:

```yaml
capabilities:
  locomotion:
    walk: false
    roll: true
    reverse: true
    turn_in_place: true
    stairs: false
    maximum_speed_mps: 0.8

  manipulation:
    utility_arm: true
    grippers: false
```

The English interface receives this capability information.

If an R2 body is told:

> Walk upstairs.

It should respond:

> This body cannot walk or climb stairs. I can navigate to the base of the stairs or request assistance.

---

# 22. Hardware abstraction

DroidOS should use `ros2_control` for standard actuator and sensor integration.

`ros2_control` defines hardware components as actuators, sensors, or complete systems. Hardware implementations are dynamically loaded as plugins, allowing controllers to work through standard interfaces instead of being tied to one device brand.

A body may expose:

```text
Joint position
Joint velocity
Joint effort
Motor current
Motor temperature
Encoder state
Foot pressure
Battery voltage
Fan speed
```

Commands may include:

```text
Desired position
Desired velocity
Desired effort
Maximum permitted current
Controller mode
```

The body hardware plugin translates these standard interfaces into:

* CAN-FD frames
* EtherCAT messages
* Serial commands
* SPI transactions
* Vendor-specific protocols

---

# 23. Locomotion architecture

The core operating system issues body-level movement requests.

Examples:

```text
Move forward at 0.2 m/s.
Turn right at 0.15 rad/s.
Stop.
Navigate to map coordinate.
Assume stable standing posture.
```

For a wheeled droid:

```text
Requested body velocity
        ↓
Wheel controller
        ↓
Wheel speeds
```

For a walking droid:

```text
Requested body velocity
        ↓
Gait policy
        ↓
Footstep and balance controller
        ↓
Joint targets
        ↓
Joint controllers
```

The LLM never generates joint targets.

The task executive never generates motor current.

---

# 24. Independent motor control

A separate microcontroller or group of motor controllers must handle the fastest control loops.

The onboard Linux computer handles:

* Route selection
* Body velocity
* Walking-policy inference
* State estimation
* Camera processing
* Task planning

The microcontroller handles:

* Encoder sampling
* Motor-current control
* Position and torque loops
* Joint-limit enforcement
* Temperature limits
* Communication timeouts
* Emergency power removal
* Safe response to invalid commands

Typical communication:

```text
DroidOS:
Desired right-knee position = 0.42 radians

Joint controller:
Reads encoder
Calculates error
Applies permitted motor current
Checks temperature
Checks hard limits
Reports actual state
```

If Linux stops communicating, the motor controller must enter its defined safe state.

---

# 25. Walking-policy support

DroidOS must support trained locomotion policies.

Training takes place on a separate simulation or training computer.

The installed DroidOS image performs inference using the exported policy.

Supported policy format should include a portable form such as ONNX where compatible.

The motion package should contain:

* Model file
* Model checksum
* Observation definition
* Action definition
* Normalization data
* Expected control rate
* Supported body revision
* Safety envelope
* Version information

DroidOS must reject a gait policy if:

* It is for a different body
* Its checksum is invalid
* Its observation layout is incompatible
* Its required sensors are unavailable
* It has not been approved for physical operation

---

# 26. Simulation support

Every body must support a simulated backend before physical activation.

The simulation interface should reproduce:

* Joint states
* Motor limits
* IMU data
* Camera feeds
* Contact sensors
* Battery state
* Temperatures where practical
* Communication delays
* Fault conditions

The same commands must operate both systems:

```bash
droid "Walk to the charging station."
```

In simulation, the action moves the simulated body.

On physical hardware, the action moves the physical body.

Only the backend changes.

Simulation is used for:

* Walking-policy training
* Navigation testing
* Failure testing
* Body-package validation
* Update testing
* Command testing
* Behaviour-tree testing
* Regression testing

---

# 27. Vision and sensor architecture

Sensors are plug-ins rather than hardcoded dependencies.

Example topics:

```text
/sensors/camera/front/image
/sensors/camera/front/info
/sensors/lidar/scan
/sensors/lidar/points
/sensors/imu/torso
/sensors/imu/pelvis
/sensors/foot/left/contact
/sensors/foot/right/contact
/sensors/battery/state
```

A camera-only body must remain a valid configuration.

A lidar-equipped body publishes additional range information.

The navigation and perception systems determine available functions from the sensor manifest.

The droid must not falsely claim to have measurements from a sensor that is not installed.

---

# 28. Diagnostics

Every major component must publish diagnostics.

## Computer diagnostics

* CPU utilization
* Memory usage
* Storage usage
* Storage health
* CPU temperature
* GPU utilization
* GPU temperature
* Fan speed
* Power mode
* Process status
* Service restart count

## Network diagnostics

* Ethernet state
* Wi-Fi state
* Signal strength
* Internet availability
* Home-server availability
* LLM-provider availability
* Packet loss where monitored

## Sensor diagnostics

* Device detected
* Data frequency
* Last message time
* Temperature
* Calibration status
* Error count
* Confidence
* Dropped frames

## Actuator diagnostics

* Position
* Velocity
* Current
* Torque estimate
* Motor temperature
* Controller temperature
* Voltage
* Limit state
* Encoder state
* Communication errors
* Fault code

## Robot-level diagnostics

* Body state
* Balance state
* Localization confidence
* Battery percentage
* Charging state
* Active task
* Emergency-stop state
* Motion permission
* Safety-controller state
* Body-package version
* Gait-policy version

The English interface should be able to answer:

> What is wrong?

> Why can’t you walk?

> Which motor is hottest?

> Are all cameras operating?

> What failed during the last task?

The response must be based on diagnostic facts, not model speculation.

---

# 29. Logging and audit records

DroidOS must maintain separate logs for:

* System boot
* Kernel
* Hardware events
* Safety events
* Tasks
* Commands
* LLM requests
* Tool calls
* Diagnostics
* Updates
* Authentication
* Body configuration
* Motion inhibition
* Emergency stops

Suggested storage:

```text
/var/log/droidos/
/var/lib/droidos/history/
/var/lib/droidos/diagnostics/
/var/lib/droidos/tasks/
```

Every physical command should record:

* Timestamp
* User
* Original natural-language request
* Parsed structured intent
* Approval result
* Selected task
* Start and completion state
* Failure reason
* Relevant safety state

Private LLM reasoning is not required. The structured request, tool calls, validation results, and external actions are the important audit record.

---

# 30. Filesystem structure

Suggested filesystem:

```text
/etc/droidos/
    Main configuration

/usr/bin/droid
    Natural-language command

/usr/bin/droidctl
    Deterministic administrator command

/usr/lib/droidos/
    Installed DroidOS programs and body packages

/var/lib/droidos/
    Mutable state, maps, models and memory

/var/log/droidos/
    Logs

/run/droidos/
    Runtime sockets and temporary state

/opt/droidos/
    Optional vendor or application packages
```

The root operating-system filesystem should normally be read-only.

Writable areas should be limited to:

* Configuration
* Logs
* Maps
* Models
* User-approved memory
* Temporary runtime state
* Update staging

---

# 31. Service security

Each service should run under its own restricted account.

Examples:

```text
droid-language
droid-perception
droid-navigation
droid-motion
droid-diagnostics
droid-update
```

Services should receive only the permissions they require.

The language model should not have direct access to:

* Motor device files
* Kernel memory
* Raw storage devices
* Update signing keys
* Password databases
* Safety-controller configuration
* Arbitrary network destinations
* Other users’ files

Systemd provides controls such as `NoNewPrivileges`, filesystem protections, device restrictions, capability limits, and namespace isolation that can be applied to services.

Example language-service restrictions:

```ini
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
PrivateDevices=true
```

The exact restrictions depend on the service’s required hardware access.

---

# 32. Users and authorization

DroidOS should define roles.

## Owner

May:

* Configure the droid
* Approve body changes
* Install updates
* Manage users
* Manage memory
* Enable remote providers
* Authorize physical capabilities

## Operator

May:

* Issue ordinary tasks
* Move the droid
* Request inspections
* View normal diagnostics
* Cancel tasks

## Guest

May:

* Converse
* Ask general questions
* Request nonphysical information

## Service technician

May:

* Access detailed diagnostics
* Run hardware tests
* Calibrate sensors
* Inspect logs
* Place the droid in maintenance mode

High-risk actions require authenticated authorization, not merely recognition of a familiar voice.

---

# 33. Updates and rollback

DroidOS must use signed image-based updates with rollback.

Recommended partition design:

```text
Boot
Root filesystem A
Root filesystem B
Persistent data
Recovery
```

The droid normally runs from one root slot.

An update is installed into the inactive slot.

```text
Running: Root A
Updating: Root B
```

After installation:

1. Verify the update signature.
2. Mark Root B as the next boot target.
3. Reboot.
4. Run boot-health checks.
5. Mark Root B successful only after required services start.
6. Return to Root A automatically if Root B fails.

RAUC is designed for robust embedded Linux updates, including signed bundles, image installation, and integration with the boot process.

The droid should be able to answer:

> What version are you running?

> Is an update available?

> Did the previous update succeed?

> Which system slot is active?

---

# 34. Recovery system

Recovery mode must be available if the normal operating system cannot boot.

Recovery functions should include:

* Network or USB repair access
* Filesystem checks
* Log export
* Factory-image restoration
* Configuration backup
* Configuration restoration
* Update rollback
* Body-package removal
* Model removal
* Safe shutdown

Recovery mode must not enable actuator power.

---

# 35. Required operating-system images

The build system should produce:

```text
droidos-rpi5-production.wic
droidos-rpi5-recovery.wic
droidos-orin-production.img
droidos-orin-recovery.img
droidos-qemu-arm64.img
droidos-sdk.tar.zst
droidos-update.raucb
```

Each build must include:

* Version
* Build timestamp
* Source revision
* Kernel revision
* ROS revision
* Body-interface revision
* Package manifest
* Cryptographic checksum
* Signature

---

# 36. Development languages

Recommended language use:

## C++

Use for:

* High-frequency ROS nodes
* Hardware interfaces
* State estimation
* Motion integration
* Performance-sensitive perception
* Navigation plug-ins

## Rust or carefully written C++

Use for:

* DroidOS supervisor
* Command broker
* Security-sensitive daemons
* Update orchestration
* Safety gateway

## Python

Use for:

* Build tooling
* Configuration generation
* Testing
* Noncritical task logic
* Data conversion
* Development utilities

The LLM service may be implemented in a language appropriate to the selected inference provider, but its command boundary must remain strongly typed.

---

# 37. Required public interfaces

The project must define stable custom messages and actions.

Example package:

```text
droid_interfaces/
├── action/
│   ├── ExecuteTask.action
│   ├── NavigateToNamedPlace.action
│   ├── InspectTarget.action
│   └── Speak.action
├── msg/
│   ├── BodyCapabilities.msg
│   ├── DroidState.msg
│   ├── SafetyState.msg
│   ├── TaskStatus.msg
│   └── StructuredIntent.msg
└── srv/
    ├── GetStatus.srv
    ├── ValidateIntent.srv
    ├── SetBody.srv
    └── CancelTask.srv
```

These interfaces allow the implementation behind a service to change without breaking the entire OS.

---

# 38. Example complete command flow

User says:

> Go to the workshop, look at the server rack, and tell me whether anything appears wrong.

## Step 1: Speech recognition

Audio becomes text.

## Step 2: Language interpretation

The LLM creates a proposed structured intent:

```json
{
  "intent": "inspect_named_target",
  "destination": "workshop",
  "target": "server rack",
  "requested_output": "spoken summary"
}
```

## Step 3: Command validation

DroidOS checks:

* User authorization
* Current body capabilities
* Motion permission
* Battery level
* Sensor availability
* Destination existence
* Route availability
* Current safety state

## Step 4: Task creation

The executive creates:

```text
Check health
Stand
Navigate to workshop
Locate server rack
Orient cameras
Capture observations
Analyze observations
Produce report
Await command
```

## Step 5: Locomotion

The navigation system requests body velocity.

The installed body adapter converts that request into walking or rolling.

## Step 6: Perception

The camera service captures the rack.

The perception service identifies visible indicators and abnormalities.

## Step 7: Reporting

The language service receives verified observations:

```json
{
  "green_indicators": 8,
  "amber_indicators": 1,
  "red_indicators": 0,
  "open_cabinet_door": true,
  "confidence": 0.87
}
```

It produces:

> I found one amber indicator and no red indicators. The left cabinet door is open. I cannot determine the meaning of the amber light without a device reference or closer inspection.

The droid must distinguish observation from interpretation.

---

# 39. Failure behaviour

If navigation fails:

> I could not reach the workshop because the hallway is blocked. I stopped 2.4 metres from the obstruction.

If localization fails:

> I am no longer sufficiently certain of my position to continue autonomous movement.

If the camera fails:

> My front camera stopped responding. I have cancelled the inspection because I cannot verify the target.

If the LLM fails:

> My advanced language service is unavailable. Basic status, stop, cancel, return, and shutdown commands remain available.

If the safety controller fails:

> Communication with my safety controller has failed. Motor power is disabled.

The system must never disguise missing information as confidence.

---

# 40. Definition of a fully functional DroidOS installation

DroidOS 1.0 is complete only when all of the following are true.

## Operating system

* Boots from a reproducible signed image
* Identifies itself as DroidOS
* Uses a controlled kernel
* Supports recovery mode
* Supports A/B updates
* Automatically rolls back a failed update
* Maintains persistent configuration and logs

## English interface

* `droid` accepts ordinary English
* Interactive conversation works
* Single-command mode works
* Voice and typed input use the same command broker
* The droid can answer questions about itself
* The droid can explain task failures
* Basic commands work without an LLM
* The LLM cannot execute arbitrary shell commands

## Robot architecture

* Body package loads dynamically
* Capabilities are published
* Unsupported actions are rejected
* Simulation and physical backends use the same interfaces
* At least one biped and one wheeled body definition can load
* Body replacement does not require rewriting core services

## Diagnostics

* Computer, sensor, actuator, network, battery, and service diagnostics are available
* `droidctl status --json` returns machine-readable state
* `droid "What is wrong?"` returns an evidence-based explanation
* Fault history is stored

## Safety

* Motor power defaults to disabled
* Independent safety controller is required for physical motion
* Emergency stop works without Linux
* Communication failure disables movement
* LLM cannot override safety
* Invalid body or policy files prevent activation
* Motion commands are audited

## Perception

* Installed cameras are detected
* Images are available to authorized services
* The droid can describe a scene
* Sensor confidence is reported
* Missing sensors are handled honestly

## Navigation

* Named places are supported
* Mapping or localization backend can be configured
* Route planning works with the active body
* Obstacles stop or reroute the droid
* Navigation can be cancelled immediately

## Motion

* Standard movement interface exists
* Wheeled and biped controllers can implement it
* Physical motor loops remain outside the LLM
* Walking policies are versioned and validated
* Invalid movement commands are rejected

## Security

* Services run with restricted permissions
* Updates are signed
* User roles are enforced
* Secrets are protected
* Remote access is disabled unless configured
* Language service cannot access raw actuator devices

---

# 41. Required project deliverables

The team receiving this specification must produce:

1. DroidOS source repository
2. Yocto distribution layer
3. Raspberry Pi board-support layer
4. Jetson board-support layer
5. Custom kernel configuration
6. Boot and recovery images
7. A/B update system
8. ROS 2 integration
9. DroidOS service supervisor
10. Natural-language `droid` command
11. Deterministic `droidctl` command
12. Pluggable LLM provider interface
13. Voice-input and text-to-speech interfaces
14. Command broker and tool registry
15. User authorization system
16. Diagnostics framework
17. Body-package format
18. Simulation backend
19. Physical-hardware backend
20. Biped locomotion interface
21. Wheeled locomotion interface
22. Camera and sensor interfaces
23. Mapping and navigation integration
24. Logging and audit system
25. Automated test suite
26. Developer SDK
27. Administrator documentation
28. Body-development documentation
29. Recovery documentation
30. Security threat model

---

# 42. Final summary

DroidOS is a complete Linux distribution for intelligent physical droids.

The defining feature is not simply that it runs Linux or includes an LLM. Its defining feature is that natural-language intelligence, robotics services, body control, diagnostics, safety, and hardware abstraction are assembled into one controlled operating system.

The user interacts with the installation in English through:

```bash
droid
```

The LLM interprets language and proposes actions.

The command broker validates those actions.

The task executive coordinates approved behaviour.

The body adapter translates general movement into body-specific locomotion.

Dedicated controllers execute motor commands and enforce physical limits.

The safety system remains independent of the LLM.

The same DroidOS installation architecture can support a B1, assassin droid, Gonk, R2, R3, or another future body by replacing the body package and hardware backend rather than replacing the brain.

The completed product should not behave like a Linux computer with a chatbot attached.

It should boot, identify its body, verify its systems, enter a safe state, listen, understand English, explain itself, perform permitted tasks, reject impossible or unsafe requests, recover from faults, update securely, and preserve a consistent droid identity.
