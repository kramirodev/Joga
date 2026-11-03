"""Testes de formação de matchmaking em PostgreSQL real (locks e concorrência)."""

import os
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, time

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.identity.models import User
from app.modules.matchmaking.models import (
    Lobby,
    LobbyParticipant,
    MatchmakingRun,
    QueueEntry,
)
from app.modules.matchmaking.service import MatchmakingService
from app.modules.profile.models import (
    Availability,
    Sport,
    SportFormat,
    UserRegion,
    UserSportProfile,
)

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "matchmaking_test"
NOW = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="JOGA_TEST_DATABASE_URL não definido; teste de matchmaking ignorado",
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


def seed_format(session: Session) -> SportFormat:
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
    return sport_format


def add_player(
    session: Session,
    sport_format: SportFormat,
    *,
    court: str = "ANY",
    level: str = "intermediate",
    lat: float = -23.55,
    lng: float = -46.63,
    radius: int = 10,
    available: bool = True,
) -> User:
    user = User(status="active")
    session.add(user)
    session.flush()
    session.add(
        UserSportProfile(
            user_id=user.id,
            format_id=sport_format.id,
            level=level,
            court_preference=court,
        )
    )
    session.add(
        UserRegion(
            user_id=user.id,
            source="cep",
            cep="01001000",
            city="São Paulo",
            state="SP",
            radius_km=radius,
            center_lat=lat,
            center_lng=lng,
        )
    )
    if available:
        session.add(
            Availability(
                user_id=user.id,
                weekday=2,
                start_time=time(18, 0),
                end_time=time(22, 0),
                timezone="America/Sao_Paulo",
            )
        )
    session.flush()
    return user


def queue_players(
    session: Session,
    sport_format: SportFormat,
    count: int,
    **kwargs: object,
) -> list[QueueEntry]:
    service = MatchmakingService(session)
    entries = []
    for _ in range(count):
        user = add_player(session, sport_format, **kwargs)  # type: ignore[arg-type]
        entries.append(service.enqueue(user.id, sport_format.id, now=NOW))
    session.flush()
    return entries


def service(session: Session) -> MatchmakingService:
    return MatchmakingService(session)


def test_forms_one_lobby_with_balanced_teams(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        levels = ["advanced", "advanced", "intermediate", "intermediate", "intermediate"] * 2
        entries = []
        for level in levels:
            user = add_player(session, sport_format, level=level)
            entries.append(service(session).enqueue(user.id, sport_format.id, now=NOW))
        session.flush()

        result = service(session).run_once(NOW)
        session.commit()

        assert result.lobbies_formed == 1
        lobby = session.scalar(select(Lobby))
        assert lobby is not None
        assert lobby.mode == "casual"
        assert lobby.algorithm_version == "level_v1"
        assert lobby.duration_minutes == 60
        assert lobby.scheduled_start_at.replace(tzinfo=UTC) == datetime(
            2026, 11, 3, 21, 0, tzinfo=UTC
        )
        assert lobby.court_preference == "ANY"

        participants = list(session.scalars(select(LobbyParticipant)))
        assert len(participants) == 10
        assert {item.team for item in participants} == {1, 2}
        assert sum(1 for item in participants if item.team == 1) == 5
        assert (
            session.scalar(
                select(func.count()).select_from(QueueEntry).where(QueueEntry.status == "matched")
            )
            == 10
        )

        run = session.scalar(select(MatchmakingRun))
        assert run is not None and run.status == "completed"
        assert run.lobbies_formed == 1


def test_rerun_does_not_duplicate(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        queue_players(session, sport_format, 10)
        session.commit()

        first = service(session).run_once(NOW)
        session.commit()
        second = service(session).run_once(NOW)
        session.commit()

        assert first.lobbies_formed == 1
        assert second.lobbies_formed == 0
        assert session.scalar(select(func.count()).select_from(Lobby)) == 1
        assert session.scalar(select(func.count()).select_from(LobbyParticipant)) == 10


def test_expired_entries_are_marked_and_not_formed(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        entries = queue_players(session, sport_format, 10)
        for entry in entries:
            entry.expires_at = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
        session.commit()

        result = service(session).run_once(NOW)
        session.commit()

        assert result.entries_expired == 10
        assert result.lobbies_formed == 0
        assert session.scalar(select(func.count()).select_from(Lobby)) == 0


def test_incompatible_court_preferences_do_not_form(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        queue_players(session, sport_format, 5, court="PUBLIC_ONLY")
        queue_players(session, sport_format, 5, court="PRIVATE_ONLY")
        session.commit()

        result = service(session).run_once(NOW)
        session.commit()

        assert result.lobbies_formed == 0
        assert session.scalar(select(func.count()).select_from(Lobby)) == 0


def test_distant_participants_do_not_form(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        queue_players(session, sport_format, 9, lat=-23.55, lng=-46.63, radius=5)
        queue_players(session, sport_format, 1, lat=-22.90, lng=-43.18, radius=5)
        session.commit()

        result = service(session).run_once(NOW)
        session.commit()

        assert result.lobbies_formed == 0


def test_missing_availability_blocks_formation(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        queue_players(session, sport_format, 9)
        queue_players(session, sport_format, 1, available=False)
        session.commit()

        result = service(session).run_once(NOW)
        session.commit()

        assert result.lobbies_formed == 0


def test_concurrent_workers_never_duplicate_participants(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        sport_format = seed_format(session)
        queue_players(session, sport_format, 20)
        session.commit()

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker() -> None:
        with session_factory() as session:
            try:
                barrier.wait(timeout=10)
                service(session).run_once(NOW)
                session.commit()
            except BaseException as error:  # noqa: BLE001 - falha é registrada e vista no teste
                session.commit()
                errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not any(thread.is_alive() for thread in threads)
    assert not errors, f"erros inesperados: {errors!r}"

    with session_factory() as session:
        lobbies = session.scalar(select(func.count()).select_from(Lobby))
        participants = list(session.scalars(select(LobbyParticipant)))
        matched_entries = session.scalar(
            select(func.count()).select_from(QueueEntry).where(QueueEntry.status == "matched")
        )

    assert lobbies == 2
    assert len(participants) == 20
    assert len({item.user_id for item in participants}) == 20
    assert matched_entries == 20
