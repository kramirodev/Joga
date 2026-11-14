"""Cálculo de prazo T2 em horário comercial (Fase 13E)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.modules.identity.clock import ensure_utc
from app.modules.venues.models import VenueBusinessHour, VenueClosure


class BusinessMinuteError(Exception):
    """Não foi possível encontrar expediente dentro da janela de busca."""


def add_business_minutes(
    start: datetime,
    minutes: int,
    hours: Sequence[VenueBusinessHour],
    closures: Sequence[VenueClosure],
    *,
    timezone: str,
    max_days: int = 14,
) -> datetime:
    """Soma minutos úteis pulando dias sem expediente e fechamentos.

    Sem expediente cadastrado, o cálculo cai para tempo corrido — o
    comportamento anterior — para não quebrar estabelecimentos legados.
    """

    if minutes <= 0:
        return ensure_utc(start)
    if not hours:
        return ensure_utc(start) + timedelta(minutes=minutes)

    try:
        zone = ZoneInfo(timezone)
    except Exception as exc:  # noqa: BLE001
        raise BusinessMinuteError("invalid_timezone") from exc

    cursor = ensure_utc(start).astimezone(zone)
    remaining = minutes
    closure_intervals = [
        (ensure_utc(item.starts_at).astimezone(zone), ensure_utc(item.ends_at).astimezone(zone))
        for item in closures
    ]
    by_weekday: dict[int, list[VenueBusinessHour]] = {}
    for item in hours:
        by_weekday.setdefault(item.weekday, []).append(item)

    day = cursor.date()
    for _offset in range(max_days + 1):
        day_cursor = max(cursor, datetime.combine(day, time.min, tzinfo=zone))
        intervals = sorted(by_weekday.get(day.isoweekday(), []), key=lambda item: item.opens_at)
        for item in intervals:
            interval_start = max(
                day_cursor,
                datetime.combine(day, item.opens_at, tzinfo=zone),
            )
            interval_end = datetime.combine(day, item.closes_at, tzinfo=zone)
            if interval_start >= interval_end:
                continue
            if any(
                closure_start < interval_end and closure_end > interval_start
                for closure_start, closure_end in closure_intervals
            ):
                continue
            available = interval_end - interval_start
            needed = timedelta(minutes=remaining)
            if needed <= available:
                return (interval_start + needed).astimezone(UTC)
            remaining -= int(available.total_seconds() // 60)
        day = day + timedelta(days=1)
        cursor = datetime.combine(day, time.min, tzinfo=zone)

    raise BusinessMinuteError("business_window_not_found")


def business_deadline(
    start: datetime,
    business_minutes: int,
    max_minutes: int,
    hours: Sequence[VenueBusinessHour],
    closures: Sequence[VenueClosure],
    *,
    timezone: str,
) -> datetime:
    """Prazo T2: minutos úteis, limitado pelo teto em tempo corrido."""

    maximum = ensure_utc(start) + timedelta(minutes=max_minutes)
    try:
        computed = add_business_minutes(
            start,
            business_minutes,
            hours,
            closures,
            timezone=timezone,
        )
    except BusinessMinuteError:
        return maximum
    return min(computed, maximum)


__all__ = ["BusinessMinuteError", "add_business_minutes", "business_deadline"]
