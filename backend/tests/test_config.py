from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import app.config as config_module
from app.config import Settings, get_settings


def _generate_rsa_pem_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private_pem, public_pem


def _flatten_pem(pem: str) -> str:
    """Simulates what a single-line env-var editor (e.g. Render's dashboard)
    does to a pasted multi-line PEM: the BEGIN/END markers survive, but the
    real newlines between them are gone — this is the exact real-world
    failure mode (cryptography raises MalformedFraming), not a synthetic
    edge case."""
    return pem.replace("\n", "")


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


def test_correctly_formatted_pem_keys_are_untouched():
    """Not required to be byte-identical (Settings.strip()s trailing
    whitespace, which predates this fix) — just still a valid, loadable PEM,
    and not run through the reflow/rebuild repair path at all."""
    private_pem, public_pem = _generate_rsa_pem_pair()
    settings = Settings(jwt_private_key=private_pem, jwt_public_key=public_pem)
    assert settings.jwt_private_key == private_pem.strip()
    assert settings.jwt_public_key == public_pem.strip()


def test_flattened_pem_with_headers_intact_is_repaired():
    """The real bug: Render's dashboard flattened a pasted multi-line PEM
    into one line while keeping "-----BEGIN...-----"/"-----END...-----"
    intact. The old repair logic gated on "BEGIN" being absent from the raw
    value, so it skipped repair entirely here and shipped a PEM cryptography
    rejects as MalformedFraming — jwt.encode() then failed on every request
    that needed to sign a token (register, login)."""
    private_pem, public_pem = _generate_rsa_pem_pair()
    settings = Settings(jwt_private_key=_flatten_pem(private_pem), jwt_public_key=_flatten_pem(public_pem))

    # The point isn't byte-for-byte equality with the original — it's that
    # the repaired value is actually loadable.
    serialization.load_pem_private_key(settings.jwt_private_key.encode(), password=None)
    serialization.load_pem_public_key(settings.jwt_public_key.encode())


def test_base64_body_only_with_no_armor_is_still_repaired():
    """The original supported case — pasting only the base64 body between
    the header/footer lines, no armor at all — must keep working."""
    private_pem, public_pem = _generate_rsa_pem_pair()
    body_only_private = "\n".join(private_pem.splitlines()[1:-1])
    body_only_public = "\n".join(public_pem.splitlines()[1:-1])

    settings = Settings(jwt_private_key=body_only_private, jwt_public_key=body_only_public)

    serialization.load_pem_private_key(settings.jwt_private_key.encode(), password=None)
    serialization.load_pem_public_key(settings.jwt_public_key.encode())


def test_unrepairable_garbage_is_passed_through_untouched():
    settings = Settings(jwt_private_key="not a key at all", jwt_public_key="also not a key")
    assert settings.jwt_private_key == "not a key at all"
    assert settings.jwt_public_key == "also not a key"


def test_get_settings_reads_render_secret_files_when_present(tmp_path, monkeypatch):
    """The real bug: Render's "Secret Files" feature mounts content on disk
    rather than injecting an env var — pydantic-settings only reads env
    vars, so a JWT key stored this way was invisible to Settings() and
    silently resolved to "" (confirmed live via a diagnostic log showing
    len=0). get_settings() must check the documented /etc/secrets/<name>
    location and use that content when a plain env var isn't set."""
    private_pem, public_pem = _generate_rsa_pem_pair()
    (tmp_path / "JWT_PRIVATE_KEY").write_text(private_pem)
    (tmp_path / "JWT_PUBLIC_KEY").write_text(public_pem)

    monkeypatch.setattr(config_module, "_RENDER_SECRET_FILES_DIR", tmp_path)
    monkeypatch.setenv("JWT_PRIVATE_KEY", "")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "")
    get_settings.cache_clear()

    settings = get_settings()
    try:
        serialization.load_pem_private_key(settings.jwt_private_key.encode(), password=None)
        serialization.load_pem_public_key(settings.jwt_public_key.encode())
    finally:
        get_settings.cache_clear()  # don't leak this override into other tests


def test_get_settings_falls_back_to_env_var_when_no_secret_file_present(tmp_path, monkeypatch):
    """Local dev (and anyone using plain env vars instead of Secret Files on
    Render) must be unaffected — no file at the mount point means the
    env-var-sourced value is used exactly as before."""
    private_pem, public_pem = _generate_rsa_pem_pair()

    monkeypatch.setattr(config_module, "_RENDER_SECRET_FILES_DIR", tmp_path)  # empty dir — no secret files
    monkeypatch.setenv("JWT_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("JWT_PUBLIC_KEY", public_pem)
    get_settings.cache_clear()

    settings = get_settings()
    try:
        assert settings.jwt_private_key == private_pem.strip()
        assert settings.jwt_public_key == public_pem.strip()
    finally:
        get_settings.cache_clear()
