# A proposed structured intent (spec §14). Produced by the language service, only
# ever a proposal until the command broker validates it.
string intent
string arguments_json        # JSON-encoded argument map
bool   requires_motion
string requested_speed       # cautious|normal
string requested_output      # text|spoken summary
string source                # offline|llm|llm-fallback
float32 confidence
