import asyncio
import json
from pathlib import Path

import httpx
import pytest

from apps.api.chat import ArkChatProvider, ProviderUnavailable, SqliteChatRepository
from apps.api.demo import DemoSettings
from apps.api.main import (
    app,
    get_chat_provider,
    get_chat_repository,
    get_demo_settings,
    get_embedding_provider,
    get_memory_repository,
    get_vector_repository,
)
from apps.api.memory import SqliteMemoryRepository
from apps.api.retrieval import SqliteVectorRepository


DEMO_USER_ID = "00000000-0000-4000-8000-000000000001"
OTHER_USER_ID = "00000000-0000-4000-8000-000000000002"


def run(coro):
    return asyncio.run(coro)


def request(method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


class StubChatProvider:
    def __init__(self, chunks=None, error: Exception | None = None):
        self.chunks = chunks or []
        self.error = error
        self.received_messages = []
        self.memory_context = None

    async def stream(self, messages, memory_context=None):
        self.received_messages = messages
        self.memory_context = memory_context
        if self.error:
            raise self.error
        for chunk in self.chunks:
            yield chunk


@pytest.fixture
def repository(tmp_path: Path):
    store = SqliteChatRepository(tmp_path / "dayfold-chat-test.sqlite3")
    run(store.initialize())
    return store


@pytest.fixture(autouse=True)
def demo_dependencies(repository):
    app.dependency_overrides[get_demo_settings] = lambda: DemoSettings(
        user_id=DEMO_USER_ID
    )
    app.dependency_overrides[get_chat_repository] = lambda: repository
    yield
    app.dependency_overrides.clear()


def test_multi_turn_chat_streams_and_persists_messages(repository):
    provider = StubChatProvider(["你之前提到过，", "正在重新思考职业方向。"])
    app.dependency_overrides[get_chat_provider] = lambda: provider

    created = request("POST", "/v1/conversations", json={"title": "职业方向"})
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    streamed = request(
        "POST",
        f"/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "最近工作让我有点迷茫。"},
    )

    assert streamed.status_code == 200
    assert streamed.headers["content-type"].startswith("text/event-stream")
    assert "event: message.start" in streamed.text
    assert streamed.text.count("event: message.delta") == 2
    assert "event: message.done" in streamed.text

    history = request("GET", f"/v1/conversations/{conversation_id}/messages")
    assert history.status_code == 200
    messages = history.json()["items"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "你之前提到过，正在重新思考职业方向。"
    assert provider.received_messages == [
        {"role": "user", "content": "最近工作让我有点迷茫。"}
    ]

    second_provider = StubChatProvider(["可以先做一个小实验。"])
    app.dependency_overrides[get_chat_provider] = lambda: second_provider
    request(
        "POST",
        f"/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "我可以怎么开始？"},
    )
    assert [message["role"] for message in second_provider.received_messages] == [
        "user",
        "assistant",
        "user",
    ]


def test_stream_reports_provider_error_without_fake_assistant_message(repository):
    provider = StubChatProvider(error=ProviderUnavailable())
    app.dependency_overrides[get_chat_provider] = lambda: provider
    conversation = run(repository.create_conversation(DEMO_USER_ID, "失败测试"))

    response = request(
        "POST",
        f"/v1/conversations/{conversation.id}/messages/stream",
        json={"content": "请回答我。"},
    )

    assert response.status_code == 200
    assert "event: message.error" in response.text
    assert "LLM_UNAVAILABLE" in response.text
    messages = run(repository.list_messages(DEMO_USER_ID, conversation.id))
    assert [message.role for message in messages] == ["user"]


def test_repository_hides_another_users_conversation(repository):
    conversation = run(repository.create_conversation(OTHER_USER_ID, "私有会话"))

    assert run(repository.get_conversation(DEMO_USER_ID, conversation.id)) is None
    assert run(repository.list_messages(DEMO_USER_ID, conversation.id)) == []


def test_chat_automatically_retrieves_relevant_active_memory(tmp_path):
    database_path = tmp_path / "dayfold-recall-test.sqlite3"
    chats = SqliteChatRepository(database_path)
    memories = SqliteMemoryRepository(database_path)
    vectors = SqliteVectorRepository(database_path)
    run(chats.initialize())
    run(memories.initialize())
    run(vectors.initialize())

    career = run(
        memories.store_extraction(
            DEMO_USER_ID,
            "entry",
            "career-entry",
            [
                {
                    "op": "upsert",
                    "type": "goal",
                    "content": "想转向 AI Agent 产品评测",
                    "confidence": 0.96,
                }
            ],
        )
    )[0]
    run(
        memories.store_extraction(
            DEMO_USER_ID,
            "entry",
            "coffee-entry",
            [
                {
                    "op": "upsert",
                    "type": "interest",
                    "content": "持续学习手冲咖啡",
                    "confidence": 0.94,
                }
            ],
        )
    )
    run(
        memories.store_extraction(
            OTHER_USER_ID,
            "entry",
            "other-entry",
            [
                {
                    "op": "upsert",
                    "type": "goal",
                    "content": "另一个用户也想转向 AI Agent 产品评测",
                    "confidence": 0.99,
                }
            ],
        )
    )

    class RecallEmbeddingProvider:
        model = "recall-test"
        dimensions = 3

        async def embed(self, texts):
            mapping = {
                "想转向 AI Agent 产品评测": [1.0, 0.0, 0.0],
                "持续学习手冲咖啡": [0.0, 1.0, 0.0],
                "最近工作让我很迷茫，之前的职业方向是什么？": [
                    0.34,
                    0.10,
                    0.935,
                ],
            }
            return [mapping[text] for text in texts]

    provider = StubChatProvider(["你之前提到过，想转向 AI Agent 产品评测。"])
    app.dependency_overrides[get_chat_repository] = lambda: chats
    app.dependency_overrides[get_memory_repository] = lambda: memories
    app.dependency_overrides[get_vector_repository] = lambda: vectors
    app.dependency_overrides[get_embedding_provider] = lambda: RecallEmbeddingProvider()
    app.dependency_overrides[get_chat_provider] = lambda: provider

    conversation = request(
        "POST",
        "/v1/conversations",
        json={"title": "职业方向"},
    ).json()
    streamed = request(
        "POST",
        f"/v1/conversations/{conversation['id']}/messages/stream",
        json={"content": "最近工作让我很迷茫，之前的职业方向是什么？"},
    )

    assert streamed.status_code == 200
    assert career.id in streamed.text
    assert '"type": "goal"' in streamed.text
    assert provider.memory_context is not None
    assert "想转向 AI Agent 产品评测" in provider.memory_context
    assert "持续学习手冲咖啡" not in provider.memory_context
    assert "另一个用户" not in provider.memory_context
    assert run(vectors.count(DEMO_USER_ID)) == 2
    assert run(vectors.count(OTHER_USER_ID)) == 0


def test_ark_provider_sends_server_side_key_and_parses_sse():
    captured = {"attempts": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["attempts"] += 1
        captured["authorization"] = request.headers.get("authorization")
        captured["x_api_key"] = request.headers.get("x-api-key")
        captured["payload"] = json.loads(request.content)
        if captured["attempts"] == 1:
            return httpx.Response(503)
        body = (
            'event: content_block_delta\n'
            'data: {"type":"content_block_delta","delta":{"type":"text_delta",'
            '"text":"你好"}}\n\n'
            'event: content_block_delta\n'
            'data: {"type":"content_block_delta","delta":{"type":"text_delta",'
            '"text":"。"}}\n\n'
        )
        return httpx.Response(200, text=body)

    provider = ArkChatProvider(
        endpoint="https://ark.example/v1/messages",
        api_key="server-secret",
        model="doubao-seed-2-0-mini",
        transport=httpx.MockTransport(handler),
    )

    async def collect():
        return [
            chunk
            async for chunk in provider.stream(
                [{"role": "user", "content": "测试"}],
                "[goal] 想转向 AI Agent 产品评测",
            )
        ]

    assert run(collect()) == ["你好", "。"]
    assert captured["authorization"] == "Bearer server-secret"
    assert captured["x_api_key"] == "server-secret"
    assert captured["payload"]["stream"] is True
    assert captured["payload"]["messages"] == [{"role": "user", "content": "测试"}]
    assert "想转向 AI Agent 产品评测" in captured["payload"]["system"]
    assert captured["attempts"] == 2
