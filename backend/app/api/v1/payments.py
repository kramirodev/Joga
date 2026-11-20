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
from app.core.environments import is_demo, is_local
from app.core.text import FreeText, OptionalMultilineText
from app.infrastructure.database.dependency import get_session
from app.modules.bookings.models import Booking
from app.modules.bookings.service import BookingNotFound, BookingService
from app.modules.fiscal.models import FiscalDocument
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
    DisputeDeadlineExpired,
    DisputeNotFound,
    DisputeStateError,
    FinancialService,
    OperatorNotAuthorized,
    ReleaseNotContestable,
    ReleaseNotFound,
    dispute_deadline,
)
from app.modules.payments.models import (
    FinancialDispute,
    PaymentRefund,
    PspWebhookEvent,
    VenueRelease,
)
from app.modules.payments.purchase import PayerEmailRequired
from app.modules.payments.service import (
    PaymentError,
    PaymentNotFound,
    PaymentService,
    WebhookPayloadMismatch,
)

router = APIRouter(tags=["payments"])


class PaymentSyncResponse(BaseModel):
    payment_id: UUID
    status: str
    provider_status: str | None


class OpenChargesResponse(BaseModel):
    payments: int


class RefundRequest(BaseModel):
    reason: FreeText = Field(min_length=1, max_length=200)


class RefundResponse(BaseModel):
    refunded: int


class LedgerView(BaseModel):
    id: UUID
    booking_payment_id: UUID | None
    release_id: UUID | None
    entry_type: str
    direction: str
    amount_cents: int
    venue_price_cents: int | None
    fee_cents: int | None
    total_cents: int | None
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


class OrganizationSummaryResponse(BaseModel):
    charged_cents: int
    paid_cents: int
    refunded_cents: int
    pending_cents: int
    released_cents: int
    pending_release_cents: int
    reversed_cents: int
    failed_cents: int
    disputed_cents: int
    # Valor do fornecedor e comissão do JOGA em campos distintos: o repasse
    # nunca é apresentado como receita da intermediação.
    venue_price_cents: int
    joga_fee_cents: int
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
    venue_price_cents: int
    fee_cents: int
    total_cents: int
    # Comprovante simulado: ``simulated:<release_id>``. Não há transferência real.
    receipt_reference: str | None
    dispute_deadline: datetime
    reason: str | None


class ReceivableListResponse(BaseModel):
    receivables: list[ReceivableView]
    total: int
    limit: int
    offset: int


class StatementEntryView(BaseModel):
    id: UUID
    booking_id: UUID
    booking_payment_id: UUID | None
    release_id: UUID | None
    entry_type: str
    direction: str
    amount_cents: int
    venue_price_cents: int | None
    fee_cents: int | None
    total_cents: int | None
    status: str
    details: dict[str, Any] | None
    created_at: datetime


class StatementListResponse(BaseModel):
    entries: list[StatementEntryView]
    total: int
    limit: int
    offset: int


class DisputeCreateRequest(BaseModel):
    booking_id: UUID
    reason: FreeText = Field(min_length=1, max_length=500)
    evidence: OptionalMultilineText = Field(default=None, max_length=2000)


class DisputeView(BaseModel):
    id: UUID
    organization_id: UUID
    booking_id: UUID
    release_id: UUID | None
    amount_cents: int
    status: str
    deadline_at: datetime
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
    total: int
    limit: int
    offset: int


class DisputeDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(ACCEPTED|REJECTED)$")
    reason: FreeText = Field(min_length=1, max_length=500)


class BookingPricingView(BaseModel):
    venue_price_cents: int
    fee_cents: int
    fee_percent_applied: int
    total_cents: int
    pricing_version: str


class FiscalDocumentView(BaseModel):
    id: UUID
    status: str
    amount_cents: int
    number: str | None
    provider_ref: str | None
    issued_at: datetime | None


class CommissionRowView(BaseModel):
    booking_id: UUID
    starts_at: datetime
    confirmed_at: datetime
    venue_price_cents: int
    fee_cents: int
    total_cents: int
    release_status: str | None


class CommissionTotalsView(BaseModel):
    bookings: int
    venue_price_cents: int
    joga_fee_cents: int
    total_cents: int


class CommissionResponse(BaseModel):
    rows: list[CommissionRowView]
    totals: CommissionTotalsView
    limit: int
    offset: int


