# Safety-controller state (spec §12.2, §24). The safety MCU is authoritative for
# motor power; this message is a read-only report published by droid-safety-gateway.
bool   alive
bool   estop_engaged
bool   power_enabled       # motor-power contactor state (defaults false at boot)
bool   watchdog_ok
bool   movement_permitted
string[] faults
float32 last_host_contact_age_s
builtin_interfaces/Time stamp
