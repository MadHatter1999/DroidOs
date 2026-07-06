"""Body abstraction: manifest, capability registry and the body manager.

A *body package* (``bodies/<id>/``) fully describes one droid body. The core
brain is body-independent (spec §20); replacing the body package + hardware
backend is enough to move the brain to a different robot.
"""

from .capabilities import Capabilities
from .manifest import BodyManifest, BodyLimits, SensorSpec
from .loader import BodyManager, LoadedBody

__all__ = [
    "Capabilities",
    "BodyManifest",
    "BodyLimits",
    "SensorSpec",
    "BodyManager",
    "LoadedBody",
]
