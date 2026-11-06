"""Testes de concorrência da Fase 7 contra PostgreSQL real.

Executados apenas quando `JOGA_TEST_DATABASE_URL` aponta para um banco
descartável. Usam um schema isolado (`results_test`) para não tocar nas
tabelas criadas pela migração.
"""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.modules.idempotency import models as idempotency_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.matches.models import Match, MatchStateTransition
from app.modules.matchmaking import models as matchmaking_models  # noqa: F401
from app.modules.profile import models as profile_models  # noqa: F401
from app.modules.ratelimit import models as ratelimit_models  # noqa: F401
from app.modules.ratelimit.models import RateLimitCounter
from app.modules.ratelimit.service import RateLimitExceeded
from app.modules.ratelimit.service import enforce as enforce_rate_limit
from app.modules.results import models as results_models  # noqa: F401
from app.modules.results.models import (
    MatchDispute,
    MatchResultCaptainConfirmation,
    MatchResultDecision,
    MatchResultReport,
    MatchResultReview,
    MatchResultRound,
)
from app.modules.results.service import (
    ConfirmationAlreadySubmitted,
    ReportAlreadySubmitted,
    ResultsService,
    ReviewNotFound,
)
from tests.helpers_results import END, build_match

TEST_DATABASE_URL = os.environ.get("JOGA_TEST_DATABASE_URL")
SCHEMA = "results_test"
AT = END + timedelta(minutes=2)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="JOGA_TEST_DATABASE_URL não definido; teste de resultados ignorado",
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


def open_round(session_factory: sessionmaker[Session], match_id: uuid.UUID) -> datetime:
    with session_factory() as session:
        service = ResultsService(session)
        service.advance(now=END)
        session.commit()
        round_row = service.current_round(match_id)
        assert round_row is not None
        assert round_row.status == "OPEN"
        return round_row.deadline


def run_concurrently(
    session_factory: sessionmaker[Session],
    actions: list[Callable[[Session], None]],
) -> list[BaseException]:
    """Executa ações em transações separadas, todas partindo juntas."""
    barrier = threading.Barrier(len(actions))
    errors: list[BaseException] = []

    def wrapper(action: Callable[[Session], None]) -> None:
        with session_factory() as session:
            try:
                barrier.wait(timeout=15)
                action(session)
                session.commit()
            except BaseException as error:  # noqa: BLE001 - erro é inspecionado
                session.rollback()
                errors.append(error)

    threads = [threading.Thread(target=wrapper, args=(action,)) for action in actions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads)
    return errors


