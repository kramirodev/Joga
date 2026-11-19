"""Projeção pública mínima da identidade visual (sem PII)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.modules.visual.service import public_identity


class PublicVisualResponse(BaseModel):
    icon_key: str | None
    frame_key: str | None
    accent_key: str | None
    badge_key: str | None


def public_visual(session: Session, user_id: UUID) -> PublicVisualResponse:
    return PublicVisualResponse(**public_identity(session, user_id))


__all__ = ["PublicVisualResponse", "public_visual"]
