"""XP, nível, tier e streak (ADR 0043).

Regras:
- XP é igual para todos e nunca comprado;
- o nível é derivado do XP total da temporada;
- o nível de temporada reseta na virada;
- a streak é de vitórias e zera com derrota, empate ou semana sem jogar.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.clock import utcnow
from app.modules.season.models import Season, SeasonProgress, WinStreak, XpEvent

XP_PER_LEVEL = 150
MAX_LEVEL = 30
TIERS: tuple[tuple[int, str], ...] = ((20, "ouro"), (10, "prata"), (0, "bronze"))


class SeasonError(Exception):
    """Erro de temporada."""


class SeasonNotFound(SeasonError):
    """Nenhuma temporada ativa."""


class XpConflict(SeasonError):
    """Chave de idempotência reutilizada com efeito diferente."""


def level_for(xp_total: int) -> int:
    return min(MAX_LEVEL, max(0, xp_total) // XP_PER_LEVEL)


def xp_for_level(level: int) -> int:
    return min(level, MAX_LEVEL) * XP_PER_LEVEL


def tier_for(level: int) -> str:
    for floor, name in TIERS:
        if level >= floor:
            return name
    return TIERS[-1][1]


def week_start(moment: datetime) -> date:
    return moment.date() - timedelta(days=moment.isoweekday() - 1)


def quarter_bounds(now: datetime) -> tuple[int, datetime, datetime]:
    quarter = (now.month - 1) // 3 + 1
    start_month = 3 * (quarter - 1) + 1
    starts = datetime(now.year, start_month, 1, tzinfo=UTC)
    if start_month == 10:
        ends = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        ends = datetime(now.year, start_month + 3, 1, tzinfo=UTC)
    return quarter, starts, ends


def seed_current_season(session: Session, now: datetime | None = None) -> Season:
    """Garante a temporada do trimestre corrente. Idempotente."""

    moment = now or utcnow()
    quarter, starts, ends = quarter_bounds(moment)
    code = f"{moment.year}-Q{quarter}"
    season = session.scalars(select(Season).where(Season.code == code)).first()
    if season is not None:
        return season
    season = Season(code=code, starts_at=starts, ends_at=ends, status="active")
    session.add(season)
    session.flush()
    return season


def active_season(session: Session, now: datetime) -> Season:
    season = session.scalars(
        select(Season)
        .where(
            Season.status == "active",
            Season.starts_at <= now,
            Season.ends_at > now,
        )
        .order_by(Season.starts_at.desc())
        .limit(1)
    ).first()
    if season is None:
        raise SeasonNotFound
    return season


def progress_for(session: Session, user_id: uuid.UUID, season: Season) -> SeasonProgress:
    record = session.get(SeasonProgress, (user_id, season.id))
    if record is None:
        record = SeasonProgress(user_id=user_id, season_id=season.id, xp_total=0, level=0)
        session.add(record)
        session.flush()
    return record


def get_progress(
    session: Session, user_id: uuid.UUID, season: Season
) -> SeasonProgress | None:
    """Leitura sem criar linha: a projeção nasce no primeiro XP."""

    return session.get(SeasonProgress, (user_id, season.id))


def award_xp(
    session: Session,
    *,
    user_id: uuid.UUID,
    season: Season,
    amount: int,
    source: str,
    idempotency_key: str,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
) -> SeasonProgress:
    """Credita XP uma única vez por chave e atualiza a projeção."""

    if amount <= 0:
        raise SeasonError("amount_invalid")
    existing = session.scalars(
        select(XpEvent).where(XpEvent.idempotency_key == idempotency_key)
    ).first()
    if existing is not None:
        if existing.user_id != user_id or existing.amount != amount:
            raise XpConflict("idempotency_key_reused")
        return progress_for(session, user_id, season)

    record = progress_for(session, user_id, season)
    session.add(
        XpEvent(
            user_id=user_id,
            season_id=season.id,
            source=source,
            amount=amount,
            ref_type=ref_type,
            ref_id=ref_id,
            idempotency_key=idempotency_key,
        )
    )
    record.xp_total += amount
    record.level = level_for(record.xp_total)
    try:
        session.flush()
    except IntegrityError as exc:
        raise XpConflict("idempotency_key_reused") from exc
    return record


def streak_for(session: Session, user_id: uuid.UUID) -> WinStreak:
    record = session.get(WinStreak, user_id)
    if record is None:
        record = WinStreak(user_id=user_id, current_wins=0, best_wins=0)
        session.add(record)
        session.flush()
    return record


def effective_streak(record: WinStreak, today: datetime) -> int:
    """A semana corrente ainda aberta não zera; uma semana inteira sem jogar, sim."""

    if record.last_match_week is None:
        return 0
    current_week = week_start(today)
    if record.last_match_week < current_week - timedelta(days=7):
        return 0
    return record.current_wins


def record_match_result(
    session: Session,
    user_id: uuid.UUID,
    *,
    match_id: uuid.UUID,
    won: bool,
    played_at: datetime,
) -> WinStreak:
    """Atualiza a streak: vitória soma, empate/derrota zeram, semana vazia zera."""

    record = streak_for(session, user_id)
    week = week_start(played_at)
    if record.last_match_week is not None and record.last_match_week < week - timedelta(days=7):
        record.current_wins = 0
    if won:
        record.current_wins += 1
        record.best_wins = max(record.best_wins, record.current_wins)
    else:
        record.current_wins = 0
    record.last_match_week = week
    record.last_match_id = match_id
    session.flush()
    return record
