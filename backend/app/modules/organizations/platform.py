"""Organização da plataforma para as quadras públicas."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.organizations.models import Organization

DEFAULT_PLATFORM_ORG_SLUG = "joga-publico"
DEFAULT_PLATFORM_ORG_NAME = "JOGA — Quadras Públicas"


def ensure_platform_organization(
    session: Session,
    *,
    slug: str = DEFAULT_PLATFORM_ORG_SLUG,
    name: str = DEFAULT_PLATFORM_ORG_NAME,
) -> Organization:
    """Garante a organização da plataforma. Idempotente por slug."""

    organization = session.scalar(select(Organization).where(Organization.slug == slug))
    if organization is not None:
        return organization
    organization = Organization(
        slug=slug,
        name=name,
        is_platform=True,
        status="active",
        payout_status="blocked",
    )
    session.add(organization)
    session.flush()
    return organization


def platform_organization(session: Session, slug: str) -> Organization:
    organization = session.scalar(
        select(Organization).where(
            Organization.slug == slug,
            Organization.is_platform.is_(True),
        )
    )
    if organization is None:
        raise LookupError("platform_organization_missing")
    return organization


__all__ = [
    "DEFAULT_PLATFORM_ORG_NAME",
    "DEFAULT_PLATFORM_ORG_SLUG",
    "ensure_platform_organization",
    "platform_organization",
]
