# Authoritative droid state (spec §9). Mirrors droidos.core.states.DroidState.
string state              # POWERED_OFF|BOOTING|HARDWARE_CHECK|SAFE_IDLE|READY|
                          # ACTIVE|DEGRADED|MOTION_INHIBITED|EMERGENCY_STOPPED|
                          # RECOVERY|SHUTTING_DOWN
string body_id
string backend            # simulation|physical
bool   motion_permitted
string[] inhibit_reasons  # why motion is disabled, if it is
float32 battery_percent
builtin_interfaces/Time stamp
