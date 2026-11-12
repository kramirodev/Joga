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
from app.modules.season.models import (
    Badge,
    PlayerBadge,
    PlayerItem,
    Season,
    SeasonClaim,
    SeasonItem,
    SeasonProgress,
    SeasonTrackLevel,
    WinStreak,
    XpEvent,
)
from app.modules.tickets.service import grant

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

# -- trilha, itens e insígnias (14D.8) -----------------------------------

# Sete itens por temporada, distribuídos pela trilha (ADR 0043 §5).
TRACK_ITEMS: tuple[tuple[int, str, str, str, str], ...] = (
    (4, "q4_emote_joinha", "Emote Joinha", "emote", "free"),
    (8, "q4_headband", "Faixa de Cabeça", "accessory", "free"),
    (12, "q4_entry_bolt", "Ícone Relâmpago", "entry_icon", "pass"),
    (17, "q4_emote_clap", "Emote Palmas", "emote", "free"),
    (21, "q4_lobby_smoke", "Entrada Fumaça", "lobby_animation", "pass"),
    (26, "q4_glasses", "Óculos Escuros", "accessory", "pass"),
    (30, "q4_badge_season", "Insígnia da Temporada", "badge", "free"),
)

FREE_TICKET_LEVELS = (5, 10, 15, 20, 25, 30)
MAX_EQUIPPED_BADGES = 3


class ClaimError(SeasonError):
    """Recompensa indisponível ou já reivindicada."""


def seed_season_track(session: Session, season: Season) -> None:
    """Cria itens, insígnia e os 30 degraus da temporada. Idempotente."""

    existing_items = set(session.scalars(select(SeasonItem.code)).all())
    for _level, code, name, category, _track in TRACK_ITEMS:
        if code in existing_items:
            continue
        session.add(
            SeasonItem(
                season_id=season.id,
                code=code,
                name=name,
                category=category,
                artwork_ref=f"placeholder/{code}",
            )
        )
    session.flush()

    badge_code = f"season_{season.code.lower().replace('-', '_')}"
    if session.scalars(select(Badge).where(Badge.code == badge_code)).first() is None:
        session.add(
            Badge(
                code=badge_code,
                name=f"Temporada {season.code}",
                kind="season",
                season_id=season.id,
                artwork_ref=f"placeholder/{badge_code}",
            )
        )
        session.flush()

    items_by_level = {level: (code, track) for level, code, _n, _c, track in TRACK_ITEMS}
    existing_levels = set(
        session.execute(
            select(SeasonTrackLevel.level).where(SeasonTrackLevel.season_id == season.id)
        ).all()
    )
    for level in range(1, MAX_LEVEL + 1):
        if (level,) in existing_levels:
            continue
        entry = items_by_level.get(level)
        item_code: str | None = entry[0] if entry else None
        track_value = entry[1] if entry else "free"
        session.add(
            SeasonTrackLevel(
                season_id=season.id,
                level=level,
                xp_required=xp_for_level(level),
                item_code=item_code,
                free_tickets=1 if level in FREE_TICKET_LEVELS else 0,
                track=track_value,
            )
        )
    session.flush()


def track_for(session: Session, season: Season) -> list[SeasonTrackLevel]:
    return list(
        session.scalars(
            select(SeasonTrackLevel)
            .where(SeasonTrackLevel.season_id == season.id)
            .order_by(SeasonTrackLevel.level.asc())
        ).all()
    )


def claimed_levels(session: Session, user_id: uuid.UUID, season: Season) -> set[int]:
    return {
        row[0]
        for row in session.execute(
            select(SeasonClaim.level).where(
                SeasonClaim.user_id == user_id,
                SeasonClaim.season_id == season.id,
            )
        ).all()
    }


def claim_level(
    session: Session,
    *,
    user_id: uuid.UUID,
    season: Season,
    level: int,
) -> tuple[SeasonClaim, str | None, int]:
    """Reivindica a recompensa do nível. Idempotente por (usuário, temporada, nível)."""

    row = session.get(SeasonTrackLevel, (season.id, level))
    if row is None:
        raise ClaimError("level_not_found")

    existing = session.get(SeasonClaim, (user_id, season.id, level))
    if existing is not None:
        return existing, row.item_code, row.free_tickets

    progress = get_progress(session, user_id, season)
    xp_total = progress.xp_total if progress else 0
    if xp_total < row.xp_required:
        raise ClaimError("level_locked")
    if row.track == "pass":
        # Sem modelo de passe ainda: a trilha paga fica bloqueada no piloto.
        raise ClaimError("pass_required")

    claim = SeasonClaim(user_id=user_id, season_id=season.id, level=level)
    session.add(claim)

    if row.item_code:
        item = session.scalars(
            select(SeasonItem).where(SeasonItem.code == row.item_code)
        ).first()
        if item is not None and item.category == "badge":
            badge = session.scalars(
                select(Badge).where(Badge.code == f"season_{season.code.lower().replace('-', '_')}")
            ).first()
            if badge is not None:
                award_badge(session, user_id=user_id, badge=badge)
        elif item is not None:
            already = session.scalars(
                select(PlayerItem).where(
                    PlayerItem.user_id == user_id,
                    PlayerItem.item_code == item.code,
                )
            ).first()
            if already is None:
                session.add(
                    PlayerItem(user_id=user_id, item_code=item.code, season_id=season.id)
                )

    if row.free_tickets:
        grant(
            session,
            user_id,
            row.free_tickets,
            source="free_level",
            idempotency_key=f"free_level:{season.id}:{level}:{user_id}",
            ref_type="season_level",
            ref_id=season.id,
        )

    session.flush()
    return claim, row.item_code, row.free_tickets


def award_badge(session: Session, *, user_id: uuid.UUID, badge: Badge) -> PlayerBadge:
    existing = session.scalars(
        select(PlayerBadge).where(
            PlayerBadge.user_id == user_id,
            PlayerBadge.badge_id == badge.id,
        )
    ).first()
    if existing is not None:
        return existing
    record = PlayerBadge(user_id=user_id, badge_id=badge.id)
    session.add(record)
    session.flush()
    return record


def equip_badge(
    session: Session,
    *,
    user_id: uuid.UUID,
    badge_id: uuid.UUID,
    slot: int,
) -> PlayerBadge:
    """Equipa a insígnia em um dos três espaços do perfil."""

    if not 1 <= slot <= MAX_EQUIPPED_BADGES:
        raise ClaimError("slot_invalid")
    record = session.scalars(
        select(PlayerBadge).where(
            PlayerBadge.user_id == user_id,
            PlayerBadge.badge_id == badge_id,
        )
    ).first()
    if record is None:
        raise ClaimError("badge_not_owned")

    occupied = session.scalars(
        select(PlayerBadge).where(
            PlayerBadge.user_id == user_id,
            PlayerBadge.equipped_slot == slot,
            PlayerBadge.badge_id != badge_id,
        )
    ).first()
    if occupied is not None:
        occupied.equipped_slot = None
    record.equipped_slot = slot
    session.flush()
    return record


def list_badges(session: Session, user_id: uuid.UUID) -> list[tuple[PlayerBadge, Badge]]:
    rows = session.execute(
        select(PlayerBadge, Badge)
        .join(Badge, Badge.id == PlayerBadge.badge_id)
        .where(PlayerBadge.user_id == user_id)
        .order_by(PlayerBadge.awarded_at.desc())
    ).all()
    return [(row[0], row[1]) for row in rows]
