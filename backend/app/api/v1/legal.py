"""Termos de Uso: versão vigente e aceite com prova (ADR 0049 §9.7)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.api.v1.request_context import request_ip_hash, request_user_agent_hash
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.legal import service as legal_service
from app.modules.legal.models import TermsAcceptance, TermsVersion

router = APIRouter(prefix="/legal", tags=["legal"])

AcceptanceContext = Literal["signup", "credit_purchase", "pass_purchase", "booking_ceiling"]


class TermsVersionView(BaseModel):
    id: UUID
    version: str
    content: str
    published_at: datetime
    terms_hash: str


class CurrentTermsView(BaseModel):
    terms: TermsVersionView | None


class TermsAcceptRequest(BaseModel):
    terms_version_id: UUID
    context: AcceptanceContext


class AcceptanceView(BaseModel):
    id: UUID
    terms_version_id: UUID
    version: str
    context: str
    accepted_at: datetime
    terms_hash: str


def _terms_view(terms: TermsVersion) -> TermsVersionView:
    return TermsVersionView(
        id=terms.id,
        version=terms.version,
        content=terms.content,
        published_at=terms.published_at,
        terms_hash=legal_service.content_hash(terms),
    )


def _acceptance_view(acceptance: TermsAcceptance, terms: TermsVersion | None) -> AcceptanceView:
    return AcceptanceView(
        id=acceptance.id,
        terms_version_id=acceptance.terms_version_id,
        version=terms.version if terms is not None else "",
        context=acceptance.context,
        accepted_at=acceptance.accepted_at,
        terms_hash=acceptance.terms_hash,
    )


@router.get("/terms/current", response_model=CurrentTermsView)
def current_terms(
    session: Annotated[Session, Depends(get_session)],
) -> CurrentTermsView:
    """Versão aprovada vigente; rascunho nunca aparece como aceitável."""
    terms = legal_service.latest_approved(session)
    return CurrentTermsView(terms=_terms_view(terms) if terms is not None else None)


@router.post("/terms/accept", response_model=AcceptanceView)
def accept_terms(
    payload: TermsAcceptRequest,
    request: Request,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AcceptanceView:
    """Registra aceite idempotente da versão aprovada, com hash de IP/UA."""
    ip_hash = request_ip_hash(request, settings)
    if ip_hash is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "terms_context_unavailable"},
        )
    try:
        acceptance = legal_service.accept_terms(
            session,
            user_id=current.user_id,
            terms_version_id=payload.terms_version_id,
            context=payload.context,
            ip_hash=ip_hash,
            user_agent_hash=request_user_agent_hash(request),
        )
    except legal_service.TermsNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "terms_not_found"},
        ) from None
    except legal_service.TermsNotApproved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "terms_not_approved"},
        ) from None
    except legal_service.InvalidTermsContext:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_terms_context"},
        ) from None
    session.commit()
    session.refresh(acceptance)
    terms = session.get(TermsVersion, acceptance.terms_version_id)
    return _acceptance_view(acceptance, terms)
