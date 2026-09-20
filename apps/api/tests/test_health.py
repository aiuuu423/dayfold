import asyncio
import json
from pathlib import Path

import httpx

from apps.api.main import app, parse_allowed_origins


EXPECTED_HEALTH = {
    "status": "ok",
    "service": "dayfold-api",
    "environment": "preview",
    "version": "p1-probe",
}

REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_ROOT = REPO_ROOT / "apps" / "web"


def request(method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_health_returns_fixed_public_contract():
    response = request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == EXPECTED_HEALTH


def test_default_local_origin_is_allowed():
    response = request(
        "GET",
        "/health",
        headers={"Origin": "http://localhost:8000"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"
    assert "access-control-allow-credentials" not in response.headers


def test_unknown_origin_is_not_allowed():
    response = request(
        "GET",
        "/health",
        headers={"Origin": "https://unknown.example"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_preflight_allows_configured_origin_without_credentials():
    response = request(
        "OPTIONS",
        "/health",
        headers={
            "Origin": "http://127.0.0.1:8000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8000"
    assert "access-control-allow-credentials" not in response.headers


def test_allowed_origins_are_trimmed_and_deduplicated():
    origins = parse_allowed_origins(
        " https://preview.example,https://preview.example, http://localhost:9000 "
    )

    assert origins == (
        "https://preview.example",
        "http://localhost:9000",
    )


def test_wildcard_origin_is_rejected():
    try:
        parse_allowed_origins("https://preview.example,*")
    except ValueError as error:
        assert "wildcard" in str(error).lower()
    else:
        raise AssertionError("Wildcard origin should be rejected")


def test_static_probe_files_and_public_copy_exist():
    html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    javascript = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
    stylesheet = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")
    vercel_config = json.loads(
        (WEB_ROOT / "vercel.json").read_text(encoding="utf-8")
    )

    assert "Dayfold Preview" in html
    assert "不包含真实数据" in html
    assert 'data-state="idle"' in html
    assert "AbortController" in javascript
    assert "--canvas:" in stylesheet
    assert vercel_config["cleanUrls"] is True


def test_static_probe_contains_no_secret_or_fixed_deployment_value():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            WEB_ROOT / "index.html",
            WEB_ROOT / "styles.css",
            WEB_ROOT / "app.js",
            WEB_ROOT / "vercel.json",
        )
    ).lower()

    forbidden_fragments = (
        "api_key",
        "apikey",
        "bearer ",
        "sk-",
        ".pythonanywhere.com",
    )

    assert all(fragment not in combined for fragment in forbidden_fragments)
