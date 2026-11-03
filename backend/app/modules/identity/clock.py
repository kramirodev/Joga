"""Relógio UTC e normalização de datas para testes e banco."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Retorna o instante atual com timezone UTC."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Trata datas sem timezone como UTC (SQLite não preserva o offset)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
