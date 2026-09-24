import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from apps.api.database import database_session, initialize_schema


ENTRY_SCHEMA = """
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
"""


class EntryVersionConflict(Exception):
    pass


@dataclass(frozen=True)
class Entry:
    id: str
    content: str
    occurred_at: str
    version: int
    created_at: str
    updated_at: str

    def public_view(self) -> dict[str, object]:
        return {
            "id": self.id,
            "content": self.content,
            "occurred_at": self.occurred_at,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SqliteEntryRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = str(database_path)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with database_session(self._database_path) as connection:
            initialize_schema(connection, ENTRY_SCHEMA)

    async def create(
        self,
        user_id: str,
        content: str,
        occurred_at: str,
    ) -> Entry:
        await self.initialize()
        entry_id = str(uuid4())
        now = utc_now()

        def insert() -> None:
            with database_session(self._database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO entries (
                        id, user_id, content, occurred_at, version,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    """,
                    (entry_id, user_id, content, occurred_at, now, now),
                )

        await asyncio.to_thread(insert)
        return Entry(entry_id, content, occurred_at, 1, now, now)

    async def list(self, user_id: str) -> list[Entry]:
        await self.initialize()

        def select() -> list[sqlite3.Row]:
            with database_session(self._database_path) as connection:
                return connection.execute(
                    """
                    SELECT id, content, occurred_at, version, created_at, updated_at
                    FROM entries
                    WHERE user_id = ? AND deleted_at IS NULL
                    ORDER BY occurred_at DESC, created_at DESC
                    """,
                    (user_id,),
                ).fetchall()

        rows = await asyncio.to_thread(select)
        return [self._to_entry(row) for row in rows]

    async def get(self, user_id: str, entry_id: str) -> Entry | None:
        await self.initialize()

        def select() -> sqlite3.Row | None:
            with database_session(self._database_path) as connection:
                return connection.execute(
                    """
                    SELECT id, content, occurred_at, version, created_at, updated_at
                    FROM entries
                    WHERE id = ? AND user_id = ? AND deleted_at IS NULL
                    """,
                    (entry_id, user_id),
                ).fetchone()

        row = await asyncio.to_thread(select)
        return self._to_entry(row) if row else None

    async def update(
        self,
        user_id: str,
        entry_id: str,
        content: str,
        expected_version: int,
    ) -> Entry | None:
        await self.initialize()
        now = utc_now()

        def update_row() -> int:
            with database_session(self._database_path) as connection:
                cursor = connection.execute(
                    """
                    UPDATE entries
                    SET content = ?, version = version + 1, updated_at = ?
                    WHERE id = ? AND user_id = ? AND deleted_at IS NULL
                      AND version = ?
                    """,
                    (content, now, entry_id, user_id, expected_version),
                )
                return cursor.rowcount

        changed = await asyncio.to_thread(update_row)
        if changed:
            return await self.get(user_id, entry_id)
        if await self.get(user_id, entry_id) is not None:
            raise EntryVersionConflict
        return None

    async def delete(self, user_id: str, entry_id: str) -> bool:
        await self.initialize()
        now = utc_now()

        def delete_row() -> int:
            with database_session(self._database_path) as connection:
                cursor = connection.execute(
                    """
                    UPDATE entries
                    SET deleted_at = ?, updated_at = ?
                    WHERE id = ? AND user_id = ? AND deleted_at IS NULL
                    """,
                    (now, now, entry_id, user_id),
                )
                return cursor.rowcount

        return bool(await asyncio.to_thread(delete_row))

    @staticmethod
    def _to_entry(row: sqlite3.Row) -> Entry:
        return Entry(
            id=row["id"],
            content=row["content"],
            occurred_at=row["occurred_at"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
