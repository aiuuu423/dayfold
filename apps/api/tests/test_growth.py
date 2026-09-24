import asyncio
import json
from pathlib import Path

import httpx
import pytest

from apps.api.demo import DemoSettings
from apps.api.growth import (
    GROWTH_SYSTEM_PROMPT,
    ArkGrowthProvider,
    SqliteGrowthRepository,
)
from apps.api.main import (
    app,
    get_demo_settings,
    get_growth_provider,
    get_growth_repository,
    get_memory_repository,
)
from apps.api.memory import SqliteMemoryRepository


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


class StubGrowthProvider:
    def __init__(self, content="最近你开始从寻找唯一答案，转向主动尝试不同可能。"):
        self.content = content
        self.evidence = None

    async def generate(self, evidence):
        self.evidence = evidence
        return self.content


@pytest.fixture
def stores(tmp_path: Path):
    database_path = tmp_path / "dayfold-growth-test.sqlite3"
    memories = SqliteMemoryRepository(database_path)
    growth = SqliteGrowthRepository(database_path)
    run(memories.initialize())
    run(growth.initialize())
    return memories, growth


@pytest.fixture(autouse=True)
def demo_dependencies(stores):
    memories, growth = stores
    app.dependency_overrides[get_demo_settings] = lambda: DemoSettings(
        user_id=DEMO_USER_ID
    )
    app.dependency_overrides[get_memory_repository] = lambda: memories
    app.dependency_overrides[get_growth_repository] = lambda: growth
    yield
    app.dependency_overrides.clear()


def create_memory(memories, user_id, source_id, memory_type, content):
    return run(
        memories.store_extraction(
            user_id,
            "entry",
            source_id,
            [
                {
                    "op": "upsert",
                    "type": memory_type,
                    "content": content,
                    "confidence": 0.95,
                }
            ],
        )
    )[0]


def test_growth_returns_collecting_state_without_enough_evidence(stores):
    memories, growth = stores
    create_memory(
        memories,
        DEMO_USER_ID,
        "entry-1",
        "goal",
        "开始重新思考职业方向",
    )
    provider = StubGrowthProvider()
    app.dependency_overrides[get_growth_provider] = lambda: provider

    response = request("GET", "/v1/growth/current")

    assert response.status_code == 200
    assert response.json() == {
        "status": "collecting",
        "content": "正在积累你的记录。",
        "evidence": [],
    }
    assert provider.evidence is None
    assert run(growth.latest(DEMO_USER_ID)) is None


def test_growth_uses_real_tenant_evidence_and_persists_sources(stores):
    memories, growth = stores
    first = create_memory(
        memories,
        DEMO_USER_ID,
        "entry-1",
        "event",
        "开始重新思考职业方向",
    )
    second = create_memory(
        memories,
        DEMO_USER_ID,
        "entry-2",
        "goal",
        "决定尝试 AI Agent 产品评测",
    )
    create_memory(
        memories,
        OTHER_USER_ID,
        "other-entry",
        "goal",
        "另一个用户准备学习摄影",
    )
    provider = StubGrowthProvider()
    app.dependency_overrides[get_growth_provider] = lambda: provider

    response = request("GET", "/v1/growth/current")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["content"] == provider.content
    assert {item["memory_id"] for item in payload["evidence"]} == {
        first.id,
        second.id,
    }
    assert all(item["source_id"] in {"entry-1", "entry-2"} for item in payload["evidence"])
    assert "另一个用户" not in json.dumps(provider.evidence, ensure_ascii=False)

    stored = run(growth.latest(DEMO_USER_ID))
    assert stored is not None
    assert stored.content == provider.content
    assert {item["memory_id"] for item in stored.evidence} == {first.id, second.id}


def test_growth_rejects_empty_model_output_without_persisting(stores):
    memories, growth = stores
    create_memory(memories, DEMO_USER_ID, "entry-1", "event", "开始探索新方向")
    create_memory(memories, DEMO_USER_ID, "entry-2", "goal", "尝试产品评测")
    app.dependency_overrides[get_growth_provider] = lambda: StubGrowthProvider("  ")

    response = request("GET", "/v1/growth/current")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_GROWTH_OUTPUT"
    assert run(growth.latest(DEMO_USER_ID)) is None


def test_ark_growth_provider_sends_only_structured_evidence():
    captured = {"attempts": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["attempts"] += 1
        captured["payload"] = json.loads(request.content)
        captured["headers"] = request.headers
        if captured["attempts"] == 1:
            return httpx.Response(429)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "最近你开始从思考职业方向，转向尝试 AI Agent 产品评测。"
                        }
                    }
                ]
            },
        )

    provider = ArkGrowthProvider(
        endpoint="https://ark.example/api/v3/chat/completions",
        api_key="server-secret",
        model="ep-standard-growth",
        transport=httpx.MockTransport(handler),
    )
    evidence = [
        {
            "memory_id": "memory-1",
            "type": "goal",
            "content": "尝试 AI Agent 产品评测",
            "source_type": "entry",
            "source_id": "entry-1",
        }
    ]

    result = run(provider.generate(evidence))

    assert "AI Agent 产品评测" in result
    assert captured["payload"]["messages"][0] == {
        "role": "system",
        "content": GROWTH_SYSTEM_PROMPT,
    }
    user_content = captured["payload"]["messages"][1]["content"]
    assert json.loads(user_content) == evidence
    assert captured["payload"]["temperature"] == 0
    assert captured["headers"]["authorization"] == "Bearer server-secret"
    assert "x-api-key" not in captured["headers"]
    assert "anthropic-version" not in captured["headers"]
    assert captured["attempts"] == 2


def test_growth_provider_requires_standard_ark_configuration(monkeypatch):
    monkeypatch.setenv("DAYFOLD_LLM_API_KEY", "agent-plan-secret")
    monkeypatch.delenv("DAYFOLD_STANDARD_ARK_API_KEY", raising=False)
    monkeypatch.delenv("DAYFOLD_STANDARD_ARK_MODEL", raising=False)

    assert get_growth_provider() is None

    monkeypatch.setenv("DAYFOLD_STANDARD_ARK_API_KEY", "standard-secret")
    monkeypatch.setenv("DAYFOLD_STANDARD_ARK_MODEL", "ep-standard-growth")
    provider = get_growth_provider()

    assert isinstance(provider, ArkGrowthProvider)
    assert provider._api_key == "standard-secret"
    assert provider._model == "ep-standard-growth"
    assert (
        provider._endpoint
        == "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    )
