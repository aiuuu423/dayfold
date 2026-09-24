import asyncio

import httpx
import pytest

from apps.api.provider_resilience import (
    ProviderRequestError,
    bounded_post,
    bounded_stream,
)


def run(coro):
    return asyncio.run(coro)


def test_bounded_post_retries_one_retryable_response_then_succeeds():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    async def send():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await bounded_post(
                client,
                "https://provider.example/v1/messages",
                json={},
                max_attempts=2,
                backoff_seconds=0,
            )

    response = run(send())

    assert response.status_code == 200
    assert attempts == 2


def test_bounded_post_does_not_retry_authentication_failure():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, request=request)

    async def send():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await bounded_post(
                client,
                "https://provider.example/v1/messages",
                json={},
                max_attempts=2,
                backoff_seconds=0,
            )

    with pytest.raises(ProviderRequestError) as captured:
        run(send())

    assert captured.value.kind == "authentication"
    assert captured.value.status_code == 401
    assert attempts == 1


def test_bounded_post_stops_after_two_timeouts():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("slow upstream", request=request)

    async def send():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            return await bounded_post(
                client,
                "https://provider.example/v1/messages",
                json={},
                max_attempts=2,
                backoff_seconds=0,
            )

    with pytest.raises(ProviderRequestError) as captured:
        run(send())

    assert captured.value.kind == "timeout"
    assert captured.value.status_code is None
    assert attempts == 2


def test_bounded_stream_retries_before_returning_response():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, request=request)
        return httpx.Response(200, text="data: ok\n\n", request=request)

    async def send():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            response = await bounded_stream(
                client,
                "https://provider.example/v1/messages",
                json={},
                max_attempts=2,
                backoff_seconds=0,
            )
            try:
                return response.status_code, await response.aread()
            finally:
                await response.aclose()

    status_code, body = run(send())

    assert status_code == 200
    assert body == b"data: ok\n\n"
    assert attempts == 2
