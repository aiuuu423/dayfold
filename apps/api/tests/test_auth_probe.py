import asyncio

import httpx
import pytest

from apps.api.auth.cloudbase import (
    AuthProviderUnavailable,
    InvalidToken,
    TokenExpired,
    VerifiedIdentity,
)
from apps.api.main import app, get_auth_adapter


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
