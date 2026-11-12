"""Fixtures compartilhadas dos testes da fundação e da Fase 3."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.main import create_app
from app.modules.bookings import models as bookings_models  # noqa: F401
from app.modules.chat import models as chat_models  # noqa: F401
from app.modules.idempotency import models as idempotency_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.identity.sms import RecordingSmsSender
from app.modules.matchmaking import models as matchmaking_models  # noqa: F401
from app.modules.organizations import models as organizations_models  # noqa: F401
from app.modules.outbox import models as outbox_models  # noqa: F401
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
from app.modules.season.service import seed_current_season
from app.modules.social import models as social_models  # noqa: F401
from app.modules.tickets import models as tickets_models  # noqa: F401
from app.modules.tickets.service import seed_default_packs
from app.modules.venues import models as venues_models  # noqa: F401


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_psp_adapter] = lambda: SimulatorPspAdapter()
    with TestClient(app) as test_client:
        yield test_client


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
        seed_current_season(session)
        session.commit()
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def sms_sender() -> RecordingSmsSender:
    return RecordingSmsSender()
