"""memory.py, reads/writes Rocky's SQLite memory.

Stores facts, preferences, project notes, etc. Never stores raw passwords; store
credential references only (see memory_schema.sql notes).
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(HERE, "memory_schema.sql")

VALID_KINDS = {
    "fact", "preference", "project_note", "warning", "system_state",
    "command_history", "file_reference", "conversation_summary",
    "credential_reference",
}


def db_path() -> str:
    return os.environ.get("ROCKY_DB", os.path.join(HERE, "rocky.db"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> str:
    """Create the SQLite database from memory_schema.sql. Idempotent."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        schema = fh.read()
    conn = connect()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
    return db_path()


def add(kind: str, content: str, *, tags=None, sensitivity: str = "normal",
        source: str = "user", confidence: float = 1.0) -> str:
    if kind not in VALID_KINDS:
        raise ValueError(f"unknown memory kind '{kind}'; valid: {sorted(VALID_KINDS)}")
    item_id = new_id("mem")
    ts = now()
    conn = connect()
    try:
        conn.execute(
            """INSERT INTO memory_items
               (id, kind, content, source, confidence, sensitivity, tags_json,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (item_id, kind, content, source, confidence, sensitivity,
             json.dumps(tags or []), ts, ts),
        )
        conn.commit()
    finally:
        conn.close()
    return item_id


def search(query: str, limit: int = 20) -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute(
            """SELECT id, kind, content, sensitivity, tags_json, created_at
               FROM memory_items
               WHERE content LIKE ? OR kind LIKE ? OR tags_json LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (f"%{query}%", f"%{query}%", f"%{query}%", limit),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
