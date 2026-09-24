import asyncio
import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from apps.api.demo import DemoSettings
from apps.api.main import (
    app,
    get_demo_settings,
    get_embedding_provider,
    get_memory_repository,
    get_vector_repository,
)
from apps.api.memory import SqliteMemoryRepository
from apps.api.retrieval import ArkEmbeddingProvider, SqliteVectorRepository


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


class StubEmbeddingProvider:
    model = "test-embedding"
    dimensions = 3

    def __init__(self):
        self.inputs = []

    async def embed(self, texts):
        self.inputs.append(texts)
        vectors = {
            "想转向 AI Agent 产品评测": [1.0, 0.0, 0.0],
            "持续学习手冲咖啡": [0.0, 1.0, 0.0],
            "职业方向让我有些迷茫": [0.9, 0.1, 0.0],
        }
        return [vectors[text] for text in texts]


@pytest.fixture
def stores(tmp_path: Path):
    database_path = tmp_path / "dayfold-retrieval-test.sqlite3"
    memories = SqliteMemoryRepository(database_path)
    vectors = SqliteVectorRepository(database_path)
    run(memories.initialize())
    run(vectors.initialize())
    return database_path, memories, vectors


@pytest.fixture(autouse=True)
def demo_dependencies(stores):
    _, memories, vectors = stores
    provider = StubEmbeddingProvider()
    app.dependency_overrides[get_demo_settings] = lambda: DemoSettings(
        user_id=DEMO_USER_ID
    )
    app.dependency_overrides[get_memory_repository] = lambda: memories
    app.dependency_overrides[get_vector_repository] = lambda: vectors
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    yield provider
    app.dependency_overrides.clear()


def create_memory(memories, user_id, memory_type, content):
    return run(
        memories.store_extraction(
            user_id,
            "entry",
            "synthetic-source",
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


def test_sync_and_retrieve_rank_active_memories_within_tenant(stores):
    database_path, memories, vectors = stores
    career = create_memory(
        memories,
        DEMO_USER_ID,
        "goal",
        "想转向 AI Agent 产品评测",
    )
    coffee = create_memory(
        memories,
        DEMO_USER_ID,
        "interest",
        "持续学习手冲咖啡",
    )
    create_memory(
        memories,
        OTHER_USER_ID,
        "goal",
        "想转向 AI Agent 产品评测",
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE memories SET status = 'disabled' WHERE id = ?",
            (coffee.id,),
        )

    synced = request("POST", "/v1/memory-embeddings/sync")
    assert synced.status_code == 200
    assert synced.json() == {"embedded": 1}

    retrieved = request(
        "POST",
        "/v1/memory-retrievals",
        json={"query": "职业方向让我有些迷茫", "limit": 3},
    )

    assert retrieved.status_code == 200
    items = retrieved.json()["items"]
    assert [item["memory"]["id"] for item in items] == [career.id]
    assert items[0]["score"] > 0.9
    assert "user_id" not in retrieved.text
    assert run(vectors.count(OTHER_USER_ID)) == 0


def test_retrieval_rejects_vector_dimension_mismatch(stores):
    _, memories, _ = stores
    create_memory(
        memories,
        DEMO_USER_ID,
        "goal",
        "想转向 AI Agent 产品评测",
    )

    class InvalidProvider(StubEmbeddingProvider):
        async def embed(self, texts):
            return [[1.0, 0.0]]

    app.dependency_overrides[get_embedding_provider] = lambda: InvalidProvider()

    response = request("POST", "/v1/memory-embeddings/sync")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_EMBEDDING"


def test_ark_embedding_provider_uses_multimodal_endpoint_contract():
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.append(
            {
                "authorization": request.headers.get("authorization"),
                "payload": payload,
            }
        )
        text = payload["input"][0]["text"]
        embedding = [0.1, 0.2, 0.3] if text == "第一条" else [0.4, 0.5, 0.6]
        return httpx.Response(
            200,
            json={
                "data": {"embedding": embedding},
                "model": "test-model",
            },
        )

    provider = ArkEmbeddingProvider(
        endpoint="https://ark.example/api/v3/embeddings/multimodal",
        api_key="server-secret",
        model="test-model",
        dimensions=3,
        transport=httpx.MockTransport(handler),
    )

    vectors = run(provider.embed(["第一条", "第二条"]))

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert len(captured) == 2
    assert all(
        item["authorization"] == "Bearer server-secret" for item in captured
    )
    assert [item["payload"]["input"] for item in captured] == [
        [{"type": "text", "text": "第一条"}],
        [{"type": "text", "text": "第二条"}],
    ]
    assert all(item["payload"]["dimensions"] == 3 for item in captured)
