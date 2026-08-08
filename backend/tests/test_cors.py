import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import add_cors_middleware


def _build_test_app(settings: Settings) -> FastAPI:
    # Exercises the exact same add_cors_middleware() the real app uses —
    # the real `app` singleton's middleware is fixed at import time from
    # real settings, so a throwaway app is how this gets tested per-case.
    app = FastAPI()
    add_cors_middleware(app, settings)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


async def _cors_response_for(settings: Settings, origin: str):
    app = _build_test_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/ping", headers={"Origin": origin})


@pytest.mark.asyncio
async def test_static_allowed_origin_is_echoed_back():
    settings = Settings(cors_allowed_origins="https://bursatrack.com,http://localhost:3000")
    resp = await _cors_response_for(settings, "https://bursatrack.com")
    assert resp.headers.get("access-control-allow-origin") == "https://bursatrack.com"


@pytest.mark.asyncio
async def test_matching_vercel_preview_origin_is_allowed():
    settings = Settings(
        cors_allowed_origins="https://bursatrack.com",
        cors_vercel_preview_regex=r"^https://bursatrack-[a-z0-9-]+-[a-z0-9]+\.vercel\.app$",
    )
    resp = await _cors_response_for(settings, "https://bursatrack-feat-login-abc123.vercel.app")
    assert resp.headers.get("access-control-allow-origin") == "https://bursatrack-feat-login-abc123.vercel.app"


@pytest.mark.asyncio
async def test_unrelated_vercel_app_is_not_allowed():
    """CRIT-R-001: a bare *.vercel.app wildcard would let any Vercel-hosted
    app make credentialed cross-origin requests — must not match."""
    settings = Settings(
        cors_allowed_origins="https://bursatrack.com",
        cors_vercel_preview_regex=r"^https://bursatrack-[a-z0-9-]+-[a-z0-9]+\.vercel\.app$",
    )
    resp = await _cors_response_for(settings, "https://some-attacker-app.vercel.app")
    assert "access-control-allow-origin" not in resp.headers


@pytest.mark.asyncio
async def test_unrecognised_origin_is_not_allowed():
    settings = Settings(cors_allowed_origins="https://bursatrack.com")
    resp = await _cors_response_for(settings, "https://evil.example.com")
    assert "access-control-allow-origin" not in resp.headers


@pytest.mark.asyncio
async def test_disabled_regex_matches_no_preview_origin():
    """cors_vercel_preview_regex="" (the real default until DEP-9.3 sets a
    real value) must disable regex matching entirely, not match everything —
    this is the empty-string-vs-None distinction add_cors_middleware() exists
    to get right."""
    settings = Settings(cors_allowed_origins="https://bursatrack.com", cors_vercel_preview_regex="")
    resp = await _cors_response_for(settings, "https://bursatrack-anything-xyz123.vercel.app")
    assert "access-control-allow-origin" not in resp.headers
