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


def test_static_portfolio_app_contains_core_product_surfaces():
    html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    javascript = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
    stylesheet = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")
    vercel_config = json.loads(
        (WEB_ROOT / "vercel.json").read_text(encoding="utf-8")
    )

    assert "<title>Dayfold</title>" in html
    assert "Demo only. Do not enter sensitive personal information." in html
    assert 'data-view="today"' in html
    assert 'data-view="chat"' in html
    assert 'data-view="memories"' in html
    assert 'data-view="growth"' in html
    assert "loadEntries" in javascript
    assert "streamSSE" in javascript
    assert "loadMemories" in javascript
    assert "loadGrowth" in javascript
    assert 'https://dayfold-api-global.vercel.app' in javascript
    assert "--canvas:" in stylesheet
    assert "#c7e8f8" in stylesheet
    assert "repeating-linear-gradient" in stylesheet
    assert "HanziPen SC" in stylesheet
    assert "sidebar" not in html
    assert "prefers-reduced-motion" in stylesheet
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


def test_dockerfile_preserves_api_package_import_path():
    dockerfile = (REPO_ROOT / "apps" / "api" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "COPY . /app/apps/api" in dockerfile
    assert '"apps.api.main:app"' in dockerfile
