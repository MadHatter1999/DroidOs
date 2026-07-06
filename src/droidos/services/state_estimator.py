"""``droid-state-estimator`` (spec §12.5).

Combines sensor measurements into an estimate of position, orientation, velocity,
joint state, support foot, body stability and localization confidence. In the
reference build the "truth" comes from the backend; confidence degrades when a
``localization_loss`` fault is injected or required localization sensors fail.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core.models import DiagnosticLevel, DiagnosticStatus
from .lifecycle import ManagedService

if TYPE_CHECKING:
    from ..system import Runtime


class StateEstimator(ManagedService):
    requires = ("safety_gateway",)

    def __init__(self, rt: "Runtime") -> None:
        super().__init__("state_estimator", rt)

    def estimate(self) -> dict[str, Any]:
        rt = self.rt
        backend = rt.backend
        if backend is None:
            return {"localization_confidence": 0.0, "valid": False}
        pose = backend.pose()
        confidence = self._localization_confidence()
        balance = self._balance_margin()
        return {
            "position": {"x": pose.x, "y": pose.y},
            "orientation_yaw": pose.theta,
            "localization_confidence": confidence,
            "balance_margin": balance,
            "support_foot": self._support_foot(),
            "valid": confidence > 0.0,
        }

    def localization_confidence(self) -> float:
        return self._localization_confidence()

    def _localization_confidence(self) -> float:
        backend = self.rt.backend
        if backend is None:
            return 0.0
        faults = getattr(backend, "_faults", {})
        if "localization_loss" in faults:
            return 0.2
        # confidence improves with a working lidar, if the body has one
        has_lidar = any(s.type.startswith("lidar") for s in self.rt.body.sensors) if self.rt.body else False
        if has_lidar:
            return 0.92 if backend.read_sensor(_first_lidar(self.rt)).ok else 0.55
        return 0.8

    def _balance_margin(self) -> float:
        # wheeled/stationary bodies are inherently stable; bipeds report a margin
        if self.rt.body and self.rt.body.manifest.locomotion_type == "biped":
            return 0.35
        return 1.0

    def _support_foot(self) -> str:
        if self.rt.body and self.rt.body.manifest.locomotion_type == "biped":
            return "double"
        return "n/a"

    def diagnostics(self) -> list[DiagnosticStatus]:
        conf = self._localization_confidence()
        level = DiagnosticLevel.OK
        if conf < 0.4:
            level = DiagnosticLevel.ERROR
        elif conf < 0.6:
            level = DiagnosticLevel.WARN
        return [
            DiagnosticStatus(
                name="state_estimator/localization",
                level=level,
                message=f"localization confidence {conf:.2f}",
                values={"confidence": round(conf, 3), "balance_margin": self._balance_margin()},
            )
        ]


def _first_lidar(rt: "Runtime") -> str:
    for s in rt.body.sensors:
        if s.type.startswith("lidar"):
            return s.id
    return ""
