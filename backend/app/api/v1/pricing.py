"""Catálogo de faixas de preço em ingressos (ADR 0042 §3)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.pricing.service import list_active_bands

router = APIRouter(prefix="/pricing", tags=["pricing"])


class BandView(BaseModel):
    id: UUID
    code: str
    label: str
    max_price_cents: int
    version: int


class BandListResponse(BaseModel):
    bands: list[BandView]


@router.get("/bands", response_model=BandListResponse)
def list_bands(
    session: Annotated[Session, Depends(get_session)],
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
) -> BandListResponse:
    """Faixas ativas, da mais barata para a mais cara."""
    del current
    return BandListResponse(
        bands=[
            BandView(
                id=band.id,
                code=band.code,
                label=band.label,
                max_price_cents=band.max_price_cents,
                version=band.version,
            )
            for band in list_active_bands(session)
        ]
    )
