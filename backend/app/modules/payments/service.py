"""Casos de uso de pagamentos Pix, webhook e ledger (Fase 14A)."""

from __future__ import annotations

import uuid
from datetime import UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.bookings.models import Booking, BookingParticipant, BookingPayment
from app.modules.bookings.service import BookingBundle, BookingNotFound, BookingService
from app.modules.identity.clock import utcnow
from app.modules.payments.adapter import (
    PixChargeRequest,
    ProviderStatus,
    PspAdapter,
)
from app.modules.payments.models import LedgerEntry, PaymentEvent, PspWebhookEvent

INTERNAL_PAID = {"processed", "approved", "paid"}
INTERNAL_REFUNDED = {"refunded", "charged_back"}
INTERNAL_FAILED = {"failed", "canceled", "cancelled"}
INTERNAL_EXPIRED = {"expired"}


class PaymentError(Exception):
    """Erro base de pagamentos."""


class PaymentNotFound(PaymentError):
    """Cobrança inexistente."""


class PaymentMismatch(PaymentError):
    """Valor ou referência divergente do registro interno."""


class WebhookRejected(PaymentError):
    """Webhook inválido ou não autenticado."""


def map_provider_status(status: str) -> str:
    normalized = status.lower()
    if normalized in INTERNAL_PAID:
        return "PAID"
    if normalized in INTERNAL_REFUNDED:
        return "REFUNDED"
    if normalized in INTERNAL_FAILED:
        return "FAILED"
    if normalized in INTERNAL_EXPIRED:
        return "EXPIRED"
    return "PENDING"


