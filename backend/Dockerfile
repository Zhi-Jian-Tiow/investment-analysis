# syntax=docker/dockerfile:1
# Production image — used by Render for both the web service and the
# refresh_prices cron job (DEP-9.3). Distinct from Dockerfile.dev: no bind
# mount dependency (source is baked in), no --reload, dev dependency group
# excluded, binds to Render's injected $PORT rather than a fixed 8000.
FROM python:3.13-slim

# Pinned to the same uv version as Dockerfile.dev and CI (uv's own Docker
# guide recommends pinning, not floating on latest).
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

EXPOSE 8000

# $PORT is injected by Render at runtime; falls back to 8000 for a manual
# `docker run` outside Render (e.g. a local smoke test of this exact image).
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
