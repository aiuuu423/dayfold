import asyncio

import httpx
import pytest

from apps.api.auth.cloudbase import (
    AuthProviderUnavailable,
    CloudBaseAuthAdapter,
    InvalidToken,
    TokenExpired,
)


def verify(adapter: CloudBaseAuthAdapter, token: str):
    return asyncio.run(adapter.verify_access_token(token))


def test_valid_token_returns_stable_verified_identity():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v2/user/me"
        assert request.headers["authorization"] == "Bearer opaque-test-token"
        return httpx.Response(
            200,
            json={
                "sub": "fictional-user-id",
                "email": "fictional@example.test",
            },
        )

    adapter = CloudBaseAuthAdapter(
        environment_id="dayfold-test",
        transport=httpx.MockTransport(handler),
    )

    identity = verify(adapter, "opaque-test-token")

    assert identity.auth_subject == "fictional-user-id"
    assert identity.email == "fictional@example.test"


@pytest.mark.parametrize(
    ("status_code", "payload", "expected_error"),
    [
        (401, {"code": "INVALID_ACCESS_TOKEN"}, InvalidToken),
        (401, {"code": "token_expired"}, TokenExpired),
        (503, {"code": "service_unavailable"}, AuthProviderUnavailable),
    ],
)
def test_provider_errors_map_to_stable_domain_errors(
    status_code: int,
    payload: dict[str, str],
    expected_error: type[Exception],
):
    adapter = CloudBaseAuthAdapter(
        environment_id="dayfold-test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status_code, json=payload)
        ),
    )

    with pytest.raises(expected_error):
        verify(adapter, "opaque-test-token")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"email": "fictional@example.test"}),
        httpx.Response(503, text="upstream unavailable"),
    ],
)
def test_malformed_provider_responses_map_to_provider_unavailable(
    response: httpx.Response,
):
    adapter = CloudBaseAuthAdapter(
        environment_id="dayfold-test",
        transport=httpx.MockTransport(lambda request: response),
    )

    with pytest.raises(AuthProviderUnavailable):
        verify(adapter, "opaque-test-token")
