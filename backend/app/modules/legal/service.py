"""Serviço de Termos de Uso: rascunho, aprovação e verificação de aceite."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import utcnow
from app.modules.legal.models import TermsVersion

DRAFT_PLACEHOLDER = (
    "Rascunho. Texto das cláusulas C1 a C14 pendente de revisão jurídica "
    "(ADR 0049 §8). Não publicar e não aceitar nesta versão."
)


def create_draft(
    session: Session,
    *,
    version: str,
    content: str = DRAFT_PLACEHOLDER,
) -> TermsVersion:
    """Cria uma versão em rascunho. Nunca nasce aceitável."""
    if not version.strip():
        raise ValueError("Versão dos termos é obrigatória")
    existing = session.scalar(select(TermsVersion).where(TermsVersion.version == version))
    if existing is not None:
        raise ValueError("Versão dos termos já existe")
    terms = TermsVersion(version=version.strip(), content=content, status="draft")
    session.add(terms)
    session.flush()
    return terms


def approve(
    session: Session,
    terms: TermsVersion,
    *,
    legal_review_ref: str,
) -> TermsVersion:
    """Aprova a versão com referência da revisão jurídica."""
    reference = legal_review_ref.strip()
    if not reference:
        raise ValueError("Referência da revisão jurídica é obrigatória")
    if terms.status == "approved":
        raise ValueError("Versão já aprovada é imutável; crie uma nova versão")
    terms.status = "approved"
    terms.legal_review_ref = reference
    terms.published_at = utcnow()
    session.flush()
    return terms


def assert_acceptable(terms: TermsVersion) -> None:
    """Recusa aceite contra versão não aprovada."""
    if terms.status != "approved":
        raise ValueError("Termos sem aprovação jurídica não podem ser aceitos")


def latest_approved(session: Session) -> TermsVersion | None:
    """Versão aprovada mais recente, ou ``None`` se não houver nenhuma."""
    return session.scalars(
        select(TermsVersion)
        .where(TermsVersion.status == "approved")
        .order_by(TermsVersion.published_at.desc())
        .limit(1)
    ).first()


def get_by_id(session: Session, terms_id: uuid.UUID) -> TermsVersion | None:
    return session.get(TermsVersion, terms_id)
