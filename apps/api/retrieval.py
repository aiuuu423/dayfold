from __future__ import annotations

import asyncio
import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from apps.api.database import database_session, initialize_schema
from apps.api.entries import utc_now
from apps.api.memory import Memory


VECTOR_SCHEMA = """
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
"""


class EmbeddingProviderUnavailable(Exception):
    pass


class InvalidEmbedding(Exception):
    pass


class EmbeddingProvider(Protocol):
    model: str
    dimensions: int

    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


@dataclass(frozen=True)
class RetrievalMatch:
    memory: Memory
    score: float

    def public_view(self) -> dict[str, object]:
        return {
            "memory": self.memory.public_view(),
            "score": round(self.score, 6),
        }


def validate_vectors(
    vectors: object,
    expected_count: int,
    expected_dimensions: int,
) -> list[list[float]]:
    if not isinstance(vectors, list) or len(vectors) != expected_count:
        raise InvalidEmbedding

    validated: list[list[float]] = []
    for vector in vectors:
        if not isinstance(vector, list) or len(vector) != expected_dimensions:
            raise InvalidEmbedding
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in vector
        ):
            raise InvalidEmbedding
        normalized = [float(value) for value in vector]
        if math.sqrt(sum(value * value for value in normalized)) == 0:
            raise InvalidEmbedding
        validated.append(normalized)
    return validated


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise InvalidEmbedding
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise InvalidEmbedding
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


class SqliteVectorRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = str(database_path)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with database_session(self._database_path) as connection:
            initialize_schema(connection, VECTOR_SCHEMA)

    def _connect(self):
        return database_session(self._database_path)

    async def list_unembedded(
        self,
        user_id: str,
        model: str,
        dimensions: int,
    ) -> list[Memory]:
        await self.initialize()

        def select() -> list[sqlite3.Row]:
            with self._connect() as connection:
                return connection.execute(
                    """
                    SELECT m.id, m.type, m.content, m.confidence, m.status,
                           m.created_at, m.updated_at
                    FROM memories AS m
                    LEFT JOIN memory_embeddings AS e
                      ON e.memory_id = m.id
                     AND e.user_id = m.user_id
                     AND e.schema_version = 1
                     AND e.model = ?
                     AND e.dimensions = ?
                    WHERE m.user_id = ?
                      AND m.status = 'active'
                      AND m.deleted_at IS NULL
                      AND e.memory_id IS NULL
                    ORDER BY m.created_at, m.rowid
                    """,
                    (model, dimensions, user_id),
                ).fetchall()

        rows = await asyncio.to_thread(select)
        return [self._to_memory(row) for row in rows]

    async def store_many(
        self,
        user_id: str,
        memories: list[Memory],
        vectors: object,
        model: str,
        dimensions: int,
    ) -> None:
        validated = validate_vectors(vectors, len(memories), dimensions)
        await self.initialize()
        now = utc_now()

        def upsert() -> None:
            with self._connect() as connection:
                for memory, vector in zip(memories, validated):
                    connection.execute(
                        """
                        INSERT INTO memory_embeddings (
                            memory_id, user_id, schema_version, model,
                            dimensions, embedding, updated_at
                        )
                        VALUES (?, ?, 1, ?, ?, ?, ?)
                        ON CONFLICT(memory_id, schema_version) DO UPDATE SET
                            user_id = excluded.user_id,
                            model = excluded.model,
                            dimensions = excluded.dimensions,
                            embedding = excluded.embedding,
                            updated_at = excluded.updated_at
                        """,
                        (
                            memory.id,
                            user_id,
                            model,
                            dimensions,
                            json.dumps(vector, separators=(",", ":")),
                            now,
                        ),
                    )

        await asyncio.to_thread(upsert)

    async def search(
        self,
        user_id: str,
        query_vector: list[float],
        model: str,
        dimensions: int,
        limit: int,
    ) -> list[RetrievalMatch]:
        validated_query = validate_vectors([query_vector], 1, dimensions)[0]
        await self.initialize()

        def select() -> list[sqlite3.Row]:
            with self._connect() as connection:
                return connection.execute(
                    """
                    SELECT m.id, m.type, m.content, m.confidence, m.status,
                           m.created_at, m.updated_at, e.embedding
                    FROM memory_embeddings AS e
                    JOIN memories AS m
                      ON m.id = e.memory_id AND m.user_id = e.user_id
                    WHERE e.user_id = ?
                      AND e.schema_version = 1
                      AND e.model = ?
                      AND e.dimensions = ?
                      AND m.status = 'active'
                      AND m.deleted_at IS NULL
                    """,
                    (user_id, model, dimensions),
                ).fetchall()

        rows = await asyncio.to_thread(select)
        matches = [
            RetrievalMatch(
                memory=self._to_memory(row),
                score=cosine_similarity(
                    validated_query,
                    json.loads(row["embedding"]),
                ),
            )
            for row in rows
        ]
        return sorted(matches, key=lambda match: match.score, reverse=True)[:limit]

    async def count(self, user_id: str) -> int:
        await self.initialize()

        def select() -> int:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM memory_embeddings
                    WHERE user_id = ?
                    """,
                    (user_id,),
                ).fetchone()
                return int(row["count"])

        return await asyncio.to_thread(select)

    @staticmethod
    def _to_memory(row: sqlite3.Row) -> Memory:
        return Memory(
            id=row["id"],
            type=row["type"],
            content=row["content"],
            confidence=row["confidence"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class ArkEmbeddingProvider:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        dimensions: int = 1024,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self._transport = transport

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            vectors: list[list[float]] = []
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=httpx.Timeout(120.0, connect=10.0),
            ) as client:
                for text in texts:
                    response = await client.post(
                        self._endpoint,
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "input": [{"type": "text", "text": text}],
                            "dimensions": self.dimensions,
                            "encoding_format": "float",
                        },
                    )
                    if response.status_code != 200:
                        raise EmbeddingProviderUnavailable
                    data = response.json().get("data")
                    if isinstance(data, list):
                        data = data[0] if len(data) == 1 else None
                    if not isinstance(data, dict):
                        raise InvalidEmbedding
                    vector = validate_vectors(
                        [data.get("embedding")],
                        1,
                        self.dimensions,
                    )[0]
                    vectors.append(vector)
            return vectors
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise EmbeddingProviderUnavailable from error
