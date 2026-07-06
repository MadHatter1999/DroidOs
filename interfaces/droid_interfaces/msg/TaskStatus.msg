# Task status (spec §12.10, §29).
string task_id
string intent
string user
string state                 # created|running|succeeded|failed|cancelled
string[] steps
string error
builtin_interfaces/Time started
builtin_interfaces/Time finished
