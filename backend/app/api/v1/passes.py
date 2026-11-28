"""Assinatura: catálogo, contrato, Pix e recibo interno (ADR 0070)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.api.v1.auth_guards import require_ticket_purchase_enabled
from app.api.v1.payment_views import PurchasePaymentView, purchase_payment_view
from app.api.v1.request_context import request_ip_hash, request_user_agent_hash
from app.core.config import Settings, get_settings
from app.core.environments import is_demo, is_local
from app.infrastructure.database.dependency import get_session
from app.modules.idempotency import service as idempotency
from app.modules.identity.clock import utcnow
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.legal import service as legal_service
from app.modules.passes.models import PassDelivery, PassPlan, PassSubscription
from app.modules.passes.plans import get_active_plan, list_active_plans
from app.modules.passes.service import (
    PassAlreadyActive,
    PassError,
    PassNotFound,
    PassPlanNotFound,
    ReceiptUnavailable,
    activate_subscription,
    cancel_subscription,
    create_subscription,
    current_delivery,
    deliveries_for,
    delivery_usage,
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


class PassPlanView(BaseModel):
    code: str
    label: str
    months: int
    tickets_per_month: int
    unit_price_cents: int
    monthly_cents: int
    cycle_total_cents: int
    installments: int
    catalog_version: int
    # Compatibilidade com o app anterior; equivale a ``monthly_cents``.
    price_per_month_cents: int


class PassPlanListResponse(BaseModel):
    plans: list[PassPlanView]
    catalog_version: int | None = None


class PassDeliveryView(BaseModel):
    month_index: int
    tickets: int
    period: str
    starts_at: datetime
    ends_at: datetime
    status: str
    delivered_at: datetime | None
    closed_at: datetime | None


class CurrentCycleView(BaseModel):
    period: str
    starts_at: datetime
    ends_at: datetime
    tickets_granted: int
    tickets_used: int
    tickets_remaining: int
    expires_at: datetime | None


class PassSubscriptionView(BaseModel):
    id: UUID
    plan_code: str
    plan_label: str
    tickets_per_month: int
    amount_cents: int
    cycle_months: int
    unit_price_cents: int
    installments: int
    status: str
    starts_at: datetime | None
    ends_at: datetime | None
    paid_at: datetime | None
    refund_window_ends_at: datetime | None
    created_at: datetime
    deliveries: list[PassDeliveryView]
    cycles: list[PassDeliveryView]
    current_cycle: CurrentCycleView | None
    next_delivery_at: datetime | None
    payment: PurchasePaymentView | None = None


class PassView(BaseModel):
    subscription: PassSubscriptionView | None


class PassSubscribeRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=24)
    terms_version_id: UUID | None = None


class PurchaseReceiptView(BaseModel):
    """Comprovante interno da compra. Não é documento fiscal."""

    receipt_id: UUID
    subscription_id: UUID
    document_type: str = "internal_receipt"
    fiscal_document: None = None
    status: str
    issued_at: datetime
    plan_code: str
    plan_label: str
    cycle_months: int
    tickets_per_month: int
    unit_price_cents: int
    monthly_cents: int
    cycle_total_cents: int
    amount_cents: int
    currency: str = "BRL"
    provider: str | None
    payment_status: str | None
    paid_at: datetime


def _delivery_view(delivery: PassDelivery) -> PassDeliveryView:
    return PassDeliveryView(
        month_index=delivery.month_index,
        tickets=delivery.tickets,
        period=delivery.period,
        starts_at=delivery.starts_at,
        ends_at=delivery.ends_at,
        status=delivery.status,
        delivered_at=delivery.delivered_at,
        closed_at=delivery.closed_at,
    )


def _plan_label(session: Session, plan_code: str) -> str:
    label = session.scalar(select(PassPlan.label).where(PassPlan.code == plan_code))
    return str(label) if label else plan_code


def _current_cycle_view(session: Session, cycle: PassDelivery | None) -> CurrentCycleView | None:
    if cycle is None:
        return None
    granted, used, remaining, expires_at = delivery_usage(session, cycle)
    return CurrentCycleView(
        period=cycle.period,
        starts_at=cycle.starts_at,
        ends_at=cycle.ends_at,
        tickets_granted=granted,
        tickets_used=used,
        tickets_remaining=remaining,
        expires_at=expires_at,
    )


def _subscription_view(session: Session, subscription: PassSubscription) -> PassSubscriptionView:
    deliveries = deliveries_for(session, subscription.id)
    moment = utcnow()
    return PassSubscriptionView(
        id=subscription.id,
        plan_code=subscription.plan_code,
        plan_label=_plan_label(session, subscription.plan_code),
        tickets_per_month=subscription.tickets_per_month,
        amount_cents=subscription.amount_cents,
        cycle_months=subscription.cycle_months,
        unit_price_cents=subscription.unit_price_cents,
        installments=subscription.installments,
        status=subscription.status,
        starts_at=subscription.starts_at,
        ends_at=subscription.ends_at,
        paid_at=subscription.paid_at,
        refund_window_ends_at=subscription.refund_window_ends_at,
        created_at=subscription.created_at,
        deliveries=[
            _delivery_view(item) for item in deliveries if item.status in {"delivered", "closed"}
        ],
        cycles=[_delivery_view(item) for item in deliveries],
        current_cycle=_current_cycle_view(
            session, current_delivery(subscription, deliveries, now=moment)
        ),
        next_delivery_at=next_delivery_at(session, subscription, now=moment),
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
    if isinstance(exc, ReceiptUnavailable):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"code": "receipt_not_available"}
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
    if isinstance(exc, legal_service.TermsNotApproved):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "terms_not_approved"},
        )
    if isinstance(exc, legal_service.TermsNotAccepted):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "terms_not_accepted"},
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
    session: Annotated[Session, Depends(get_session)],
) -> PassPlanListResponse:
    """Catálogo ativo: franquia mensal × duração, preço vindo do banco."""

    del current
    plans = list_active_plans(session)
    return PassPlanListResponse(
        plans=[
            PassPlanView(
                code=plan.code,
                label=plan.label,
                months=plan.months,
                tickets_per_month=plan.tickets_per_month,
                unit_price_cents=plan.unit_price_cents,
                monthly_cents=plan.monthly_cents,
                cycle_total_cents=plan.cycle_amount_cents,
                installments=plan.installments,
                catalog_version=plan.catalog_version,
                price_per_month_cents=plan.monthly_cents,
            )
            for plan in plans
        ],
        catalog_version=plans[0].catalog_version if plans else None,
    )


@router.get("", response_model=PassView)
def read_pass(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PassView:
    """Assinatura vigente ou a última tentativa, com ciclos e uso corrente."""

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
    dependencies=[Depends(require_ticket_purchase_enabled)],
)
def subscribe(
    payload: PassSubscribeRequest,
    request: Request,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PassSubscriptionView | JSONResponse:
    """Cria o contrato pendente e abre o Pix do ciclo.

    O preço vem do catálogo do servidor; o cliente só envia ``plan_code``. Com
    ``Idempotency-Key``, o replay devolve o mesmo contrato sem abrir segunda
    cobrança.
    """

    key = idempotency_key.strip() if idempotency_key is not None else None
    if idempotency_key is not None and (not key or len(key) > 120):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_idempotency_key"},
        )
    scope = f"me.pass.subscriptions:{current.user_id}"
    request_hash = idempotency.payload_hash(
        {
            "plan_code": payload.plan_code,
            "terms_version_id": (
                str(payload.terms_version_id) if payload.terms_version_id is not None else None
            ),
        }
    )
    try:
        stored = (
            idempotency.begin(session, scope=scope, key=key, request_hash=request_hash)
            if key is not None
            else None
        )
        if stored is not None:
            return JSONResponse(status_code=stored.status_code, content=stored.body)
        ip_hash = request_ip_hash(request, settings)
        if ip_hash is None and legal_service.latest_approved(session) is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "terms_context_unavailable"},
            )
        legal_service.require_purchase_acceptance(
            session,
            user_id=current.user_id,
            terms_version_id=payload.terms_version_id,
            ip_hash=ip_hash or "",
            user_agent_hash=request_user_agent_hash(request),
            context="pass_purchase",
        )
        subscription = create_subscription(session, current.user_id, payload.plan_code)
        plan = get_active_plan(session, subscription.plan_code)
        label = plan.label if plan is not None else subscription.plan_code
        open_charge(
            session,
            adapter,
            kind="pass",
            reference_id=subscription.id,
            user_id=current.user_id,
            amount_cents=subscription.amount_cents,
            description=f"JOGA · Assinatura {label} · {subscription.cycle_months} mês(es)",
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


@router.get(
    "/subscriptions/{subscription_id}/receipt",
    response_model=PurchaseReceiptView,
)
def read_receipt(
    subscription_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> PurchaseReceiptView:
    """Comprovante interno da compra; não substitui NFS-e (decisão fiscal pendente)."""

    try:
        subscription = get_subscription(session, current.user_id, subscription_id)
        payment = payment_for(session, "pass", subscription.id)
        if payment is None:
            raise PurchasePaymentNotFound
        if subscription.paid_at is None and payment.paid_at is None:
            raise ReceiptUnavailable
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from None
    paid_at = subscription.paid_at or payment.paid_at
    assert paid_at is not None
    units = subscription.tickets_per_month * subscription.unit_price_cents
    return PurchaseReceiptView(
        receipt_id=payment.id,
        subscription_id=subscription.id,
        status="paid",
        issued_at=paid_at,
        plan_code=subscription.plan_code,
        plan_label=_plan_label(session, subscription.plan_code),
        cycle_months=subscription.cycle_months,
        tickets_per_month=subscription.tickets_per_month,
        unit_price_cents=subscription.unit_price_cents,
        monthly_cents=units,
        cycle_total_cents=subscription.amount_cents,
        amount_cents=payment.amount_cents,
        provider=payment.provider,
        payment_status=payment.provider_status,
        paid_at=paid_at,
    )


@router.post("/subscriptions/{subscription_id}/sync", response_model=PassSubscriptionView)
def sync_subscription(
    subscription_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
) -> PassSubscriptionView:
    """Consulta o PSP; se o Pix caiu, ativa o contrato e entrega o ciclo corrente."""

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
    """Ativa sem PSP em ambiente local ou demo. Em produção exige webhook ou sync."""

    if not (is_local(settings.environment) or is_demo(settings.environment)):
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
    """Cancela uma assinatura ainda não paga. Assinatura ativa não é cancelável aqui."""

    try:
        subscription = cancel_subscription(session, current.user_id, subscription_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _handle(exc) from None
    return _subscription_view(session, subscription)
