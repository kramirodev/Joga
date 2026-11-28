"""Snapshot público do cartão de perfil.

O perfil de outro jogador precisa renderizar exatamente o mesmo ``ProfileCard``
do dono: tema, identidade visual, tier/nível, divisão, temporada, recorde e
sequência de vitórias. Este módulo lê as fontes já existentes (perfil, visual,
temporada, rating e estatística) sem criar escrita em rota de leitura e sem
expor MMR bruto, e-mail, telefone, CPF ou localização.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import utcnow
from app.modules.profile.models import Sport, SportFormat, UserSportProfile
from app.modules.ratings.engine import division_for
from app.modules.ratings.service import RatingService
from app.modules.season.models import Badge, PlayerBadge, Season, WinStreak
from app.modules.season.service import (
    effective_streak,
    get_progress,
    level_for,
    quarter_bounds,
    tier_for,
)
from app.modules.stats.service import player_totals
from app.modules.visual.service import get_identity

MAX_CARD_BADGES = 3

# Rótulos que o cartão do dono exibe (mobile: divisionLabel(division).toUpperCase()).
DIVISION_LABELS: dict[str, str] = {
    "BRONZE": "BRONZE",
    "SILVER": "PRATA",
    "GOLD": "OURO",
    "PLATINUM": "PLATINA",
    "DIAMOND": "DIAMANTE",
    "PROVISIONAL": "PROVISÓRIO",
}


@dataclass(frozen=True)
class CardVisual:
    icon_key: str | None
    frame_key: str | None
    accent_key: str | None
    entry_key: str | None
    emote_key: str | None
    badge_key: str | None
    catalog_version: int


@dataclass(frozen=True)
class CardBadge:
    code: str
    name: str
    kind: str


@dataclass(frozen=True)
class PublicCard:
    theme_id: str | None
    visual: CardVisual
    tier: str | None
    level: int | None
    qualifier: str | None
    season_label: str
    record: int
    win_streak: int
    badges: list[CardBadge]


def _primary_format_id(session: Session, user_id: uuid.UUID) -> uuid.UUID | None:
    """Mesmo formato que o app usa no perfil próprio: o primeiro do jogador.

    Sem modalidade escolhida, cai no primeiro formato ativo do catálogo, como a
    tela do dono faz antes do onboarding esportivo.
    """

    format_id = session.scalar(
        select(UserSportProfile.format_id)
        .where(UserSportProfile.user_id == user_id)
        .order_by(UserSportProfile.created_at.asc())
        .limit(1)
    )
    if format_id is not None:
        return format_id
    return session.scalar(
        select(SportFormat.id)
        .join(Sport, Sport.id == SportFormat.sport_id)
        .where(SportFormat.active.is_(True), Sport.active.is_(True))
        .order_by(Sport.name.asc(), SportFormat.name.asc())
        .limit(1)
    )


def _qualifier(
    session: Session,
    service: RatingService,
    user_id: uuid.UUID,
    season: Season | None,
) -> str | None:
    format_id = _primary_format_id(session, user_id)
    if format_id is None:
        return None
    account = service.account_for(user_id, format_id)
    if account is None:
        return DIVISION_LABELS["PROVISIONAL"]
    matches = (
        service.placement_matches(user_id, season.id)
        if season is not None
        else account.matches_played
    )
    division = division_for(account.rating, matches)
    return DIVISION_LABELS.get(division, division)


def _equipped_badges(session: Session, user_id: uuid.UUID) -> list[CardBadge]:
    rows = session.execute(
        select(PlayerBadge, Badge)
        .join(Badge, Badge.id == PlayerBadge.badge_id)
        .where(
            PlayerBadge.user_id == user_id,
            PlayerBadge.equipped_slot.is_not(None),
        )
        .order_by(PlayerBadge.equipped_slot.asc())
        .limit(MAX_CARD_BADGES)
    ).all()
    return [CardBadge(code=badge.code, name=badge.name, kind=badge.kind) for _row, badge in rows]


def build_public_card(
    session: Session,
    user_id: uuid.UUID,
    *,
    theme_id: str | None,
    now: datetime | None = None,
) -> PublicCard:
    """Monta o cartão público a partir de uma leitura por bloco (sem N+1)."""

    moment = now or utcnow()
    service = RatingService(session)
    season = service.current_season(moment)

    tier: str | None = None
    level: int | None = None
    if season is not None:
        progress = get_progress(session, user_id, season)
        level = level_for(progress.xp_total if progress is not None else 0)
        tier = tier_for(level)

    identity = get_identity(session, user_id)
    streak = session.get(WinStreak, user_id)
    quarter, _starts, _ends = quarter_bounds(moment)

    return PublicCard(
        theme_id=theme_id,
        visual=CardVisual(
            icon_key=identity.icon_key,
            frame_key=identity.frame_key,
            accent_key=identity.accent_key,
            entry_key=identity.entry_key,
            emote_key=identity.emote_key,
            badge_key=identity.badge_key,
            catalog_version=identity.catalog_version,
        ),
        tier=tier,
        level=level,
        qualifier=_qualifier(session, service, user_id, season),
        season_label=f"T{quarter} {moment.year}",
        record=player_totals(session, user_id).matches,
        win_streak=effective_streak(streak, moment) if streak is not None else 0,
        badges=_equipped_badges(session, user_id),
    )


__all__ = [
    "CardBadge",
    "CardVisual",
    "PublicCard",
    "build_public_card",
]