def test_concurrent_duplicate_report_creates_one_vote(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        match, users, participants, _ = build_match(session, checked_in=10)
        match_id = match.id
        user_id = users[0]
        participant = next(item for item in participants if item.user_id == user_id)
        participant_id = participant.id
        session.commit()

    open_round(session_factory, match_id)

    def submit(key: str) -> Callable[[Session], None]:
        def action(session: Session) -> None:
            ResultsService(session).submit_report(
                match_id=match_id,
                user_id=user_id,
                round_number=1,
                outcome="TEAM_1",
                idempotency_key=key,
                request_hash=key,
                now=AT,
            )

        return action

    errors = run_concurrently(session_factory, [submit("concurrent-a"), submit("concurrent-b")])

    assert sum(isinstance(error, ReportAlreadySubmitted) for error in errors) == 1
    assert all(isinstance(error, ReportAlreadySubmitted) for error in errors)

    with session_factory() as session:
        reports = session.scalar(
            select(func.count())
            .select_from(MatchResultReport)
            .where(MatchResultReport.participant_id == participant_id)
        )
        assert reports == 1


def test_concurrent_reports_from_different_participants_are_preserved(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        match, users, participants, _ = build_match(session, checked_in=10)
        match_id = match.id
        voters = users[:2]
        voter_participant_ids = [item.id for item in participants if item.user_id in set(voters)]
        session.commit()

    open_round(session_factory, match_id)

    def submit(user_id: uuid.UUID, key: str) -> Callable[[Session], None]:
        def action(session: Session) -> None:
            ResultsService(session).submit_report(
                match_id=match_id,
                user_id=user_id,
                round_number=1,
                outcome="TEAM_1",
                idempotency_key=key,
                request_hash=key,
                now=AT,
            )

        return action

    errors = run_concurrently(
        session_factory,
        [submit(voters[0], "voter-a"), submit(voters[1], "voter-b")],
    )
    assert errors == []

    with session_factory() as session:
        reports = session.scalar(
            select(func.count())
            .select_from(MatchResultReport)
            .where(MatchResultReport.participant_id.in_(voter_participant_ids))
        )
        assert reports == 2


def test_two_workers_close_round_and_open_single_dispute(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        match, users, _, _ = build_match(session, checked_in=10)
        match_id = match.id
        session.commit()

    deadline = open_round(session_factory, match_id)

    with session_factory() as session:
        service = ResultsService(session)
        for index, outcome in enumerate(
            ["TEAM_1", "TEAM_1", "TEAM_1", "TEAM_2", "TEAM_2", "DRAW", "DRAW"]
        ):
            service.submit_report(
                match_id=match_id,
                user_id=users[index],
                round_number=1,
                outcome=outcome,
                idempotency_key=f"vote-{index}",
                request_hash=f"vote-{index}",
                now=AT,
            )
        session.commit()

    when = max(deadline, END) + timedelta(minutes=1)

    def advance(session: Session) -> None:
        ResultsService(session).advance(now=when)

    errors = run_concurrently(session_factory, [advance, advance])
    assert errors == []

    with session_factory() as session:
        round_row = session.scalar(
            select(MatchResultRound).where(MatchResultRound.match_id == match_id)
        )
        match = session.get(Match, match_id)
        reviews = session.scalar(
            select(func.count())
            .select_from(MatchResultReview)
            .where(MatchResultReview.match_id == match_id)
        )
        disputes = session.scalar(
            select(func.count()).select_from(MatchDispute).where(MatchDispute.match_id == match_id)
        )
        disputed_events = session.scalar(
            select(func.count())
            .select_from(MatchStateTransition)
            .where(
                MatchStateTransition.match_id == match_id,
                MatchStateTransition.to_state == "DISPUTED",
            )
        )

    assert round_row is not None and round_row.status == "CLOSED"
    assert round_row.valid_votes == 7
    assert match is not None and match.state == "DISPUTED"
    assert reviews == 1
    assert disputes == 1
    assert disputed_events == 1


def test_concurrent_captain_confirmation_creates_one_record(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        match, users, participants, _ = build_match(session, checked_in=10)
        match_id = match.id
        captain = next(participant for participant in participants if participant.is_captain)
        captain_user_id = captain.user_id
        session.commit()

    open_round(session_factory, match_id)

    def confirm(key: str) -> Callable[[Session], None]:
        def action(session: Session) -> None:
            ResultsService(session).submit_confirmation(
                match_id=match_id,
                user_id=captain_user_id,
                round_number=1,
                outcome="TEAM_1",
                idempotency_key=key,
                request_hash=key,
                now=AT,
            )

        return action

    errors = run_concurrently(session_factory, [confirm("captain-a"), confirm("captain-b")])

    assert sum(isinstance(error, ConfirmationAlreadySubmitted) for error in errors) == 1
    assert all(isinstance(error, ConfirmationAlreadySubmitted) for error in errors)

    with session_factory() as session:
        confirmations = session.scalar(
            select(func.count())
            .select_from(MatchResultCaptainConfirmation)
            .where(MatchResultCaptainConfirmation.participant_id == captain.id)
        )
        assert confirmations == 1


def test_two_workers_open_only_one_second_round(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        match, users, _, _ = build_match(session, checked_in=10)
        match_id = match.id
        session.commit()

    deadline = open_round(session_factory, match_id)

    with session_factory() as session:
        service = ResultsService(session)
        for index in range(6):
            service.submit_report(
                match_id=match_id,
                user_id=users[index],
                round_number=1,
                outcome="TEAM_1" if index < 3 else "TEAM_2",
                idempotency_key=f"tie-{index}",
                request_hash=f"tie-{index}",
                now=AT,
            )
        session.commit()

    when = deadline + timedelta(minutes=1)

    def advance(session: Session) -> None:
        ResultsService(session).advance(now=when)

    errors = run_concurrently(session_factory, [advance, advance])
    assert errors == []

    with session_factory() as session:
        first = session.scalar(
            select(MatchResultRound).where(
                MatchResultRound.match_id == match_id,
                MatchResultRound.round_number == 1,
            )
        )
        second = session.scalar(
            select(MatchResultRound).where(
                MatchResultRound.match_id == match_id,
                MatchResultRound.round_number == 2,
            )
        )
        total_rounds = session.scalar(
            select(func.count())
            .select_from(MatchResultRound)
            .where(MatchResultRound.match_id == match_id)
        )

    assert first is not None and first.outcome == "SECOND_ROUND"
    assert second is not None and second.status == "OPEN"
    assert total_rounds == 2


def test_concurrent_human_decisions_resolve_review_once(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        match, users, _, _ = build_match(session, checked_in=10)
        match_id = match.id
        session.commit()

    deadline = open_round(session_factory, match_id)

    with session_factory() as session:
        service = ResultsService(session)
        for index in range(4):
            service.submit_report(
                match_id=match_id,
                user_id=users[index],
                round_number=1,
                outcome="TEAM_1",
                idempotency_key=f"quorum-{index}",
                request_hash=f"quorum-{index}",
                now=AT,
            )
        service.advance(now=deadline + timedelta(minutes=1))
        session.commit()

    def decide(operator: str) -> Callable[[Session], None]:
        def action(session: Session) -> None:
            ResultsService(session).decide(
                match_id=match_id,
                decision="FINALIZE",
                outcome="TEAM_1",
                reason=f"decisão {operator}",
                operator_id=operator,
            )

        return action

    errors = run_concurrently(session_factory, [decide("operator-a"), decide("operator-b")])

    assert sum(isinstance(error, ReviewNotFound) for error in errors) == 1
    assert all(isinstance(error, ReviewNotFound) for error in errors)

    with session_factory() as session:
        decision_count = session.scalar(
            select(func.count())
            .select_from(MatchResultDecision)
            .where(MatchResultDecision.match_id == match_id)
        )
        resolved = session.scalar(
            select(func.count())
            .select_from(MatchResultReview)
            .where(
                MatchResultReview.match_id == match_id,
                MatchResultReview.status == "RESOLVED",
            )
        )
        match = session.get(Match, match_id)

    assert decision_count == 1
    assert resolved == 1
    assert match is not None and match.state == "FINALIZED"
    assert match.final_result == "TEAM_1"
    assert match.result_version == 1


def test_rate_limit_allows_exactly_limit_under_concurrency(
    session_factory: sessionmaker[Session],
) -> None:
    def hit(session: Session) -> None:
        enforce_rate_limit(
            session,
            scope="concurrent-test",
            key="same-user",
            limit=5,
            now=AT,
        )

    errors = run_concurrently(session_factory, [hit] * 10)

    assert len(errors) == 5, errors
    assert all(isinstance(error, RateLimitExceeded) for error in errors), errors

    with session_factory() as session:
        count = session.scalar(
            select(RateLimitCounter.count).where(
                RateLimitCounter.scope == "concurrent-test",
                RateLimitCounter.key == "same-user",
            )
        )
    assert count == 5
