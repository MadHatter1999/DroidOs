"""Body manifest, limits and sensor specifications (spec §20, §24, §27)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.errors import BodyError
from ..util import miniyaml


@dataclass
class SensorSpec:
    id: str
    type: str
    topic: str
    rate_hz: float = 0.0
    required: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SensorSpec":
        known = {"id", "type", "topic", "rate_hz", "required"}
        return cls(
            id=d["id"],
            type=d.get("type", "unknown"),
            topic=d.get("topic", ""),
            rate_hz=float(d.get("rate_hz", 0) or 0),
            required=bool(d.get("required", False)),
            extra={k: v for k, v in d.items() if k not in known},
        )


@dataclass
class BodyLimits:
    battery: dict[str, Any] = field(default_factory=dict)
    thermal: dict[str, Any] = field(default_factory=dict)
    velocity: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    joints: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BodyLimits":
        d = d or {}
        return cls(
            battery=d.get("battery", {}) or {},
            thermal=d.get("thermal", {}) or {},
            velocity=d.get("velocity", {}) or {},
            payload=d.get("payload", {}) or {},
            joints=d.get("joints", {}) or {},
        )

    def battery_motion_minimum(self) -> float:
        return float(self.battery.get("motion_minimum_percent", 20.0))

    def motor_fault_temp(self) -> float:
        return float(self.thermal.get("motor_fault_temp_c", 85.0))

    def motor_warn_temp(self) -> float:
        return float(self.thermal.get("motor_warn_temp_c", 70.0))

    def max_linear(self) -> float:
        return float(self.velocity.get("max_linear_mps", 0.0) or 0.0)

    def max_angular(self) -> float:
        return float(self.velocity.get("max_angular_rps", 0.0) or 0.0)


@dataclass
class GaitPolicySpec:
    file: str
    checksum: str = ""
    format: str = "onnx"
    control_rate_hz: float = 0.0
    supported_body_revision: str = ""
    approved_for_physical: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "GaitPolicySpec | None":
        if not d:
            return None
        return cls(
            file=d.get("file", ""),
            checksum=d.get("checksum", ""),
            format=d.get("format", "onnx"),
            control_rate_hz=float(d.get("control_rate_hz", 0) or 0),
            supported_body_revision=str(d.get("supported_body_revision", "")),
            approved_for_physical=bool(d.get("approved_for_physical", False)),
        )


@dataclass
class BodyManifest:
    body_id: str
    name: str
    model_family: str
    revision: str
    interface_revision: str
    locomotion_type: str
    description: str = ""
    hardware_profile: str = ""
    files: dict[str, str] = field(default_factory=dict)
    required_sensors: list[str] = field(default_factory=list)
    required_actuators: list[str] = field(default_factory=list)
    gait_policy: GaitPolicySpec | None = None
    signature: dict[str, Any] = field(default_factory=dict)
    directory: Path | None = None

    VALID_LOCOMOTION = {"biped", "differential", "omni", "tracked", "stationary", "manipulator"}

    @classmethod
    def load(cls, directory: Path) -> "BodyManifest":
        manifest_path = directory / "manifest.yaml"
        if not manifest_path.exists():
            raise BodyError(f"body package has no manifest.yaml: {directory}")
        data = miniyaml.load_file(str(manifest_path))
        if not isinstance(data, dict):
            raise BodyError(f"manifest.yaml is not a mapping: {manifest_path}")
        try:
            manifest = cls(
                body_id=data["body_id"],
                name=data.get("name", data["body_id"]),
                model_family=data.get("model_family", "unknown"),
                revision=str(data.get("revision", "")),
                interface_revision=str(data.get("interface_revision", "")),
                locomotion_type=data["locomotion_type"],
                description=str(data.get("description", "")).strip(),
                hardware_profile=data.get("hardware_profile", ""),
                files=data.get("files", {}) or {},
                required_sensors=list(data.get("required_sensors", []) or []),
                required_actuators=list(data.get("required_actuators", []) or []),
                gait_policy=GaitPolicySpec.from_dict(data.get("gait_policy")),
                signature=data.get("signature", {}) or {},
                directory=directory,
            )
        except KeyError as exc:
            raise BodyError(f"manifest.yaml missing required field: {exc}") from exc

        if manifest.locomotion_type not in cls.VALID_LOCOMOTION:
            raise BodyError(
                f"unknown locomotion_type {manifest.locomotion_type!r}; "
                f"expected one of {sorted(cls.VALID_LOCOMOTION)}"
            )
        return manifest

    def file_path(self, key: str) -> Path | None:
        name = self.files.get(key)
        if not name or self.directory is None:
            return None
        return self.directory / name

    def load_component(self, key: str) -> Any:
        path = self.file_path(key)
        if path is None or not path.exists():
            return None
        return miniyaml.load_file(str(path))
