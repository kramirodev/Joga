"""Dependência FastAPI do consultor de CNPJ (ADR 0062)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.modules.organizations.cnpj import BrasilApiCnpjLookup, CnpjLookup


@lru_cache(maxsize=4)
def _build_lookup(
    base_url: str,
    timeout_seconds: int,
    attempts: int,
    cache_ttl_seconds: int,
) -> BrasilApiCnpjLookup:
    return BrasilApiCnpjLookup(
        base_url,
        timeout_seconds=timeout_seconds,
        attempts=attempts,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def get_cnpj_lookup(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CnpjLookup:
    """Cliente compartilhado por processo; testes substituem por um fake."""

    return _build_lookup(
        settings.cnpj_api_base_url,
        settings.cnpj_timeout_seconds,
        settings.cnpj_lookup_attempts,
        settings.cnpj_cache_ttl_seconds,
    )


__all__ = ["get_cnpj_lookup"]
