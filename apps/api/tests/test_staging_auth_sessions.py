import json

import httpx
import pytest

from apps.api.scripts.staging_auth_sessions import (
    DeviceCredentials,
    ProbeConfig,
    StagingSessionVerifier,
)


ENV_ID = "dayfold-staging"
PROTECTED_URL = "https://api-staging.example.test/v1/auth/probe"


def make_verifier(handler) -> StagingSessionVerifier:
    return StagingSessionVerifier(
        config=ProbeConfig(
            environment_id=ENV_ID,
            protected_url=PROTECTED_URL,
        ),
        transport=httpx.MockTransport(handler),
    )


def devices() -> tuple[DeviceCredentials, DeviceCredentials]:
    return (
        DeviceCredentials("device_a", "access-a-secret", "refresh-a-secret"),
        DeviceCredentials("device_b", "access-b-secret", "refresh-b-secret"),
    )


def test_verifier_rejects_duplicate_device_sessions():
    duplicate_devices = (
        DeviceCredentials(
            "device_a",
            "shared-access-secret",
            "shared-refresh-secret",
        ),
        DeviceCredentials(
            "device_b",
            "shared-access-secret",
            "shared-refresh-secret",
        ),
    )

    with pytest.raises(ValueError, match="independent"):
        make_verifier(lambda request: httpx.Response(500)).run(
            "baseline",
            duplicate_devices,
        )


def test_baseline_requires_two_valid_sessions_for_the_same_subject():
    token_subjects = {
        "access-a-secret": "fictional-user",
        "access-b-secret": "fictional-user",
        "new-a-secret": "fictional-user",
        "new-b-secret": "fictional-user",
    }
    refreshed_tokens = {
        "refresh-a-secret": "new-a-secret",
        "refresh-b-secret": "new-b-secret",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        authorization = request.headers.get("authorization", "")
        token = authorization.removeprefix("Bearer ")
        if request.url.path == "/auth/v2/user/me":
            return httpx.Response(200, json={"sub": token_subjects[token]})
        if request.url.path == "/auth/v2/token":
            refresh_token = json.loads(request.content)["refresh_token"]
            return httpx.Response(
                200,
                json={"access_token": refreshed_tokens[refresh_token]},
            )
        if str(request.url) == PROTECTED_URL:
            return httpx.Response(200, json={"status": "ok"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    result = make_verifier(handler).run("baseline", devices())

    assert result["passed"] is True
    assert result["subject_match"] is True
    assert all(device["passed"] for device in result["devices"])
    serialized = json.dumps(result)
    assert "access-a-secret" not in serialized
    assert "refresh-a-secret" not in serialized
    assert "new-a-secret" not in serialized


def test_baseline_accepts_only_latest_session_refresh_token():
    token_subjects = {
        "access-a-secret": "fictional-user",
        "access-b-secret": "fictional-user",
        "new-a-secret": "fictional-user",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        authorization = request.headers.get("authorization", "")
        token = authorization.removeprefix("Bearer ")
        if request.url.path == "/auth/v2/user/me":
            return httpx.Response(200, json={"sub": token_subjects[token]})
        if request.url.path == "/auth/v2/token":
            refresh_token = json.loads(request.content)["refresh_token"]
            if refresh_token == "refresh-a-secret":
                return httpx.Response(200, json={"access_token": "new-a-secret"})
            return httpx.Response(404, json={"code": "invalid_refresh_token"})
        if str(request.url) == PROTECTED_URL:
            return httpx.Response(200, json={"status": "ok"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    result = make_verifier(handler).run("baseline", devices())

    assert result["passed"] is True
    assert result["subject_match"] is True
    assert result["refresh_contract"] == "latest_session_only"
    assert all(device["passed"] for device in result["devices"])


def test_baseline_rejects_when_no_refresh_token_is_valid():
    def handler(request: httpx.Request) -> httpx.Response:
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        if request.url.path == "/auth/v2/user/me":
            return httpx.Response(200, json={"sub": "fictional-user"})
        if request.url.path == "/auth/v2/token":
            return httpx.Response(404, json={"code": "invalid_refresh_token"})
        if str(request.url) == PROTECTED_URL:
            return httpx.Response(200, json={"token": token})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    result = make_verifier(handler).run("baseline", devices())

    assert result["passed"] is False
    assert result["refresh_contract"] == "invalid"
    assert all(device["refresh_denied"] for device in result["devices"])


def test_baseline_rejects_sessions_from_different_subjects():
    def handler(request: httpx.Request) -> httpx.Response:
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        if request.url.path == "/auth/v2/user/me":
            return httpx.Response(
                200,
                json={"sub": "user-a" if token.endswith("a-secret") else "user-b"},
            )
        if request.url.path == "/auth/v2/token":
            return httpx.Response(200, json={"access_token": "new-token"})
        if str(request.url) == PROTECTED_URL:
            return httpx.Response(200)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    result = make_verifier(handler).run("baseline", devices())

    assert result["passed"] is False
    assert result["subject_match"] is False


@pytest.mark.parametrize("phase", ["blocked", "deleted"])
def test_restricted_phase_passes_when_old_access_and_refresh_tokens_are_rejected(
    phase: str,
):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/v2/token":
            return httpx.Response(400, json={"code": "invalid_refresh_token"})
        return httpx.Response(401, json={"code": "INVALID_ACCESS_TOKEN"})

    result = make_verifier(handler).run(phase, devices())

    assert result["passed"] is True
    assert all(device["old_access_denied"] for device in result["devices"])
    assert all(device["refresh_denied"] for device in result["devices"])


def test_blocked_phase_accepts_refresh_only_when_dayfold_rejects_new_token():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/v2/token":
            return httpx.Response(200, json={"access_token": "new-access-secret"})
        if request.url.path == "/auth/v2/user/me":
            token = request.headers.get("authorization", "")
            status = 200 if token.endswith("new-access-secret") else 401
            return httpx.Response(status, json={"sub": "fictional-user"})
        if str(request.url) == PROTECTED_URL:
            token = request.headers.get("authorization", "")
            status = 401 if token.endswith("new-access-secret") else 403
            return httpx.Response(status)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    result = make_verifier(handler).run("blocked", devices())

    assert result["passed"] is True
    assert all(device["refresh_denied"] is False for device in result["devices"])
    assert all(device["refreshed_access_denied"] for device in result["devices"])


def test_blocked_phase_fails_if_refreshed_token_can_access_dayfold():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/v2/token":
            return httpx.Response(200, json={"access_token": "new-access-secret"})
        if request.url.path == "/auth/v2/user/me":
            return httpx.Response(401)
        if str(request.url) == PROTECTED_URL:
            token = request.headers.get("authorization", "")
            return httpx.Response(200 if token.endswith("new-access-secret") else 401)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    result = make_verifier(handler).run("blocked", devices())

    assert result["passed"] is False
    assert any(not device["refreshed_access_denied"] for device in result["devices"])
