import asyncio
from pathlib import Path

import httpx
import pytest

from apps.api.demo import DemoSettings
from apps.api.entries import SqliteEntryRepository
from apps.api.main import app, get_demo_settings, get_entry_repository


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
def repository(tmp_path: Path):
    store = SqliteEntryRepository(tmp_path / "dayfold-test.sqlite3")
    run(store.initialize())
    return store


@pytest.fixture(autouse=True)
def demo_dependencies(repository):
    app.dependency_overrides[get_demo_settings] = lambda: DemoSettings(
        user_id=DEMO_USER_ID
    )
    app.dependency_overrides[get_entry_repository] = lambda: repository
    yield
    app.dependency_overrides.clear()


def test_today_entry_crud_round_trip(repository):
    created = request(
        "POST",
        "/v1/entries",
        json={
            "content": "最近开始重新思考职业方向。",
            "occurred_at": "2026-09-23T09:30:00Z",
        },
    )

    assert created.status_code == 201
    entry = created.json()
    assert entry["content"] == "最近开始重新思考职业方向。"
    assert entry["version"] == 1
    assert "user_id" not in entry

    listed = request("GET", "/v1/entries")
    assert listed.status_code == 200
    assert listed.json()["items"] == [entry]

    fetched = request("GET", f"/v1/entries/{entry['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == entry

    updated = request(
        "PATCH",
        f"/v1/entries/{entry['id']}",
        headers={"If-Match": "1"},
        json={"content": "最近开始认真探索新的职业方向。"},
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == "最近开始认真探索新的职业方向。"
    assert updated.json()["version"] == 2

    deleted = request("DELETE", f"/v1/entries/{entry['id']}")
    assert deleted.status_code == 202
    assert deleted.json() == {"id": entry["id"], "status": "deleted"}

    assert request("GET", f"/v1/entries/{entry['id']}").status_code == 404
    assert request("GET", "/v1/entries").json() == {"items": []}


def test_update_rejects_stale_version(repository):
    entry = run(
        repository.create(
            DEMO_USER_ID,
            "第一版",
            "2026-09-23T09:30:00Z",
        )
    )

    response = request(
        "PATCH",
        f"/v1/entries/{entry.id}",
        headers={"If-Match": "2"},
        json={"content": "不应写入"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_repository_never_reads_or_changes_another_users_entry(repository):
    entry = run(
        repository.create(
            OTHER_USER_ID,
            "另一个用户的记录",
            "2026-09-23T09:30:00Z",
        )
    )

    assert run(repository.get(DEMO_USER_ID, entry.id)) is None
    assert run(repository.list(DEMO_USER_ID)) == []
    assert (
        run(repository.update(DEMO_USER_ID, entry.id, "越权修改", expected_version=1))
        is None
    )
    assert run(repository.delete(DEMO_USER_ID, entry.id)) is False


def test_create_rejects_client_supplied_user_id(repository):
    response = request(
        "POST",
        "/v1/entries",
        json={
            "user_id": OTHER_USER_ID,
            "content": "不允许覆盖租户。",
            "occurred_at": "2026-09-23T09:30:00Z",
        },
    )

    assert response.status_code == 422
    assert run(repository.list(OTHER_USER_ID)) == []


def test_create_rejects_occurred_at_without_timezone():
    response = request(
        "POST",
        "/v1/entries",
        json={
            "content": "缺少时区的记录。",
            "occurred_at": "2026-09-23T09:30:00",
        },
    )

    assert response.status_code == 422
