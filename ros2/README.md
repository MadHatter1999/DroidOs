# DroidOS ROS 2 nodes (roadmap M1)

The reference brain runs as a single process. This package is the **ROS 2 bridge**:
`rclpy` lifecycle nodes that expose the same brain over real ROS 2 middleware using
the [`droid_interfaces`](../interfaces/droid_interfaces) messages, services and
actions (spec §10, §11, §37).

This is the first milestone toward the full node split (see
[ROADMAP.md](../documentation/ROADMAP.md)). It reuses the `droidos` Python package
for the logic, so behaviour and safety gates are identical; the nodes add the ROS 2
lifecycle, topics, services and actions around them. The eventual end state runs
each service as its own process; here they share one `DroidSystem` instance to keep
the bridge small while the interfaces stabilise.

## Requires (not runnable in this checkout)

- ROS 2 (Lyrical Luth) with `rclpy` and lifecycle
- the built `droid_interfaces` package
- the `droidos` Python package on `PYTHONPATH`

## Nodes

| Node | Exposes |
|------|---------|
| `droid_supervisor` | `~/state` (`DroidState`), lifecycle transitions, boot |
| `droid_safety_gateway` | `~/safety` (`SafetyState`), `~/estop` service |
| `droid_language` | `validate_intent` (`ValidateIntent` srv), `execute_task` action |

## Run

```bash
colcon build --packages-select droid_interfaces droid_nodes droid_bringup
source install/setup.bash
ros2 launch droid_bringup droidos.launch.py
ros2 topic echo /droid_supervisor/state
ros2 service call /droid_language/validate_intent droid_interfaces/srv/ValidateIntent "{...}"
```
