import asyncio
from pathlib import Path

import httpx
import pytest

from apps.api.auth.user_status import (
    CloudBaseHttpUserStatusStore,
    InternalUser,
    PostgresUserStatusStore,
    UserStatusStoreUnavailable,
)

USER_ID = "00000000-0000-4000-8000-000000000101"
ORIGINAL_MIGRATION = (
    Path(__file__).parents[3]
    / "infra"
    / "cloudbase"
    / "migrations"
    / "20260923_users_select_self.sql"
)
INTERNAL_ID_MIGRATION = (
    Path(__file__).parents[3]
    / "infra"
    / "cloudbase"
    / "migrations"
    / "20260925_users_grant_internal_id.sql"
)


class FakeCursor:
    def __init__(self, rows=None, error: Exception | None = None):
        self.rows = rows or []
        self.error = error
        self.query = None
        self.params = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def execute(self, query, params):
        if self.error:
            raise self.error
        self.query = query
        self.params = params

    async def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    def cursor(self):
        return self._cursor


def test_postgres_user_status_store_uses_bound_subject_query():
    cursor = FakeCursor(rows=[(USER_ID, "fictional-user", "active")])

    async def connect(database_url: str, connect_timeout: float):
        assert database_url == "postgresql://example.test/dayfold"
        assert connect_timeout == 3.0
        return FakeConnection(cursor)

    store = PostgresUserStatusStore(
        "postgresql://example.test/dayfold",
        connect=connect,
    )

    user = asyncio.run(
        store.get_user("fictional-user", "opaque-test-token")
    )

    assert user == InternalUser(
        id=USER_ID,
        auth_subject="fictional-user",
        status="active",
    )
    assert "SELECT id, auth_subject, status" in " ".join(cursor.query.split())
    assert "auth_subject = %s" in cursor.query
    assert "deleted_at IS NULL" in cursor.query
    assert cursor.params == ("fictional-user",)


def test_postgres_user_status_store_returns_none_for_missing_mapping():
    async def connect(database_url: str, connect_timeout: float):
        return FakeConnection(FakeCursor(rows=[]))

    store = PostgresUserStatusStore("postgresql://example.test/dayfold", connect)

    assert (
        asyncio.run(
            store.get_user("fictional-user", "opaque-test-token")
        )
        is None
    )


def test_postgres_user_status_store_normalizes_database_failure():
    async def connect(database_url: str, connect_timeout: float):
        return FakeConnection(FakeCursor(error=RuntimeError("database detail")))

    store = PostgresUserStatusStore("postgresql://example.test/dayfold", connect)

    with pytest.raises(UserStatusStoreUnavailable) as captured:
        asyncio.run(
            store.get_user("fictional-user", "opaque-test-token")
        )

    assert "database detail" not in str(captured.value)


def test_cloudbase_http_user_status_store_queries_current_user_status():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/rdb/rest/users"
        assert request.headers["authorization"] == "Bearer opaque-test-token"
        assert request.url.params["select"] == "id,auth_subject,status"
        assert request.url.params["auth_subject"] == "eq.fictional-user"
        assert request.url.params["deleted_at"] == "is.null"
        assert request.url.params["limit"] == "2"
        return httpx.Response(
            200,
            json=[{
                "id": USER_ID,
                "auth_subject": "fictional-user",
                "status": "active",
            }],
        )

    store = CloudBaseHttpUserStatusStore(
        "example-environment",
        transport=httpx.MockTransport(handler),
    )

    user = asyncio.run(
        store.get_user("fictional-user", "opaque-test-token")
    )

    assert user == InternalUser(
        id=USER_ID,
        auth_subject="fictional-user",
        status="active",
    )


def test_cloudbase_http_user_status_store_returns_none_for_missing_mapping():
    store = CloudBaseHttpUserStatusStore(
        "example-environment",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=[])
        ),
    )

    assert (
        asyncio.run(
            store.get_user("fictional-user", "opaque-test-token")
        )
        is None
    )


@pytest.mark.parametrize("status_code", [401, 403])
def test_cloudbase_http_user_status_store_returns_none_when_token_is_rejected(
    status_code,
):
    store = CloudBaseHttpUserStatusStore(
        "example-environment",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status_code)
        ),
    )

    assert (
        asyncio.run(
            store.get_user("fictional-user", "opaque-test-token")
        )
        is None
    )


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(404),
        httpx.Response(200, text="not-json"),
        httpx.Response(
            200,
            json=[
                {"id": USER_ID, "auth_subject": "fictional-user", "status": "active"},
                {"id": USER_ID, "auth_subject": "fictional-user", "status": "active"},
            ],
        ),
        httpx.Response(
            200,
            json=[{
                "id": USER_ID,
                "auth_subject": "fictional-user",
                "status": "unexpected",
            }],
        ),
        httpx.Response(
            200,
            json={"id": USER_ID, "auth_subject": "fictional-user", "status": "active"},
        ),
        httpx.Response(
            200,
            json=[{
                "id": "not-a-uuid",
                "auth_subject": "fictional-user",
                "status": "active",
            }],
        ),
        httpx.Response(
            200,
            json=[{
                "id": USER_ID,
                "auth_subject": "different-user",
                "status": "active",
            }],
        ),
    ],
)
def test_cloudbase_http_user_status_store_normalizes_invalid_responses(response):
    store = CloudBaseHttpUserStatusStore(
        "example-environment",
        transport=httpx.MockTransport(lambda request: response),
    )

    with pytest.raises(UserStatusStoreUnavailable):
        asyncio.run(
            store.get_user("fictional-user", "opaque-test-token")
        )


def test_cloudbase_http_user_status_store_normalizes_network_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("provider detail", request=request)

    store = CloudBaseHttpUserStatusStore(
        "example-environment",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(UserStatusStoreUnavailable) as captured:
        asyncio.run(
            store.get_user("fictional-user", "opaque-test-token")
        )

    assert "provider detail" not in str(captured.value)


def test_users_rls_grants_authenticated_read_access_to_internal_id_only():
    original_sql = " ".join(
        ORIGINAL_MIGRATION.read_text(encoding="utf-8").split()
    ).lower()
    sql = " ".join(
        INTERNAL_ID_MIGRATION.read_text(encoding="utf-8").split()
    ).lower()

    assert "grant select (auth_subject, status, deleted_at)" in original_sql
    assert "grant select (id, auth_subject, status, deleted_at)" not in original_sql
    assert "grant select (id, auth_subject, status, deleted_at)" in sql
    assert "grant insert" not in sql
    assert "grant update" not in sql
    assert "grant delete" not in sql
