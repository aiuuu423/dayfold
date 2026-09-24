import asyncio
from pathlib import Path

import httpx
import pytest

from apps.api.demo import DemoSettings
from apps.api.main import app, get_demo_settings, get_memory_repository
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


@pytest.fixture
def stores(tmp_path: Path):
    database_path = tmp_path / "dayfold-memory-control-test.sqlite3"
    memories = SqliteMemoryRepository(database_path)
    vectors = SqliteVectorRepository(database_path)
    run(memories.initialize())
    run(vectors.initialize())
    return memories, vectors


@pytest.fixture(autouse=True)
def demo_dependencies(stores):
    memories, _ = stores
    app.dependency_overrides[get_demo_settings] = lambda: DemoSettings(
        user_id=DEMO_USER_ID
    )
    app.dependency_overrides[get_memory_repository] = lambda: memories
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


def test_list_and_detail_include_memory_sources(stores):
    memories, _ = stores
    memory = create_memory(
        memories,
        DEMO_USER_ID,
        "entry-1",
        "goal",
        "尝试 AI Agent 产品评测",
    )

    listed = request("GET", "/v1/memories")
    detailed = request("GET", f"/v1/memories/{memory.id}")

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [memory.id]
    assert detailed.status_code == 200
    assert detailed.json()["sources"] == [
        {"source_type": "entry", "source_id": "entry-1"}
    ]
    assert "user_id" not in detailed.text


def test_disable_immediately_removes_memory_embedding(stores):
    memories, vectors = stores
    memory = create_memory(
        memories,
        DEMO_USER_ID,
        "entry-1",
        "goal",
        "尝试 AI Agent 产品评测",
    )
    run(
        vectors.store_many(
            DEMO_USER_ID,
            [memory],
            [[1.0, 0.0, 0.0]],
            "test-model",
            3,
        )
    )

    response = request(
        "PATCH",
        f"/v1/memories/{memory.id}",
        json={"status": "disabled"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert run(vectors.count(DEMO_USER_ID)) == 0
    assert run(memories.get(DEMO_USER_ID, memory.id)).status == "disabled"


def test_delete_removes_memory_sources_and_embedding(stores):
    memories, vectors = stores
    memory = create_memory(
        memories,
        DEMO_USER_ID,
        "entry-2",
        "interest",
        "持续学习手冲咖啡",
    )
    run(
        vectors.store_many(
            DEMO_USER_ID,
            [memory],
            [[0.0, 1.0, 0.0]],
            "test-model",
            3,
        )
    )

    deleted = request("DELETE", f"/v1/memories/{memory.id}")

    assert deleted.status_code == 202
    assert deleted.json() == {"id": memory.id, "status": "deleted"}
    assert request("GET", f"/v1/memories/{memory.id}").status_code == 404
    assert run(memories.list_sources(DEMO_USER_ID, memory.id)) == []
    assert run(vectors.count(DEMO_USER_ID)) == 0


def test_memory_control_cannot_access_another_users_memory(stores):
    memories, _ = stores
    memory = create_memory(
        memories,
        OTHER_USER_ID,
        "other-entry",
        "goal",
        "另一个用户的目标",
    )

    assert request("GET", f"/v1/memories/{memory.id}").status_code == 404
    assert (
        request(
            "PATCH",
            f"/v1/memories/{memory.id}",
            json={"status": "disabled"},
        ).status_code
        == 404
    )
    assert request("DELETE", f"/v1/memories/{memory.id}").status_code == 404
    assert run(memories.get(OTHER_USER_ID, memory.id)).status == "active"
