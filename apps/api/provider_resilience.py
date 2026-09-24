from __future__ import annotations

import asyncio
from typing import Literal

import httpx


ProviderErrorKind = Literal[
    "authentication",
    "network",
    "rate_limited",
    "request_rejected",
    "timeout",
    "upstream",
]


class ProviderRequestError(RuntimeError):
    def __init__(
        self,
        kind: ProviderErrorKind,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(kind)
        self.kind = kind
        self.status_code = status_code

    @property
    def retryable(self) -> bool:
        return self.kind in {"network", "rate_limited", "timeout", "upstream"}


def classify_status(status_code: int) -> ProviderRequestError:
    if status_code in {401, 403}:
        kind: ProviderErrorKind = "authentication"
    elif status_code == 408:
        kind = "timeout"
    elif status_code == 429:
        kind = "rate_limited"
    elif status_code >= 500:
        kind = "upstream"
    else:
        kind = "request_rejected"
    return ProviderRequestError(kind, status_code=status_code)


def classify_transport_error(error: httpx.RequestError) -> ProviderRequestError:
    if isinstance(error, httpx.TimeoutException):
        return ProviderRequestError("timeout")
    return ProviderRequestError("network")


async def retry_pause(attempt: int, backoff_seconds: float) -> None:
    if backoff_seconds > 0:
        await asyncio.sleep(backoff_seconds * (2**attempt))


async def bounded_post(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_attempts: int = 2,
    backoff_seconds: float = 0.5,
    **kwargs,
) -> httpx.Response:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    for attempt in range(max_attempts):
        try:
            response = await client.post(url, **kwargs)
        except httpx.RequestError as error:
            failure = classify_transport_error(error)
        else:
            if response.status_code == 200:
                return response
            failure = classify_status(response.status_code)

        if not failure.retryable or attempt == max_attempts - 1:
            raise failure
        await retry_pause(attempt, backoff_seconds)

    raise AssertionError("bounded retry loop exited unexpectedly")


async def bounded_stream(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_attempts: int = 2,
    backoff_seconds: float = 0.5,
    **kwargs,
) -> httpx.Response:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    for attempt in range(max_attempts):
        try:
            request = client.build_request("POST", url, **kwargs)
            response = await client.send(request, stream=True)
        except httpx.RequestError as error:
            failure = classify_transport_error(error)
        else:
            if response.status_code == 200:
                return response
            failure = classify_status(response.status_code)
            await response.aclose()

        if not failure.retryable or attempt == max_attempts - 1:
            raise failure
        await retry_pause(attempt, backoff_seconds)

    raise AssertionError("bounded retry loop exited unexpectedly")
