"""Composition root: the ``Runtime`` shared context and the ``DroidSystem`` builder.

The reference brain runs as a single process rather than as separate ROS 2 nodes.
:class:`Runtime` is the shared context every service receives; :class:`DroidSystem`
wires the object graph and runs the boot sequence (spec §8) via the supervisor.

This module sits above ``core``, ``body``, ``backends``, ``services``,
``language`` and ``executive`` in the layering, so importing it pulls in the
whole brain without creating cycles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .backends.base import HardwareBackend
from .body.loader import BodyManager, LoadedBody
from .core.config import Config
from .core.events import EventBus
from .core.logging import AuditLog, Logger
from .core.states import StateMachine

if TYPE_CHECKING:
    from .services.lifecycle import ManagedService
    from .services.safety_gateway import SafetyGateway


class Runtime:
    """Mutable shared context passed to every service."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.paths = config.paths
        self.log = Logger("droidos", log_file=config.paths.log_dir / "droidos.log")
        self.audit = AuditLog(config.paths.audit_log_file)
        self.bus = EventBus()
        self.state = StateMachine()
        self.body_manager = BodyManager(config)

        # populated during boot
        self.body: Optional[LoadedBody] = None
        self.backend: Optional[HardwareBackend] = None
        self.safety: Optional["SafetyGateway"] = None
        self._services: dict[str, "ManagedService"] = {}

    # service registry ----------------------------------------------------- #
    def register(self, service: "ManagedService") -> "ManagedService":
        self._services[service.name] = service
        return service

    def service(self, name: str) -> "ManagedService":
        return self._services[name]

    def has(self, name: str) -> bool:
        return name in self._services

    def all_services(self) -> list["ManagedService"]:
        return list(self._services.values())

    # typed convenience accessors (return base type; callers use duck typing) #
    @property
    def perception(self): return self._services.get("perception")

    @property
    def navigation(self): return self._services.get("navigation")

    @property
    def motion(self): return self._services.get("motion")

    @property
    def world_model(self): return self._services.get("world_model")

    @property
    def memory(self): return self._services.get("memory")

    @property
    def diagnostics(self): return self._services.get("diagnostics")

    @property
    def state_estimator(self): return self._services.get("state_estimator")

    @property
    def executive(self): return self._services.get("executive")

    @property
    def hardware(self): return self._services.get("hardware")

    @property
    def update(self): return self._services.get("update")

    @property
    def voice(self): return self._services.get("voice")


class DroidSystem:
    """Builds the full object graph and runs the boot sequence via the supervisor."""

    def __init__(self, rt: Runtime) -> None:
        self.rt = rt
        self.supervisor = rt.supervisor  # type: ignore[attr-defined]
        self.language = rt.language       # type: ignore[attr-defined]
        self.readiness = rt.supervisor.readiness  # type: ignore[attr-defined]

    # ---------------------------------------------------------------------- #
    @classmethod
    def boot(cls, config: Optional[Config] = None) -> "DroidSystem":
        # deferred imports keep this module importable even mid-build
        from .backends import make_backend
        from .executive.executive import Executive
        from .language.service import LanguageService
        from .services.diagnostics import Diagnostics
        from .services.hardware import Hardware
        from .services.memory import Memory
        from .services.motion import Motion
        from .services.navigation import Navigation
        from .services.perception import Perception
        from .services.safety_gateway import SafetyGateway
        from .services.state_estimator import StateEstimator
        from .services.supervisor import Supervisor
        from .services.update import Update
        from .services.voice import Voice
        from .services.world_model import WorldModel

        config = config or Config.load()
        rt = Runtime(config)

        # load the active body and construct the matching backend (spec §20)
        rt.body = rt.body_manager.load_active()
        selection = rt.body_manager.selection()
        rt.backend = make_backend(
            rt.body, rt.body.backend_kind, selection.get("hardware_backend")
        )

        # safety first: it is boot-critical and everything else depends on it
        rt.safety = SafetyGateway(rt)
        rt.register(rt.safety)

        # robot services (registered; the supervisor activates them in order)
        for svc in (
            Hardware(rt),
            Diagnostics(rt),
            StateEstimator(rt),
            WorldModel(rt),
            Memory(rt),
            Perception(rt),
            Navigation(rt),
            Motion(rt),
            Update(rt),
            Executive(rt),
        ):
            rt.register(svc)

        # language interaction layer (plain service, constructed after the rest)
        rt.language = LanguageService(rt)  # type: ignore[attr-defined]

        # voice service depends on the language + safety services above
        rt.register(Voice(rt))

        # supervisor drives the boot sequence (spec §8)
        supervisor = Supervisor(rt)
        rt.supervisor = supervisor  # type: ignore[attr-defined]
        supervisor.boot()

        return cls(rt)

    # convenience API ------------------------------------------------------ #
    def ask(self, text: str, user: str | None = None, confirmed: bool = False):
        return self.rt.language.process(text, user, confirmed)

    def shutdown(self) -> None:
        self.supervisor.request_shutdown()

