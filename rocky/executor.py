"""executor.py, runs approved actions using safe argv arrays.

The executor is not the policy. It assumes the caller (rockyctl) already asked the
policy and, for anything needing confirmation, got it. It NEVER uses a shell:
commands run as argv lists, so shell metacharacters cannot be interpreted.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

import memory

DEFAULT_TIMEOUT_S = 30


def run(action: dict[str, Any], action_id: str = "act_unknown") -> dict[str, Any]:
    kind = action.get("kind", "")
    handler = _HANDLERS.get(kind)
    if handler is None:
        return _fail(action_id, kind, f"no executor for kind '{kind}'")
    start = time.monotonic()
    try:
        result = handler(action, action_id)
    except Exception as exc:  # noqa: BLE001 - report, never crash the CLI
        return _fail(action_id, kind, f"{type(exc).__name__}: {exc}",
                     duration_ms=_ms(start))
    result.setdefault("duration_ms", _ms(start))
    return result


# --------------------------------------------------------------------------- #
def _run_command(action, action_id) -> dict[str, Any]:
    p = action.get("payload", {}) or {}
    command = p.get("command")
    if not command or not isinstance(command, str):
        return _fail(action_id, "debian.command", "missing/invalid 'command'")
    args = [str(a) for a in (p.get("args") or [])]
    cwd = p.get("cwd") or None
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [command, *args],          # argv only, no shell, no shell=True
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=p.get("timeout", DEFAULT_TIMEOUT_S),
            shell=False,
        )
    except FileNotFoundError:
        return _fail(action_id, "debian.command", f"command not found: {command}")
    except subprocess.TimeoutExpired:
        return _fail(action_id, "debian.command", "command timed out")
    return {
        "ok": proc.returncode == 0,
        "action_id": action_id,
        "kind": "debian.command",
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_ms": _ms(start),
    }


def _file_read(action, action_id) -> dict[str, Any]:
    path = (action.get("payload") or {}).get("path")
    if not path:
        return _fail(action_id, "file.read", "missing 'path'")
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    return _ok(action_id, "file.read", stdout=content)


def _file_write(action, action_id) -> dict[str, Any]:
    p = action.get("payload", {}) or {}
    path, content = p.get("path"), p.get("content", "")
    if not path:
        return _fail(action_id, "file.write", "missing 'path'")
    mode = "a" if p.get("mode") == "append" else "w"
    with open(path, mode, encoding="utf-8") as fh:
        fh.write(content)
    return _ok(action_id, "file.write", stdout=f"wrote {len(content)} bytes to {path}")


def _file_delete(action, action_id) -> dict[str, Any]:
    path = (action.get("payload") or {}).get("path")
    if not path:
        return _fail(action_id, "file.delete", "missing 'path'")
    os.remove(path)
    return _ok(action_id, "file.delete", stdout=f"deleted {path}")


def _memory_write(action, action_id) -> dict[str, Any]:
    p = action.get("payload", {}) or {}
    mem_id = memory.add(
        kind=p.get("kind", "fact"),
        content=p.get("content", ""),
        tags=p.get("tags"),
        sensitivity=p.get("sensitivity", "normal"),
        source="rocky",
    )
    return _ok(action_id, "memory.write", stdout=mem_id)


def _memory_search(action, action_id) -> dict[str, Any]:
    p = action.get("payload", {}) or {}
    results = memory.search(p.get("query", ""))
    import json
    return _ok(action_id, "memory.search", stdout=json.dumps(results, indent=2))


def _notify(action, action_id) -> dict[str, Any]:
    msg = (action.get("payload") or {}).get("message", "")
    print(msg)
    return _ok(action_id, action.get("kind", "notify"), stdout=msg)


_HANDLERS = {
    "debian.command": _run_command,
    "file.read": _file_read,
    "file.write": _file_write,
    "file.delete": _file_delete,
    "memory.write": _memory_write,
    "memory.search": _memory_search,
    "notify": _notify,
    "speak": _notify,
}


# --------------------------------------------------------------------------- #
def _ok(action_id, kind, stdout="") -> dict[str, Any]:
    return {"ok": True, "action_id": action_id, "kind": kind,
            "exit_code": 0, "stdout": stdout, "stderr": ""}


def _fail(action_id, kind, stderr, duration_ms=0) -> dict[str, Any]:
    return {"ok": False, "action_id": action_id, "kind": kind,
            "exit_code": 1, "stdout": "", "stderr": stderr, "duration_ms": duration_ms}


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
