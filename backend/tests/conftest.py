"""Fixtures compartilhadas dos testes da fundação e da Fase 3."""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import (
    DEFAULT_PHONE_HASH_SECRET,
    DEFAULT_TOKEN_HASH_SECRET,
    get_settings,
)
from app.infrastructure.database.base import Base
from app.infrastructure.database.dependency import (
    get_database,
    get_engine,
    get_session,
    get_session_factory,
)
from app.main import create_app
from app.modules.avatar import models as avatar_models  # noqa: F401
from app.modules.bookings import models as bookings_models  # noqa: F401
from app.modules.chat import models as chat_models  # noqa: F401
from app.modules.clans import models as clans_models  # noqa: F401
from app.modules.email import models as email_models  # noqa: F401
from app.modules.fiscal import models as fiscal_models  # noqa: F401
from app.modules.geo import models as geo_models  # noqa: F401
from app.modules.idempotency import models as idempotency_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.identity.sms import RecordingSmsSender
from app.modules.ledger import models as ledger_models  # noqa: F401
from app.modules.legal import models as legal_models  # noqa: F401
from app.modules.matchmaking import models as matchmaking_models  # noqa: F401
from app.modules.moderation import models as moderation_models  # noqa: F401
from app.modules.notifications import models as notifications_models  # noqa: F401
from app.modules.organizations import models as organizations_models  # noqa: F401
from app.modules.organizations.platform import ensure_platform_organization
from app.modules.outbox import models as outbox_models  # noqa: F401
from app.modules.passes import models as passes_models  # noqa: F401
from app.modules.payments import models as payments_models  # noqa: F401
from app.modules.payments.adapter import SimulatorPspAdapter
from app.modules.payments.dependency import get_psp_adapter
from app.modules.pricing import models as pricing_models  # noqa: F401
from app.modules.pricing.service import seed_default_bands
from app.modules.profile import models as profile_models  # noqa: F401
from app.modules.ratelimit import models as ratelimit_models  # noqa: F401
from app.modules.ratings import models as ratings_models  # noqa: F401
from app.modules.results import models as results_models  # noqa: F401
from app.modules.season import models as season_models  # noqa: F401
from app.modules.season.service import seed_current_season, seed_season_track
from app.modules.social import models as social_models  # noqa: F401
from app.modules.tickets import models as tickets_models  # noqa: F401
from app.modules.tickets.service import seed_default_packs
from app.modules.venues import models as venues_models  # noqa: F401
from app.modules.visual import models as visual_models  # noqa: F401
from app.modules.visual.seed import seed_default_visual_catalog
from tests.compliance_helpers import TEST_CPF_KEY, TEST_CPF_KEY_ID


@pytest.fixture(scope="session", autouse=True)
def hermetic_test_settings() -> Iterator[None]:
    """Isola a suíte do ``.env`` real do desenvolvedor.

    Os testes usam apenas segredos/placeholders de teste e mantêm o caminho de
    telefone habilitado por padrão. Nenhuma credencial real do ``.env`` (por
    exemplo, provedor de e-mail) é carregada.
    """
    overrides = {
        "JOGA_ENVIRONMENT": "test",
        "JOGA_DATABASE_URL": os.environ.get("JOGA_TEST_DATABASE_URL")
        or "postgresql+psycopg://joga:joga@127.0.0.1:5434/joga",
        "JOGA_AUTH_EMAIL_ENABLED": "false",
        "JOGA_AUTH_PHONE_ENABLED": "true",
        "JOGA_ALLOW_EMAIL_REGISTRATION": "true",
        "JOGA_ALLOW_PHONE_REGISTRATION": "true",
        "JOGA_PHONE_REQUIRED_FOR_BOOKING": "false",
        "JOGA_SIGNUP_MODE": "open",
        "JOGA_EMAIL_PROVIDER": "none",
        "JOGA_EMAIL_API_KEY": "test-placeholder-not-a-real-key",
        "JOGA_EMAIL_FROM": "no-reply@joga.example",
        "JOGA_EMAIL_FROM_NAME": "JOGA",
        "JOGA_EMAIL_REPLY_TO": "",
        "JOGA_PHONE_HASH_SECRET": DEFAULT_PHONE_HASH_SECRET,
        "JOGA_TOKEN_HASH_SECRET": DEFAULT_TOKEN_HASH_SECRET,
        "JOGA_CPF_KEY": TEST_CPF_KEY,
        "JOGA_CPF_KEY_ID": TEST_CPF_KEY_ID,
        "JOGA_DEV_FIXED_OTP": "",
        "JOGA_WEB_COOKIE_SECURE": "false",
        # A compra fica desligada em produção por padrão; os testes existentes
        # que exercitam o checkout habilitam a flag explicitamente no fixture.
        "JOGA_TICKET_PURCHASE_ENABLED": "true",
        # Push nunca faz rede real nos testes; o sender é injetado.
        "JOGA_EXPO_PUSH_URL": "https://exp.host/--/api/v2/push/send",
        "JOGA_EXPO_ACCESS_TOKEN": "",
        "JOGA_PUSH_WEBHOOK_URL": "",
    }
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_database.cache_clear()
    get_session_factory.cache_clear()
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_database.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_psp_adapter] = lambda: SimulatorPspAdapter()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def email_api(client: TestClient, db_session: Session) -> Iterator[TestClient]:
    """Cliente com a credencial de e-mail habilitada e sessão SQLite isolada."""
    from app.api.v1.email_auth import get_password_service
    from tests.email_helpers import email_settings, fast_password_service

    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_settings] = lambda: email_settings()
    client.app.dependency_overrides[get_password_service] = fast_password_service
    yield client


@pytest.fixture(autouse=True)
def clear_dependency_overrides(client: TestClient) -> Iterator[None]:
    yield
    client.app.dependency_overrides.clear()


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_bands(session)
        seed_default_packs(session)
        seed_default_visual_catalog(session)
        ensure_platform_organization(session)
        season = seed_current_season(session)
        seed_season_track(session, season)
        session.commit()
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def sms_sender() -> RecordingSmsSender:
    return RecordingSmsSender()
