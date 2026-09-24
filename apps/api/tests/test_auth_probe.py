import asyncio

import httpx
import pytest

from apps.api.auth.cloudbase import (
    AuthProviderUnavailable,
    InvalidToken,
    TokenExpired,
    VerifiedIdentity,
)
from apps.api.auth.user_status import (
    CloudBaseHttpUserStatusStore,
    PostgresUserStatusStore,
)
from apps.api.main import app, get_auth_adapter, get_user_status_store


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
    def __init__(self, status=None, error: Exception | None = None):
        self._status = status
        self._error = error

    async def get_status(self, auth_subject: str, access_token: str):
        assert auth_subject == "fictional-user"
        assert access_token == "opaque-test-token"
        if self._error:
            raise self._error
        return self._status


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
        status="active"
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


@pytest.mark.parametrize("status", ["deletion_pending", "disabled", None])
def test_auth_probe_rejects_non_active_or_missing_internal_user(status):
    app.dependency_overrides[get_auth_adapter] = lambda: StubAuthAdapter(
        result=VerifiedIdentity(
            auth_subject="fictional-user",
            email="fictional@example.test",
        )
    )
    app.dependency_overrides[get_user_status_store] = lambda: StubUserStatusStore(
        status=status
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
