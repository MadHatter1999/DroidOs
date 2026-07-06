"""``droid-motion`` (spec §12.9, §23).

Provides the standard body-level locomotion interface. Depending on the body it
selects a biped gait, differential-drive, omni, track or stationary controller.
The core brain issues *body velocities* only, the LLM never generates joint
targets and this service never generates motor current (spec §23, §24). Physical
motor loops live in the independent controllers.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..backends.base import Pose
from ..core.errors import CapabilityError
from ..core.models import BodyVelocity, DiagnosticLevel, DiagnosticStatus
from .lifecycle import ManagedService

if TYPE_CHECKING:
    from ..system import Runtime

_CONTROLLER_BY_TYPE = {
    "biped": "biped_gait_controller",
    "differential": "diff_drive_controller",
    "omni": "omni_drive_controller",
    "tracked": "track_controller",
    "stationary": "stationary_controller",
    "manipulator": "manipulator_controller",
}


class Motion(ManagedService):
    requires = ("safety_gateway",)

    def __init__(self, rt: "Runtime") -> None:
        super().__init__("motion", rt)
        self.controller_name = "unconfigured"
        self.gait_policy = None
        self.gait_issues: list[str] = []
        self.last_joint_targets: dict[str, float] = {}

    def _on_configure(self) -> bool:
        loco = self.rt.body.manifest.locomotion_type if self.rt.body else "stationary"
        self.controller_name = _CONTROLLER_BY_TYPE.get(loco, "stationary_controller")
        # Load and validate the walking policy for bipeds (spec §25).
        if loco == "biped" and self.rt.body is not None:
            from ..gait import load_for_body

            self.gait_policy, self.gait_issues = load_for_body(self.rt.body)
        return True

    def can_move(self) -> bool:
        return bool(self.rt.body and self.rt.body.capabilities.supports_motion())

    # command path --------------------------------------------------------- #
    def drive(self, vel: BodyVelocity, dt: float) -> None:
        """Validate, clamp and forward a body-velocity command (spec §23)."""
        if not self.can_move():
            raise CapabilityError("this body has no locomotion capability")
        self._validate(vel)
        clamped = self._clamp(vel)
        # For a biped, the gait policy turns body velocity into joint targets
        # (spec §23, §25). The LLM never produces these; this service does not
        # produce motor current, the independent controllers do (spec §24).
        if self.gait_policy is not None:
            obs = {
                "cmd_vx": clamped.linear_x,
                "cmd_wz": clamped.angular_z,
                "base_lin_vel": clamped.linear_x,
                "base_ang_vel": clamped.angular_z,
                "gravity_z": -9.81,
            }
            self.last_joint_targets = self.gait_policy.infer(obs, dt)
            self.rt.backend.command_joints(self.last_joint_targets)
        # The backend refuses to move unless motor power is enabled (spec §24),
        # so a missing motion permission simply results in no movement.
        self.rt.backend.command_velocity(clamped, dt)
        self.rt.backend.step(dt)

    def stop(self) -> None:
        """Always available (spec §17). Commands zero velocity immediately."""
        if self.rt.backend is not None:
            self.rt.backend.command_velocity(BodyVelocity(), 0.0)

    def _validate(self, vel: BodyVelocity) -> None:
        for name, v in (("linear_x", vel.linear_x), ("linear_y", vel.linear_y), ("angular_z", vel.angular_z)):
            if math.isnan(v) or math.isinf(v):
                raise CapabilityError(f"invalid velocity component {name}={v}")

    def _clamp(self, vel: BodyVelocity) -> BodyVelocity:
        limits = self.rt.body.limits
        max_lin = limits.max_linear() or self.rt.body.capabilities.max_speed() or 0.3
        max_ang = limits.max_angular() or 0.8
        # Lateral velocity is only meaningful for omnidirectional bodies.
        is_omni = self.rt.body.manifest.locomotion_type == "omni"
        return BodyVelocity(
            linear_x=_clamp(vel.linear_x, max_lin),
            linear_y=_clamp(vel.linear_y, max_lin) if is_omni else 0.0,
            angular_z=_clamp(vel.angular_z, max_ang),
        )

    # heading control used by navigation/executive ------------------------- #
    def velocity_toward(self, goal: Pose, current: Pose) -> tuple[BodyVelocity, float]:
        """Return a body velocity that drives toward *goal* and the remaining distance."""
        dx = goal.x - current.x
        dy = goal.y - current.y
        distance = math.hypot(dx, dy)
        desired_yaw = math.atan2(dy, dx)
        yaw_err = _wrap(desired_yaw - current.theta)
        max_lin = self.rt.body.limits.max_linear() or self.rt.body.capabilities.max_speed() or 0.3
        max_ang = self.rt.body.limits.max_angular() or 0.8
        # turn first, then advance once roughly aligned
        angular = _clamp(2.0 * yaw_err, max_ang)
        linear = max_lin if abs(yaw_err) < 0.3 else 0.0
        if distance < max_lin:  # ease in near the goal
            linear = min(linear, distance)
        return BodyVelocity(linear_x=linear, angular_z=angular), distance

    def diagnostics(self) -> list[DiagnosticStatus]:
        out = [
            DiagnosticStatus(
                name="motion/controller",
                level=DiagnosticLevel.OK,
                message=f"{self.controller_name} ({'mobile' if self.can_move() else 'stationary'})",
                values={"controller": self.controller_name},
            )
        ]
        if self.rt.body and self.rt.body.manifest.locomotion_type == "biped":
            ok = self.gait_policy is not None and not self.gait_issues
            out.append(
                DiagnosticStatus(
                    name="motion/gait_policy",
                    level=DiagnosticLevel.OK if ok else DiagnosticLevel.WARN,
                    message=(
                        f"{self.gait_policy.runtime} policy, rate "
                        f"{self.gait_policy.control_rate_hz:g} Hz"
                        if self.gait_policy else "no gait policy loaded"
                    ) + ("" if ok else f"; issues: {', '.join(self.gait_issues)}"),
                    values={
                        "loaded": self.gait_policy is not None,
                        "issues": self.gait_issues,
                    },
                )
            )
        return out


def _clamp(v: float, limit: float) -> float:
    return max(-limit, min(limit, v))


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi
