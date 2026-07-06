"""Gait-policy loading, validation and inference (spec §25).

Two runtimes are supported behind one interface:

* **ONNX**, if the policy file is ``.onnx`` and ``onnxruntime`` is installed, the
  trained network is executed directly (portable exported form, spec §25).
* **JSON CPG fallback**, a dependency-free central-pattern-generator policy
  described in JSON, so the reference build runs a *real* joint-level gait without
  any ML runtime. This is what ships with the reference biped.

Whichever runtime, the loader enforces the spec's rejection rules before the
policy may drive physical motion.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..body.loader import LoadedBody


class GaitPolicyError(ValueError):
    """Raised when a gait policy is invalid for the body it is asked to drive."""


@dataclass
class GaitPolicy:
    body_id: str
    supported_body_revision: str
    control_rate_hz: float
    observation: list[str]
    action: list[str]
    safety_envelope: dict[str, float]
    runtime: str  # "onnx" | "cpg"
    checksum: str
    approved_for_physical: bool
    params: dict[str, Any] = field(default_factory=dict)
    _phase: float = 0.0
    _onnx: Any = None

    # inference ------------------------------------------------------------ #
    def infer(self, observation: dict[str, float], dt: float) -> dict[str, float]:
        """Return joint targets (radians) for one control step.

        The observation carries at least commanded ``cmd_vx`` / ``cmd_wz``. The
        result is clamped to the policy's safety envelope (spec §25).
        """
        self._phase = (self._phase + 2 * math.pi * self._step_freq() * dt) % (2 * math.pi)
        if self.runtime == "onnx" and self._onnx is not None:
            action = self._infer_onnx(observation)
        else:
            action = self._infer_cpg(observation)
        return self._apply_envelope(action)

    def _step_freq(self) -> float:
        return float(self.params.get("step_freq_hz", 1.4))

    def _infer_cpg(self, obs: dict[str, float]) -> dict[str, float]:
        vx = float(obs.get("cmd_vx", 0.0))
        gain = 0.0 if abs(vx) < 1e-3 else min(1.0, abs(vx) / 0.35)
        hip = float(self.params.get("hip_amp", 0.35)) * gain
        knee = float(self.params.get("knee_amp", 0.6)) * gain
        ankle = float(self.params.get("ankle_amp", 0.2)) * gain
        p = self._phase
        targets: dict[str, float] = {}
        # left leg leads by pi relative to right leg
        for side, off in (("left", 0.0), ("right", math.pi)):
            s = math.sin(p + off)
            c = math.cos(p + off)
            targets[f"{side}_hip_pitch"] = hip * s
            targets[f"{side}_knee"] = max(0.0, knee * (0.5 - 0.5 * c))
            targets[f"{side}_ankle"] = ankle * -s
        # keep only joints the policy declares
        return {j: targets.get(j, 0.0) for j in self.action}

    def _infer_onnx(self, obs: dict[str, float]) -> dict[str, float]:  # pragma: no cover
        vec = [float(obs.get(name, 0.0)) for name in self.observation]
        out = self._onnx.run(None, {"obs": [vec]})[0][0]
        return {j: float(v) for j, v in zip(self.action, out)}

    def _apply_envelope(self, action: dict[str, float]) -> dict[str, float]:
        lim = float(self.safety_envelope.get("max_action", 1.5))
        return {j: max(-lim, min(lim, v)) for j, v in action.items()}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_for_body(body: "LoadedBody") -> tuple["GaitPolicy | None", list[str]]:
    """Load and validate the body's gait policy. Returns (policy, issues).

    A non-empty issues list with the policy still returned means it loaded but is
    not cleared for physical operation; ``policy is None`` means it could not be
    used at all.
    """
    spec = body.manifest.gait_policy
    if spec is None:
        return None, ["body declares no gait policy"]

    directory = body.manifest.directory
    path = directory / spec.file if directory else None
    if path is None or not path.exists():
        return None, [f"gait policy file not found: {spec.file}"]

    issues: list[str] = []

    # 1. checksum (spec §25)
    actual = _sha256(path)
    if spec.checksum and spec.checksum != actual:
        return None, [f"gait policy checksum mismatch (expected {spec.checksum}, got {actual})"]

    # 2. load the descriptor
    if path.suffix == ".onnx":
        policy = _load_onnx(path, spec, actual)
    else:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return None, [f"gait policy is not valid JSON: {exc}"]
        policy = _load_cpg(doc, spec, actual)

    # 3. body match (spec §25)
    if policy.body_id and policy.body_id != body.body_id:
        return None, [f"gait policy is for body {policy.body_id!r}, not {body.body_id!r}"]
    if policy.supported_body_revision and policy.supported_body_revision != body.manifest.revision:
        issues.append(
            f"gait policy revision {policy.supported_body_revision!r} != body {body.manifest.revision!r}"
        )

    # 4. action joints must exist on the body
    have = set(body.manifest.required_actuators)
    missing = [j for j in policy.action if j not in have]
    if missing:
        issues.append(f"gait policy drives unknown joints: {', '.join(missing)}")

    # 5. required observation sensors available
    declared_sensors = {s.type for s in body.sensors}
    if "base_lin_vel" in policy.observation and "imu" not in declared_sensors:
        issues.append("gait policy needs an IMU but none is declared")

    # 6. physical approval (spec §25, §40)
    if body.backend_kind == "physical" and not policy.approved_for_physical:
        issues.append("gait policy is not approved for physical operation")

    return policy, issues


def _load_cpg(doc: dict[str, Any], spec, checksum: str) -> GaitPolicy:
    return GaitPolicy(
        body_id=doc.get("body_id", ""),
        supported_body_revision=doc.get("supported_body_revision", ""),
        control_rate_hz=float(doc.get("control_rate_hz", 0.0)),
        observation=list(doc.get("observation", [])),
        action=list(doc.get("action", [])),
        safety_envelope=doc.get("safety_envelope", {}) or {},
        runtime="cpg",
        checksum=checksum,
        approved_for_physical=bool(spec.approved_for_physical),
        params=doc.get("gait", {}) or {},
    )


def _load_onnx(path: Path, spec, checksum: str) -> GaitPolicy:  # pragma: no cover
    try:
        import onnxruntime  # type: ignore

        session = onnxruntime.InferenceSession(str(path))
    except Exception:
        session = None
    sidecar = path.with_suffix(".json")
    doc = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
    return GaitPolicy(
        body_id=doc.get("body_id", ""),
        supported_body_revision=doc.get("supported_body_revision", spec.supported_body_revision),
        control_rate_hz=spec.control_rate_hz,
        observation=list(doc.get("observation", [])),
        action=list(doc.get("action", [])),
        safety_envelope=doc.get("safety_envelope", {}) or {},
        runtime="onnx",
        checksum=checksum,
        approved_for_physical=bool(spec.approved_for_physical),
        params=doc.get("gait", {}) or {},
        _onnx=session,
    )
