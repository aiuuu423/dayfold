PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('event', 'interest', 'goal')),
    content TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'disabled', 'deleted')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    UNIQUE (id, user_id)
);

CREATE TABLE IF NOT EXISTS memory_sources (
    memory_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('entry', 'message')),
    source_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (memory_id, source_type, source_id),
    FOREIGN KEY (memory_id, user_id)
        REFERENCES memories (id, user_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS memories_user_status_updated_idx
ON memories (user_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS memory_sources_user_source_idx
ON memory_sources (user_id, source_type, source_id);
