"""policy.py, takes an action and returns allow, ask_user, or deny.

The LLM proposes. The policy decides. This module never runs anything; it only
judges a typed action against capabilities.yaml and tool_registry.yaml plus the
risk rules in policy_rules.md.
"""

from __future__ import annotations

import os
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))

# Which capability each action needs. If a capability is disabled, the action is
# denied regardless of its stated risk.
_KIND_CAPABILITY = {
    "file.read": "file_read",
    "file.write": "file_write",
    "file.delete": "file_delete",
    "memory.write": "memory_write",
    "memory.search": "memory_read",
}

_PRIVILEGED_COMMANDS = {
    "sudo", "su", "systemctl", "service", "apt", "apt-get", "dpkg", "pip", "pip3",
    "mount", "umount", "useradd", "userdel", "usermod", "passwd", "reboot",
    "shutdown", "crontab",
}


# --------------------------------------------------------------------------- #
# minimal YAML loader (uses PyYAML if installed; otherwise parses the small
# subset used by our two config files: nested maps and simple lists)
# --------------------------------------------------------------------------- #
def _load_yaml(path: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except ImportError:
        with open(path, "r", encoding="utf-8") as fh:
            return _parse_simple_yaml(fh.read())


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small YAML subset our two config files use: nested maps and
    simple scalar lists. Not a general YAML parser."""
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))
    if not lines:
        return {}
    value, _ = _parse_block(lines, 0, lines[0][0])
    return value if isinstance(value, dict) else {}


def _parse_block(lines: list[tuple[int, str]], i: int, indent: int):
    if lines[i][1].startswith("- "):
        items: list[Any] = []
        while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
            items.append(_scalar(lines[i][1][2:].strip()))
            i += 1
        return items, i
    result: dict[str, Any] = {}
    while i < len(lines) and lines[i][0] == indent and not lines[i][1].startswith("- "):
        key, _, val = lines[i][1].partition(":")
        key, val = key.strip(), val.strip()
        if val:
            result[key] = _scalar(val)
            i += 1
        elif i + 1 < len(lines) and lines[i + 1][0] > indent:
            child, i = _parse_block(lines, i + 1, lines[i + 1][0])
            result[key] = child
        else:
            result[key] = None
            i += 1
    return result, i


def _scalar(token: str) -> Any:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    low = token.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", ""):
        return None
    return token


# --------------------------------------------------------------------------- #
def load_capabilities(path: str | None = None) -> dict[str, Any]:
    data = _load_yaml(path or os.path.join(HERE, "capabilities.yaml"))
    return data.get("capabilities", {}) if isinstance(data, dict) else {}


def load_registry(path: str | None = None) -> dict[str, Any]:
    return _load_yaml(path or os.path.join(HERE, "tool_registry.yaml"))


def command_string(action: dict[str, Any]) -> str:
    """Reconstruct a command string from a debian.command action, for pattern checks."""
    p = action.get("payload", {}) or {}
    parts = [str(p.get("command", ""))] + [str(a) for a in p.get("args", []) or []]
    return " ".join(parts).strip()


# --------------------------------------------------------------------------- #
def decide(action: dict[str, Any],
           capabilities: dict[str, Any] | None = None,
           registry: dict[str, Any] | None = None) -> dict[str, str]:
    """Return {'decision': allow|ask_user|deny, 'reason': str} for one action."""
    caps = capabilities if capabilities is not None else load_capabilities()
    reg = registry if registry is not None else load_registry()

    kind = action.get("kind", "")
    risk = action.get("risk", "")
    payload = action.get("payload", {}) or {}

    # 1. explicit forbidden risk
    if risk == "forbidden":
        return _d("deny", "risk is 'forbidden'")

    # 2. forbidden patterns (defense in depth against a mislabeled command)
    haystack = command_string(action) + " " + str(payload.get("content", ""))
    for pattern in reg.get("forbidden_patterns", []) or []:
        if pattern and pattern in haystack:
            return _d("deny", f"matches forbidden pattern: {pattern!r}")

    # 3. capability gating
    cap_name = _required_capability(kind, risk, payload, reg)
    if cap_name is not None:
        cap = caps.get(cap_name)
        if cap is None or not cap.get("enabled", False):
            return _d("deny", f"capability '{cap_name}' is disabled")

    # 4. command-level rules for debian.command
    if kind == "debian.command":
        base = str(payload.get("command", "")).strip()
        if not base:
            return _d("deny", "no command specified")
        allow = set(reg.get("debian_read_only_commands", []) or [])
        dangerous = set(reg.get("dangerous_commands", []) or [])
        if base in dangerous:
            return _d("ask_user", f"command '{base}' is potentially dangerous")
        if risk == "read_only" and base in allow:
            return _d("allow", f"'{base}' is an allowlisted read-only command")
        return _d("ask_user", f"'{base}' is not on the read-only allowlist")

    # 5. risk defaults for non-command actions
    if risk == "read_only":
        return _d("allow", "read-only action")
    return _d("ask_user", f"risk '{risk or 'unknown'}' requires confirmation")


def _required_capability(kind: str, risk: str, payload: dict, reg: dict) -> str | None:
    if kind == "debian.command":
        base = str(payload.get("command", "")).strip()
        if base in _PRIVILEGED_COMMANDS or risk == "privileged":
            return "privileged"
        if risk == "network":
            return "network"
        allow = set(reg.get("debian_read_only_commands", []) or [])
        if risk == "read_only" and base in allow:
            return "shell_read"
        return "shell_write"
    if risk == "network":
        return "network"
    return _KIND_CAPABILITY.get(kind)


def _d(decision: str, reason: str) -> dict[str, str]:
    return {"decision": decision, "reason": reason}
