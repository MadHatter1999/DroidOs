"""audit.py, logs every action, decision, command, and result.

The audit log remembers. Uses the same SQLite database as memory.py.
"""

from __future__ import annotations

import json
from typing import Any

from memory import connect, new_id, now


def log(event_type: str, actor: str, message: str, data: dict | None = None) -> str:
    event_id = new_id("ev")
    conn = connect()
    try:
        conn.execute(
            """INSERT INTO audit_log (id, event_type, actor, message, data_json, created_at)
               VALUES (?,?,?,?,?,?)""",
            (event_id, event_type, actor, message, json.dumps(data or {}), now()),
        )
        conn.commit()
    finally:
        conn.close()
    return event_id


def record_action(action: dict[str, Any], decision: str, reason: str,
                  status: str = "proposed") -> str:
    action_id = new_id("act")
    ts = now()
    conn = connect()
    try:
        conn.execute(
            """INSERT INTO actions
               (id, kind, risk, needs_confirmation, payload_json, status, decision,
                reason, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (action_id, action.get("kind", ""), action.get("risk", ""),
             1 if action.get("needs_confirmation") else 0,
             json.dumps(action.get("payload", {})), status, decision, reason, ts, ts),
        )
        conn.commit()
    finally:
        conn.close()
    return action_id


def update_action_status(action_id: str, status: str) -> None:
    conn = connect()
    try:
        conn.execute(
            "UPDATE actions SET status = ?, updated_at = ? WHERE id = ?",
            (status, now(), action_id),
        )
        conn.commit()
    finally:
        conn.close()


def record_tool_call(action_id: str, tool_name: str, input_data: dict,
                     output_data: dict | None, exit_code: int | None,
                     started_at: str, finished_at: str | None) -> str:
    call_id = new_id("tc")
    conn = connect()
    try:
        conn.execute(
            """INSERT INTO tool_calls
               (id, action_id, tool_name, input_json, output_json, exit_code,
                started_at, finished_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (call_id, action_id, tool_name, json.dumps(input_data),
             json.dumps(output_data) if output_data is not None else None,
             exit_code, started_at, finished_at),
        )
        conn.commit()
    finally:
        conn.close()
    return call_id


def tail(limit: int = 20) -> list[dict]:
    """Recent actions with their decision and status (spec: 'audit tail')."""
    conn = connect()
    try:
        rows = conn.execute(
            """SELECT id, kind, risk, status, decision, reason, created_at
               FROM actions ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
