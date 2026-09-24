PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS growth_summaries (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ready', 'deleted')),
    created_at TEXT NOT NULL,
    deleted_at TEXT,
    UNIQUE (id, user_id)
);

CREATE TABLE IF NOT EXISTS growth_sources (
    growth_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('entry', 'message')),
    source_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (growth_id, memory_id, source_type, source_id),
    FOREIGN KEY (growth_id, user_id)
        REFERENCES growth_summaries (id, user_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS growth_summaries_user_created_idx
ON growth_summaries (user_id, created_at DESC)
WHERE deleted_at IS NULL;
