"""Serviço de Termos de Uso: rascunho, aprovação, aceite e verificação."""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import utcnow
from app.modules.legal.models import (
    TERMS_ACCEPTANCE_CONTEXTS,
    TermsAcceptance,
    TermsVersion,
)

DRAFT_PLACEHOLDER = (
    "Rascunho. Texto das cláusulas C1 a C14 pendente de revisão jurídica "
    "(ADR 0049 §8). Não publicar e não aceitar nesta versão."
)


class TermsError(ValueError):
    """Erro base de termos e aceite."""


class TermsNotFound(TermsError):
    """Versão de termos inexistente."""


class TermsNotApproved(TermsError):
    """Versão em rascunho não pode ser aceita."""


class TermsNotAccepted(TermsError):
    """A compra exige aceite da versão aprovada vigente."""


class InvalidTermsContext(TermsError):
    """Contexto de aceite fora da lista permitida."""


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
        raise TermsNotApproved("Termos sem aprovação jurídica não podem ser aceitos")


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


def content_hash(terms: TermsVersion) -> str:
    """SHA-256 do texto aceito; prova o que foi mostrado."""
    return hashlib.sha256(terms.content.encode("utf-8")).hexdigest()


def accept_terms(
    session: Session,
    *,
    user_id: uuid.UUID,
    terms_version_id: uuid.UUID,
    context: str,
    ip_hash: str,
    user_agent_hash: str | None = None,
) -> TermsAcceptance:
    """Registra o aceite de uma versão ``approved``, de forma idempotente."""
    if context not in TERMS_ACCEPTANCE_CONTEXTS:
        raise InvalidTermsContext("contexto de aceite inválido")
    if not ip_hash:
        raise TermsError("hash de IP é obrigatório para o aceite")
    terms = session.get(TermsVersion, terms_version_id)
    if terms is None:
        raise TermsNotFound("versão dos termos não encontrada")
    assert_acceptable(terms)
    existing = session.scalar(
        select(TermsAcceptance).where(
            TermsAcceptance.user_id == user_id,
            TermsAcceptance.terms_version_id == terms.id,
            TermsAcceptance.context == context,
        )
    )
    if existing is not None:
        return existing
    acceptance = TermsAcceptance(
        user_id=user_id,
        terms_version_id=terms.id,
        context=context,
        accepted_at=utcnow(),
        ip_hash=ip_hash,
        user_agent_hash=user_agent_hash,
        terms_hash=content_hash(terms),
    )
    session.add(acceptance)
    session.flush()
    return acceptance


def require_purchase_acceptance(
    session: Session,
    *,
    user_id: uuid.UUID,
    terms_version_id: uuid.UUID | None,
    ip_hash: str,
    user_agent_hash: str | None = None,
    context: str = "credit_purchase",
) -> TermsAcceptance | None:
    """Exige o aceite vigente quando existe versão aprovada.

    Publicar Termos está bloqueado nesta fase (ADR 0049 §5.6). Enquanto não
    houver versão ``approved``, a compra mantém o comportamento atual e não
    aceita rascunho. A partir da primeira versão aprovada, a compra sem o aceite
    dela é recusada.
    """
    latest = latest_approved(session)
    if latest is None:
        if terms_version_id is not None:
            raise TermsNotAccepted("não há versão aprovada para aceitar")
        return None
    if terms_version_id is None or terms_version_id != latest.id:
        raise TermsNotAccepted("aceite da versão vigente é obrigatório")
    return accept_terms(
        session,
        user_id=user_id,
        terms_version_id=latest.id,
        context=context,
        ip_hash=ip_hash,
        user_agent_hash=user_agent_hash,
    )


def latest_acceptance(
    session: Session,
    user_id: uuid.UUID,
    *,
    context: str | None = None,
) -> TermsAcceptance | None:
    query = select(TermsAcceptance).where(TermsAcceptance.user_id == user_id)
    if context is not None:
        query = query.where(TermsAcceptance.context == context)
    return session.scalars(query.order_by(TermsAcceptance.accepted_at.desc()).limit(1)).first()
