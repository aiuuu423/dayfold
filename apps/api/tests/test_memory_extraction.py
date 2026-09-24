import asyncio
import json
from pathlib import Path

import httpx
import pytest

from apps.api.demo import DemoSettings
from apps.api.chat import SqliteChatRepository
from apps.api.entries import SqliteEntryRepository
from apps.api.main import (
    app,
    get_demo_settings,
    get_memory_provider,
    get_memory_repository,
)
from apps.api.memory import (
    ArkMemoryExtractionProvider,
    MemoryProviderUnavailable,
    SqliteMemoryRepository,
)


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


class StubMemoryProvider:
    def __init__(self, operations):
        self.operations = operations
        self.source_content = None

    async def extract(self, source_content):
        self.source_content = source_content
        return self.operations


@pytest.fixture
def stores(tmp_path: Path):
    database_path = tmp_path / "dayfold-memory-test.sqlite3"
    entries = SqliteEntryRepository(database_path)
    memories = SqliteMemoryRepository(database_path)
    run(entries.initialize())
    run(memories.initialize())
    return database_path, entries, memories


@pytest.fixture(autouse=True)
def demo_dependencies(stores):
    _, _, memories = stores
    app.dependency_overrides[get_demo_settings] = lambda: DemoSettings(
        user_id=DEMO_USER_ID
    )
    app.dependency_overrides[get_memory_repository] = lambda: memories
    yield
    app.dependency_overrides.clear()


