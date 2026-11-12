"""Endpoints de webhook, sincronização e abertura de cobranças Pix (Fase 14A)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.bookings.service import BookingNotFound, BookingService
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.organizations.permissions import Capability
from app.modules.organizations.service import (
    Forbidden,
    OrganizationNotFound,
    OrganizationService,
)
from app.modules.payments.adapter import PspAdapter, PspError, verify_webhook_signature
from app.modules.payments.dependency import get_psp_adapter
from app.modules.payments.financial import (
    DisputeConflict,
    DisputeNotFound,
    FinancialService,
    ReleaseNotFound,
)
from app.modules.payments.models import FinancialDispute, PaymentRefund
from app.modules.payments.service import PaymentError, PaymentNotFound, PaymentService

router = APIRouter(tags=["payments"])
LOCAL_ENVIRONMENTS = frozenset({"local", "test", "development", "ci"})


class PaymentSyncResponse(BaseModel):
    payment_id: UUID
    status: str
    provider_status: str | None


class OpenChargesResponse(BaseModel):
    payments: int


class RefundRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class RefundResponse(BaseModel):
    refunded: int


class LedgerView(BaseModel):
    id: UUID
    booking_payment_id: UUID | None
    entry_type: str
    direction: str
    amount_cents: int
    status: str
    details: dict[str, Any] | None
    created_at: datetime


class RefundView(BaseModel):
    id: UUID
    booking_payment_id: UUID
    amount_cents: int
    status: str
    reason: str | None
    provider_reference: str | None
    processed_at: datetime | None
    created_at: datetime


class BookingFinancialResponse(BaseModel):
    booking_id: UUID
    ledger: list[LedgerView]
    refunds: list[RefundView]


class OrganizationSummaryResponse(BaseModel):
    charged_cents: int
    paid_cents: int
    refunded_cents: int
    pending_cents: int
    released_cents: int
    pending_release_cents: int
    disputed_cents: int
    payments: int
    refunds: int


class ReceivableView(BaseModel):
    booking_id: UUID
    release_id: UUID
    amount_cents: int
    status: str
    eligible_at: datetime
    released_at: datetime | None
    starts_at: datetime
    ends_at: datetime
    has_open_dispute: bool
    dispute_id: UUID | None


class ReceivableListResponse(BaseModel):
    receivables: list[ReceivableView]
    limit: int
    offset: int


class StatementEntryView(BaseModel):
    id: UUID
    booking_id: UUID
    booking_payment_id: UUID | None
    entry_type: str
    direction: str
    amount_cents: int
    status: str
    details: dict[str, Any] | None
    created_at: datetime


class StatementListResponse(BaseModel):
    entries: list[StatementEntryView]
    limit: int
    offset: int


class DisputeCreateRequest(BaseModel):
    booking_id: UUID
    reason: str = Field(min_length=1, max_length=500)
    evidence: str | None = Field(default=None, max_length=2000)


class DisputeView(BaseModel):
    id: UUID
    organization_id: UUID
    booking_id: UUID
    release_id: UUID | None
    amount_cents: int
    status: str
    reason: str
    evidence: str | None
    decision_reason: str | None
    decided_by: str | None
    decided_at: datetime | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class DisputeListResponse(BaseModel):
    disputes: list[DisputeView]
    limit: int
    offset: int


def _dispute_view(dispute: FinancialDispute) -> DisputeView:
    return DisputeView(
        id=dispute.id,
        organization_id=dispute.organization_id,
        booking_id=dispute.booking_id,
        release_id=dispute.release_id,
        amount_cents=dispute.amount_cents,
        status=dispute.status,
        reason=dispute.reason,
        evidence=dispute.evidence,
        decision_reason=dispute.decision_reason,
        decided_by=dispute.decided_by,
        decided_at=dispute.decided_at,
        created_by=dispute.created_by,
        created_at=dispute.created_at,
        updated_at=dispute.updated_at,
    )


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


def _require_org_capability(
    session: Session,
    user_id: UUID,
    organization_id: UUID,
    capability: Capability,
) -> None:
    try:
        OrganizationService(session).require_capability(user_id, organization_id, capability)
    except OrganizationNotFound as exc:
        raise _error("organization_not_found", status.HTTP_404_NOT_FOUND) from exc
    except Forbidden as exc:
        raise _error("forbidden", status.HTTP_403_FORBIDDEN) from exc


@router.post("/payments/mercadopago/webhook", include_in_schema=False)
async def mercadopago_webhook(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _error("invalid_webhook", status.HTTP_400_BAD_REQUEST) from exc
    if not isinstance(payload, dict):
        raise _error("invalid_webhook", status.HTTP_400_BAD_REQUEST)

    data = payload.get("data")
    data_id = str(data.get("id")) if isinstance(data, dict) and data.get("id") is not None else ""
    if not data_id:
        raise _error("invalid_webhook", status.HTTP_400_BAD_REQUEST)

    secret = (
        settings.mercado_pago_webhook_secret.get_secret_value()
        if settings.mercado_pago_webhook_secret is not None
        else None
    )
    if secret is None:
        if settings.environment.lower() not in LOCAL_ENVIRONMENTS:
            raise _error("webhook_secret_required", status.HTTP_401_UNAUTHORIZED)
    elif not verify_webhook_signature(
        secret=secret,
        signature_header=request.headers.get("x-signature"),
        request_id=request.headers.get("x-request-id"),
        data_id=data_id,
    ):
        raise _error("invalid_webhook_signature", status.HTTP_401_UNAUTHORIZED)

    event_type = payload.get("type") or payload.get("topic") or payload.get("action")
    event_id = str(payload.get("id") or f"{event_type}:{data_id}")
    service = PaymentService(session, adapter)
    try:
        service.handle_webhook(
            provider="mercadopago",
            event_id=event_id,
            event_type=str(event_type) if event_type is not None else None,
            data_id=data_id,
            payload=payload,
        )
        session.commit()
    except PspError as exc:
        session.rollback()
        raise _error("psp_unavailable", status.HTTP_503_SERVICE_UNAVAILABLE) from exc
    except (PaymentError, Exception) as exc:  # noqa: BLE001
        session.rollback()
        raise _error("webhook_processing_failed", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc
    return {"status": "ok"}


@router.post(
    "/bookings/{booking_id}/payments/{payment_id}/sync",
    response_model=PaymentSyncResponse,
)
def sync_payment(
    booking_id: UUID,
    payment_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
) -> PaymentSyncResponse:
    service = PaymentService(session, adapter)
    try:
        bundle = service.sync_payment(current.user_id, booking_id, payment_id)
        session.commit()
    except PaymentNotFound as exc:
        session.rollback()
        raise _error("payment_not_found", status.HTTP_404_NOT_FOUND) from exc
    except PspError as exc:
        session.rollback()
        raise _error("psp_unavailable", status.HTTP_503_SERVICE_UNAVAILABLE) from exc
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _error("payment_sync_failed", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc
    payment = next(item for item in bundle.payments if item.id == payment_id)
    return PaymentSyncResponse(
        payment_id=payment.id,
        status=payment.status,
        provider_status=payment.provider_status,
    )


@router.post(
    "/organizations/{organization_id}/bookings/{booking_id}/payments/open",
    response_model=OpenChargesResponse,
)
def open_charges(
    organization_id: UUID,
    booking_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
) -> OpenChargesResponse:
    organizations = OrganizationService(session)
    organizations.require_capability(current.user_id, organization_id, Capability.BOOKINGS_MANAGE)
    booking = BookingService(session).get(current.user_id, booking_id)
    if booking.booking.organization_id != organization_id:
        raise _error("booking_not_found", status.HTTP_404_NOT_FOUND)
    service = PaymentService(session, adapter)
    try:
        bundle = service.open_charges(booking_id)
        session.commit()
    except PspError as exc:
        session.rollback()
        raise _error("psp_unavailable", status.HTTP_503_SERVICE_UNAVAILABLE) from exc
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise _error("payment_open_failed", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc
    return OpenChargesResponse(payments=len(bundle.payments))


@router.post(
    "/organizations/{organization_id}/bookings/{booking_id}/refund",
    response_model=RefundResponse,
)
def refund_booking(
    organization_id: UUID,
    booking_id: UUID,
    payload: RefundRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
) -> RefundResponse:
    _require_org_capability(session, current.user_id, organization_id, Capability.BOOKINGS_MANAGE)
    try:
        booking = BookingService(session).get(current.user_id, booking_id)
    except Exception as exc:  # noqa: BLE001
        raise _error("booking_not_found", status.HTTP_404_NOT_FOUND) from exc
    if booking.booking.organization_id != organization_id:
        raise _error("booking_not_found", status.HTTP_404_NOT_FOUND)
    service = PaymentService(session, adapter)
    try:
        refunded = service.refund_booking(
            booking_id,
            reason=payload.reason,
            requested_by=current.user_id,
        )
        session.commit()
    except PspError as exc:
        session.rollback()
        raise _error("psp_unavailable", status.HTTP_503_SERVICE_UNAVAILABLE) from exc
    except PaymentError as exc:
        session.rollback()
        raise _error("refund_failed", status.HTTP_409_CONFLICT) from exc
    return RefundResponse(refunded=refunded)


@router.get(
    "/organizations/{organization_id}/financial/summary",
    response_model=OrganizationSummaryResponse,
)
def organization_summary(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
) -> OrganizationSummaryResponse:
    _require_org_capability(session, current.user_id, organization_id, Capability.BOOKINGS_READ)
    summary = PaymentService(session, adapter).organization_summary(organization_id)
    return OrganizationSummaryResponse(**summary)


@router.get(
    "/organizations/{organization_id}/bookings/{booking_id}/financial",
    response_model=BookingFinancialResponse,
)
def booking_financial(
    organization_id: UUID,
    booking_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    adapter: Annotated[PspAdapter, Depends(get_psp_adapter)],
) -> BookingFinancialResponse:
    _require_org_capability(session, current.user_id, organization_id, Capability.BOOKINGS_READ)
    try:
        booking = BookingService(session).get(current.user_id, booking_id)
    except Exception as exc:  # noqa: BLE001
        raise _error("booking_not_found", status.HTTP_404_NOT_FOUND) from exc
    if booking.booking.organization_id != organization_id:
        raise _error("booking_not_found", status.HTTP_404_NOT_FOUND)
    service = PaymentService(session, adapter)
    ledger = service.booking_ledger(booking_id)
    refunds = session.scalars(
        select(PaymentRefund)
        .where(PaymentRefund.booking_id == booking_id)
        .order_by(PaymentRefund.created_at)
    ).all()
    return BookingFinancialResponse(
        booking_id=booking_id,
        ledger=[
            LedgerView(
                id=item.id,
                booking_payment_id=item.booking_payment_id,
                entry_type=item.entry_type,
                direction=item.direction,
                amount_cents=item.amount_cents,
                status=item.status,
                details=item.details,
                created_at=item.created_at,
            )
            for item in ledger
        ],
        refunds=[
            RefundView(
                id=item.id,
                booking_payment_id=item.booking_payment_id,
                amount_cents=item.amount_cents,
                status=item.status,
                reason=item.reason,
                provider_reference=item.provider_reference,
                processed_at=item.processed_at,
                created_at=item.created_at,
            )
            for item in refunds
        ],
    )


@router.get(
    "/organizations/{organization_id}/financial/receivables",
    response_model=ReceivableListResponse,
)
def list_receivables(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    status_filter: Annotated[
        str | None,
        Query(alias="status", pattern="^(PENDING|RELEASED|FAILED|REVERSED)$"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReceivableListResponse:
    _require_org_capability(session, current.user_id, organization_id, Capability.FINANCIAL_READ)
    rows = FinancialService(session).list_receivables(
        organization_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ReceivableListResponse(
        receivables=[
            ReceivableView(
                booking_id=booking.id,
                release_id=release.id,
                amount_cents=release.amount_cents,
                status=release.status,
                eligible_at=release.eligible_at,
                released_at=release.released_at,
                starts_at=booking.starts_at,
                ends_at=booking.ends_at,
                has_open_dispute=dispute_id is not None,
                dispute_id=dispute_id,
            )
            for release, booking, dispute_id in rows
        ],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/organizations/{organization_id}/financial/statement",
    response_model=StatementListResponse,
)
def financial_statement(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StatementListResponse:
    _require_org_capability(session, current.user_id, organization_id, Capability.FINANCIAL_READ)
    entries = FinancialService(session).statement(organization_id, limit=limit, offset=offset)
    return StatementListResponse(
        entries=[
            StatementEntryView(
                id=item.id,
                booking_id=item.booking_id,
                booking_payment_id=item.booking_payment_id,
                entry_type=item.entry_type,
                direction=item.direction,
                amount_cents=item.amount_cents,
                status=item.status,
                details=item.details,
                created_at=item.created_at,
            )
            for item in entries
        ],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/organizations/{organization_id}/financial/disputes",
    response_model=DisputeListResponse,
)
def list_disputes(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    status_filter: Annotated[
        str | None,
        Query(alias="status", pattern="^(OPEN|ACCEPTED|REJECTED|WITHDRAWN)$"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DisputeListResponse:
    _require_org_capability(session, current.user_id, organization_id, Capability.FINANCIAL_READ)
    disputes = FinancialService(session).list_disputes(
        organization_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return DisputeListResponse(
        disputes=[_dispute_view(item) for item in disputes],
        limit=limit,
        offset=offset,
    )


@router.post(
    "/organizations/{organization_id}/financial/disputes",
    response_model=DisputeView,
    status_code=status.HTTP_201_CREATED,
)
def open_dispute(
    organization_id: UUID,
    payload: DisputeCreateRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> DisputeView:
    _require_org_capability(session, current.user_id, organization_id, Capability.FINANCIAL_MANAGE)
    try:
        dispute = FinancialService(session).open_dispute(
            actor_user_id=current.user_id,
            organization_id=organization_id,
            booking_id=payload.booking_id,
            reason=payload.reason,
            evidence=payload.evidence,
        )
        session.commit()
    except BookingNotFound as exc:
        session.rollback()
        raise _error("booking_not_found", status.HTTP_404_NOT_FOUND) from exc
    except ReleaseNotFound as exc:
        session.rollback()
        raise _error("release_not_found", status.HTTP_404_NOT_FOUND) from exc
    except DisputeConflict as exc:
        session.rollback()
        raise _error("dispute_already_open", status.HTTP_409_CONFLICT) from exc
    return _dispute_view(dispute)


@router.get(
    "/organizations/{organization_id}/financial/disputes/{dispute_id}",
    response_model=DisputeView,
)
def get_dispute(
    organization_id: UUID,
    dispute_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
) -> DisputeView:
    _require_org_capability(session, current.user_id, organization_id, Capability.FINANCIAL_READ)
    try:
        dispute = FinancialService(session).get_dispute(organization_id, dispute_id)
    except DisputeNotFound as exc:
        raise _error("dispute_not_found", status.HTTP_404_NOT_FOUND) from exc
    return _dispute_view(dispute)
