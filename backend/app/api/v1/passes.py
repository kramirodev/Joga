"""Passe trimestral: planos, assinatura e cobrança Pix (ADR 0042 §2, ADR 0043 §2)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.api.v1.payment_views import PurchasePaymentView, purchase_payment_view
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.idempotency import service as idempotency
from app.modules.identity.clock import utcnow
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.passes.models import PassDelivery, PassSubscription
from app.modules.passes.plans import list_plans
from app.modules.passes.service import (
    PassAlreadyActive,
    PassError,
    PassNotFound,
    PassPlanNotFound,
    activate_subscription,
    cancel_subscription,
    create_subscription,
    deliveries_for,
    get_subscription,
    next_delivery_at,
)
from app.modules.payments.adapter import PspAdapter, PspError
from app.modules.payments.dependency import get_psp_adapter
from app.modules.payments.purchase import (
    PayerEmailRequired,
    PurchasePaymentError,
    PurchasePaymentMismatch,
    PurchasePaymentNotFound,
    open_charge,
    payment_for,
    sync_charge,
)

router = APIRouter(prefix="/me/pass", tags=["pass"])

LOCAL_ENVIRONMENTS = frozenset({"local", "test", "development", "ci"})


class PassPlanView(BaseModel):
    code: str
    label: str
    tickets_per_month: int
    unit_price_cents: int
    price_per_month_cents: int
    quarter_cents: int


class PassPlanListResponse(BaseModel):
    plans: list[PassPlanView]


class PassDeliveryView(BaseModel):
    month_index: int
    tickets: int
    delivered_at: datetime


class PassSubscriptionView(BaseModel):
    id: UUID
    plan_code: str
    tickets_per_month: int
    amount_cents: int
    status: str
    starts_at: datetime | None
    ends_at: datetime | None
    paid_at: datetime | None
    created_at: datetime
    deliveries: list[PassDeliveryView]
    next_delivery_at: datetime | None
    payment: PurchasePaymentView | None = None


class PassView(BaseModel):
    subscription: PassSubscriptionView | None


class PassSubscribeRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=20)


def _delivery_view(delivery: PassDelivery) -> PassDeliveryView:
    return PassDeliveryView(
        month_index=delivery.month_index,
        tickets=delivery.tickets,
        delivered_at=delivery.delivered_at,
    )


def _subscription_view(session: Session, subscription: PassSubscription) -> PassSubscriptionView:
    return PassSubscriptionView(
        id=subscription.id,
        plan_code=subscription.plan_code,
        tickets_per_month=subscription.tickets_per_month,
        amount_cents=subscription.amount_cents,
        status=subscription.status,
        starts_at=subscription.starts_at,
        ends_at=subscription.ends_at,
        paid_at=subscription.paid_at,
        created_at=subscription.created_at,
        deliveries=[_delivery_view(item) for item in deliveries_for(session, subscription.id)],
        next_delivery_at=next_delivery_at(subscription, now=utcnow()),
        payment=purchase_payment_view(payment_for(session, "pass", subscription.id)),
    )


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, (PassNotFound, PassPlanNotFound, PurchasePaymentNotFound)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "not_found"})
    if isinstance(exc, idempotency.IdempotencyConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"code": "idempotency_conflict"}
        )
    if isinstance(exc, idempotency.IdempotencyInProgress):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"code": "idempotency_in_progress"}
        )
    if isinstance(exc, PassAlreadyActive):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"code": "pass_already_active"}
        )
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
    if isinstance(exc, (PassError, PurchasePaymentError)):
        code = exc.args[0] if exc.args and isinstance(exc.args[0], str) else "pass_error"
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": code})
    raise exc


@router.get("/plans", response_model=PassPlanListResponse)
def read_plans(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
) -> PassPlanListResponse:
    """Quatro tamanhos: 10, 20, 30 ou 50 ingressos por mês, cobrados por trimestre."""

    del current
    return PassPlanListResponse(
        plans=[
            PassPlanView(
                code=plan.code,
                label=plan.label,
                tickets_per_month=plan.tickets_per_month,
                unit_price_cents=plan.unit_price_cents,
                price_per_month_cents=plan.price_per_month_cents,
                quarter_cents=plan.quarter_cents,
            )
            for plan in list_plans()
        ]
    )


@router.get("", response_model=PassView)
def read_pass(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PassView:
    """Assinatura vigente ou a última tentativa, com franquias já entregues."""

    subscription = session.scalars(
        select(PassSubscription)
        .where(PassSubscription.user_id == current.user_id)
        .order_by(
            (PassSubscription.status == "active").desc(),
            PassSubscription.created_at.desc(),
        )
    ).first()
    if subscription is None:
        return PassView(subscription=None)
    return PassView(subscription=_subscription_view(session, subscription))


@router.post(
    "/subscriptions",
    response_model=PassSubscriptionView,
    status_code=status.HTTP_201_CREATED,
)
def subscribe(
    payload: PassSubscribeRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PassSubscriptionView | JSONResponse:
    """Cria a assinatura pendente e abre o Pix do trimestre.

    Com ``Idempotency-Key``, o replay devolve a mesma assinatura sem abrir uma
    segunda cobrança; a mesma chave com outro plano responde
    ``409 idempotency_conflict``.
    """

    key = idempotency_key.strip() if idempotency_key is not None else None
    if idempotency_key is not None and (not key or len(key) > 120):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_idempotency_key"},
        )
    scope = f"me.pass.subscriptions:{current.user_id}"
    request_hash = idempotency.payload_hash({"plan_code": payload.plan_code})
    try:
        stored = (
            idempotency.begin(session, scope=scope, key=key, request_hash=request_hash)
            if key is not None
            else None
        )
        if stored is not None:
            return JSONResponse(status_code=stored.status_code, content=stored.body)
        subscription = create_subscription(session, current.user_id, payload.plan_code)
        plan = next(item for item in list_plans() if item.code == subscription.plan_code)
        open_charge(
            session,
            adapter,
            kind="pass",
            reference_id=subscription.id,
            user_id=current.user_id,
            amount_cents=subscription.amount_cents,
            description=f"JOGA · Passe {plan.label} · trimestre",
        )
        view = _subscription_view(session, subscription)
        if key is not None:
            idempotency.finish(
                session,
                scope=scope,
                key=key,
                status_code=status.HTTP_201_CREATED,
                body=view.model_dump(mode="json"),
            )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return view


@router.get("/subscriptions/{subscription_id}", response_model=PassSubscriptionView)
def read_subscription(
    subscription_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PassSubscriptionView:
    try:
        subscription = get_subscription(session, current.user_id, subscription_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    return _subscription_view(session, subscription)


@router.post("/subscriptions/{subscription_id}/sync", response_model=PassSubscriptionView)
def sync_subscription(
    subscription_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
) -> PassSubscriptionView:
    """Consulta o PSP; se o Pix caiu, ativa o passe e entrega o mês corrente."""

    try:
        subscription = get_subscription(session, current.user_id, subscription_id)
        payment = payment_for(session, "pass", subscription.id)
        if payment is None:
            raise PurchasePaymentNotFound
        sync_charge(session, adapter, payment)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    session.refresh(subscription)
    return _subscription_view(session, subscription)


@router.post("/subscriptions/{subscription_id}/confirm", response_model=PassSubscriptionView)
def confirm_subscription(
    subscription_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PassSubscriptionView:
    """Ativa sem PSP em ambiente local. Em produção exige webhook ou sync."""

    if settings.environment.lower() not in LOCAL_ENVIRONMENTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "confirmation_requires_psp"},
        )
    try:
        subscription = get_subscription(session, current.user_id, subscription_id)
        activate_subscription(session, subscription.id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    session.refresh(subscription)
    return _subscription_view(session, subscription)


@router.delete("/subscriptions/{subscription_id}", response_model=PassSubscriptionView)
def cancel_pending_subscription(
    subscription_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PassSubscriptionView:
    """Cancela uma assinatura ainda não paga. Assinatura ativa não é cancelável."""

    try:
        subscription = cancel_subscription(session, current.user_id, subscription_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _subscription_view(session, subscription)
