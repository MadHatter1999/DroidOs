"""The ``droid-body-manager`` service (spec §12.3).

Loads and validates the installed body: reads the manifest, loads the robot
description and component files, verifies required hardware, publishes
capabilities and physical limits, selects the simulation or physical backend,
and rejects incompatible hardware configurations. Invalid body or gait-policy
files prevent activation (spec §40).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.config import Config
from ..core.errors import BodyError
from ..util import miniyaml
from .capabilities import Capabilities
from .manifest import BodyLimits, BodyManifest, SensorSpec


DEFAULT_BODY_SELECTION: dict[str, Any] = {
    "body_id": "ig-mk1",
    "backend": "simulation",
    "simulation_engine": "mujoco",
    "hardware_profile": "canfd-v1",
}


@dataclass
class LoadedBody:
    manifest: BodyManifest
    capabilities: Capabilities
    limits: BodyLimits
    sensors: list[SensorSpec]
    controllers: dict[str, Any]
    diagnostic_rules: dict[str, Any]
    backend_kind: str  # "simulation" | "physical"
    issues: list[str] = field(default_factory=list)

    @property
    def body_id(self) -> str:
        return self.manifest.body_id

    @property
    def name(self) -> str:
        return self.manifest.name

    def required_sensor_ids(self) -> list[str]:
        return list(self.manifest.required_sensors)

    def sensor_ids(self) -> list[str]:
        return [s.id for s in self.sensors]

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_id": self.manifest.body_id,
            "name": self.manifest.name,
            "model_family": self.manifest.model_family,
            "revision": self.manifest.revision,
            "interface_revision": self.manifest.interface_revision,
            "locomotion_type": self.manifest.locomotion_type,
            "hardware_profile": self.manifest.hardware_profile,
            "backend": self.backend_kind,
            "required_sensors": self.manifest.required_sensors,
            "required_actuators": self.manifest.required_actuators,
            "capabilities": self.capabilities.to_dict(),
            "issues": self.issues,
        }


class BodyManager:
    """Discovers, loads, validates and selects body packages."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.paths = config.paths

    # discovery / selection ------------------------------------------------ #
    def available_bodies(self) -> list[str]:
        base = self.paths.bodies_dir
        if not base.is_dir():
            return []
        return sorted(p.name for p in base.iterdir() if (p / "manifest.yaml").exists())

    def selection(self) -> dict[str, Any]:
        """Current body selection from state, falling back to shipped default."""
        for path in (self.paths.body_select_file, self.paths.default_body_select_file):
            if path.exists():
                data = miniyaml.load_file(str(path)) or {}
                if isinstance(data, dict) and data.get("body_id"):
                    merged = dict(DEFAULT_BODY_SELECTION)
                    merged.update(data)
                    return merged
        return dict(DEFAULT_BODY_SELECTION)

    def set_active(self, body_id: str, backend: str | None = None) -> dict[str, Any]:
        """Persist a new active body selection (spec §20). Validates it loads first."""
        if body_id not in self.available_bodies():
            raise BodyError(
                f"unknown body {body_id!r}; available: {', '.join(self.available_bodies()) or 'none'}"
            )
        selection = self.selection()
        selection["body_id"] = body_id
        if backend:
            if backend not in ("simulation", "physical"):
                raise BodyError(f"backend must be 'simulation' or 'physical', got {backend!r}")
            selection["backend"] = backend
        # validate it actually loads before committing
        self.load(body_id, selection["backend"])
        text = miniyaml.dump(selection)
        self.paths.body_select_file.write_text(text, encoding="utf-8")
        return selection

    # loading -------------------------------------------------------------- #
    def load_active(self) -> LoadedBody:
        sel = self.selection()
        return self.load(sel["body_id"], sel.get("backend", "simulation"))

    def load(self, body_id: str, backend_kind: str = "simulation") -> LoadedBody:
        directory = self.paths.bodies_dir / body_id
        if not directory.is_dir():
            raise BodyError(f"body package not found: {directory}")
        manifest = BodyManifest.load(directory)

        caps = Capabilities.from_dict(manifest.load_component("capabilities") or {})
        limits = BodyLimits.from_dict(manifest.load_component("limits") or {})

        sensors_doc = manifest.load_component("sensors") or {}
        sensor_list = sensors_doc.get("sensors", []) if isinstance(sensors_doc, dict) else []
        sensors = [SensorSpec.from_dict(s) for s in sensor_list]

        controllers = manifest.load_component("controllers") or {}
        diag_rules_doc = manifest.load_component("diagnostic_rules") or {}
        diag_rules = (
            diag_rules_doc.get("rules", {}) if isinstance(diag_rules_doc, dict) else {}
        )

        body = LoadedBody(
            manifest=manifest,
            capabilities=caps,
            limits=limits,
            sensors=sensors,
            controllers=controllers if isinstance(controllers, dict) else {},
            diagnostic_rules=diag_rules,
            backend_kind=backend_kind,
        )
        body.issues = self._static_validate(body)
        return body

    # validation ----------------------------------------------------------- #
    def _static_validate(self, body: LoadedBody) -> list[str]:
        """Checks that do not require a live backend (spec §20, §25)."""
        issues: list[str] = []
        m = body.manifest

        # every required sensor must be declared in sensors.yaml
        declared = set(body.sensor_ids())
        for req in m.required_sensors:
            if req not in declared:
                issues.append(f"required sensor {req!r} is not declared in sensors.yaml")

        # capability/locomotion coherence
        loco = body.capabilities.category("locomotion")
        if m.locomotion_type == "biped" and loco.get("walk") is False:
            issues.append("biped locomotion_type but capabilities.locomotion.walk is false")
        if m.locomotion_type in ("differential", "omni", "tracked") and loco.get("roll") is False:
            issues.append(f"{m.locomotion_type} locomotion_type but capabilities.roll is false")

        # gait policy validation for walking bodies (spec §25)
        if m.locomotion_type == "biped":
            gp = m.gait_policy
            if gp is None:
                issues.append("biped body has no gait_policy declared")
            else:
                if not gp.checksum:
                    issues.append("gait policy has no checksum")
                if gp.supported_body_revision and gp.supported_body_revision != m.revision:
                    issues.append(
                        f"gait policy is for revision {gp.supported_body_revision!r}, "
                        f"body is {m.revision!r}"
                    )
                if body.backend_kind == "physical" and not gp.approved_for_physical:
                    issues.append("gait policy is not approved for physical operation")

        # signature must be present; a placeholder is flagged but not fatal in the
        # reference implementation (production verifies against the signing key).
        if not m.signature or str(m.signature.get("value", "")).startswith("PLACEHOLDER"):
            issues.append("body signature is a placeholder (not verified in reference build)")

        return issues
