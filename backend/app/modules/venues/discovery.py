"""Vitrine de quadras comerciais reserváveis (Fase 13C).

A leitura é deliberadamente separada do painel de gestão: expõe apenas dados
operacionais públicos para o aplicativo, nunca payout, financeiro ou auditoria.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.bookings.models import (
    Booking,
    BookingHold,
)
from app.modules.bookings.service import SPACE_BLOCKING_STATUSES
from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.organizations.models import Organization, OrganizationVenue
from app.modules.pricing.models import PricingBand, PricingBandTicket
from app.modules.pricing.service import PricingBandError, tickets_for
from app.modules.profile.models import Sport, SportFormat, UserRegion
from app.modules.venues.models import (
    VenueAvailability,
    VenueBlackout,
    VenuePhoto,
    VenueSpace,
    VenueSport,
)
from app.modules.venues.storage import PhotoNotFound as StoredPhotoNotFound
from app.modules.venues.storage import PhotoStorage, PhotoStorageError

MAX_PAGE_SIZE = 50
LOOKAHEAD_DAYS = 7
MAX_SLOTS_PER_SPACE = 5


class DiscoveryError(Exception):
    """Erro base da vitrine reservável."""


class DiscoveryNotFound(DiscoveryError):
    """Estabelecimento, quadra ou foto não encontrados."""


class DiscoveryInvalid(DiscoveryError):
    """Parâmetros inválidos de paginação, cidade ou filtros da vitrine."""


@dataclass(frozen=True)
class BandOption:
    id: uuid.UUID
    code: str
    label: str
    max_price_cents: int


@dataclass(frozen=True)
class FormatOption:
    id: uuid.UUID
    slug: str
    name: str
    team_size: int
    total_participants: int
    tickets_by_band: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SportOption:
    id: uuid.UUID
    slug: str
    name: str
    formats: tuple[FormatOption, ...]


@dataclass(frozen=True)
class AvailabilityOption:
    weekday: int
    start_time: time
    end_time: time
    price_cents: int
    slot_minutes: int
    band: BandOption | None


@dataclass(frozen=True)
class SlotOption:
    starts_at: datetime
    ends_at: datetime
    price_cents: int
    band_code: str | None


@dataclass(frozen=True)
class PhotoOption:
    id: uuid.UUID
    caption: str | None
    content_type: str


@dataclass(frozen=True)
class SpaceOption:
    id: uuid.UUID
    name: str
    description: str | None
    is_covered: bool
    sports: tuple[SportOption, ...]
    availability: tuple[AvailabilityOption, ...]
    next_slots: tuple[SlotOption, ...]


@dataclass(frozen=True)
class VenueFormatOption:
    """Formato que o estabelecimento aceita, para o filtro honesto do app.

    ``format_id`` é o mesmo valor aceito em ``GET /discovery/bookable-venues``;
    ``sport_id`` permite filtrar pela modalidade sem inferir pelo nome.
    """

    sport_id: uuid.UUID
    sport_name: str
    format_id: uuid.UUID
    name: str


@dataclass(frozen=True)
class VenueCard:
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    city: str | None
    state: str | None
    address_line: str | None
    latitude: float | None
    longitude: float | None
    timezone: str
    is_public: bool
    covered: bool
    sports: tuple[VenueFormatOption, ...]
    spaces_count: int
    min_price_cents: int
    min_tickets: int | None
    distance_km: float | None
    photo_id: uuid.UUID | None


@dataclass(frozen=True)
class VenueCardPage:
    venues: tuple[VenueCard, ...]
    total: int
    page: int
    page_size: int


@dataclass
class _CardDetails:
    """Dados carregados em lote apenas para a página já cortada."""

    spaces_by_venue: dict[uuid.UUID, list[VenueSpace]]
    availability_by_space: dict[uuid.UUID, list[VenueAvailability]]
    formats_by_space: dict[uuid.UUID, list[tuple[SportFormat, Sport]]]
    tickets: dict[tuple[uuid.UUID, int], int]
    first_photo: dict[uuid.UUID, uuid.UUID]


@dataclass(frozen=True)
class VenueDetail:
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    city: str | None
    state: str | None
    address_line: str | None
    latitude: float | None
    longitude: float | None
    timezone: str
    is_public: bool
    photos: tuple[PhotoOption, ...]
    spaces: tuple[SpaceOption, ...]


class VenueDiscoveryService:
    """Consultas de vitrine com isolamento de dados internos."""

    def __init__(self, session: Session, storage: PhotoStorage | None = None) -> None:
        self.session = session
        self.storage = storage

    def list_venues(
        self,
        user_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        city: str | None = None,
        format_id: uuid.UUID | None = None,
        sport_id: uuid.UUID | None = None,
        covered: bool | None = None,
        max_distance_km: int | None = None,
    ) -> VenueCardPage:
        """Vitrine filtrada **no servidor**, antes da paginação.

        ``format_id``, ``sport_id``, ``covered`` e ``max_distance_km`` entram na
        consulta de candidatos (ou no cálculo de distância sobre os candidatos),
        nunca sobre a página já cortada. Assim ``total`` e as páginas seguintes
        refletem o filtro inteiro.

        ``max_distance_km`` exige região gravada do usuário: sem ela, responder
        ``422 region_required`` é mais honesto do que devolver uma lista sem
        saber a origem. Estabelecimentos sem coordenada não entram quando o
        filtro de distância está ativo.
        """
        if page < 1:
            raise DiscoveryInvalid("page_invalid")
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise DiscoveryInvalid("page_size_invalid")
        if max_distance_km is not None and not 1 <= max_distance_km <= 100:
            raise DiscoveryInvalid("max_distance_invalid")
        clean_city = city.strip() if city else None

        sport_format = self._filter_format(format_id, sport_id)
        region = self.session.get(UserRegion, user_id)
        if max_distance_km is not None and region is None:
            raise DiscoveryInvalid("region_required")

        availability_exists = (
            select(VenueAvailability.id)
            .where(VenueAvailability.venue_space_id == VenueSpace.id)
            .exists()
        )
        space_conditions = [
            VenueSpace.organization_venue_id == OrganizationVenue.id,
            VenueSpace.status == "active",
            availability_exists,
        ]
        if covered is not None:
            covered_space = (
                select(VenueSpace.id)
                .where(
                    VenueSpace.organization_venue_id == OrganizationVenue.id,
                    VenueSpace.status == "active",
                    VenueSpace.is_covered.is_(True),
                )
                .exists()
            )
            space_conditions.append(covered_space if covered else ~covered_space)
        if sport_format is not None:
            linked_sport = (
                select(VenueSport.id)
                .where(
                    VenueSport.venue_space_id == VenueSpace.id,
                    VenueSport.sport_id == sport_format.sport_id,
                )
                .exists()
            )
            # O formato explícito de publicação e as modalidades vinculadas
            # formam o conjunto aceito pela quadra. O card usa a mesma união,
            # para nenhum resultado do filtro ficar sem chip correspondente.
            space_conditions.append(or_(VenueSpace.format_id == sport_format.id, linked_sport))
        elif sport_id is not None:
            linked_sport = (
                select(VenueSport.id)
                .where(
                    VenueSport.venue_space_id == VenueSpace.id,
                    VenueSport.sport_id == sport_id,
                )
                .exists()
            )
            explicit_sport = (
                select(SportFormat.id)
                .where(
                    SportFormat.id == VenueSpace.format_id,
                    SportFormat.sport_id == sport_id,
                )
                .exists()
            )
            space_conditions.append(or_(linked_sport, explicit_sport))
        active_space = select(VenueSpace.id).where(*space_conditions).exists()

        statement = (
            select(OrganizationVenue, Organization.is_platform)
            .join(Organization, Organization.id == OrganizationVenue.organization_id)
            .where(
                OrganizationVenue.status == "active",
                Organization.status == "active",
                or_(
                    Organization.is_platform.is_(True),
                    Organization.verification_status == "verified",
                ),
                active_space,
            )
            .order_by(OrganizationVenue.name, OrganizationVenue.id)
        )
        if clean_city:
            statement = statement.where(
                func.lower(OrganizationVenue.city).contains(clean_city.lower(), autoescape=True)
            )

        candidates: list[tuple[OrganizationVenue, bool, float | None]] = []
        for venue, is_platform in self.session.execute(statement).all():
            raw_distance = self._raw_distance(region, venue)
            if max_distance_km is not None and (
                raw_distance is None or raw_distance > max_distance_km
            ):
                continue
            candidates.append((venue, is_platform, raw_distance))
        candidates.sort(
            key=lambda item: (
                item[2] is None,
                item[2] if item[2] is not None else 0.0,
                item[0].name,
                str(item[0].id),
            )
        )

        total = len(candidates)
        start = (page - 1) * page_size
        page_rows = candidates[start : start + page_size]
        if not page_rows:
            return VenueCardPage(venues=(), total=total, page=page, page_size=page_size)

        details = self._card_details([venue.id for venue, _, _ in page_rows])
        cards: list[VenueCard] = []
        for venue, is_platform, raw_distance in page_rows:
            card = self._build_card(venue, is_platform, raw_distance, details)
            if card is not None:
                cards.append(card)
        return VenueCardPage(
            venues=tuple(cards),
            total=total,
            page=page,
            page_size=page_size,
        )

    def _filter_format(
        self,
        format_id: uuid.UUID | None,
        sport_id: uuid.UUID | None,
    ) -> SportFormat | None:
        """Valida os filtros de catálogo e devolve o formato, quando houver."""
        sport_format: SportFormat | None = None
        if format_id is not None:
            sport_format = self.session.get(SportFormat, format_id)
            if sport_format is None or not sport_format.active:
                raise DiscoveryInvalid("invalid_format")
            sport = self.session.get(Sport, sport_format.sport_id)
            if sport is None or not sport.active:
                raise DiscoveryInvalid("invalid_format")
            if sport_id is not None and sport_format.sport_id != sport_id:
                raise DiscoveryInvalid("format_sport_mismatch")
        if sport_id is not None:
            sport = self.session.get(Sport, sport_id)
            if sport is None or not sport.active:
                raise DiscoveryInvalid("invalid_sport")
        return sport_format

    def _card_details(self, venue_ids: list[uuid.UUID]) -> _CardDetails:
        """Carrega quadras, agenda, formatos, faixas e foto em lote.

        A quantidade de consultas depende do número de *páginas*, não do número
        de quadras ou formatos: evita o N+1 que a vitrine tinha ao consultar
        cada espaço individualmente.
        """
        spaces = list(
            self.session.scalars(
                select(VenueSpace)
                .where(
                    VenueSpace.organization_venue_id.in_(venue_ids),
                    VenueSpace.status == "active",
                )
                .order_by(VenueSpace.name, VenueSpace.id)
            ).all()
        )
        spaces_by_venue: dict[uuid.UUID, list[VenueSpace]] = {}
        for space in spaces:
            spaces_by_venue.setdefault(space.organization_venue_id, []).append(space)
        space_ids = [space.id for space in spaces]

        availability_by_space: dict[uuid.UUID, list[VenueAvailability]] = {}
        if space_ids:
            for row in self.session.scalars(
                select(VenueAvailability)
                .where(VenueAvailability.venue_space_id.in_(space_ids))
                .order_by(
                    VenueAvailability.weekday,
                    VenueAvailability.start_time,
                    VenueAvailability.id,
                )
            ):
                availability_by_space.setdefault(row.venue_space_id, []).append(row)

        links_by_space: dict[uuid.UUID, list[uuid.UUID]] = {}
        sport_ids: set[uuid.UUID] = set()
        if space_ids:
            for space_id, sport_id in self.session.execute(
                select(VenueSport.venue_space_id, VenueSport.sport_id).where(
                    VenueSport.venue_space_id.in_(space_ids)
                )
            ):
                links_by_space.setdefault(space_id, []).append(sport_id)
                sport_ids.add(sport_id)

        explicit_format_ids = {space.format_id for space in spaces if space.format_id is not None}
        explicit_formats = (
            list(
                self.session.scalars(
                    select(SportFormat).where(SportFormat.id.in_(explicit_format_ids))
                ).all()
            )
            if explicit_format_ids
            else []
        )
        sport_ids.update(sport_format.sport_id for sport_format in explicit_formats)

        sports = (
            {
                sport.id: sport
                for sport in self.session.scalars(
                    select(Sport).where(Sport.id.in_(sport_ids), Sport.active.is_(True))
                ).all()
            }
            if sport_ids
            else {}
        )
        active_formats = (
            list(
                self.session.scalars(
                    select(SportFormat).where(
                        SportFormat.sport_id.in_(sports),
                        SportFormat.active.is_(True),
                    )
                ).all()
            )
            if sports
            else []
        )
        active_format_by_id = {sport_format.id: sport_format for sport_format in active_formats}
        formats_by_sport: dict[uuid.UUID, list[SportFormat]] = {}
        for sport_format in active_formats:
            formats_by_sport.setdefault(sport_format.sport_id, []).append(sport_format)

        formats_by_space: dict[uuid.UUID, list[tuple[SportFormat, Sport]]] = {}
        for space in spaces:
            chosen: list[SportFormat] = []
            if space.format_id is not None:
                explicit = active_format_by_id.get(space.format_id)
                if explicit is not None and explicit.sport_id in sports:
                    chosen.append(explicit)
            for linked_id in links_by_space.get(space.id, []):
                chosen.extend(formats_by_sport.get(linked_id, []))
            deduped: dict[uuid.UUID, SportFormat] = {}
            for sport_format in chosen:
                deduped.setdefault(sport_format.id, sport_format)
            formats_by_space[space.id] = [
                (sport_format, sports[sport_format.sport_id]) for sport_format in deduped.values()
            ]

        band_ids = {
            row.band_id
            for rows in availability_by_space.values()
            for row in rows
            if row.band_id is not None
        }
        tickets: dict[tuple[uuid.UUID, int], int] = {}
        if band_ids:
            for band_id, team_size, count in self.session.execute(
                select(
                    PricingBandTicket.band_id,
                    PricingBandTicket.team_size,
                    PricingBandTicket.tickets,
                ).where(PricingBandTicket.band_id.in_(band_ids))
            ):
                tickets[(band_id, team_size)] = count

        first_photo: dict[uuid.UUID, uuid.UUID] = {}
        for photo in self.session.scalars(
            select(VenuePhoto)
            .where(
                VenuePhoto.organization_venue_id.in_(venue_ids),
                VenuePhoto.status == "APPROVED",
            )
            .order_by(VenuePhoto.created_at, VenuePhoto.id)
        ):
            first_photo.setdefault(photo.organization_venue_id, photo.id)

        return _CardDetails(
            spaces_by_venue=spaces_by_venue,
            availability_by_space=availability_by_space,
            formats_by_space=formats_by_space,
            tickets=tickets,
            first_photo=first_photo,
        )

    def _build_card(
        self,
        venue: OrganizationVenue,
        is_platform: bool,
        raw_distance: float | None,
        details: _CardDetails,
    ) -> VenueCard | None:
        spaces = details.spaces_by_venue.get(venue.id, [])
        if not spaces:
            return None
        prices = [
            row.price_cents
            for space in spaces
            for row in details.availability_by_space.get(space.id, [])
        ]
        if not prices:
            return None
        # Quadra pública é gratuita (ADR 0055 §2.2: organização da plataforma
        # + `is_public`), então o app exibe "Grátis" a partir de zero ingressos,
        # mesmo que exista tabela de faixas configurada.
        min_tickets = (
            0 if venue.is_public and is_platform else self._min_tickets_from(spaces, details)
        )
        formats: dict[uuid.UUID, VenueFormatOption] = {}
        for space in spaces:
            for sport_format, sport in details.formats_by_space.get(space.id, []):
                formats.setdefault(
                    sport_format.id,
                    VenueFormatOption(
                        sport_id=sport.id,
                        sport_name=sport.name,
                        format_id=sport_format.id,
                        name=sport_format.name,
                    ),
                )
        return VenueCard(
            id=venue.id,
            organization_id=venue.organization_id,
            name=venue.name,
            city=venue.city,
            state=venue.state,
            address_line=venue.address_line,
            latitude=self._round_coordinate(venue.latitude),
            longitude=self._round_coordinate(venue.longitude),
            timezone=venue.timezone,
            is_public=venue.is_public,
            covered=any(space.is_covered for space in spaces),
            sports=tuple(
                sorted(
                    formats.values(),
                    key=lambda item: (item.sport_name, item.name, str(item.format_id)),
                )
            ),
            spaces_count=len(spaces),
            min_price_cents=min(prices),
            min_tickets=min_tickets,
            distance_km=round(raw_distance, 2) if raw_distance is not None else None,
            photo_id=details.first_photo.get(venue.id),
        )

    @staticmethod
    def _min_tickets_from(spaces: list[VenueSpace], details: _CardDetails) -> int | None:
        """Menor quantidade de ingressos usando as faixas já carregadas em lote."""
        tickets: list[int] = []
        for space in spaces:
            formats = details.formats_by_space.get(space.id, [])
            for row in details.availability_by_space.get(space.id, []):
                if row.band_id is None:
                    continue
                for sport_format, _ in formats:
                    count = details.tickets.get((row.band_id, sport_format.team_size))
                    if count is not None:
                        tickets.append(count)
        return min(tickets) if tickets else None

    def get_venue(self, venue_id: uuid.UUID) -> VenueDetail:
        venue = self._active_venue(venue_id)
        spaces = self._active_spaces(venue.id)
        if not spaces:
            raise DiscoveryNotFound

        space_options: list[SpaceOption] = []
        for space in spaces:
            availability_rows = self._availability(space.id)
            bands = {
                row.band_id: self.session.get(PricingBand, row.band_id)
                for row in availability_rows
                if row.band_id is not None
            }
            sports: list[SportOption] = []
            for sport in self._sports(space.id):
                formats = self._formats(sport.id, bands)
                sports.append(
                    SportOption(
                        id=sport.id,
                        slug=sport.slug,
                        name=sport.name,
                        formats=tuple(formats),
                    )
                )
            space_options.append(
                SpaceOption(
                    id=space.id,
                    name=space.name,
                    description=space.description,
                    is_covered=space.is_covered,
                    sports=tuple(sports),
                    availability=tuple(
                        self._availability_option(
                            row,
                            bands.get(row.band_id) if row.band_id is not None else None,
                        )
                        for row in availability_rows
                    ),
                    next_slots=tuple(self._next_slots(space, venue, availability_rows)),
                )
            )

        return VenueDetail(
            id=venue.id,
            organization_id=venue.organization_id,
            name=venue.name,
            city=venue.city,
            state=venue.state,
            address_line=venue.address_line,
            latitude=self._round_coordinate(venue.latitude),
            longitude=self._round_coordinate(venue.longitude),
            timezone=venue.timezone,
            is_public=venue.is_public,
            photos=tuple(self._photos(venue.id)),
            spaces=tuple(space_options),
        )

    def photo_content(self, venue_id: uuid.UUID, photo_id: uuid.UUID) -> tuple[bytes, str]:
        if self.storage is None:
            raise DiscoveryNotFound
        photo = self.session.scalar(
            select(VenuePhoto)
            .join(OrganizationVenue, OrganizationVenue.id == VenuePhoto.organization_venue_id)
            .join(Organization, Organization.id == OrganizationVenue.organization_id)
            .where(
                VenuePhoto.id == photo_id,
                VenuePhoto.organization_venue_id == venue_id,
                VenuePhoto.status == "APPROVED",
                OrganizationVenue.status == "active",
                Organization.status == "active",
                or_(
                    Organization.is_platform.is_(True),
                    Organization.verification_status == "verified",
                ),
            )
        )
        if photo is None:
            raise DiscoveryNotFound
        try:
            return self.storage.read(photo.storage_key), photo.content_type
        except (StoredPhotoNotFound, PhotoStorageError) as exc:
            raise DiscoveryNotFound from exc

    def _active_venue(self, venue_id: uuid.UUID) -> OrganizationVenue:
        venue = self.session.scalar(
            select(OrganizationVenue)
            .join(Organization, Organization.id == OrganizationVenue.organization_id)
            .where(
                OrganizationVenue.id == venue_id,
                OrganizationVenue.status == "active",
                Organization.status == "active",
                or_(
                    Organization.is_platform.is_(True),
                    Organization.verification_status == "verified",
                ),
            )
        )
        if venue is None:
            raise DiscoveryNotFound
        return venue

    def _active_spaces(self, venue_id: uuid.UUID) -> list[VenueSpace]:
        return list(
            self.session.scalars(
                select(VenueSpace)
                .where(
                    VenueSpace.organization_venue_id == venue_id,
                    VenueSpace.status == "active",
                )
                .order_by(VenueSpace.name, VenueSpace.id)
            ).all()
        )

    def _availability(self, space_id: uuid.UUID) -> list[VenueAvailability]:
        return list(
            self.session.scalars(
                select(VenueAvailability)
                .where(VenueAvailability.venue_space_id == space_id)
                .order_by(
                    VenueAvailability.weekday,
                    VenueAvailability.start_time,
                    VenueAvailability.id,
                )
            ).all()
        )

    def _sports(self, space_id: uuid.UUID) -> list[Sport]:
        return list(
            self.session.scalars(
                select(Sport)
                .join(VenueSport, VenueSport.sport_id == Sport.id)
                .where(
                    VenueSport.venue_space_id == space_id,
                    Sport.active.is_(True),
                )
                .order_by(Sport.name, Sport.id)
            ).all()
        )

    def _formats(
        self,
        sport_id: uuid.UUID,
        bands: dict[uuid.UUID, PricingBand | None],
    ) -> list[FormatOption]:
        formats = list(
            self.session.scalars(
                select(SportFormat)
                .where(
                    SportFormat.sport_id == sport_id,
                    SportFormat.active.is_(True),
                )
                .order_by(SportFormat.team_size, SportFormat.name, SportFormat.id)
            ).all()
        )
        options: list[FormatOption] = []
        for format_ in formats:
            tickets: dict[str, int] = {}
            for band in bands.values():
                if band is None:
                    continue
                try:
                    tickets[band.code] = tickets_for(self.session, band.id, format_.team_size)
                except PricingBandError:
                    continue
            options.append(
                FormatOption(
                    id=format_.id,
                    slug=format_.slug,
                    name=format_.name,
                    team_size=format_.team_size,
                    total_participants=format_.total_participants,
                    tickets_by_band=tickets,
                )
            )
        return options

    def _availability_option(
        self,
        row: VenueAvailability,
        band: PricingBand | None,
    ) -> AvailabilityOption:
        return AvailabilityOption(
            weekday=row.weekday,
            start_time=row.start_time,
            end_time=row.end_time,
            price_cents=row.price_cents,
            slot_minutes=row.slot_minutes,
            band=(
                BandOption(
                    id=band.id,
                    code=band.code,
                    label=band.label,
                    max_price_cents=band.max_price_cents,
                )
                if band is not None
                else None
            ),
        )

    def _photos(self, venue_id: uuid.UUID) -> list[PhotoOption]:
        rows = self.session.scalars(
            select(VenuePhoto)
            .where(
                VenuePhoto.organization_venue_id == venue_id,
                VenuePhoto.status == "APPROVED",
            )
            .order_by(VenuePhoto.created_at, VenuePhoto.id)
        ).all()
        return [
            PhotoOption(id=row.id, caption=row.caption, content_type=row.content_type)
            for row in rows
        ]

    def _next_slots(
        self,
        space: VenueSpace,
        venue: OrganizationVenue,
        availability: list[VenueAvailability],
    ) -> list[SlotOption]:
        if not availability:
            return []
        try:
            zone = ZoneInfo(venue.timezone)
        except Exception:  # noqa: BLE001 - fuso inválido não deve derrubar a vitrine
            return []

        now = utcnow()
        settings = get_settings()
        lead_minutes = max(
            settings.matchmaking_min_lead_minutes,
            settings.booking_t1_minutes
            + settings.booking_t2_minutes
            + settings.booking_t3_minutes
            + settings.booking_payment_buffer_minutes,
        )
        earliest = now + timedelta(minutes=lead_minutes)
        horizon = now + timedelta(days=LOOKAHEAD_DAYS + 1)
        blackouts = list(
            self.session.scalars(
                select(VenueBlackout).where(
                    VenueBlackout.venue_space_id == space.id,
                    VenueBlackout.ends_at > now,
                    VenueBlackout.starts_at < horizon,
                )
            ).all()
        )
        holds = list(
            self.session.scalars(
                select(BookingHold).where(
                    BookingHold.venue_space_id == space.id,
                    BookingHold.status == "ACTIVE",
                    BookingHold.ends_at > now,
                    BookingHold.starts_at < horizon,
                )
            ).all()
        )
        bookings = list(
            self.session.scalars(
                select(Booking).where(
                    Booking.venue_space_id == space.id,
                    Booking.status.in_(SPACE_BLOCKING_STATUSES),
                    Booking.ends_at > now,
                    Booking.starts_at < horizon,
                )
            ).all()
        )

        slots: list[SlotOption] = []
        today = now.astimezone(zone).date()
        for offset in range(LOOKAHEAD_DAYS + 1):
            local_day = today + timedelta(days=offset)
            for row in availability:
                if row.weekday != local_day.isoweekday():
                    continue
                window_start = datetime.combine(local_day, row.start_time, tzinfo=zone)
                window_end = datetime.combine(local_day, row.end_time, tzinfo=zone)
                cursor = window_start
                while cursor + timedelta(minutes=row.slot_minutes) <= window_end:
                    start = cursor.astimezone(UTC)
                    end = start + timedelta(minutes=row.slot_minutes)
                    if start < earliest:
                        cursor += timedelta(minutes=row.slot_minutes)
                        continue
                    if self._overlaps(start, end, blackouts, holds, bookings):
                        cursor += timedelta(minutes=row.slot_minutes)
                        continue
                    band = (
                        self.session.get(PricingBand, row.band_id)
                        if row.band_id is not None
                        else None
                    )
                    slots.append(
                        SlotOption(
                            starts_at=start,
                            ends_at=end,
                            price_cents=row.price_cents,
                            band_code=band.code if band is not None else None,
                        )
                    )
                    if len(slots) >= MAX_SLOTS_PER_SPACE:
                        return sorted(slots, key=lambda item: item.starts_at)
                    cursor += timedelta(minutes=row.slot_minutes)
        return sorted(slots, key=lambda item: item.starts_at)

    @staticmethod
    def _overlaps(
        start: datetime,
        end: datetime,
        blackouts: list[VenueBlackout],
        holds: list[BookingHold],
        bookings: list[Booking],
    ) -> bool:
        return (
            any(_interval_overlaps(start, end, item.starts_at, item.ends_at) for item in blackouts)
            or any(_interval_overlaps(start, end, item.starts_at, item.ends_at) for item in holds)
            or any(
                _interval_overlaps(start, end, item.starts_at, item.ends_at) for item in bookings
            )
        )

    @staticmethod
    def _raw_distance(region: UserRegion | None, venue: OrganizationVenue) -> float | None:
        """Distância sem arredondar, para o corte de ``max_distance_km``."""
        if region is None or venue.latitude is None or venue.longitude is None:
            return None
        return _haversine_km(
            region.center_lat,
            region.center_lng,
            venue.latitude,
            venue.longitude,
        )

    @staticmethod
    def _round_coordinate(value: float | None) -> float | None:
        if value is None:
            return None
        return round(value, get_settings().location_round_decimals)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math

    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _interval_overlaps(
    start: datetime,
    end: datetime,
    item_start: datetime,
    item_end: datetime,
) -> bool:
    return ensure_utc(item_start) < end and ensure_utc(item_end) > start


__all__ = [
    "BandOption",
    "DiscoveryError",
    "DiscoveryInvalid",
    "DiscoveryNotFound",
    "FormatOption",
    "PhotoOption",
    "SlotOption",
    "SpaceOption",
    "SportOption",
    "VenueCard",
    "VenueCardPage",
    "VenueDetail",
    "VenueFormatOption",
    "VenueDiscoveryService",
]
