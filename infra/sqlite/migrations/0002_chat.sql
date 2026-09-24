PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    deleted_at TEXT,
    UNIQUE (id, user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id, user_id)
        REFERENCES conversations (id, user_id)
);

CREATE INDEX IF NOT EXISTS messages_user_conversation_idx
ON messages (user_id, conversation_id, created_at)
WHERE status = 'completed';
