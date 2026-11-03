"""Testes de concorrência do ciclo de partida em PostgreSQL."""

import os
import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.identity.models import User
from app.modules.matches.models import Match, MatchParticipant, MatchStateTransition
from app.modules.matches.service import MatchService, create_match_for_lobby
from app.modules.matchmaking.models import Lobby, LobbyParticipant, QueueEntry
from app.modules.profile.models import (
    Availability,
    Sport,
    SportFormat,
    UserRegion,
    UserSportProfile,
)

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "matches_test"
NOW = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)
START = datetime(2026, 11, 4, 21, 0, tzinfo=UTC)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="JOGA_TEST_DATABASE_URL não definido; teste de partidas ignorado",
)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    assert TEST_DATABASE_URL is not None
    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    admin_engine.dispose()

    database_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True).execution_options(
        schema_translate_map={None: SCHEMA}
    )
    Base.metadata.create_all(database_engine)
    yield database_engine

    Base.metadata.drop_all(database_engine)
    database_engine.dispose()
    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    admin_engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def clean_tables(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def build_match(session: Session) -> tuple[Match, list[uuid.UUID]]:
    sport = Sport(slug="futebol", name="Futebol")
    session.add(sport)
    session.flush()
    sport_format = SportFormat(
        sport_id=sport.id,
        slug="futebol-5x5",
        name="Futebol 5x5",
        team_size=5,
        total_participants=10,
        play_minutes=50,
        break_minutes=10,
        duration_minutes=60,
        version=1,
    )
    session.add(sport_format)
    session.flush()
    lobby = Lobby(
        format_id=sport_format.id,
        format_version=1,
        origin="matchmaking",
        mode="casual",
        status="scheduled",
        court_preference="ANY",
        scheduled_start_at=START,
        scheduled_end_at=START + timedelta(minutes=60),
        duration_minutes=60,
        center_lat=-23.55,
        center_lng=-46.63,
        radius_km=10,
        algorithm_version="level_v1",
    )
    session.add(lobby)
    session.flush()

    users: list[uuid.UUID] = []
    participants: list[LobbyParticipant] = []
    for index in range(10):
        user = User(status="active")
        session.add(user)
        session.flush()
        session.add(
            UserRegion(
                user_id=user.id,
                source="cep",
                cep="01001000",
                city="São Paulo",
                state="SP",
                radius_km=10,
                center_lat=-23.55,
                center_lng=-46.63,
            )
        )
        session.add(
            UserSportProfile(
                user_id=user.id,
                format_id=sport_format.id,
                level="intermediate",
                court_preference="ANY",
            )
        )
        session.add(
            Availability(
                user_id=user.id,
                weekday=3,
                start_time=time(18, 0),
                end_time=time(22, 0),
                timezone="America/Sao_Paulo",
            )
        )
        entry = QueueEntry(
            user_id=user.id,
            format_id=sport_format.id,
            mode="casual",
            court_preference="ANY",
            level="intermediate",
            status="matched",
            center_lat=-23.55,
            center_lng=-46.63,
            radius_km=10,
            lobby_id=lobby.id,
            expires_at=NOW + timedelta(hours=48),
        )
        session.add(entry)
        session.flush()
        participant = LobbyParticipant(
            lobby_id=lobby.id,
            user_id=user.id,
            queue_entry_id=entry.id,
            team=1 if index < 5 else 2,
            level="intermediate",
        )
        session.add(participant)
        participants.append(participant)
        users.append(user.id)
    session.flush()

    match = create_match_for_lobby(session, lobby, participants, now=NOW)
    session.commit()
    return match, users


def test_concurrent_confirmations_make_match_ready_once(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        match, users = build_match(session)
        match_id = match.id

    barrier = threading.Barrier(10)
    errors: list[BaseException] = []

    def confirm(user_id: uuid.UUID) -> None:
        with session_factory() as session:
            try:
                barrier.wait(timeout=15)
                MatchService(session).confirm(match_id, user_id, now=NOW)
                session.commit()
            except BaseException as error:  # noqa: BLE001 - erro é inspecionado no teste
                session.rollback()
                errors.append(error)

    threads = [threading.Thread(target=confirm, args=(user_id,)) for user_id in users]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert not any(thread.is_alive() for thread in threads)
    assert not errors, f"erros inesperados: {errors!r}"

    with session_factory() as session:
        match = session.get(Match, match_id)
        assert match is not None and match.state == "READY"
        confirmed = session.scalar(
            select(func.count())
            .select_from(MatchParticipant)
            .where(
                MatchParticipant.match_id == match_id,
                MatchParticipant.status == "confirmed",
            )
        )
        ready_events = session.scalar(
            select(func.count())
            .select_from(MatchStateTransition)
            .where(
                MatchStateTransition.match_id == match_id,
                MatchStateTransition.to_state == "READY",
            )
        )

    assert confirmed == 10
    assert ready_events == 1
