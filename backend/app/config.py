from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Render's "Secret Files" feature (as opposed to a plain environment
# variable) mounts the file's content on disk rather than injecting it into
# the process environment — pydantic-settings only ever reads real env vars,
# so a value stored this way is invisible to Settings() and silently
# resolves to the field's default ("") unless read from disk explicitly.
# Render documents this exact path convention: /etc/secrets/<key-name>,
# where <key-name> is whatever name was given when the Secret File was
# created (JWT_PRIVATE_KEY / JWT_PUBLIC_KEY here, matching the env-var name
# these would otherwise have used).
_RENDER_SECRET_FILES_DIR = Path("/etc/secrets")

# PEM header/footer candidates tried, in order, when a jwt_private_key /
# jwt_public_key value can't be loaded as-is — either because it has no
# "-----BEGIN ...-----" armor at all (only the base64 body was pasted), or
# because the armor is present but a single-line env-var editor (e.g.
# Render's dashboard) flattened the real newlines out of a multi-line paste,
# leaving "-----BEGIN...-----MIIEv...-----END...-----" all on one line —
# cryptography rejects that as MalformedFraming even though "BEGIN" is
# present, which is exactly why this can't gate on "BEGIN" being absent.
_PRIVATE_KEY_HEADERS = [
    ("-----BEGIN PRIVATE KEY-----", "-----END PRIVATE KEY-----"),  # PKCS8
    ("-----BEGIN RSA PRIVATE KEY-----", "-----END RSA PRIVATE KEY-----"),  # PKCS1
]
_PUBLIC_KEY_HEADERS = [
    ("-----BEGIN PUBLIC KEY-----", "-----END PUBLIC KEY-----"),  # X.509 SubjectPublicKeyInfo
    ("-----BEGIN RSA PUBLIC KEY-----", "-----END RSA PUBLIC KEY-----"),  # PKCS1
]


def _reflow_pem_body(raw: str) -> str:
    # Also un-escapes a literal "\n" text sequence, which some .env editors
    # introduce in place of a real newline when a multi-line value is pasted
    # awkwardly.
    compact = "".join(raw.replace("\\n", "\n").split())
    return "\n".join(compact[i : i + 64] for i in range(0, len(compact), 64))


def _repair_missing_pem_armor(raw: str, headers: list[tuple[str, str]], loader) -> str:
    value = raw.strip()
    if not value:
        return value

    # Fast path: already correctly formatted (real newlines intact) — the
    # overwhelmingly common case for local dev's multi-line .env value.
    try:
        loader(value.encode())
        return value
    except Exception:
        pass

    # Strip any header/footer text that IS present before reflowing, so it
    # doesn't get mangled into the base64 body alongside it.
    body = value
    for header, footer in headers:
        body = body.replace(header, "").replace(footer, "")
    body = _reflow_pem_body(body)

    for header, footer in headers:
        candidate = f"{header}\n{body}\n{footer}\n"
        try:
            loader(candidate.encode())
            return candidate
        except Exception:
            continue
    return value  # couldn't repair it — let the original error surface downstream


class Settings(BaseSettings):
    """Application configuration. Values come from environment variables / .env
    (architecture §14.5 — secrets are env vars only, never committed to git).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://bursatrack:bursatrack@localhost:5433/bursatrack"

    @field_validator("database_url")
    @classmethod
    def _normalize_asyncpg_driver(cls, v: str) -> str:
        # Managed Postgres providers (Render, Heroku, Supabase, ...) hand out
        # a bare "postgres://" or "postgresql://" connection string in their
        # dashboard. Without an explicit "+asyncpg" driver suffix, SQLAlchemy
        # defaults the postgresql dialect to the sync psycopg2 driver — which
        # this app never installs, since every DB call here is async via
        # asyncpg. Rewrite rather than require the pasted value to already be
        # SQLAlchemy-specific; already-correct URLs (any explicit "+driver")
        # pass through untouched.
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v

    # RS256 keypair, PEM-encoded (architecture §14.1). Stored as raw PEM content in
    # the env var, matching how Render environment variables are documented to hold it.
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    jwt_access_token_expiry_days: int = 7

    @field_validator("jwt_private_key")
    @classmethod
    def _fix_private_key_armor(cls, v: str) -> str:
        return _repair_missing_pem_armor(
            v, _PRIVATE_KEY_HEADERS, lambda b: serialization.load_pem_private_key(b, password=None)
        )

    @field_validator("jwt_public_key")
    @classmethod
    def _fix_public_key_armor(cls, v: str) -> str:
        return _repair_missing_pem_armor(v, _PUBLIC_KEY_HEADERS, serialization.load_pem_public_key)

    trial_period_days: int = 14
    email_verification_token_expiry_hours: int = 24

    session_cookie_name: str = "bursatrack_session"
    cookie_secure: bool = True

    admin_api_key: str = ""

    # Resend (architecture §11.3). email_from_address defaults to Resend's own
    # sandbox sender, which works with no domain verification — fine for local
    # dev/testing; swap to a verified BursaTrack domain address before launch.
    resend_api_key: str = ""
    email_from_address: str = "BursaTrack <onboarding@resend.dev>"
    # Base URL emailed verify/reset links point at. No frontend exists yet
    # (FE-1.x not started) — this makes that an env var, not a hardcoded
    # guess, so it's a one-line config change once the frontend is deployed.
    frontend_base_url: str = "http://localhost:3000"

    # CORS (architecture §14.3). Comma-separated static allowlist — production
    # domain(s) plus http://localhost:3000 for local dev.
    cors_allowed_origins: str = "http://localhost:3000"

    # CRIT-R-001: a bare "https://*.vercel.app" wildcard is unsafe combined
    # with allow_credentials=True (any Vercel-hosted app could then make
    # credentialed cross-origin requests). This must instead be a regex
    # scoped to this project's own preview URLs specifically — e.g.
    # r"^https://bursatrack-[a-z0-9-]+-[a-z0-9]+\.vercel\.app$" once the real
    # Vercel project slug is known. Left empty (disabled) until then — DEP-9.3
    # sets this once the Vercel project actually exists, not before.
    cors_vercel_preview_regex: str = ""

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


def _read_render_secret_file(key_name: str) -> str | None:
    path = _RENDER_SECRET_FILES_DIR / key_name
    if path.is_file():
        return path.read_text()
    return None  # not present — e.g. local dev, or this key uses a plain env var instead


@lru_cache
def get_settings() -> Settings:
    # Explicit constructor kwargs take priority over env-var-sourced values
    # in pydantic-settings, so this only overrides jwt_private_key/
    # jwt_public_key when a matching Secret File actually exists — every
    # other field (and these two, on a machine using plain env vars instead)
    # still resolves normally from the environment/.env file.
    secret_file_overrides = {}
    for env_name, field_name in [("JWT_PRIVATE_KEY", "jwt_private_key"), ("JWT_PUBLIC_KEY", "jwt_public_key")]:
        content = _read_render_secret_file(env_name)
        if content is not None:
            secret_file_overrides[field_name] = content

    return Settings(**secret_file_overrides)