class PaymentService:
    """Orquestra cobranças Pix, confirmação e ledger."""

    def __init__(self, session: Session, adapter: PspAdapter) -> None:
        self.session = session
        self.adapter = adapter
        self.bookings = BookingService(session)

    def open_charges(self, booking_id: uuid.UUID) -> BookingBundle:
        booking = self.session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if booking is None:
            raise BookingNotFound
        if booking.status not in {"PAYMENT_PENDING", "SUBSTITUTING"}:
            return self.bookings.get(booking.created_by or uuid.uuid4(), booking.id)

        participants = {
            item.id: item
            for item in self.session.scalars(
                select(BookingParticipant).where(
                    BookingParticipant.booking_id == booking.id,
                    BookingParticipant.active.is_(True),
                )
            ).all()
        }
        payments = self.session.scalars(
            select(BookingPayment).where(
                BookingPayment.booking_id == booking.id,
                BookingPayment.version == booking.payment_version,
            )
        ).all()
        settings = get_settings()
        for payment in payments:
            if payment.provider_order_id is not None:
                continue
            participant = participants.get(payment.participant_id)
            if participant is None:
                continue
            due = booking.payment_due_at
            if due is not None and due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            minutes = max(1, int((due - utcnow()).total_seconds() // 60)) if due else 30
            result = self.adapter.create_pix_charge(
                PixChargeRequest(
                    external_reference=str(payment.id),
                    amount_cents=payment.amount_cents,
                    description=f"JOGA reserva {booking.id} vaga {participant.seat}",
                    payer_email=settings.mercado_pago_payer_email
                    if self.adapter.provider_name == "mercadopago"
                    else f"user-{participant.user_id}@testuser.com",
                    expiration_minutes=minutes,
                    metadata={
                        "booking_id": str(booking.id),
                        "participant_id": str(participant.id),
                        "seat": participant.seat,
                    },
                )
            )
            payment.provider = result.provider
            payment.provider_order_id = result.provider_order_id
            payment.provider_payment_id = result.provider_payment_id
            payment.provider_status = result.status
            payment.qr_code = result.qr_code
            payment.qr_code_base64 = result.qr_code_base64
            payment.ticket_url = result.ticket_url
            payment.expires_at = result.expires_at
            payment.last_synced_at = utcnow()
            self._ledger(
                payment,
                "CHARGE_CREATED",
                "DEBIT",
                payment.amount_cents,
                {"provider": result.provider, "order_id": result.provider_order_id},
            )
            self.session.add(
                PaymentEvent(
                    booking_payment_id=payment.id,
                    event_type="CHARGE_CREATED",
                    details={
                        "provider": result.provider,
                        "order_id": result.provider_order_id,
                    },
                )
            )
        self.session.flush()
        actor = booking.created_by or next(iter(participants.values())).user_id
        return self.bookings.get(actor, booking.id)

    def sync_payment(
        self,
        actor_user_id: uuid.UUID,
        booking_id: uuid.UUID,
        payment_id: uuid.UUID,
    ) -> BookingBundle:
        bundle = self.bookings.get(actor_user_id, booking_id)
        payment = self._payment(bundle.booking.id, payment_id)
        if not self.bookings.viewer_is_org(actor_user_id, bundle.booking):
            participant = self.session.scalar(
                select(BookingParticipant).where(
                    BookingParticipant.booking_id == bundle.booking.id,
                    BookingParticipant.user_id == actor_user_id,
                    BookingParticipant.active.is_(True),
                )
            )
            if participant is None or participant.id != payment.participant_id:
                raise PaymentNotFound
        if payment.provider_order_id is None:
            raise PaymentNotFound
        status = self.adapter.get_order(payment.provider_order_id)
        self._apply_status(bundle.booking, payment, status)
        self.session.flush()
        return self.bookings.get(actor_user_id, booking_id)

    def handle_webhook(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str | None,
        data_id: str,
        payload: dict[str, Any],
    ) -> None:
        existing = self.session.scalar(
            select(PspWebhookEvent).where(
                PspWebhookEvent.provider == provider,
                PspWebhookEvent.provider_event_id == event_id,
            )
        )
        if existing is not None:
            return
        webhook = PspWebhookEvent(
            provider=provider,
            provider_event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
        self.session.add(webhook)
        self.session.flush()

        try:
            if event_type and "payment" in event_type.lower():
                status = self.adapter.get_payment(data_id)
            else:
                status = self.adapter.get_order(data_id)
        except Exception:
            self.session.flush()
            raise

        payment = self.session.scalar(
            select(BookingPayment).where(
                BookingPayment.provider_order_id == status.provider_order_id
            )
        )
        if payment is None and status.provider_payment_id is not None:
            payment = self.session.scalar(
                select(BookingPayment).where(
                    BookingPayment.provider_payment_id == status.provider_payment_id
                )
            )
        if payment is None:
            webhook.processed_at = utcnow()
            self.session.flush()
            return
        booking = self.session.get(Booking, payment.booking_id)
        if booking is None:
            raise PaymentNotFound
        self._apply_status(booking, payment, status)
        webhook.processed_at = utcnow()
        self.session.flush()

    def record_venue_release(self, booking_id: uuid.UUID) -> None:
        booking = self.session.get(Booking, booking_id)
        if booking is None:
            raise BookingNotFound
        if booking.status != "COMPLETED":
            return
        exists = self.session.scalar(
            select(LedgerEntry).where(
                LedgerEntry.booking_id == booking.id,
                LedgerEntry.entry_type == "VENUE_RELEASE",
            )
        )
        if exists is not None:
            return
        total = sum(
            payment.amount_cents
            for payment in self.session.scalars(
                select(BookingPayment).where(
                    BookingPayment.booking_id == booking.id,
                    BookingPayment.status == "PAID",
                )
            ).all()
        )
        if total <= 0:
            return
        self.session.add(
            LedgerEntry(
                booking_id=booking.id,
                booking_payment_id=None,
                entry_type="VENUE_RELEASE",
                direction="CREDIT",
                amount_cents=total,
                details={"simulated": True, "provider": self.adapter.provider_name},
            )
        )
        self.session.flush()

    def _payment(self, booking_id: uuid.UUID, payment_id: uuid.UUID) -> BookingPayment:
        payment = self.session.get(BookingPayment, payment_id)
        if payment is None or payment.booking_id != booking_id:
            raise PaymentNotFound
        return payment

    def _apply_status(
        self,
        booking: Booking,
        payment: BookingPayment,
        status: ProviderStatus,
    ) -> None:
        if status.amount_cents is not None and status.amount_cents != payment.amount_cents:
            raise PaymentMismatch
        if status.external_reference is not None and status.external_reference != str(payment.id):
            raise PaymentMismatch
        internal = map_provider_status(status.status)
        payment.provider_order_id = status.provider_order_id or payment.provider_order_id
        payment.provider_payment_id = status.provider_payment_id or payment.provider_payment_id
        payment.provider_status = status.status
        payment.last_synced_at = utcnow()
        if internal == "PAID" and payment.status != "PAID":
            self._ledger(
                payment,
                "PAYMENT_CONFIRMED",
                "CREDIT",
                payment.amount_cents,
                {"provider": status.provider, "provider_status": status.status},
            )
        if internal == "REFUNDED" and payment.status != "REFUNDED":
            self._ledger(
                payment,
                "PAYMENT_REFUNDED",
                "DEBIT",
                payment.amount_cents,
                {"provider": status.provider, "provider_status": status.status},
            )
        self.bookings.register_payment_result(
            booking.id,
            payment.id,
            status=internal,
            provider_reference=status.provider_order_id,
            paid_at=utcnow() if internal == "PAID" else None,
        )
        self._event(
            payment,
            f"PSP_{internal}",
            f"{status.provider}:{status.provider_order_id}:{internal}",
            {"provider_status": status.status, "status_detail": status.status_detail},
        )

    def _event(
        self,
        payment: BookingPayment,
        event_type: str,
        provider_event_id: str | None,
        details: dict[str, Any],
    ) -> None:
        if provider_event_id is not None:
            existing = self.session.scalar(
                select(PaymentEvent).where(PaymentEvent.provider_event_id == provider_event_id)
            )
            if existing is not None:
                return
        self.session.add(
            PaymentEvent(
                booking_payment_id=payment.id,
                event_type=event_type,
                provider_event_id=provider_event_id,
                details=details,
            )
        )

    def _ledger(
        self,
        payment: BookingPayment,
        entry_type: str,
        direction: str,
        amount_cents: int,
        details: dict[str, Any],
    ) -> None:
        existing = self.session.scalar(
            select(LedgerEntry).where(
                LedgerEntry.booking_payment_id == payment.id,
                LedgerEntry.entry_type == entry_type,
            )
        )
        if existing is not None:
            return
        self.session.add(
            LedgerEntry(
                booking_id=payment.booking_id,
                booking_payment_id=payment.id,
                entry_type=entry_type,
                direction=direction,
                amount_cents=amount_cents,
                details=details,
            )
        )


__all__ = [
    "PaymentError",
    "PaymentMismatch",
    "PaymentNotFound",
    "PaymentService",
    "WebhookRejected",
    "map_provider_status",
]
