"""DroidOS reference brain.

A runnable, dependency-free reference implementation of the DroidOS control
architecture described in ``documentation/SPEC.md``. It implements the top four
architectural layers (interaction, executive, robot services, body/hardware
abstraction) in software against a simulated hardware and safety backend.

The public entry points are the :mod:`droidos.cli.droid` (natural language)
and :mod:`droidos.cli.droidctl` (deterministic) command-line interfaces.
"""

__version__ = "1.0.0"

# Interface revision numbers used by droidctl / diagnostics (spec §35).
BODY_INTERFACE_REVISION = "1.0.0"
LANGUAGE_INTERFACE_REVISION = "1.0.0"

__all__ = ["__version__", "BODY_INTERFACE_REVISION", "LANGUAGE_INTERFACE_REVISION"]
