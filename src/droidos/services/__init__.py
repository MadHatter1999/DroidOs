"""DroidOS robot services (spec §12).

Each important service is a :class:`ManagedService` with an explicit lifecycle
(spec §11) so the supervisor can create and validate a component before allowing
it to operate.
"""
