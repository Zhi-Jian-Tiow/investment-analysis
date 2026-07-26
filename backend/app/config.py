from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# PEM header/footer candidates tried, in order, when a jwt_private_key /
# jwt_public_key value has no "-----BEGIN ...-----" armor at all — the
# signature of someone having pasted only the base64 body of a generated key
# (e.g. copying between the header/footer lines rather than including them).
# Only engaged when "BEGIN" is missing from the raw value, so a
# correctly-armored key is never touched.
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
    if not value or "BEGIN" in value:
        return value  # empty, or already has real armor — leave untouched

    body = _reflow_pem_body(value)
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

    # CORS (architecture §14.3). Comma-separated static allowlist. The
    # architecture's fuller design (production domain + a regex for Vercel
    # preview URLs) is deferred until there's an actual deployment target —
    # this is just enough for local dev against the FE-1.x Next.js app.
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
