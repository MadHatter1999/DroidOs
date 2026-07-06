"""Filesystem layout and configuration loading (spec §15, §30).

On a real target the layout is fixed (``/etc/droidos``, ``/var/lib/droidos`` …).
For development the whole mutable tree is redirected under a single writable
*state root* so the reference brain runs from a checkout without root access.

Resolution order for each location (first hit wins):

* an explicit environment variable (``DROIDOS_CONFIG``, ``DROIDOS_BODIES`` …)
* the repository checkout, if one is detected (``bodies/`` + ``pyproject.toml``)
* the production path (``/etc/droidos`` …)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..util import miniyaml
from .errors import ConfigError


def _find_repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "bodies").is_dir():
            return parent
    # also try current working directory
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "bodies").is_dir() and (parent / "src" / "droidos").is_dir():
            return parent
    return None


@dataclass
class Paths:
    repo_root: Path | None
    config_dir: Path
    bodies_dir: Path
    state_dir: Path
    log_dir: Path
    run_dir: Path
    models_dir: Path

    @classmethod
    def resolve(cls) -> "Paths":
        repo = _find_repo_root()
        # state root: where mutable data lives
        state = Path(
            os.environ.get("DROIDOS_STATE")
            or (str(repo / "run-state") if repo else "/var/lib/droidos")
        )
        config = Path(
            os.environ.get("DROIDOS_CONFIG")
            or (str(repo / "config") if repo else "/etc/droidos")
        )
        bodies = Path(
            os.environ.get("DROIDOS_BODIES")
            or (str(repo / "bodies") if repo else "/usr/lib/droidos/bodies")
        )
        models = Path(
            os.environ.get("DROIDOS_MODELS")
            or (str(repo / "models") if repo else "/var/lib/droidos/models")
        )
        log = Path(os.environ.get("DROIDOS_LOG") or str(state / "log"))
        run = Path(os.environ.get("DROIDOS_RUN") or str(state / "run"))
        paths = cls(repo, config, bodies, state, log, run, models)
        paths.ensure_writable()
        return paths

    def ensure_writable(self) -> None:
        for p in (self.state_dir, self.log_dir, self.run_dir):
            try:
                p.mkdir(parents=True, exist_ok=True)
            except OSError as exc:  # pragma: no cover
                raise ConfigError(f"cannot create writable dir {p}: {exc}") from exc

    # convenience file locations ------------------------------------------- #
    @property
    def system_config_file(self) -> Path:
        return self.config_dir / "droidos.yaml"

    @property
    def body_select_file(self) -> Path:
        # mutable body selection lives in state; falls back to shipped default
        return self.state_dir / "body.yaml"

    @property
    def default_body_select_file(self) -> Path:
        return self.config_dir / "body.yaml"

    @property
    def memory_file(self) -> Path:
        return self.state_dir / "memory.json"

    @property
    def world_model_file(self) -> Path:
        return self.state_dir / "world_model.json"

    @property
    def safety_latch_file(self) -> Path:
        return self.state_dir / "safety_latch.json"

    @property
    def audit_log_file(self) -> Path:
        return self.log_dir / "audit.jsonl"

    @property
    def users_file(self) -> Path:
        return self.config_dir / "users.yaml"


DEFAULT_SYSTEM_CONFIG: dict[str, Any] = {
    "identity": {
        "name": "IG-12",
        "model_family": "assassin_droid",
        "voice_profile": "mechanical_01",
        "personality_profile": "dry_literal",
        "verbosity": "concise",
        "wake_names": ["IG-12", "droid"],
    },
    "language": {
        "primary_provider": "offline",
        "fallback_provider": "offline",
        "providers": {
            "offline": {"type": "offline"},
            "local": {
                "type": "llama_cpp",
                "endpoint": "unix:///run/droidos/llm.sock",
                "model": "/var/lib/droidos/models/default.gguf",
            },
        },
    },
    "safety": {
        "battery_motion_minimum_percent": 20.0,
        "motor_warn_temp_c": 70.0,
        "motor_fault_temp_c": 85.0,
    },
    "default_user": "operator",
}


@dataclass
class Config:
    paths: Paths
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Config":
        paths = Paths.resolve()
        data = dict(DEFAULT_SYSTEM_CONFIG)
        if paths.system_config_file.exists():
            loaded = miniyaml.load_file(str(paths.system_config_file)) or {}
            if not isinstance(loaded, dict):
                raise ConfigError("droidos.yaml must be a mapping")
            data = _deep_merge(data, loaded)
        return cls(paths=paths, data=data)

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    @property
    def identity(self) -> dict[str, Any]:
        return self.data.get("identity", {})

    @property
    def language(self) -> dict[str, Any]:
        return self.data.get("language", {})

    @property
    def safety(self) -> dict[str, Any]:
        return self.data.get("safety", {})


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, val in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out
