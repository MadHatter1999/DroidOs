"""``droid-world-model`` (spec §12.7).

Maintains the droid's current understanding of the world: named destinations,
fixed objects, temporary obstacles, charging locations, restricted areas and
last-seen object locations, each with a confidence and timestamp. Persisted to
state so named places survive reboots.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from ..core.models import DiagnosticLevel, DiagnosticStatus
from .lifecycle import ManagedService

if TYPE_CHECKING:
    from ..system import Runtime


DEFAULT_WORLD: dict[str, Any] = {
    "places": {
        "charging station": {"x": 0.0, "y": 0.0, "kind": "charge"},
        "hallway": {"x": 2.0, "y": 0.0, "kind": "passage"},
        "workshop": {"x": 4.0, "y": 1.0, "kind": "room"},
        "stairs": {"x": 3.0, "y": -2.0, "kind": "stairs"},
    },
    "restricted": [],
    "obstacles": [],
    "last_seen": {},
}


class WorldModel(ManagedService):
    def __init__(self, rt: "Runtime") -> None:
        super().__init__("world_model", rt)
        self.data: dict[str, Any] = json.loads(json.dumps(DEFAULT_WORLD))

    def _on_configure(self) -> bool:
        self._load()
        return True

    # places --------------------------------------------------------------- #
    def places(self) -> dict[str, Any]:
        return dict(self.data["places"])

    def place_names(self) -> list[str]:
        return sorted(self.data["places"].keys())

    def get_place(self, name: str) -> dict[str, Any] | None:
        return self.data["places"].get(_norm(name))

    def add_place(self, name: str, x: float, y: float, kind: str = "room") -> None:
        self.data["places"][_norm(name)] = {"x": float(x), "y": float(y), "kind": kind}
        self._save()

    def remove_place(self, name: str) -> bool:
        if _norm(name) in self.data["places"]:
            del self.data["places"][_norm(name)]
            self._save()
            return True
        return False

    def is_restricted(self, name: str) -> bool:
        return _norm(name) in {_norm(r) for r in self.data.get("restricted", [])}

    def add_restricted(self, name: str) -> None:
        self.data.setdefault("restricted", []).append(_norm(name))
        self._save()

    # observations --------------------------------------------------------- #
    def note_object(self, label: str, x: float, y: float, confidence: float) -> None:
        self.data.setdefault("last_seen", {})[label] = {
            "x": x, "y": y, "confidence": confidence, "stamp": time.time(),
        }
        self._save()

    def set_obstacle(self, x: float, y: float) -> None:
        self.data.setdefault("obstacles", []).append({"x": x, "y": y, "stamp": time.time()})
        self._save()

    def clear_obstacles(self) -> None:
        self.data["obstacles"] = []
        self._save()

    # diagnostics ---------------------------------------------------------- #
    def diagnostics(self) -> list[DiagnosticStatus]:
        return [
            DiagnosticStatus(
                name="world_model/places",
                level=DiagnosticLevel.OK,
                message=f"{len(self.data['places'])} known places",
                values={"places": self.place_names()},
            )
        ]

    # persistence ---------------------------------------------------------- #
    def _load(self) -> None:
        path = self.rt.paths.world_model_file
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except (OSError, json.JSONDecodeError):
                pass

    def _save(self) -> None:
        try:
            self.rt.paths.world_model_file.write_text(
                json.dumps(self.data, indent=2), encoding="utf-8"
            )
        except OSError:
            pass


def _norm(name: str) -> str:
    return " ".join(str(name).strip().lower().split())