class BookingFinancialResponse(BaseModel):
    booking_id: UUID
    pricing: BookingPricingView
    release: ReceivableView | None
    dispute: DisputeView | None
    fiscal_document: FiscalDocumentView | None
    ledger: list[LedgerView]
    refunds: list[RefundView]


def _dispute_view(dispute: FinancialDispute) -> DisputeView:
    return DisputeView(
        id=dispute.id,
        organization_id=dispute.organization_id,
        booking_id=dispute.booking_id,
        release_id=dispute.release_id,
        amount_cents=dispute.amount_cents,
        status=dispute.status,
        deadline_at=dispute.deadline_at,
        reason=dispute.reason,
        evidence=dispute.evidence,
        decision_reason=dispute.decision_reason,
        decided_by=dispute.decided_by,
        decided_at=dispute.decided_at,
        created_by=dispute.created_by,
        created_at=dispute.created_at,
        updated_at=dispute.updated_at,
    )


def _receivable_view(
    release: VenueRelease,
    booking: Booking,
    dispute_id: UUID | None,
) -> ReceivableView:
    return ReceivableView(
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
        venue_price_cents=booking.venue_price_cents,
        fee_cents=booking.fee_cents,
        total_cents=booking.total_cents,
        receipt_reference=release.provider_reference,
        dispute_deadline=dispute_deadline(release),
        reason=release.reason,
    )


def _pricing_view(booking: Booking) -> BookingPricingView:
    return BookingPricingView(
        venue_price_cents=booking.venue_price_cents,
        fee_cents=booking.fee_cents,
        fee_percent_applied=booking.fee_percent_applied,
        total_cents=booking.total_cents,
        pricing_version=booking.pricing_version,
    )


