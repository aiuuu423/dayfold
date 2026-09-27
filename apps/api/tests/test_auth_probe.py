import asyncio
from dataclasses import asdict

import httpx
import pytest

from apps.api.auth.cloudbase import (
    AuthProviderUnavailable,
    InvalidToken,
    TokenExpired,
    VerifiedIdentity,
)
from apps.api.auth.context import AuthContext
from apps.api.auth.user_status import (
    CloudBaseHttpUserStatusStore,
    InternalUser,
    PostgresUserStatusStore,
)
from apps.api.main import (
    app,
    get_auth_adapter,
    get_auth_context,
    get_user_status_store,
)

USER_ID = "00000000-0000-4000-8000-000000000101"


def request(method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


class StubAuthAdapter:
    def __init__(self, result=None, error: Exception | None = None):
        self._result = result
        self._error = error

    async def verify_access_token(self, token: str):
        assert token == "opaque-test-token"
        if self._error:
            raise self._error
        return self._result


class StubUserStatusStore:
    def __init__(self, user=None, error: Exception | None = None):
        self._user = user
        self._error = error

    async def get_user(self, auth_subject: str, access_token: str):
        assert auth_subject == "fictional-user"
        assert access_token == "opaque-test-token"
        if self._error:
            raise self._error
        return self._user


def internal_user(status: str = "active") -> InternalUser:
    return InternalUser(
        id=USER_ID,
        auth_subject="fictional-user",
        status=status,
    )


@pytest.fixture(autouse=True)
def reset_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def test_auth_probe_returns_only_authenticated_status_for_valid_token():
    app.dependency_overrides[get_auth_adapter] = lambda: StubAuthAdapter(
        result=VerifiedIdentity(
            auth_subject="fictional-user",
            email="fictional@example.test",
        )
    )
    app.dependency_overrides[get_user_status_store] = lambda: StubUserStatusStore(
        user=internal_user()
    )

    response = request(
        "GET",
        "/v1/auth/probe",
        headers={"Authorization": "Bearer opaque-test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "authenticated"}
    assert "fictional-user" not in response.text
    assert "fictional@example.test" not in response.text


@pytest.mark.parametrize(
    "user",
    [internal_user("deletion_pending"), internal_user("disabled"), None],
)
def test_auth_probe_rejects_non_active_or_missing_internal_user(user):
    app.dependency_overrides[get_auth_adapter] = lambda: StubAuthAdapter(
        result=VerifiedIdentity(
            auth_subject="fictional-user",
            email="fictional@example.test",
        )
    )
    app.dependency_overrides[get_user_status_store] = lambda: StubUserStatusStore(
        user=user
    )

    response = request(
        "GET",
        "/v1/auth/probe",
        headers={"Authorization": "Bearer opaque-test-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"
    assert "fictional-user" not in response.text


def test_auth_probe_fails_closed_when_user_status_store_is_unavailable():
    app.dependency_overrides[get_auth_adapter] = lambda: StubAuthAdapter(
        result=VerifiedIdentity(
            auth_subject="fictional-user",
            email="fictional@example.test",
        )
    )
    app.dependency_overrides[get_user_status_store] = lambda: None

    response = request(
        "GET",
        "/v1/auth/probe",
        headers={"Authorization": "Bearer opaque-test-token"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "USER_STATUS_UNAVAILABLE"


def test_get_user_status_store_selects_cloudbase_http_backend(monkeypatch):
    monkeypatch.setenv("DAYFOLD_USER_STATUS_BACKEND", "cloudbase_http")
    monkeypatch.setenv(
        "DAYFOLD_CLOUDBASE_ENV_ID",
        "example-environment",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)

    store = get_user_status_store()

    assert isinstance(store, CloudBaseHttpUserStatusStore)


def test_get_user_status_store_selects_postgres_backend(monkeypatch):
    monkeypatch.setenv("DAYFOLD_USER_STATUS_BACKEND", "postgres")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://example.test/dayfold",
    )

    store = get_user_status_store()

    assert isinstance(store, PostgresUserStatusStore)


def test_get_user_status_store_preserves_database_url_compatibility(monkeypatch):
    monkeypatch.delenv("DAYFOLD_USER_STATUS_BACKEND", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://example.test/dayfold",
    )

    store = get_user_status_store()

    assert isinstance(store, PostgresUserStatusStore)


@pytest.mark.parametrize(
    ("backend", "environment_id", "database_url"),
    [
        ("cloudbase_http", None, None),
        ("postgres", None, None),
        ("unknown", "example-environment", None),
        (None, "example-environment", None),
    ],
)
def test_get_user_status_store_rejects_incomplete_or_unknown_configuration(
    monkeypatch,
    backend,
    environment_id,
    database_url,
):
    for name, value in (
        ("DAYFOLD_USER_STATUS_BACKEND", backend),
        ("DAYFOLD_CLOUDBASE_ENV_ID", environment_id),
        ("DATABASE_URL", database_url),
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    assert get_user_status_store() is None


@pytest.mark.parametrize(
    "authorization",
    [None, "", "Basic opaque-test-token", "Bearer "],
)
def test_auth_probe_rejects_missing_or_malformed_bearer_token(authorization):
    headers = {"Authorization": authorization} if authorization else {}

    response = request("GET", "/v1/auth/probe", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.parametrize("error", [InvalidToken(), TokenExpired()])
def test_auth_probe_maps_token_failures_to_generic_invalid_token(error):
    app.dependency_overrides[get_auth_adapter] = lambda: StubAuthAdapter(error=error)

    response = request(
        "GET",
        "/v1/auth/probe",
        headers={"Authorization": "Bearer opaque-test-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_auth_probe_maps_provider_failure_to_service_unavailable():
    app.dependency_overrides[get_auth_adapter] = lambda: StubAuthAdapter(
        error=AuthProviderUnavailable()
    )

    response = request(
        "GET",
        "/v1/auth/probe",
        headers={"Authorization": "Bearer opaque-test-token"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_PROVIDER_UNAVAILABLE"


def test_auth_context_contains_only_verified_identity_fields():
    context = AuthContext(
        user_id=USER_ID,
        auth_subject="fictional-user",
        email="fictional@example.test",
    )

    assert asdict(context) == {
        "user_id": USER_ID,
        "auth_subject": "fictional-user",
        "email": "fictional@example.test",
    }
    assert "opaque-test-token" not in repr(context)
    assert not hasattr(context, "token")
    assert not hasattr(context, "access_token")


@pytest.mark.parametrize("path", ["/v1/auth/probe", "/v1/auth/session"])
def test_auth_endpoints_reuse_auth_context_and_return_no_identity(path):
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id=USER_ID,
        auth_subject="fictional-user",
        email="fictional@example.test",
    )

    response = request("GET", path)

    assert response.status_code == 200
    assert response.json() == {"status": "authenticated"}
    assert USER_ID not in response.text
    assert "fictional-user" not in response.text
    assert "fictional@example.test" not in response.text


def test_every_business_route_depends_on_auth_context():
    business_paths = {
        "/v1/entries",
        "/v1/entries/{entry_id}",
        "/v1/conversations",
        "/v1/conversations/{conversation_id}/messages",
        "/v1/conversations/{conversation_id}/messages/stream",
        "/v1/memory-extractions",
        "/v1/memories",
        "/v1/memories/{memory_id}",
        "/v1/memory-embeddings/sync",
        "/v1/memory-retrievals",
        "/v1/growth/current",
    }
    matching_routes = [route for route in app.routes if route.path in business_paths]

    assert {route.path for route in matching_routes} == business_paths
    for route in matching_routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_auth_context in dependency_calls, route.path


def test_auth_probe_cors_preflight_allows_authorization_header(monkeypatch):
    response = request(
        "OPTIONS",
        "/v1/auth/probe",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
