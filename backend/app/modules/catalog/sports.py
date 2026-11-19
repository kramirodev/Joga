"""Catálogo administrável de esportes e formatos.

O catálogo público mostra apenas esportes/formatos ativos. A criação nasce
inativa e a publicação exige ao menos um formato ativo com preço configurado.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking
from app.modules.clans.models import ClanTrophyEvent, ClanTrophySnapshot
from app.modules.matches.models import Match
from app.modules.matchmaking.models import Lobby, QueueEntry
from app.modules.pricing.suggest import pricing_configured
from app.modules.profile.models import Sport, SportFormat
from app.modules.ratings.models import RatingAccount, RatingEvent
from app.modules.visual.models import VisualCatalogItem

SPORT_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SCORE_MODELS = ("sets_points", "goals")


class SportError(Exception):
    """Erro base do catálogo de esportes."""


class SportNotFound(SportError):
    """Esporte inexistente."""


class SportSlugConflict(SportError):
    """Slug já utilizado."""


class InvalidSport(SportError):
    """Dados de esporte/formatos inválidos."""


class InvalidSportIcon(SportError):
    """icon_key não é item ativo do tipo icon."""


class SportNotPublishable(SportError):
    """Esporte sem formato ativo ou com preço ausente."""


class FormatNotFound(SportError):
    """Formato inexistente no esporte informado."""


class FormatSlugConflict(SportError):
    """Slug de formato já usado dentro do esporte."""


class FormatInUse(SportError):
    """Formato já referenciado por fila, partida, reserva, rating ou troféu."""


class PricingNotConfigured(SportError):
    """Falta célula de preço em alguma faixa ativa para o formato."""


class InvalidFormat(SportError):
    """Dados de formato inválidos."""


@dataclass(frozen=True)
class FormatInput:
    slug: str
    name: str
    team_size: int
    duration_minutes: int
    players_per_team: int | None = None
    period_count: int = 1
    score_model: str = "sets_points"
    positions: list[str] = field(default_factory=list)


def _normalize_slug(value: str) -> str:
    slug = value.strip().lower()
    if not SPORT_SLUG_PATTERN.fullmatch(slug) or len(slug) > 40:
        raise InvalidSport
    return slug


def _validate_icon(session: Session, icon_key: str) -> str:
    key = icon_key.strip().lower()
    item = session.scalar(
        select(VisualCatalogItem).where(
            VisualCatalogItem.key == key,
            VisualCatalogItem.kind == "icon",
            VisualCatalogItem.active.is_(True),
        )
    )
    if item is None:
        raise InvalidSportIcon
    return key


def _build_format(sport_id: uuid.UUID, spec: FormatInput) -> SportFormat:
    slug = _normalize_slug(spec.slug)
    name = spec.name.strip()
    if not name or len(name) > 80:
        raise InvalidSport
    if spec.team_size <= 0 or spec.team_size > 20:
        raise InvalidSport
    if spec.duration_minutes <= 0 or spec.duration_minutes > 240:
        raise InvalidSport
    if spec.period_count <= 0 or spec.period_count > 20:
        raise InvalidSport
    if spec.score_model not in SCORE_MODELS:
        raise InvalidSport
    players = spec.players_per_team or spec.team_size
    if players != spec.team_size:
        raise InvalidSport
    if len(spec.positions) > 20 or any(
        not position.strip() or len(position.strip()) > 40 for position in spec.positions
    ):
        raise InvalidSport
    return SportFormat(
        sport_id=sport_id,
        slug=slug,
        name=name,
        team_size=spec.team_size,
        players_per_team=players,
        total_participants=spec.team_size * 2,
        play_minutes=spec.duration_minutes,
        break_minutes=0,
        duration_minutes=spec.duration_minutes,
        period_count=spec.period_count,
        score_model=spec.score_model,
        positions=[position.strip() for position in spec.positions],
        version=1,
        active=True,
    )


def create_sport(
    session: Session,
    *,
    slug: str,
    name: str,
    icon_key: str,
    sort_order: int,
    formats: list[FormatInput],
) -> Sport:
    """Cria esporte e formatos na mesma transação; nasce inativo."""

    normalized = _normalize_slug(slug)
    clean_name = name.strip()
    if not clean_name or len(clean_name) > 80 or sort_order < 0:
        raise InvalidSport
    if not formats:
        raise InvalidSport
    resolved_icon = _validate_icon(session, icon_key)
    if session.scalar(select(Sport.id).where(Sport.slug == normalized)) is not None:
        raise SportSlugConflict

    sport = Sport(
        slug=normalized,
        name=clean_name,
        icon_key=resolved_icon,
        sort_order=sort_order,
        active=False,
    )
    session.add(sport)
    try:
        session.flush()
        for spec in formats:
            session.add(_build_format(sport.id, spec))
        session.flush()
    except IntegrityError as exc:
        raise SportSlugConflict from exc
    return sport


def get_sport(session: Session, slug: str) -> Sport:
    sport = session.scalar(select(Sport).where(Sport.slug == _normalize_slug(slug)))
    if sport is None:
        raise SportNotFound
    return sport


def _next_version(session: Session, row: SportFormat) -> int:
    current = session.scalar(
        select(func.max(SportFormat.version)).where(
            SportFormat.sport_id == row.sport_id,
            SportFormat.slug == row.slug,
        )
    )
    return int(current or row.version) + 1


def get_format(session: Session, sport: Sport, format_id: uuid.UUID) -> SportFormat:
    row = session.scalar(
        select(SportFormat).where(
            SportFormat.id == format_id,
            SportFormat.sport_id == sport.id,
        )
    )
    if row is None:
        raise FormatNotFound
    return row


def format_in_use(session: Session, format_id: uuid.UUID) -> bool:
    """Verdadeiro quando o formato já tem uso competitivo/financeiro/histórico."""

    lobby_ids = select(Lobby.id).where(Lobby.format_id == format_id)
    checks = (
        select(QueueEntry.id).where(QueueEntry.format_id == format_id),
        select(Lobby.id).where(Lobby.format_id == format_id),
        select(Booking.id).where(Booking.lobby_id.in_(lobby_ids)),
        select(Match.id).where(Match.lobby_id.in_(lobby_ids)),
        select(RatingAccount.id).where(RatingAccount.format_id == format_id),
        select(RatingEvent.id).where(RatingEvent.format_id == format_id),
        select(ClanTrophyEvent.id).where(ClanTrophyEvent.format_id == format_id),
        select(ClanTrophySnapshot.id).where(ClanTrophySnapshot.format_id == format_id),
    )
    return any(session.scalar(query.limit(1)) is not None for query in checks)


def add_format(session: Session, *, slug: str, spec: FormatInput) -> SportFormat:
    """Adiciona formato ativo, exigindo preço em todas as faixas ativas."""

    sport = get_sport(session, slug)
    format_slug = _normalize_slug(spec.slug)
    existing = session.scalar(
        select(SportFormat.id).where(
            SportFormat.sport_id == sport.id,
            SportFormat.slug == format_slug,
        )
    )
    if existing is not None:
        raise FormatSlugConflict
    if not pricing_configured(session, spec.team_size):
        raise PricingNotConfigured
    row = _build_format(sport.id, spec)
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise FormatSlugConflict from exc
    return row


def update_format(
    session: Session,
    *,
    slug: str,
    format_id: uuid.UUID,
    name: str | None = None,
    team_size: int | None = None,
    players_per_team: int | None = None,
    duration_minutes: int | None = None,
    period_count: int | None = None,
    score_model: str | None = None,
    positions: list[str] | None = None,
    active: bool | None = None,
) -> SportFormat:
    """Edita um formato; ``team_size`` só muda enquanto não houver uso."""

    sport = get_sport(session, slug)
    row = get_format(session, sport, format_id)
    changed: dict[str, dict[str, object]] = {}

    if team_size is not None or players_per_team is not None:
        new_team = team_size if team_size is not None else row.team_size
        new_players = players_per_team if players_per_team is not None else new_team
        if new_team <= 0 or new_team > 20 or new_players != new_team:
            raise InvalidFormat
        if new_team != row.team_size:
            if format_in_use(session, row.id):
                raise FormatInUse
            if not pricing_configured(session, new_team):
                raise PricingNotConfigured
            changed["team_size"] = {"before": row.team_size, "after": new_team}
            row.team_size = new_team
            row.players_per_team = new_team
            row.total_participants = new_team * 2

    if name is not None:
        clean = name.strip()
        if not clean or len(clean) > 80:
            raise InvalidFormat
        if clean != row.name:
            changed["name"] = {"before": row.name, "after": clean}
            row.name = clean

    if duration_minutes is not None:
        if duration_minutes <= 0 or duration_minutes > 240:
            raise InvalidFormat
        if duration_minutes != row.duration_minutes:
            changed["duration_minutes"] = {
                "before": row.duration_minutes,
                "after": duration_minutes,
            }
            row.duration_minutes = duration_minutes
            row.play_minutes = duration_minutes
            row.break_minutes = 0

    if period_count is not None:
        if period_count <= 0 or period_count > 20:
            raise InvalidFormat
        if period_count != row.period_count:
            changed["period_count"] = {"before": row.period_count, "after": period_count}
            row.period_count = period_count

    if score_model is not None:
        if score_model not in SCORE_MODELS:
            raise InvalidFormat
        if score_model != row.score_model:
            changed["score_model"] = {"before": row.score_model, "after": score_model}
            row.score_model = score_model

    if positions is not None:
        if len(positions) > 20 or any(
            not position.strip() or len(position.strip()) > 40 for position in positions
        ):
            raise InvalidFormat
        clean_positions = [position.strip() for position in positions]
        if clean_positions != list(row.positions or []):
            changed["positions"] = {
                "before": list(row.positions or []),
                "after": clean_positions,
            }
            row.positions = clean_positions

    if active is not None and active != row.active:
        if active and not pricing_configured(session, row.team_size):
            raise PricingNotConfigured
        changed["active"] = {"before": row.active, "after": active}
        row.active = active

    if changed:
        row.version = _next_version(session, row)
    session.flush()
    return row


def activate_format(session: Session, *, slug: str, format_id: uuid.UUID) -> SportFormat:
    sport = get_sport(session, slug)
    row = get_format(session, sport, format_id)
    if not pricing_configured(session, row.team_size):
        raise PricingNotConfigured
    if not row.active:
        row.active = True
        row.version = _next_version(session, row)
        session.flush()
    return row


def deactivate_format(session: Session, *, slug: str, format_id: uuid.UUID) -> SportFormat:
    """Some do catálogo público; nenhuma linha histórica é apagada."""

    sport = get_sport(session, slug)
    row = get_format(session, sport, format_id)
    if row.active:
        row.active = False
        row.version = _next_version(session, row)
        session.flush()
    return row


def update_sport(
    session: Session,
    *,
    slug: str,
    name: str | None = None,
    icon_key: str | None = None,
    sort_order: int | None = None,
) -> Sport:
    sport = get_sport(session, slug)
    if name is not None:
        clean = name.strip()
        if not clean or len(clean) > 80:
            raise InvalidSport
        sport.name = clean
    if icon_key is not None:
        sport.icon_key = _validate_icon(session, icon_key)
    if sort_order is not None:
        if sort_order < 0:
            raise InvalidSport
        sport.sort_order = sort_order
    session.flush()
    return sport


def active_formats(session: Session, sport_id: uuid.UUID) -> list[SportFormat]:
    return list(
        session.scalars(
            select(SportFormat)
            .where(SportFormat.sport_id == sport_id, SportFormat.active.is_(True))
            .order_by(SportFormat.slug)
        )
    )


def all_formats(session: Session, sport_id: uuid.UUID) -> list[SportFormat]:
    """Formatos ativos e inativos para a visão administrativa."""

    return list(
        session.scalars(
            select(SportFormat)
            .where(SportFormat.sport_id == sport_id)
            .order_by(SportFormat.slug, SportFormat.version.desc())
        )
    )


def activate_sport(session: Session, slug: str) -> Sport:
    """Publica somente com formato ativo e preço configurado em todas as faixas."""

    sport = get_sport(session, slug)
    formats = active_formats(session, sport.id)
    if not formats:
        raise SportNotPublishable
    for item in formats:
        if not pricing_configured(session, item.team_size):
            raise SportNotPublishable
    sport.active = True
    session.flush()
    return sport


def deactivate_sport(session: Session, slug: str) -> Sport:
    """Despublica sem apagar formatos, preços ou referências históricas."""

    sport = get_sport(session, slug)
    sport.active = False
    session.flush()
    return sport


def list_public_catalog(session: Session) -> list[tuple[Sport, list[SportFormat]]]:
    sports = session.scalars(
        select(Sport).where(Sport.active.is_(True)).order_by(Sport.sort_order, Sport.slug)
    ).all()
    catalog: list[tuple[Sport, list[SportFormat]]] = []
    for sport in sports:
        formats = active_formats(session, sport.id)
        if formats:
            catalog.append((sport, formats))
    return catalog


def list_admin_catalog(session: Session) -> list[tuple[Sport, list[SportFormat]]]:
    sports = session.scalars(select(Sport).order_by(Sport.sort_order, Sport.slug)).all()
    return [(sport, all_formats(session, sport.id)) for sport in sports]


__all__ = [
    "FormatInUse",
    "FormatInput",
    "FormatNotFound",
    "FormatSlugConflict",
    "InvalidFormat",
    "InvalidSport",
    "InvalidSportIcon",
    "PricingNotConfigured",
    "SportError",
    "SportNotPublishable",
    "SportNotFound",
    "SportSlugConflict",
    "activate_format",
    "activate_sport",
    "active_formats",
    "add_format",
    "all_formats",
    "create_sport",
    "deactivate_format",
    "deactivate_sport",
    "format_in_use",
    "get_format",
    "get_sport",
    "list_admin_catalog",
    "list_public_catalog",
    "update_format",
    "update_sport",
]
