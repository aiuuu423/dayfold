from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4

import httpx

from apps.api.database import database_session, initialize_schema
from apps.api.entries import utc_now
from apps.api.provider_resilience import ProviderRequestError, bounded_post


MEMORY_TYPES = frozenset({"event", "interest", "goal"})
SOURCE_TYPES = frozenset({"entry", "message"})

MEMORY_SCHEMA = """
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
"""


class MemoryProviderUnavailable(ProviderRequestError):
    def __init__(
        self,
        kind="network",
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(kind, status_code=status_code)


class InvalidModelOutput(Exception):
    pass


class MemoryExtractionProvider(Protocol):
    async def extract(self, source_content: str) -> list[dict[str, Any]]:
        ...


@dataclass(frozen=True)
class Memory:
    id: str
    type: str
    content: str
    confidence: float
    status: str
    created_at: str
    updated_at: str

    def public_view(self) -> dict[str, object]:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "confidence": self.confidence,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def validate_operations(
    operations: object,
) -> list[dict[str, str | float]]:
    if not isinstance(operations, list):
        raise InvalidModelOutput

    validated: list[dict[str, str | float]] = []
    seen: set[tuple[str, str]] = set()
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") != "upsert":
            raise InvalidModelOutput
        memory_type = operation.get("type")
        content = operation.get("content")
        confidence = operation.get("confidence")
        if memory_type not in MEMORY_TYPES:
            raise InvalidModelOutput
        if not isinstance(content, str) or not content.strip() or len(content) > 500:
            raise InvalidModelOutput
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            raise InvalidModelOutput
        key = (memory_type, content.strip())
        if key in seen:
            continue
        seen.add(key)
        validated.append(
            {
                "type": memory_type,
                "content": content.strip(),
                "confidence": float(confidence),
            }
        )
    return validated


class SqliteMemoryRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = str(database_path)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with database_session(self._database_path) as connection:
            initialize_schema(connection, MEMORY_SCHEMA)

    def _connect(self):
        return database_session(self._database_path)

    async def get_source_content(
        self,
        user_id: str,
        source_type: Literal["entry", "message"],
        source_id: str,
    ) -> str | None:
        await self.initialize()

        def select() -> sqlite3.Row | None:
            with self._connect() as connection:
                try:
                    if source_type == "entry":
                        return connection.execute(
                            """
                            SELECT content
                            FROM entries
                            WHERE id = ? AND user_id = ? AND deleted_at IS NULL
                            """,
                            (source_id, user_id),
                        ).fetchone()
                    return connection.execute(
                        """
                        SELECT content
                        FROM messages
                        WHERE id = ? AND user_id = ? AND role = 'user'
                          AND status = 'completed'
                        """,
                        (source_id, user_id),
                    ).fetchone()
                except sqlite3.OperationalError:
                    return None

        row = await asyncio.to_thread(select)
        return row["content"] if row else None

    async def store_extraction(
        self,
        user_id: str,
        source_type: Literal["entry", "message"],
        source_id: str,
        operations: object,
    ) -> list[Memory]:
        validated = validate_operations(operations)
        await self.initialize()
        now = utc_now()
        memories = [
            Memory(
                id=str(uuid4()),
                type=str(operation["type"]),
                content=str(operation["content"]),
                confidence=float(operation["confidence"]),
                status="active",
                created_at=now,
                updated_at=now,
            )
            for operation in validated
        ]

        def insert_all() -> None:
            with self._connect() as connection:
                for memory in memories:
                    connection.execute(
                        """
                        INSERT INTO memories (
                            id, user_id, type, content, confidence,
                            status, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            memory.id,
                            user_id,
                            memory.type,
                            memory.content,
                            memory.confidence,
                            memory.status,
                            memory.created_at,
                            memory.updated_at,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO memory_sources (
                            memory_id, user_id, source_type, source_id, created_at
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (memory.id, user_id, source_type, source_id, now),
                    )

        await asyncio.to_thread(insert_all)
        return memories

    async def list(self, user_id: str) -> list[Memory]:
        await self.initialize()

        def select() -> list[sqlite3.Row]:
            with self._connect() as connection:
                return connection.execute(
                    """
                    SELECT id, type, content, confidence, status,
                           created_at, updated_at
                    FROM memories
                    WHERE user_id = ? AND deleted_at IS NULL
                    ORDER BY updated_at DESC, rowid DESC
                    """,
                    (user_id,),
                ).fetchall()

        rows = await asyncio.to_thread(select)
        return [
            Memory(
                id=row["id"],
                type=row["type"],
                content=row["content"],
                confidence=row["confidence"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def get(self, user_id: str, memory_id: str) -> Memory | None:
        await self.initialize()

        def select() -> sqlite3.Row | None:
            with self._connect() as connection:
                return connection.execute(
                    """
                    SELECT id, type, content, confidence, status,
                           created_at, updated_at
                    FROM memories
                    WHERE id = ? AND user_id = ? AND deleted_at IS NULL
                    """,
                    (memory_id, user_id),
                ).fetchone()

        row = await asyncio.to_thread(select)
        if row is None:
            return None
        return Memory(
            id=row["id"],
            type=row["type"],
            content=row["content"],
            confidence=row["confidence"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def disable(self, user_id: str, memory_id: str) -> Memory | None:
        await self.initialize()
        now = utc_now()

        def update() -> int:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE memories
                    SET status = 'disabled', updated_at = ?
                    WHERE id = ? AND user_id = ? AND deleted_at IS NULL
                    """,
                    (now, memory_id, user_id),
                )
                if cursor.rowcount and self._table_exists(
                    connection,
                    "memory_embeddings",
                ):
                    connection.execute(
                        """
                        DELETE FROM memory_embeddings
                        WHERE memory_id = ? AND user_id = ?
                        """,
                        (memory_id, user_id),
                    )
                return cursor.rowcount

        changed = await asyncio.to_thread(update)
        return await self.get(user_id, memory_id) if changed else None

    async def delete(self, user_id: str, memory_id: str) -> bool:
        await self.initialize()
        now = utc_now()

        def delete_memory() -> int:
            with self._connect() as connection:
                exists = connection.execute(
                    """
                    SELECT 1
                    FROM memories
                    WHERE id = ? AND user_id = ? AND deleted_at IS NULL
                    """,
                    (memory_id, user_id),
                ).fetchone()
                if exists is None:
                    return 0

                if self._table_exists(connection, "memory_embeddings"):
                    connection.execute(
                        """
                        DELETE FROM memory_embeddings
                        WHERE memory_id = ? AND user_id = ?
                        """,
                        (memory_id, user_id),
                    )
                if self._table_exists(connection, "growth_sources"):
                    growth_rows = connection.execute(
                        """
                        SELECT DISTINCT growth_id
                        FROM growth_sources
                        WHERE memory_id = ? AND user_id = ?
                        """,
                        (memory_id, user_id),
                    ).fetchall()
                    connection.execute(
                        """
                        DELETE FROM growth_sources
                        WHERE memory_id = ? AND user_id = ?
                        """,
                        (memory_id, user_id),
                    )
                    if self._table_exists(connection, "growth_summaries"):
                        for row in growth_rows:
                            connection.execute(
                                """
                                UPDATE growth_summaries
                                SET status = 'deleted', deleted_at = ?
                                WHERE id = ? AND user_id = ?
                                """,
                                (now, row["growth_id"], user_id),
                            )
                connection.execute(
                    """
                    DELETE FROM memory_sources
                    WHERE memory_id = ? AND user_id = ?
                    """,
                    (memory_id, user_id),
                )
                cursor = connection.execute(
                    """
                    UPDATE memories
                    SET status = 'deleted', deleted_at = ?, updated_at = ?
                    WHERE id = ? AND user_id = ? AND deleted_at IS NULL
                    """,
                    (now, now, memory_id, user_id),
                )
                return cursor.rowcount

        return bool(await asyncio.to_thread(delete_memory))

    async def list_sources(
        self,
        user_id: str,
        memory_id: str,
    ) -> list[dict[str, str]]:
        await self.initialize()

        def select() -> list[sqlite3.Row]:
            with self._connect() as connection:
                return connection.execute(
                    """
                    SELECT source_type, source_id
                    FROM memory_sources
                    WHERE memory_id = ? AND user_id = ?
                    ORDER BY created_at, rowid
                    """,
                    (memory_id, user_id),
                ).fetchall()

        rows = await asyncio.to_thread(select)
        return [
            {"source_type": row["source_type"], "source_id": row["source_id"]}
            for row in rows
        ]

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
        row = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table_name,),
        ).fetchone()
        return row is not None


class ArkMemoryExtractionProvider:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        system_prompt: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._model = model
        self._system_prompt = system_prompt
        self._transport = transport

    async def extract(self, source_content: str) -> list[dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": 600,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": source_content},
            ],
        }
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=httpx.Timeout(80.0, connect=10.0),
            ) as client:
                response = await bounded_post(
                    client,
                    self._endpoint,
                    headers=headers,
                    json=payload,
                )
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            parsed = self._parse_json_text(text)
            operations = parsed.get("operations")
            if not isinstance(operations, list):
                raise InvalidModelOutput
            return operations
        except ProviderRequestError as error:
            raise MemoryProviderUnavailable(
                error.kind,
                status_code=error.status_code,
            ) from error
        except (KeyError, TypeError) as error:
            raise MemoryProviderUnavailable("upstream") from error

    @staticmethod
    def _parse_json_text(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise InvalidModelOutput
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as error:
            raise InvalidModelOutput from error
        if not isinstance(parsed, dict):
            raise InvalidModelOutput
        return parsed
