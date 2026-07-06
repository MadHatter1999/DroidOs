"""``droid-navigation`` (spec §12.8).

Localization gating, route planning, obstacle detection, destination management,
docking and body-specific traversability. Mirrors the role of Nav2 in a real
system, including an independent collision check on incoming range data that can
stop the droid outside the normal planner path (spec §12.8). The actual driving
loop is run by the executive, which calls :meth:`plan`, :meth:`is_path_blocked`
and motion together while holding a motion-permission token.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..backends.base import Pose
from ..core.models import DiagnosticLevel, DiagnosticStatus
from .lifecycle import ManagedService

if TYPE_CHECKING:
    from ..system import Runtime

COLLISION_STOP_M = 0.6
MIN_LOCALIZATION_CONFIDENCE = 0.4


class Navigation(ManagedService):
    requires = ("safety_gateway", "state_estimator", "world_model")

    def __init__(self, rt: "Runtime") -> None:
        super().__init__("navigation", rt)

    # destinations --------------------------------------------------------- #
    def known_places(self) -> list[str]:
        wm = self.rt.world_model
        return wm.place_names() if wm else []

    def resolve(self, name: str) -> Pose | None:
        wm = self.rt.world_model
        if wm is None:
            return None
        place = wm.get_place(name)
        if place is None:
            return None
        return Pose(x=place["x"], y=place["y"], theta=0.0)

    def traversable(self, name: str) -> tuple[bool, str]:
        """Body-specific reachability check (spec §21, §12.8)."""
        body = self.rt.body
        if body is None or not body.capabilities.supports_motion():
            return False, "this body cannot move"
        wm = self.rt.world_model
        if wm and wm.is_restricted(name):
            return False, f"{name} is a restricted area"
        place = wm.get_place(name) if wm else None
        if place is None:
            return False, f"{name!r} is not a known destination"
        if place.get("kind") == "stairs" and not body.capabilities.can("stairs"):
            return False, "this body cannot traverse stairs"
        return True, "reachable"

    # planning ------------------------------------------------------------- #
    def plan(self, goal: Pose) -> list[Pose]:
        """Return a list of waypoints to the goal (straight line in the reference)."""
        return [goal]

    def localization_ok(self) -> bool:
        est = self.rt.state_estimator
        if est is None:
            return False
        return est.localization_confidence() >= MIN_LOCALIZATION_CONFIDENCE

    # collision monitor ---------------------------------------------------- #
    def is_path_blocked(self) -> tuple[bool, float | None]:
        """Independent forward-collision check (spec §12.8)."""
        backend = self.rt.backend
        if backend is None:
            return False, None
        faults = getattr(backend, "_faults", {})
        if "path_blocked" in faults:
            return True, float(faults["path_blocked"].get("distance", 2.4))
        scan = backend.lidar_scan()
        if scan:
            # forward sector = middle third of the scan
            n = len(scan)
            forward = scan[n // 3 : 2 * n // 3]
            nearest = min(forward) if forward else None
            if nearest is not None and nearest < COLLISION_STOP_M:
                return True, nearest
        return False, None

    def diagnostics(self) -> list[DiagnosticStatus]:
        conf_ok = self.localization_ok()
        blocked, dist = self.is_path_blocked()
        level = DiagnosticLevel.OK
        msg = f"{len(self.known_places())} destinations; localization {'ok' if conf_ok else 'low'}"
        if not conf_ok:
            level = DiagnosticLevel.WARN
        return [
            DiagnosticStatus(
                name="navigation/status",
                level=level,
                message=msg,
                values={
                    "known_places": self.known_places(),
                    "localization_ok": conf_ok,
                    "path_blocked": blocked,
                    "obstacle_distance_m": dist,
                },
            )
        ]

    def as_report(self) -> dict[str, Any]:
        return {"known_places": self.known_places(), "localization_ok": self.localization_ok()}
