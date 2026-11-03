"""Serviço de perfil, disponibilidade, região e descoberta de locais."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import time
from typing import Any

import sqlalchemy as sa
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from sqlalchemy.types import UserDefinedType

from app.modules.identity.clock import utcnow
from app.modules.profile.cep import CepResolver
from app.modules.profile.models import (
    COURT_PREFERENCES,
    LEVELS,
    Availability,
    Sport,
    SportFormat,
    UserProfile,
    UserRegion,
    UserSportProfile,
    Venue,
)


class ProfileError(Exception):
    """Erro base do perfil."""


class InvalidProfile(ProfileError):
    """Dados de perfil inválidos."""


class InvalidSportFormat(ProfileError):
    """Formato inexistente ou inativo."""


class InvalidAvailability(ProfileError):
    """Janelas de disponibilidade inválidas ou sobrepostas."""


class RegionRequired(ProfileError):
    """Usuário ainda não definiu uma região de busca."""


class DiscoveryError(ProfileError):
    """Parâmetros de descoberta inválidos."""


class Geography(UserDefinedType[Any]):
    """Tipo mínimo para cast geography no PostgreSQL."""

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "geography"


@dataclass(frozen=True)
class ProfileSnapshot:
    user_id: uuid.UUID
    display_name: str | None
    bio: str | None
    sports: list[UserSportProfile]
    availability: list[Availability]
    region: UserRegion | None


@dataclass(frozen=True)
class VenuePage:
    items: list[Venue]
    total: int
    page: int
    page_size: int


class ProfileService:
    """Orquestra perfil, disponibilidade, região e descoberta."""

    def __init__(
        self,
        session: Session,
        cep_resolver: CepResolver,
        *,
        max_radius_km: int = 100,
        default_radius_km: int = 10,
        max_page_size: int = 20,
        location_round_decimals: int = 2,
        default_timezone: str = "America/Sao_Paulo",
    ) -> None:
        self._session = session
        self._cep = cep_resolver
        self._max_radius = max_radius_km
        self._default_radius = default_radius_km
        self._max_page_size = max_page_size
        self._round_decimals = location_round_decimals
        self._timezone = default_timezone

    def catalog(self) -> list[dict[str, Any]]:
        sports = list(
            self._session.scalars(select(Sport).where(Sport.active.is_(True)).order_by(Sport.name))
        )
        result: list[dict[str, Any]] = []
        for sport in sports:
            formats = list(
                self._session.scalars(
                    select(SportFormat)
                    .where(
                        SportFormat.sport_id == sport.id,
                        SportFormat.active.is_(True),
                    )
                    .order_by(SportFormat.name)
                )
            )
            result.append(
                {
                    "id": sport.id,
                    "slug": sport.slug,
                    "name": sport.name,
                    "formats": [
                        {
                            "id": item.id,
                            "slug": item.slug,
                            "name": item.name,
                            "team_size": item.team_size,
                            "total_participants": item.total_participants,
                            "play_minutes": item.play_minutes,
                            "break_minutes": item.break_minutes,
                            "duration_minutes": item.duration_minutes,
                            "version": item.version,
                        }
                        for item in formats
                    ],
                }
            )
        return result

    def get_profile(self, user_id: uuid.UUID) -> ProfileSnapshot:
        profile = self._session.get(UserProfile, user_id)
        sports = list(
            self._session.scalars(
                select(UserSportProfile)
                .where(UserSportProfile.user_id == user_id)
                .order_by(UserSportProfile.created_at)
            )
        )
        availability = list(
            self._session.scalars(
                select(Availability)
                .where(Availability.user_id == user_id)
                .order_by(Availability.weekday, Availability.start_time)
            )
        )
        region = self._session.get(UserRegion, user_id)
        return ProfileSnapshot(
            user_id=user_id,
            display_name=profile.display_name if profile else None,
            bio=profile.bio if profile else None,
            sports=sports,
            availability=availability,
            region=region,
        )

    def update_basic_profile(
        self,
        user_id: uuid.UUID,
        *,
        display_name: str | None,
        bio: str | None,
    ) -> ProfileSnapshot:
        profile = self._session.get(UserProfile, user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self._session.add(profile)
        profile.display_name = _clean_optional(display_name)
        profile.bio = _clean_optional(bio)
        self._session.flush()
        return self.get_profile(user_id)

    def replace_sports(
        self,
        user_id: uuid.UUID,
        items: list[dict[str, Any]],
    ) -> ProfileSnapshot:
        seen: set[uuid.UUID] = set()
        rows: list[UserSportProfile] = []
        for item in items:
            format_id = item["format_id"]
            if format_id in seen:
                raise InvalidProfile("formato duplicado no perfil")
            seen.add(format_id)
            sport_format = self._session.get(SportFormat, format_id)
            if sport_format is None or not sport_format.active:
                raise InvalidSportFormat("formato inexistente ou inativo")
            level = item["level"]
            court = item["court_preference"]
            if level not in LEVELS:
                raise InvalidProfile("nível inválido")
            if court not in COURT_PREFERENCES:
                raise InvalidProfile("preferência de quadra inválida")
            rows.append(
                UserSportProfile(
                    user_id=user_id,
                    format_id=format_id,
                    level=level,
                    court_preference=court,
                )
            )

        self._session.execute(delete(UserSportProfile).where(UserSportProfile.user_id == user_id))
        self._session.add_all(rows)
        self._session.flush()
        return self.get_profile(user_id)

    def replace_availability(
        self,
        user_id: uuid.UUID,
        windows: list[dict[str, Any]],
    ) -> ProfileSnapshot:
        normalized: list[Availability] = []
        by_weekday: dict[int, list[tuple[time, time]]] = {}
        for window in windows:
            weekday = window["weekday"]
            start = window["start_time"]
            end = window["end_time"]
            timezone = window.get("timezone") or self._timezone
            if not 1 <= weekday <= 7:
                raise InvalidAvailability("dia da semana inválido")
            if start >= end:
                raise InvalidAvailability("horário inicial deve ser menor que o final")
            ranges = by_weekday.setdefault(weekday, [])
            for existing_start, existing_end in ranges:
                if start < existing_end and existing_start < end:
                    raise InvalidAvailability("janelas de disponibilidade se sobrepõem")
            ranges.append((start, end))
            normalized.append(
                Availability(
                    user_id=user_id,
                    weekday=weekday,
                    start_time=start,
                    end_time=end,
                    timezone=timezone,
                )
            )

        self._session.execute(delete(Availability).where(Availability.user_id == user_id))
        self._session.add_all(normalized)
        self._session.flush()
        return self.get_profile(user_id)

    def set_region_by_cep(
        self,
        user_id: uuid.UUID,
        cep: str,
        radius_km: int | None = None,
    ) -> ProfileSnapshot:
        radius = self._validate_radius(radius_km)
        location = self._cep.resolve(cep)
        region = self._session.get(UserRegion, user_id)
        if region is None:
            region = UserRegion(user_id=user_id)
            self._session.add(region)
        region.source = "cep"
        region.cep = location.cep
        region.city = location.city
        region.state = location.state
        region.radius_km = radius
        region.center_lat = round(location.lat, self._round_decimals)
        region.center_lng = round(location.lng, self._round_decimals)
        region.updated_at = utcnow()
        self._session.flush()
        return self.get_profile(user_id)

    def set_region_by_location(
        self,
        user_id: uuid.UUID,
        lat: float,
        lng: float,
        radius_km: int | None = None,
    ) -> ProfileSnapshot:
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise InvalidProfile("coordenadas inválidas")
        radius = self._validate_radius(radius_km)
        region = self._session.get(UserRegion, user_id)
        if region is None:
            region = UserRegion(user_id=user_id)
            self._session.add(region)
        region.source = "gps"
        region.cep = None
        region.city = None
        region.state = None
        region.radius_km = radius
        region.center_lat = round(lat, self._round_decimals)
        region.center_lng = round(lng, self._round_decimals)
        region.updated_at = utcnow()
        self._session.flush()
        return self.get_profile(user_id)

    def discover_venues(
        self,
        user_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int | None = None,
    ) -> VenuePage:
        if page < 1:
            raise DiscoveryError("página inválida")
        resolved_page_size = self._max_page_size if page_size is None else page_size
        if not 1 <= resolved_page_size <= self._max_page_size:
            raise DiscoveryError("tamanho de página inválido")

        region = self._session.get(UserRegion, user_id)
        if region is None:
            raise RegionRequired("defina uma região antes de descobrir locais")

        dialect = self._session.get_bind().dialect.name
        if dialect == "postgresql":
            return self._discover_postgres(region, page, resolved_page_size)
        return self._discover_python(region, page, resolved_page_size)

    def _validate_radius(self, radius_km: int | None) -> int:
        value = self._default_radius if radius_km is None else radius_km
        if not 1 <= value <= self._max_radius:
            raise InvalidProfile(f"raio deve estar entre 1 e {self._max_radius} km")
        return value

    def _discover_postgres(
        self,
        region: UserRegion,
        page: int,
        page_size: int,
    ) -> VenuePage:
        center = func.ST_SetSRID(func.ST_MakePoint(region.center_lng, region.center_lat), 4326)
        center_geography = sa.cast(center, Geography)
        venue_point = func.ST_SetSRID(func.ST_MakePoint(Venue.lng, Venue.lat), 4326)
        venue_geography = sa.cast(venue_point, Geography)
        distance = func.ST_Distance(center_geography, venue_geography)
        radius_m = region.radius_km * 1000

        where = sa.and_(
            Venue.active.is_(True),
            func.ST_DWithin(center_geography, venue_geography, radius_m),
        )
        total = int(self._session.scalar(select(func.count()).select_from(Venue).where(where)) or 0)
        items = list(
            self._session.scalars(
                select(Venue)
                .where(where)
                .order_by(distance, Venue.name)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return VenuePage(items=items, total=total, page=page, page_size=page_size)

    def _discover_python(
        self,
        region: UserRegion,
        page: int,
        page_size: int,
    ) -> VenuePage:
        """Fallback para SQLite (testes); não substitui PostGIS em produção."""
        candidates = list(self._session.scalars(select(Venue).where(Venue.active.is_(True))))
        with_distance = [
            (item, _haversine_km(region.center_lat, region.center_lng, item.lat, item.lng))
            for item in candidates
        ]
        filtered = [
            (item, distance) for item, distance in with_distance if distance <= region.radius_km
        ]
        filtered.sort(key=lambda pair: (pair[1], pair[0].name))
        start = (page - 1) * page_size
        return VenuePage(
            items=[item for item, _ in filtered[start : start + page_size]],
            total=len(filtered),
            page=page,
            page_size=page_size,
        )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))
