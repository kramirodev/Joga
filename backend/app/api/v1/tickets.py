"""Carteira de ingressos do jogador (ADR 0042 §2)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.core.config import get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.tickets.models import TicketPack, TicketPurchase
from app.modules.tickets.service import (
    PackNotFound,
    PurchaseNotFound,
    TicketError,
    confirm_purchase,
    create_purchase,
    get_balance,
    list_entries,
    list_packs,
)

router = APIRouter(prefix="/me/tickets", tags=["tickets"])

LOCAL_ENVIRONMENTS = frozenset({"local", "test", "development", "ci"})


class TicketEntryView(BaseModel):
    id: UUID
    amount: int
    source: str
    ref_type: str | None
    ref_id: UUID | None
    created_at: datetime


class TicketWalletView(BaseModel):
    balance: int
    entries: list[TicketEntryView]


@router.get("", response_model=TicketWalletView)
def read_wallet(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> TicketWalletView:
    """Saldo e últimos movimentos. O saldo nunca é editável pelo cliente."""

    entries = list_entries(session, current.user_id, limit=limit)
    return TicketWalletView(
        balance=get_balance(session, current.user_id),
        entries=[
            TicketEntryView(
                id=item.id,
                amount=item.amount,
                source=item.source,
                ref_type=item.ref_type,
                ref_id=item.ref_id,
                created_at=item.created_at,
            )
            for item in entries
        ],
    )


class PackView(BaseModel):
    code: str
    label: str
    tickets: int
    unit_price_cents: int
    amount_cents: int


class PackListResponse(BaseModel):
    packs: list[PackView]


class PurchaseCreate(BaseModel):
    pack_code: str = Field(min_length=1, max_length=20)


class PurchaseView(BaseModel):
    id: UUID
    pack_id: UUID
    tickets: int
    amount_cents: int
    status: str
    created_at: datetime
    paid_at: datetime | None


def _purchase_view(purchase: TicketPurchase) -> PurchaseView:
    return PurchaseView(
        id=purchase.id,
        pack_id=purchase.pack_id,
        tickets=purchase.tickets,
        amount_cents=purchase.amount_cents,
        status=purchase.status,
        created_at=purchase.created_at,
        paid_at=purchase.paid_at,
    )


def _pack_view(pack: TicketPack) -> PackView:
    return PackView(
        code=pack.code,
        label=pack.label,
        tickets=pack.tickets,
        unit_price_cents=pack.unit_price_cents,
        amount_cents=pack.amount_cents,
    )


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, (PackNotFound, PurchaseNotFound)):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": "not_found"}
        )
    if isinstance(exc, TicketError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"code": "ticket_error"}
        )
    raise exc


@router.get("/packs", response_model=PackListResponse)
def read_packs(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PackListResponse:
    """Escada de preço vigente. Reais aparecem só aqui e no checkout."""

    del current
    return PackListResponse(packs=[_pack_view(pack) for pack in list_packs(session)])


@router.post("/purchases", response_model=PurchaseView, status_code=status.HTTP_201_CREATED)
def create_ticket_purchase(
    payload: PurchaseCreate,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PurchaseView:
    """Cria a intenção de compra. A cobrança Pix entra na Fase 14B."""

    try:
        purchase = create_purchase(session, current.user_id, payload.pack_code)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _purchase_view(purchase)


@router.get("/purchases/{purchase_id}", response_model=PurchaseView)
def read_purchase(
    purchase_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PurchaseView:
    purchase = session.get(TicketPurchase, purchase_id)
    if purchase is None or purchase.user_id != current.user_id:
        raise _handle(PurchaseNotFound())
    return _purchase_view(purchase)


@router.post("/purchases/{purchase_id}/confirm", response_model=PurchaseView)
def confirm_ticket_purchase(
    purchase_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PurchaseView:
    """Confirma o pagamento em ambiente local. Dinheiro real depende da Fase 14B."""

    if get_settings().environment.lower() not in LOCAL_ENVIRONMENTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "confirmation_requires_psp"},
        )
    try:
        purchase, _ = confirm_purchase(session, current.user_id, purchase_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _purchase_view(purchase)
