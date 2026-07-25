from uuid import uuid4

import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Import every module's models so Base.metadata is fully populated before
# create_all runs.
import app.admin.models  # noqa: F401
import app.auth.models  # noqa: F401
import app.portfolio.models  # noqa: F401
from app.auth.lockout import tracker as login_lockout_tracker
from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.portfolio.models import BrokerConfig
from app.rate_limit import limiter


def _generate_rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest_asyncio.fixture(autouse=True)
async def reset_rate_limiter():
    # Prevents the 3/minute register limit (and others) from leaking state
    # between tests that share the same in-process Limiter.
    limiter.reset()
    yield


@pytest_asyncio.fixture(autouse=True)
async def reset_login_lockout():
    # Same reasoning as reset_rate_limiter, for the separate BR-016 in-process
    # login-failure tracker.
    login_lockout_tracker.reset()
    yield


@pytest_asyncio.fixture
async def test_settings() -> Settings:
    private_key, public_key = _generate_rsa_keypair()
    return Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_private_key=private_key,
        jwt_public_key=public_key,
        cookie_secure=False,
    )


@pytest_asyncio.fixture
async def db_engine():
    # StaticPool keeps a single underlying connection alive for the in-memory
    # SQLite DB — otherwise each checkout would see an empty database.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_broker(db_session) -> BrokerConfig:
    broker = BrokerConfig(
        id=uuid4(),
        name="Maybank IB",
        fee_type="percentage",
        rate="0.007",
        minimum_fee="8.00",
        is_system=True,
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest_asyncio.fixture
async def client(db_session, test_settings):
    async def override_get_db():
        yield db_session

    async def override_get_settings():
        return test_settings

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_settings] = override_get_settings

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_with_cookie(client):
    """Factory for a second client sharing the same app/dependency overrides
    as `client`, but with an explicit, arbitrary cookie jar. Used to send a
    specific (possibly stale/expired/malformed) session cookie for a single
    request without touching the main `client` fixture's own cookie jar —
    the supported alternative to httpx's now-deprecated per-request
    `cookies=` argument.
    """

    async def _make(cookies: dict[str, str]) -> AsyncClient:
        transport = ASGITransport(app=fastapi_app)
        return AsyncClient(transport=transport, base_url="http://test", cookies=cookies)

    return _make
