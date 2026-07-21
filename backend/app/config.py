from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration. Values come from environment variables / .env
    (architecture §14.5 — secrets are env vars only, never committed to git).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://bursatrack:bursatrack@localhost:5432/bursatrack"

    # RS256 keypair, PEM-encoded (architecture §14.1). Stored as raw PEM content in
    # the env var, matching how Render environment variables are documented to hold it.
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    jwt_access_token_expiry_days: int = 7

    trial_period_days: int = 14
    email_verification_token_expiry_hours: int = 24

    session_cookie_name: str = "bursatrack_session"
    cookie_secure: bool = True

    admin_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
