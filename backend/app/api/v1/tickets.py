"""Carteira de ingressos do jogador (ADR 0042 §2)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.api.v1.payment_views import PurchasePaymentView, purchase_payment_view
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.payments.adapter import PspAdapter, PspError
from app.modules.payments.dependency import get_psp_adapter
from app.modules.payments.models import PurchasePayment
from app.modules.payments.purchase import (
    PayerEmailRequired,
    PurchasePaymentError,
    PurchasePaymentMismatch,
    PurchasePaymentNotFound,
    open_charge,
    payment_for,
    sync_charge,
)
from app.modules.tickets.models import TicketPack, TicketPurchase
from app.modules.tickets.service import (
    PackNotFound,
    PurchaseNotFound,
    TicketError,
    confirm_purchase,
    create_purchase,
    get_balance,
    list_entries,
    list_lots,
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


class TicketLotView(BaseModel):
    id: UUID
    source: str
    original_amount: int
    remaining: int
    expires_at: datetime | None
    ref_type: str | None
    ref_id: UUID | None


class TicketWalletView(BaseModel):
    balance: int
    entries: list[TicketEntryView]
    lots: list[TicketLotView]


@router.get("", response_model=TicketWalletView)
def read_wallet(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> TicketWalletView:
    """Saldo e últimos movimentos. O saldo nunca é editável pelo cliente."""

    entries = list_entries(session, current.user_id, limit=limit)
    lots = list_lots(session, current.user_id)
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
        lots=[
            TicketLotView(
                id=item.id,
                source=item.source,
                original_amount=item.original_amount,
                remaining=item.remaining,
                expires_at=item.expires_at,
                ref_type=item.ref_type,
                ref_id=item.ref_id,
            )
            for item in lots
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
    payment: PurchasePaymentView | None = None


def _purchase_view(purchase: TicketPurchase, payment: PurchasePayment | None) -> PurchaseView:
    return PurchaseView(
        id=purchase.id,
        pack_id=purchase.pack_id,
        tickets=purchase.tickets,
        amount_cents=purchase.amount_cents,
        status=purchase.status,
        created_at=purchase.created_at,
        paid_at=purchase.paid_at,
        payment=purchase_payment_view(payment),
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
    if isinstance(exc, (PackNotFound, PurchaseNotFound, PurchasePaymentNotFound)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "not_found"})
    if isinstance(exc, PurchasePaymentMismatch):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"code": "payment_mismatch"}
        )
    if isinstance(exc, PayerEmailRequired):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "payer_email_required"},
        )
    if isinstance(exc, PspError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "psp_unavailable"},
        )
    if isinstance(exc, (TicketError, PurchasePaymentError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "ticket_error"})
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
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
) -> PurchaseView:
    """Cria a compra e abre a cobrança Pix. Os ingressos só entram quando pagos."""

    try:
        purchase = create_purchase(session, current.user_id, payload.pack_code)
        pack = session.get(TicketPack, purchase.pack_id)
        payment = open_charge(
            session,
            adapter,
            kind="ticket_pack",
            reference_id=purchase.id,
            user_id=current.user_id,
            amount_cents=purchase.amount_cents,
            description=f"JOGA · Pacote {pack.label if pack else purchase.tickets}",
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _purchase_view(purchase, payment)


@router.get("/purchases/{purchase_id}", response_model=PurchaseView)
def read_purchase(
    purchase_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PurchaseView:
    purchase = session.get(TicketPurchase, purchase_id)
    if purchase is None or purchase.user_id != current.user_id:
        raise _handle(PurchaseNotFound())
    return _purchase_view(purchase, payment_for(session, "ticket_pack", purchase.id))


@router.post("/purchases/{purchase_id}/sync", response_model=PurchaseView)
def sync_ticket_purchase(
    purchase_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
) -> PurchaseView:
    """Consulta o PSP e credita a compra se o Pix já foi pago."""

    try:
        purchase = session.get(TicketPurchase, purchase_id)
        if purchase is None or purchase.user_id != current.user_id:
            raise PurchaseNotFound
        payment = payment_for(session, "ticket_pack", purchase.id)
        if payment is None:
            raise PurchasePaymentNotFound
        sync_charge(session, adapter, payment)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    session.refresh(purchase)
    return _purchase_view(purchase, payment_for(session, "ticket_pack", purchase.id))


@router.post("/purchases/{purchase_id}/confirm", response_model=PurchaseView)
def confirm_ticket_purchase(
    purchase_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PurchaseView:
    """Confirma o pagamento em ambiente local, sem PSP. Só para desenvolvimento."""

    if settings.environment.lower() not in LOCAL_ENVIRONMENTS:
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
    return _purchase_view(purchase, payment_for(session, "ticket_pack", purchase.id))
