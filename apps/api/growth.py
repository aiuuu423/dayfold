from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import httpx

from apps.api.database import database_session, initialize_schema
from apps.api.entries import utc_now
from apps.api.memory import MEMORY_SCHEMA
from apps.api.provider_resilience import ProviderRequestError, bounded_post


GROWTH_SCHEMA = """
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
"""

GROWTH_SYSTEM_PROMPT = """
你是 Dayfold 的“最近的你”总结器。
只根据输入的结构化 Memory 证据，总结用户最近出现的一个变化或方向。
输出一到两句简洁中文，不要标题、列表、Markdown 或建议。
禁止补充证据中不存在的事实，禁止心理诊断，禁止绝对化推断。
如果证据不足以支持变化，只输出：正在积累你的记录。
""".strip()


class GrowthProviderUnavailable(ProviderRequestError):
    def __init__(
        self,
        kind="network",
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(kind, status_code=status_code)


class InvalidGrowthOutput(Exception):
    pass


class GrowthProvider(Protocol):
    async def generate(self, evidence: list[dict[str, str]]) -> str:
        ...


@dataclass(frozen=True)
class GrowthSummary:
    id: str
    content: str
    status: str
    created_at: str
    evidence: list[dict[str, str]]

    def public_view(self) -> dict[str, object]:
        return {
            "id": self.id,
            "status": self.status,
            "content": self.content,
            "created_at": self.created_at,
            "evidence": self.evidence,
        }


def validate_growth_content(content: object) -> str:
    if not isinstance(content, str):
        raise InvalidGrowthOutput
    normalized = content.strip()
    if not normalized or len(normalized) > 300:
        raise InvalidGrowthOutput
    return normalized


def has_enough_evidence(evidence: list[dict[str, str]]) -> bool:
    memory_ids = {item["memory_id"] for item in evidence}
    source_ids = {
        (item["source_type"], item["source_id"])
        for item in evidence
    }
    return len(memory_ids) >= 2 and len(source_ids) >= 2


class SqliteGrowthRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = str(database_path)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with database_session(self._database_path) as connection:
            initialize_schema(connection, MEMORY_SCHEMA)
            initialize_schema(connection, GROWTH_SCHEMA)

    def _connect(self):
        return database_session(self._database_path)

    async def collect_evidence(
        self,
        user_id: str,
        limit: int = 8,
    ) -> list[dict[str, str]]:
        await self.initialize()

        def select() -> list[sqlite3.Row]:
            with self._connect() as connection:
                return connection.execute(
                    """
                    SELECT m.id AS memory_id, m.type, m.content,
                           s.source_type, s.source_id
                    FROM memories AS m
                    JOIN memory_sources AS s
                      ON s.memory_id = m.id AND s.user_id = m.user_id
                    WHERE m.user_id = ?
                      AND m.status = 'active'
                      AND m.deleted_at IS NULL
                    ORDER BY m.updated_at DESC, m.rowid DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()

        rows = await asyncio.to_thread(select)
        return [
            {
                "memory_id": row["memory_id"],
                "type": row["type"],
                "content": row["content"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
            }
            for row in rows
        ]

    async def store(
        self,
        user_id: str,
        content: object,
        evidence: list[dict[str, str]],
    ) -> GrowthSummary:
        normalized = validate_growth_content(content)
        await self.initialize()
        summary = GrowthSummary(
            id=str(uuid4()),
            content=normalized,
            status="ready",
            created_at=utc_now(),
            evidence=evidence,
        )

        def insert() -> None:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO growth_summaries (
                        id, user_id, content, status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        summary.id,
                        user_id,
                        summary.content,
                        summary.status,
                        summary.created_at,
                    ),
                )
                for item in evidence:
                    connection.execute(
                        """
                        INSERT INTO growth_sources (
                            growth_id, user_id, memory_id,
                            source_type, source_id, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            summary.id,
                            user_id,
                            item["memory_id"],
                            item["source_type"],
                            item["source_id"],
                            summary.created_at,
                        ),
                    )

        await asyncio.to_thread(insert)
        return summary

    async def latest(self, user_id: str) -> GrowthSummary | None:
        await self.initialize()

        def select() -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
            with self._connect() as connection:
                summary = connection.execute(
                    """
                    SELECT id, content, status, created_at
                    FROM growth_summaries
                    WHERE user_id = ? AND deleted_at IS NULL
                    ORDER BY created_at DESC, rowid DESC
                    LIMIT 1
                    """,
                    (user_id,),
                ).fetchone()
                if summary is None:
                    return None, []
                sources = connection.execute(
                    """
                    SELECT gs.memory_id, m.type, m.content,
                           gs.source_type, gs.source_id
                    FROM growth_sources AS gs
                    JOIN memories AS m
                      ON m.id = gs.memory_id AND m.user_id = gs.user_id
                    WHERE gs.growth_id = ? AND gs.user_id = ?
                    ORDER BY gs.rowid
                    """,
                    (summary["id"], user_id),
                ).fetchall()
                return summary, sources

        row, source_rows = await asyncio.to_thread(select)
        if row is None:
            return None
        evidence = [
            {
                "memory_id": item["memory_id"],
                "type": item["type"],
                "content": item["content"],
                "source_type": item["source_type"],
                "source_id": item["source_id"],
            }
            for item in source_rows
        ]
        return GrowthSummary(
            id=row["id"],
            content=row["content"],
            status=row["status"],
            created_at=row["created_at"],
            evidence=evidence,
        )


class ArkGrowthProvider:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._model = model
        self._transport = transport

    async def generate(self, evidence: list[dict[str, str]]) -> str:
        payload = {
            "model": self._model,
            "max_tokens": 220,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": GROWTH_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        evidence,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                }
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
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return validate_growth_content(content)
        except ProviderRequestError as error:
            raise GrowthProviderUnavailable(
                error.kind,
                status_code=error.status_code,
            ) from error
        except (KeyError, TypeError) as error:
            raise GrowthProviderUnavailable("upstream") from error
