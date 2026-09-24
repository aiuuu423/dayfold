import asyncio

import httpx

from apps.api.main import app, get_demo_settings


def request(method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_demo_info_is_not_available_when_demo_mode_is_disabled():
    app.dependency_overrides[get_demo_settings] = lambda: None

    try:
        response = request("GET", "/v1/demo")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_demo_info_exposes_only_safe_synthetic_contract():
    from apps.api.demo import DemoSettings

    app.dependency_overrides[get_demo_settings] = lambda: DemoSettings(
        user_id="00000000-0000-4000-8000-000000000001"
    )

    try:
        response = request("GET", "/v1/demo")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "mode": "demo",
        "user": {"id": "00000000-0000-4000-8000-000000000001", "synthetic": True},
        "privacy_notice": "Demo only. Do not enter sensitive personal information.",
        "memory_types": ["event", "interest", "goal"],
    }
    assert "token" not in response.text.lower()
    assert "key" not in response.text.lower()
