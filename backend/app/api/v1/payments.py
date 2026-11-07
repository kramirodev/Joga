"""Endpoints de webhook, sincronização e abertura de cobranças Pix (Fase 14A)."""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_session
from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.bookings.service import BookingService
from app.modules.identity.sessions import AuthenticatedSession
from app.modules.organizations.permissions import Capability
from app.modules.organizations.service import OrganizationService
from app.modules.payments.adapter import PspAdapter, PspError, verify_webhook_signature
from app.modules.payments.dependency import get_psp_adapter
from app.modules.payments.service import PaymentError, PaymentNotFound, PaymentService

router = APIRouter(tags=["payments"])
LOCAL_ENVIRONMENTS = frozenset({"local", "test", "development", "ci"})


class PaymentSyncResponse(BaseModel):
    payment_id: UUID
    status: str
    provider_status: str | None


class OpenChargesResponse(BaseModel):
    payments: int


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


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
