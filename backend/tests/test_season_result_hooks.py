"""Ganchos de temporada no resultado e no check-in (Fase 14D.10 e 14D.11)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.modules.identity.clock import utcnow
from app.modules.matches.service import MatchService
from app.modules.season.models import MissionProgress
from app.modules.season.service import (
    active_season,
    get_progress,
    record_match_result,
    streak_for,
    week_start,
)
from tests.helpers_results import END, build_match
from tests.test_matches_service import START as MATCH_START
from tests.test_matches_service import build_match as build_match_lifecycle
from tests.test_results_service import AT, close_round, open_round, submit


def test_finalized_win_awards_xp_and_streak(db_session: Session) -> None:
    match, users, participants, _ = build_match(db_session, checked_in=10)
    team_one = {row.user_id for row in participants if row.team == 1}
    assert team_one

    service, round_row = open_round(db_session, match.id)
    submit(service, match.id, users, ["TEAM_1"] * len(users))
    close_round(db_session, round_row)

    assert match.state == "FINALIZED"
    assert match.final_result == "TEAM_1"
    season = active_season(db_session, AT)
    for user_id in users:
        progress = get_progress(db_session, user_id, season)
        expected = 40 if user_id in team_one else 0
        assert (progress.xp_total if progress else 0) == expected
        streak = streak_for(db_session, user_id)
        assert streak.current_wins == (1 if user_id in team_one else 0)

    # Reexecutar o gancho não duplica XP nem sequer a streak do mesmo jogo.
    service._award_season_result(match, AT)
    db_session.flush()
    for user_id in team_one:
        progress = get_progress(db_session, user_id, season)
        assert progress is not None and progress.xp_total == 40
        assert streak_for(db_session, user_id).current_wins == 1


def test_draw_resets_streak_without_win_xp(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    record_match_result(
        db_session,
        users[0],
        match_id=uuid.uuid4(),
        won=True,
        played_at=END - timedelta(days=7),
    )
    assert streak_for(db_session, users[0]).current_wins == 1

    service, round_row = open_round(db_session, match.id)
    submit(service, match.id, users, ["DRAW"] * len(users))
    close_round(db_session, round_row)

    assert match.final_result == "DRAW"
    season = active_season(db_session, AT)
    for user_id in users:
        progress = get_progress(db_session, user_id, season)
        assert progress is None or progress.xp_total == 0
        assert streak_for(db_session, user_id).current_wins == 0


def test_disputed_result_awards_nothing(db_session: Session) -> None:
    match, users, _, _ = build_match(db_session, checked_in=10)
    service, round_row = open_round(db_session, match.id)
    submit(
        service,
        match.id,
        users,
        ["TEAM_1", "TEAM_1", "TEAM_1", "TEAM_1"]
        + ["TEAM_2", "TEAM_2", "TEAM_2"]
        + ["DRAW", "DRAW", "DRAW"],
    )
    close_round(db_session, round_row)

    assert match.state == "DISPUTED"
    season = active_season(db_session, utcnow())
    for user_id in users:
        progress = get_progress(db_session, user_id, season)
        assert progress is None or progress.xp_total == 0
        assert streak_for(db_session, user_id).current_wins == 0


def test_on_time_checkin_completes_mission(db_session: Session) -> None:
    match, users = build_match_lifecycle(db_session, confirmed=10, state="READY")
    service = MatchService(db_session)
    checked_at = MATCH_START - timedelta(minutes=40)

    service.check_in(match.id, users[0], now=checked_at)

    season = active_season(db_session, checked_at)
    mission = db_session.get(
        MissionProgress, (users[0], season.id, week_start(checked_at), "on_time_checkin")
    )
    assert mission is not None
    assert mission.completed_at is not None
    progress = get_progress(db_session, users[0], season)
    assert progress is not None and progress.xp_total == 40

    # Repetir o check-in não avança a missão de novo.
    service.check_in(match.id, users[0], now=checked_at + timedelta(minutes=1))
    again = db_session.get(
        MissionProgress, (users[0], season.id, week_start(checked_at), "on_time_checkin")
    )
    assert again is not None and again.progress == 1
