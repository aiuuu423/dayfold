PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS memory_embeddings (
    memory_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedding TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (memory_id, schema_version),
    FOREIGN KEY (memory_id, user_id)
        REFERENCES memories (id, user_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS memory_embeddings_user_model_idx
ON memory_embeddings (user_id, model, dimensions);
