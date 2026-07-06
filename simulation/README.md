# DroidOS simulation

Every body must support a simulated backend before physical activation (spec §26).
The same commands drive both backends; only the backend changes:

```bash
# simulation (default in a checkout)
droid "Walk to the charging station."

# physical
#   set backend: droidctl body set ig-mk1 --backend physical
```

## Reference simulator

The runnable reference brain ships with a lightweight, deterministic simulator
(`droidos.backends.simulation`) that models kinematics, a thermal model, a
draining battery, a structured camera scene, 2D lidar and injectable faults. It
needs no external engine and is what the test suite and the CLIs use by default.

## Production simulator

For walking-policy training, physics-accurate navigation and body-package
validation, a production build bridges the same `HardwareBackend` interface to a
full engine (MuJoCo or Gazebo). The body package's `simulation.yaml` selects the
engine and model:

```yaml
simulation:
  engine: mujoco
  model: ig-mk1.mjcf
  timestep: 0.005
```

## Fault injection

The simulator can inject the fault conditions listed in each body's
`simulation.yaml` for failure testing (spec §26, §39):

- `motor_overheat`, pushes a joint over its fault temperature
- `sensor_dropout`, a named sensor stops responding
- `localization_loss`, localization confidence collapses
- `path_blocked`, an obstacle appears in the forward path
- `safety_link_loss`, the safety-controller link drops (power removed)

See `droidos_sim.yaml` for global simulation defaults.