def test_extracts_valid_memories_and_binds_entry_source(stores):
    _, entries, memories = stores
    entry = run(
        entries.create(
            DEMO_USER_ID,
            "过去四个月我一直在练习手冲咖啡，现在最喜欢浅烘焙豆的花果香。",
            "2026-09-23T09:30:00Z",
        )
    )
    provider = StubMemoryProvider(
        [
            {
                "op": "upsert",
                "type": "interest",
                "content": "持续练习手冲咖啡，偏爱浅烘焙豆的花果香",
                "confidence": 0.96,
            }
        ]
    )
    app.dependency_overrides[get_memory_provider] = lambda: provider

    response = request(
        "POST",
        "/v1/memory-extractions",
        json={"source_type": "entry", "source_id": entry.id},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["source"] == {"type": "entry", "id": entry.id}
    assert payload["memories"][0]["type"] == "interest"
    assert payload["memories"][0]["confidence"] == 0.96
    assert "user_id" not in response.text
    assert provider.source_content == entry.content

    stored = run(memories.list(DEMO_USER_ID))
    assert len(stored) == 1
    assert stored[0].content == payload["memories"][0]["content"]
    assert run(memories.list_sources(DEMO_USER_ID, stored[0].id)) == [
        {"source_type": "entry", "source_id": entry.id}
    ]


def test_invalid_model_output_is_rejected_without_partial_storage(stores):
    _, entries, memories = stores
    entry = run(
        entries.create(
            DEMO_USER_ID,
            "我最近在学习咖啡。",
            "2026-09-23T09:30:00Z",
        )
    )
    provider = StubMemoryProvider(
        [
            {
                "op": "upsert",
                "type": "personality",
                "content": "喜欢咖啡",
                "confidence": 1.2,
            }
        ]
    )
    app.dependency_overrides[get_memory_provider] = lambda: provider

    response = request(
        "POST",
        "/v1/memory-extractions",
        json={"source_type": "entry", "source_id": entry.id},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_MODEL_OUTPUT"
    assert run(memories.list(DEMO_USER_ID)) == []


def test_cannot_extract_from_another_users_source(stores):
    _, entries, _ = stores
    entry = run(
        entries.create(
            OTHER_USER_ID,
            "另一个用户的私有记录。",
            "2026-09-23T09:30:00Z",
        )
    )
    provider = StubMemoryProvider([])
    app.dependency_overrides[get_memory_provider] = lambda: provider

    response = request(
        "POST",
        "/v1/memory-extractions",
        json={"source_type": "entry", "source_id": entry.id},
    )

    assert response.status_code == 404
    assert provider.source_content is None


def test_extracts_only_from_user_chat_messages(stores):
    database_path, _, memories = stores
    chats = SqliteChatRepository(database_path)
    conversation = run(chats.create_conversation(DEMO_USER_ID, "目标"))
    user_message = run(
        chats.add_message(
            DEMO_USER_ID,
            conversation.id,
            "user",
            "我决定转向 AI Agent 产品评测。",
        )
    )
    assistant_message = run(
        chats.add_message(
            DEMO_USER_ID,
            conversation.id,
            "assistant",
            "这是助手回复。",
        )
    )
    provider = StubMemoryProvider([])
    app.dependency_overrides[get_memory_provider] = lambda: provider

    accepted = request(
        "POST",
        "/v1/memory-extractions",
        json={"source_type": "message", "source_id": user_message.id},
    )
    rejected = request(
        "POST",
        "/v1/memory-extractions",
        json={"source_type": "message", "source_id": assistant_message.id},
    )

    assert accepted.status_code == 201
    assert provider.source_content == user_message.content
    assert rejected.status_code == 404
    assert run(memories.list(DEMO_USER_ID)) == []


def test_ark_memory_provider_parses_validated_json_response():
    captured = {"attempts": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["attempts"] += 1
        captured["payload"] = json.loads(request.content)
        captured["headers"] = request.headers
        if captured["attempts"] == 1:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "operations": [
                                        {
                                            "op": "upsert",
                                            "type": "goal",
                                            "content": "转向 AI Agent 产品评测",
                                            "confidence": 0.94,
                                        }
                                    ]
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    provider = ArkMemoryExtractionProvider(
        endpoint="https://ark.example/api/v3/chat/completions",
        api_key="server-secret",
        model="ep-standard-memory",
        system_prompt="只输出 JSON",
        transport=httpx.MockTransport(handler),
    )

    operations = run(provider.extract("我决定转向 AI Agent 产品评测。"))

    assert operations[0]["type"] == "goal"
    assert captured["payload"]["temperature"] == 0
    assert captured["payload"]["messages"] == [
        {"role": "system", "content": "只输出 JSON"},
        {"role": "user", "content": "我决定转向 AI Agent 产品评测。"}
    ]
    assert captured["headers"]["authorization"] == "Bearer server-secret"
    assert "x-api-key" not in captured["headers"]
    assert "anthropic-version" not in captured["headers"]
    assert captured["attempts"] == 2


def test_memory_provider_requires_standard_ark_configuration(monkeypatch):
    monkeypatch.setenv("DAYFOLD_LLM_API_KEY", "agent-plan-secret")
    monkeypatch.delenv("DAYFOLD_STANDARD_ARK_API_KEY", raising=False)
    monkeypatch.delenv("DAYFOLD_STANDARD_ARK_MODEL", raising=False)

    assert get_memory_provider() is None

    monkeypatch.setenv("DAYFOLD_STANDARD_ARK_API_KEY", "standard-secret")
    monkeypatch.setenv("DAYFOLD_STANDARD_ARK_MODEL", "ep-standard-memory")
    provider = get_memory_provider()

    assert isinstance(provider, ArkMemoryExtractionProvider)
    assert provider._api_key == "standard-secret"
    assert provider._model == "ep-standard-memory"
    assert (
        provider._endpoint
        == "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    )


def test_memory_timeout_returns_classified_gateway_timeout(stores):
    _, entries, _ = stores
    entry = run(
        entries.create(
            DEMO_USER_ID,
            "Portfolio Demo 虚构记录。",
            "2026-09-23T09:30:00Z",
        )
    )

    class TimeoutProvider:
        async def extract(self, source_content):
            raise MemoryProviderUnavailable("timeout")

    app.dependency_overrides[get_memory_provider] = lambda: TimeoutProvider()

    response = request(
        "POST",
        "/v1/memory-extractions",
        json={"source_type": "entry", "source_id": entry.id},
    )

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "LLM_TIMEOUT"