def _fiscal_view(document: FiscalDocument) -> FiscalDocumentView:
    return FiscalDocumentView(
        id=document.id,
        status=document.status,
        amount_cents=document.amount_cents,
        number=document.number,
        provider_ref=document.provider_ref,
        issued_at=document.issued_at,
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
    if is_demo(settings.environment):
        raise _error("webhook_disabled", status.HTTP_404_NOT_FOUND)
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
        if not is_local(settings.environment):
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
        webhook, _created = service.record_webhook(
            provider="mercadopago",
            event_id=event_id,
            event_type=str(event_type) if event_type is not None else None,
            payload=payload,
        )
    except WebhookPayloadMismatch as exc:
        session.rollback()
        raise _error("webhook_payload_mismatch", status.HTTP_409_CONFLICT) from exc
    # O evento bruto fica persistido mesmo se o processamento falhar.
    session.commit()
    if webhook.processed_at is not None:
        return {"status": "ok"}
    try:
        service.process_webhook(webhook)
        session.commit()
    except PspError as exc:
        session.rollback()
        failed = session.get(PspWebhookEvent, webhook.id)
        if failed is not None:
            service.fail_webhook(failed, type(exc).__name__)
            session.commit()
        raise _error("psp_unavailable", status.HTTP_503_SERVICE_UNAVAILABLE) from exc
    except (PaymentError, Exception) as exc:  # noqa: BLE001
        session.rollback()
        failed = session.get(PspWebhookEvent, webhook.id)
        if failed is not None:
            service.fail_webhook(failed, type(exc).__name__)
            session.commit()
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
    except PayerEmailRequired as exc:
        session.rollback()
        raise _error("payer_email_required", status.HTTP_422_UNPROCESSABLE_CONTENT) from exc
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
    booking_row = booking.booking
    release = session.scalar(select(VenueRelease).where(VenueRelease.booking_id == booking_id))
    dispute = session.scalar(
        select(FinancialDispute)
        .where(FinancialDispute.booking_id == booking_id)
        .order_by(FinancialDispute.created_at.desc(), FinancialDispute.id.desc())
        .limit(1)
    )
    document = session.scalar(select(FiscalDocument).where(FiscalDocument.booking_id == booking_id))
    open_dispute_id = dispute.id if dispute is not None and dispute.status == "OPEN" else None
    return BookingFinancialResponse(
        booking_id=booking_id,
        pricing=_pricing_view(booking_row),
        release=None
        if release is None
        else _receivable_view(release, booking_row, open_dispute_id),
        dispute=None if dispute is None else _dispute_view(dispute),
        fiscal_document=None if document is None else _fiscal_view(document),
        ledger=[
            LedgerView(
                id=item.id,
                booking_payment_id=item.booking_payment_id,
                release_id=item.release_id,
                entry_type=item.entry_type,
                direction=item.direction,
                amount_cents=item.amount_cents,
                venue_price_cents=item.venue_price_cents,
                fee_cents=item.fee_cents,
                total_cents=item.total_cents,
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
    financial = FinancialService(session)
    rows = financial.list_receivables(
        organization_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ReceivableListResponse(
        receivables=[
            _receivable_view(release, booking, dispute_id) for release, booking, dispute_id in rows
        ],
        total=financial.count_receivables(organization_id, status=status_filter),
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
    financial = FinancialService(session)
    entries = financial.statement(organization_id, limit=limit, offset=offset)
    return StatementListResponse(
        entries=[
            StatementEntryView(
                id=item.id,
                booking_id=item.booking_id,
                booking_payment_id=item.booking_payment_id,
                release_id=item.release_id,
                entry_type=item.entry_type,
                direction=item.direction,
                amount_cents=item.amount_cents,
                venue_price_cents=item.venue_price_cents,
                fee_cents=item.fee_cents,
                total_cents=item.total_cents,
                status=item.status,
                details=item.details,
                created_at=item.created_at,
            )
            for item in entries
        ],
        total=financial.count_statement(organization_id),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/organizations/{organization_id}/financial/commission",
    response_model=CommissionResponse,
)
def financial_commission(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    date_from: Annotated[datetime | None, Query(alias="from")] = None,
    date_to: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CommissionResponse:
    """Relatório por reserva: valor do fornecedor e comissão do JOGA separados."""

    _require_org_capability(session, current.user_id, organization_id, Capability.FINANCIAL_READ)
    financial = FinancialService(session)
    rows = financial.commission_rows(
        organization_id,
        from_=date_from,
        to=date_to,
        limit=limit,
        offset=offset,
    )
    totals = financial.commission_totals(organization_id, from_=date_from, to=date_to)
    return CommissionResponse(
        rows=[
            CommissionRowView(
                booking_id=row.booking_id,
                starts_at=row.starts_at,
                confirmed_at=row.confirmed_at,
                venue_price_cents=row.venue_price_cents,
                fee_cents=row.fee_cents,
                total_cents=row.total_cents,
                release_status=row.release_status,
            )
            for row in rows
        ],
        totals=CommissionTotalsView(**totals),
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
    financial = FinancialService(session)
    disputes = financial.list_disputes(
        organization_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return DisputeListResponse(
        disputes=[_dispute_view(item) for item in disputes],
        total=financial.count_disputes(organization_id, status=status_filter),
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
    except ReleaseNotContestable as exc:
        session.rollback()
        raise _error("release_not_contestable", status.HTTP_409_CONFLICT) from exc
    except DisputeDeadlineExpired as exc:
        session.rollback()
        raise _error("dispute_window_expired", status.HTTP_409_CONFLICT) from exc
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


@router.post(
    "/organizations/{organization_id}/financial/disputes/{dispute_id}/decision",
    response_model=DisputeView,
)
def decide_dispute(
    organization_id: UUID,
    dispute_id: UUID,
    payload: DisputeDecisionRequest,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DisputeView:
    """Decisão auditável por operador interno do JOGA.

    Exige ``financial:manage`` **e** que o usuário esteja em
    ``JOGA_REVIEW_OPERATORS``: o próprio fornecedor não decide a sua
    contestação. Enquanto o modelo de moderação não for aprovado, a lista de
    operadores é a salvaguarda técnica.
    """

    _require_org_capability(session, current.user_id, organization_id, Capability.FINANCIAL_MANAGE)
    financial = FinancialService(session)
    try:
        financial.get_dispute(organization_id, dispute_id)
        dispute = financial.decide_dispute(
            dispute_id,
            operator=str(current.user_id),
            decision=payload.decision,
            reason=payload.reason,
            authorized_operators=settings.review_operator_ids,
            organization_id=organization_id,
        )
        session.commit()
    except DisputeNotFound as exc:
        session.rollback()
        raise _error("dispute_not_found", status.HTTP_404_NOT_FOUND) from exc
    except (DisputeStateError, OperatorNotAuthorized) as exc:
        session.rollback()
        code = (
            "operator_not_authorized"
            if isinstance(exc, OperatorNotAuthorized)
            else "dispute_not_open"
        )
        raise _error(
            code,
            status.HTTP_409_CONFLICT if code == "dispute_not_open" else status.HTTP_403_FORBIDDEN,
        ) from exc
    return _dispute_view(dispute)
