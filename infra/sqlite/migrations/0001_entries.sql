CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS entries_user_occurred_at_idx
ON entries (user_id, occurred_at DESC)
WHERE deleted_at IS NULL;
