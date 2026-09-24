import asyncio
import json
import sqlite3
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import httpx

from apps.api.database import database_session, initialize_schema
from apps.api.entries import utc_now
from apps.api.provider_resilience import (
    ProviderRequestError,
    bounded_stream,
    classify_transport_error,
)


CHAT_SCHEMA = """
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
"""

CHAT_SYSTEM_PROMPT = (
    "你是 Dayfold，一位克制、温和的日记陪伴助手。"
    "只根据当前对话回答，不假装记得未提供的信息。"
    "避免诊断和绝对化结论，使用简洁自然的中文。"
)


class ProviderUnavailable(ProviderRequestError):
    def __init__(
        self,
        kind="network",
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(kind, status_code=status_code)


class ChatProvider(Protocol):
    async def stream(
        self,
        messages: list[dict[str, str]],
        memory_context: str | None = None,
    ) -> AsyncIterator[str]:
        ...


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    created_at: str

    def public_view(self) -> dict[str, str]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class Message:
    id: str
    conversation_id: str
    role: str
    content: str
    status: str
    created_at: str

    def public_view(self) -> dict[str, str]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "status": self.status,
            "created_at": self.created_at,
        }


class SqliteChatRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = str(database_path)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with database_session(self._database_path) as connection:
            initialize_schema(connection, CHAT_SCHEMA)

    def _connect(self):
        return database_session(self._database_path)

    async def create_conversation(
        self,
        user_id: str,
        title: str,
    ) -> Conversation:
        await self.initialize()
        conversation = Conversation(str(uuid4()), title, utc_now())

        def insert() -> None:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO conversations (id, user_id, title, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        conversation.id,
                        user_id,
                        conversation.title,
                        conversation.created_at,
                    ),
                )

        await asyncio.to_thread(insert)
        return conversation

    async def get_conversation(
        self,
        user_id: str,
        conversation_id: str,
    ) -> Conversation | None:
        await self.initialize()

        def select() -> sqlite3.Row | None:
            with self._connect() as connection:
                return connection.execute(
                    """
                    SELECT id, title, created_at
                    FROM conversations
                    WHERE id = ? AND user_id = ? AND deleted_at IS NULL
                    """,
                    (conversation_id, user_id),
                ).fetchone()

        row = await asyncio.to_thread(select)
        if row is None:
            return None
        return Conversation(row["id"], row["title"], row["created_at"])

    async def list_messages(
        self,
        user_id: str,
        conversation_id: str,
    ) -> list[Message]:
        await self.initialize()

        def select() -> list[sqlite3.Row]:
            with self._connect() as connection:
                return connection.execute(
                    """
                    SELECT id, conversation_id, role, content, status, created_at
                    FROM messages
                    WHERE user_id = ? AND conversation_id = ?
                      AND status = 'completed'
                    ORDER BY created_at, rowid
                    """,
                    (user_id, conversation_id),
                ).fetchall()

        rows = await asyncio.to_thread(select)
        return [
            Message(
                row["id"],
                row["conversation_id"],
                row["role"],
                row["content"],
                row["status"],
                row["created_at"],
            )
            for row in rows
        ]

    async def add_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
    ) -> Message | None:
        await self.initialize()
        message = Message(
            str(uuid4()),
            conversation_id,
            role,
            content,
            "completed",
            utc_now(),
        )

        def insert() -> int:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO messages (
                        id, user_id, conversation_id, role,
                        content, status, created_at
                    )
                    SELECT ?, ?, ?, ?, ?, ?, ?
                    WHERE EXISTS (
                        SELECT 1
                        FROM conversations
                        WHERE id = ? AND user_id = ? AND deleted_at IS NULL
                    )
                    """,
                    (
                        message.id,
                        user_id,
                        conversation_id,
                        role,
                        content,
                        message.status,
                        message.created_at,
                        conversation_id,
                        user_id,
                    ),
                )
                return cursor.rowcount

        return message if await asyncio.to_thread(insert) else None


class ArkChatProvider:
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

    async def stream(
        self,
        messages: list[dict[str, str]],
        memory_context: str | None = None,
    ) -> AsyncIterator[str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        system_prompt = CHAT_SYSTEM_PROMPT
        if memory_context:
            system_prompt += (
                "\n\n以下内容是系统从用户本人历史中检索到的长期记忆。"
                "仅在与当前问题直接相关时自然使用，不要声称看到了数据库，"
                "不要补充上下文中不存在的信息：\n"
                f"{memory_context}"
            )
        payload = {
            "model": self._model,
            "max_tokens": 800,
            "temperature": 0.4,
            "stream": True,
            "system": system_prompt,
            "messages": messages,
        }

        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=httpx.Timeout(80.0, connect=10.0),
            ) as client:
                response = await bounded_stream(
                    client,
                    self._endpoint,
                    headers=headers,
                    json=payload,
                )
                try:
                    async for line in response.aiter_lines():
                        text = self._parse_sse_line(line)
                        if text:
                            yield text
                finally:
                    await response.aclose()
        except ProviderRequestError as error:
            raise ProviderUnavailable(
                error.kind,
                status_code=error.status_code,
            ) from error
        except httpx.RequestError as error:
            failure = classify_transport_error(error)
            raise ProviderUnavailable(
                failure.kind,
                status_code=failure.status_code,
            ) from error
        except (ValueError, KeyError, TypeError) as error:
            raise ProviderUnavailable("upstream") from error

    @staticmethod
    def _parse_sse_line(line: str) -> str | None:
        if not line.startswith("data:"):
            return None
        raw_data = line.removeprefix("data:").strip()
        if not raw_data or raw_data == "[DONE]":
            return None
        payload: dict[str, Any] = json.loads(raw_data)
        delta = payload.get("delta")
        if isinstance(delta, dict) and delta.get("type") == "text_delta":
            text = delta.get("text")
            return text if isinstance(text, str) else None
        return None
