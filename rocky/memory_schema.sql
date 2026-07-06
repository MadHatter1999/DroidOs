PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    sensitivity TEXT NOT NULL DEFAULT 'normal',
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    risk TEXT NOT NULL,
    needs_confirmation INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    decision TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input_json TEXT NOT NULL,
    output_json TEXT,
    exit_code INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY(action_id) REFERENCES actions(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    message TEXT NOT NULL,
    data_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_kind
    ON memory_items(kind);

CREATE INDEX IF NOT EXISTS idx_memory_content
    ON memory_items(content);

CREATE INDEX IF NOT EXISTS idx_actions_created_at
    ON actions(created_at);

CREATE INDEX IF NOT EXISTS idx_audit_created_at
    ON audit_log(created_at);
