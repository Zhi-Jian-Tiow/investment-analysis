from app.config import Settings


def test_bare_postgres_scheme_is_rewritten_to_asyncpg():
    """Render (and most managed Postgres providers) hand out a bare
    "postgres://" URL — without a rewrite, SQLAlchemy defaults to the
    unavailable sync psycopg2 driver instead of asyncpg."""
    settings = Settings(database_url="postgres://user:pass@host/db")
    assert settings.database_url == "postgresql+asyncpg://user:pass@host/db"


def test_bare_postgresql_scheme_is_rewritten_to_asyncpg():
    settings = Settings(database_url="postgresql://user:pass@host/db")
    assert settings.database_url == "postgresql+asyncpg://user:pass@host/db"


def test_already_correct_asyncpg_url_is_untouched():
    settings = Settings(database_url="postgresql+asyncpg://user:pass@host/db")
    assert settings.database_url == "postgresql+asyncpg://user:pass@host/db"


def test_explicit_non_asyncpg_driver_is_left_alone():
    """Not this app's setup, but the rewrite is scoped to the two bare
    schemes specifically — it must never silently override an explicit,
    different driver choice."""
    settings = Settings(database_url="postgresql+psycopg2://user:pass@host/db")
    assert settings.database_url == "postgresql+psycopg2://user:pass@host/db"
