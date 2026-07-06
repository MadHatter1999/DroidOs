"""``droid-perception`` (spec §12.6).

Processes the droid's sensors and produces structured observations with an
explicit confidence. Critically, it separates *observation* from *interpretation*
(spec §38): it reports what was measured and its confidence, and does not invent
meaning the sensors cannot support. If the camera is unavailable it says so rather
than fabricating a scene (spec §27, §39).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core.errors import DroidError
from ..core.models import DiagnosticLevel, DiagnosticStatus
from .lifecycle import ManagedService

if TYPE_CHECKING:
    from ..system import Runtime


class Perception(ManagedService):
    requires = ("safety_gateway",)

    def __init__(self, rt: "Runtime") -> None:
        super().__init__("perception", rt)

    def has_camera(self) -> bool:
        body = self.rt.body
        return bool(body and body.capabilities.has_perception("front_camera"))

    def describe(self) -> dict[str, Any]:
        """Answer 'what can you see?' with a structured, honest observation."""
        if not self.has_camera():
            return {"camera_ok": False, "summary": "this body has no camera", "objects": []}
        scene = self.rt.backend.describe_scene()
        if not scene.get("camera_ok", False):
            return {
                "camera_ok": False,
                "summary": "front camera is not responding",
                "objects": [],
                "confidence": 0.0,
            }
        objects = scene.get("objects", [])
        people = scene.get("people", [])
        parts = [o["label"] for o in objects]
        summary = ", ".join(parts) if parts else "nothing identifiable"
        if people:
            nearest = min(p["distance_m"] for p in people)
            summary += f"; {len(people)} person(s), nearest ~{nearest:.1f} m"
        return {
            "camera_ok": True,
            "summary": summary,
            "objects": objects,
            "people": people,
            "confidence": scene.get("confidence", 0.0),
        }

    def inspect(self, target: str) -> dict[str, Any]:
        """Inspect a named target and report measured indicators (spec §38)."""
        if not self.has_camera():
            raise DroidError("this body has no camera; cannot inspect a visual target")
        scene = self.rt.backend.describe_scene()
        if not scene.get("camera_ok", False):
            raise DroidError("front camera is not responding; cannot verify the target")
        match = None
        for obj in scene.get("objects", []):
            if target.lower() in obj["label"].lower():
                match = obj
                break
        if match is None:
            return {
                "found": False,
                "target": target,
                "confidence": scene.get("confidence", 0.0),
                "note": f"{target!r} not currently in view",
            }
        result: dict[str, Any] = {
            "found": True,
            "target": match["label"],
            "distance_m": match.get("distance_m"),
            "confidence": scene.get("confidence", 0.0),
        }
        if "indicators" in match:
            result["indicators"] = match["indicators"]
        if "open_cabinet_door" in match:
            result["open_cabinet_door"] = match["open_cabinet_door"]
        return result

    def diagnostics(self) -> list[DiagnosticStatus]:
        if not self.has_camera():
            return [DiagnosticStatus("perception/camera", DiagnosticLevel.OK, "no camera on this body")]
        ok = self.rt.backend.describe_scene().get("camera_ok", False)
        return [
            DiagnosticStatus(
                name="perception/camera/front",
                level=DiagnosticLevel.OK if ok else DiagnosticLevel.ERROR,
                message="front camera streaming" if ok else "front camera not responding",
            )
        ]
