"""Casos de uso de pagamentos Pix, webhook e ledger (Fase 14A)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import (
    Booking,
    BookingParticipant,
    BookingPayment,
    BookingRefundExclusion,
    BookingSubstitution,
)
from app.modules.bookings.service import BookingBundle, BookingNotFound, BookingService
from app.modules.identity.clock import utcnow
from app.modules.identity.models import User
from app.modules.matchmaking.models import LobbySubstitute
from app.modules.payments.adapter import (
    PixChargeRequest,
    ProviderStatus,
    PspAdapter,
)
from app.modules.payments.models import (
    LedgerEntry,
    PaymentEvent,
    PaymentRefund,
    PspWebhookEvent,
)
from app.modules.payments.purchase import (
    PayerEmailRequired,
)
from app.modules.payments.purchase import (
    apply_status as apply_purchase_status,
)
from app.modules.payments.purchase import (
    find_by_provider as find_purchase_payment,
)
from app.modules.payments.status import map_provider_status


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "PaymentError",
    "PaymentMismatch",
    "PaymentNotFound",
    "PaymentService",
    "WebhookPayloadMismatch",
    "WebhookRejected",
    "map_provider_status",
]


class PaymentError(Exception):
    """Erro base de pagamentos."""


class PaymentNotFound(PaymentError):
    """Cobrança inexistente."""


class PaymentMismatch(PaymentError):
    """Valor ou referência divergente do registro interno."""


class WebhookRejected(PaymentError):
    """Webhook inválido ou não autenticado."""


class WebhookPayloadMismatch(WebhookRejected):
    """Mesmo ID de evento com corpo diferente; replay não é confiável."""


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
        emails: dict[uuid.UUID, str | None] = {}
        for payment in payments:
            if payment.provider_order_id is not None:
                continue
            participant = participants.get(payment.participant_id)
            if participant is None:
                continue
            payer_email: str | None = None
            if self.adapter.provider_name == "mercadopago":
                if participant.user_id not in emails:
                    emails[participant.user_id] = self.session.scalar(
                        select(User.email).where(User.id == participant.user_id)
                    )
                payer_email = emails[participant.user_id]
                if not payer_email:
                    raise PayerEmailRequired
            due = booking.payment_due_at
            if due is not None and due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            minutes = max(1, int((due - utcnow()).total_seconds() // 60)) if due else 30
            result = self.adapter.create_pix_charge(
                PixChargeRequest(
                    external_reference=str(payment.id),
                    amount_cents=payment.amount_cents,
                    description=f"JOGA reserva {booking.id} vaga {participant.seat}",
                    payer_email=payer_email or f"user-{participant.user_id}@simulator.invalid",
                    expiration_minutes=minutes,
                    metadata={
                        "booking_id": str(booking.id),
                        "participant_id": str(participant.id),
                        "seat": participant.seat,
                    },
                )
            )
            payment.payer_email = payer_email
            payment.provider = result.provider
            payment.provider_order_id = result.provider_order_id
            payment.provider_payment_id = result.provider_payment_id
            payment.provider_status = result.status
            payment.provider_status_detail = result.status_detail
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

    def record_webhook(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str | None,
        payload: dict[str, Any],
    ) -> tuple[PspWebhookEvent, bool]:
        """Persiste o evento bruto antes de processar; idempotente por evento."""

        existing = self.session.scalar(
            select(PspWebhookEvent).where(
                PspWebhookEvent.provider == provider,
                PspWebhookEvent.provider_event_id == event_id,
            )
        )
        digest = _payload_hash(payload)
        if existing is not None:
            if existing.payload_hash and existing.payload_hash != digest:
                raise WebhookPayloadMismatch(f"evento {event_id} repetido com payload diferente")
            if not existing.payload_hash:
                existing.payload_hash = digest
                self.session.flush()
            return existing, False
        webhook = PspWebhookEvent(
            provider=provider,
            provider_event_id=event_id,
            event_type=event_type,
            payload=payload,
            payload_hash=digest,
        )
        self.session.add(webhook)
        self.session.flush()
        return webhook, True

    def process_webhook(
        self,
        webhook: PspWebhookEvent,
        *,
        data_id: str | None = None,
    ) -> None:
        """Consulta o PSP e aplica o status; incrementa a tentativa."""

        payload = webhook.payload or {}
        if data_id is None:
            data = payload.get("data")
            data_id = str(data.get("id")) if isinstance(data, dict) and data.get("id") else ""
        if not data_id:
            webhook.attempts = (webhook.attempts or 0) + 1
            raise PaymentError("webhook sem data.id")
        event_type = webhook.event_type
        webhook.attempts = (webhook.attempts or 0) + 1
        if event_type and "payment" in event_type.lower():
            status = self.adapter.get_payment(data_id)
        else:
            status = self.adapter.get_order(data_id)

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
            purchase_payment = find_purchase_payment(
                self.session,
                provider_order_id=status.provider_order_id,
                provider_payment_id=status.provider_payment_id,
            )
            if purchase_payment is not None:
                apply_purchase_status(self.session, purchase_payment, status)
            webhook.processed_at = utcnow()
            webhook.last_error = None
            webhook.next_attempt_at = None
            self.session.flush()
            return
        booking = self.session.get(Booking, payment.booking_id)
        if booking is None:
            raise PaymentNotFound
        self._apply_status(booking, payment, status)
        webhook.processed_at = utcnow()
        webhook.last_error = None
        webhook.next_attempt_at = None
        self.session.flush()

    def fail_webhook(
        self,
        webhook: PspWebhookEvent,
        error: str,
        *,
        now: datetime | None = None,
    ) -> None:
        """Guarda a falha e agenda nova tentativa com backoff exponencial."""

        moment = now or utcnow()
        webhook.attempts = (webhook.attempts or 0) + 1
        webhook.last_error = error[:200]
        exponent = min(webhook.attempts or 1, 6)
        webhook.next_attempt_at = moment + timedelta(minutes=min(60, 2**exponent))
        self.session.flush()

    def handle_webhook(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str | None,
        data_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Atalho legado: persiste e processa na mesma transação."""

        webhook, _created = self.record_webhook(
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
        self.process_webhook(webhook, data_id=data_id)

    def simulate_payment(self, actor_user_id: uuid.UUID, booking_id: uuid.UUID) -> BookingBundle:
        """Registra pagamento simulado e mantém o ledger consistente."""

        bundle = self.bookings.simulate_payment(actor_user_id, booking_id)
        participant = self.session.scalar(
            select(BookingParticipant).where(
                BookingParticipant.booking_id == booking_id,
                BookingParticipant.user_id == actor_user_id,
                BookingParticipant.active.is_(True),
            )
        )
        if participant is None:
            return bundle
        payment = self.session.scalar(
            select(BookingPayment).where(
                BookingPayment.booking_id == booking_id,
                BookingPayment.participant_id == participant.id,
                BookingPayment.version == bundle.booking.payment_version,
            )
        )
        if payment is None or payment.status != "PAID":
            return bundle
        self._ledger(
            payment,
            "PAYMENT_CONFIRMED",
            "CREDIT",
            payment.amount_cents,
            {"provider": "simulator"},
        )
        self._event(
            payment,
            "PAYMENT_SIMULATED",
            f"simulator:{payment.id}:PAID",
            {"provider": "simulator"},
        )
        self._finalize_substitution(payment)
        self.session.flush()
        return bundle

    def refund_payment(
        self,
        booking_id: uuid.UUID,
        payment_id: uuid.UUID,
        *,
        reason: str,
        requested_by: uuid.UUID | None = None,
    ) -> PaymentRefund:
        """Estorna uma cobrança paga; a operação é idempotente por pagamento."""

        booking = self.session.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        if booking is None:
            raise BookingNotFound
        payment = self._payment(booking.id, payment_id)
        existing = self.session.scalar(
            select(PaymentRefund).where(
                PaymentRefund.booking_payment_id == payment.id,
                PaymentRefund.refund_type == "FULL",
            )
        )
        if existing is not None and existing.status == "PROCESSED":
            return existing
        if existing is not None and existing.status == "PENDING" and existing.provider_reference:
            # O PSP já aceitou o estorno; não dispara um segundo refund.
            return existing
        if payment.status == "REFUNDED":
            if existing is not None:
                return existing
            raise PaymentError("payment already refunded without refund record")
        if payment.status != "PAID":
            raise PaymentError("only paid charges can be refunded")

        if existing is None:
            existing = PaymentRefund(
                booking_id=booking.id,
                booking_payment_id=payment.id,
                amount_cents=payment.amount_cents,
                refund_type="FULL",
                idempotency_key=f"refund:{payment.id}:full",
                status="PENDING",
                reason=reason,
                requested_by=requested_by,
            )
            self.session.add(existing)
            self.session.flush()

        result = self.adapter.refund(
            provider_order_id=payment.provider_order_id or "",
            provider_payment_id=payment.provider_payment_id,
            amount_cents=payment.amount_cents,
        )
        normalized = result.status.lower()
        if normalized in {"processed", "approved", "refunded", "succeeded"}:
            refund_status = "PROCESSED"
        elif normalized in {"processing", "in_process", "pending", "queued"}:
            refund_status = "PENDING"
        else:
            refund_status = "FAILED"
        existing.status = refund_status
        existing.provider_reference = result.refund_id
        existing.processed_at = utcnow() if refund_status == "PROCESSED" else None
        if refund_status == "PROCESSED":
            self.bookings.register_payment_result(
                booking.id,
                payment.id,
                status="REFUNDED",
                provider_reference=result.refund_id,
            )
            from app.modules.ledger.flow import post_payment_refund

            participant = self.session.get(BookingParticipant, payment.participant_id)
            if participant is not None:
                post_payment_refund(self.session, payment, participant)
            self._ledger(
                payment,
                "PAYMENT_REFUNDED",
                "DEBIT",
                payment.amount_cents,
                {"provider": result.provider, "refund_id": result.refund_id},
            )
            self._event(
                payment,
                "REFUND_PROCESSED",
                f"{result.provider}:{result.refund_id}:REFUNDED",
                {"reason": reason, "refund_id": result.refund_id},
            )
        self.session.flush()
        return existing

    def refund_booking(
        self,
        booking_id: uuid.UUID,
        *,
        reason: str,
        requested_by: uuid.UUID | None = None,
        exclude_user_ids: set[uuid.UUID] | None = None,
    ) -> int:
        """Estorna todas as cobranças pagas de uma reserva.

        ``exclude_user_ids`` implementa a ADR 0039: quem desistiu após a
        confirmação não recebe reembolso quando o lobby é cancelado.
        """

        statement = select(BookingPayment).where(
            BookingPayment.booking_id == booking_id,
            BookingPayment.status == "PAID",
        )
        if exclude_user_ids:
            statement = statement.join(
                BookingParticipant,
                BookingParticipant.id == BookingPayment.participant_id,
            ).where(BookingParticipant.user_id.not_in(exclude_user_ids))
        payments = list(self.session.scalars(statement).all())
        for payment in payments:
            self.refund_payment(
                booking_id,
                payment.id,
                reason=reason,
                requested_by=requested_by,
            )
        from app.modules.payments.financial import FinancialService

        FinancialService(self.session).reverse_for_refund(booking_id, reason=reason)
        return len(payments)

    def refund_participant(
        self,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        reason: str,
        requested_by: uuid.UUID | None = None,
    ) -> int:
        """Estorna cobranças pagas de um participante substituído."""

        participant_ids = list(
            self.session.scalars(
                select(BookingParticipant.id).where(
                    BookingParticipant.booking_id == booking_id,
                    BookingParticipant.user_id == user_id,
                )
            ).all()
        )
        if not participant_ids:
            return 0
        payments = list(
            self.session.scalars(
                select(BookingPayment).where(
                    BookingPayment.booking_id == booking_id,
                    BookingPayment.participant_id.in_(participant_ids),
                    BookingPayment.status == "PAID",
                )
            ).all()
        )
        for payment in payments:
            self.refund_payment(
                booking_id,
                payment.id,
                reason=reason,
                requested_by=requested_by,
            )
        return len(payments)

    def refund_cancelled_bookings(self) -> int:
        """Estorna reservas terminais que ainda tenham cobrança paga."""

        booking_ids = list(
            self.session.scalars(
                select(Booking.id)
                .join(BookingPayment, BookingPayment.booking_id == Booking.id)
                .where(
                    Booking.status.in_(
                        {
                            "CANCELLED",
                            "EXPIRED",
                            "CANCELLED_BY_VENUE",
                            "CANCELLED_BY_PLAYER",
                            "DECLINED",
                        }
                    ),
                    BookingPayment.status == "PAID",
                )
                .distinct()
            ).all()
        )
        count = 0
        for booking_id in booking_ids:
            excluded = set(
                self.session.scalars(
                    select(BookingRefundExclusion.user_id).where(
                        BookingRefundExclusion.booking_id == booking_id
                    )
                ).all()
            )
            count += self.refund_booking(
                booking_id,
                reason="booking_cancelled",
                exclude_user_ids=excluded,
            )
        return count

    def booking_ledger(self, booking_id: uuid.UUID) -> list[LedgerEntry]:
        return list(
            self.session.scalars(
                select(LedgerEntry)
                .where(LedgerEntry.booking_id == booking_id)
                .order_by(LedgerEntry.created_at, LedgerEntry.id)
            ).all()
        )

    def organization_summary(self, organization_id: uuid.UUID) -> dict[str, int]:
        """Totais financeiros internos da organização, sem conciliação externa."""

        from app.modules.payments.financial import FinancialService

        base = (
            select(BookingPayment)
            .join(Booking, Booking.id == BookingPayment.booking_id)
            .where(Booking.organization_id == organization_id)
        )
        payments = list(self.session.scalars(base).all())
        totals = FinancialService(self.session).release_totals(organization_id)
        return {
            "charged_cents": sum(item.amount_cents for item in payments),
            "paid_cents": sum(item.amount_cents for item in payments if item.status == "PAID"),
            "refunded_cents": sum(
                item.amount_cents for item in payments if item.status == "REFUNDED"
            ),
            "pending_cents": sum(
                item.amount_cents for item in payments if item.status == "PENDING"
            ),
            "released_cents": totals["released_cents"],
            "pending_release_cents": totals["pending_release_cents"],
            "disputed_cents": totals["disputed_cents"],
            "payments": len(payments),
            "refunds": self.session.scalar(
                select(func.count())
                .select_from(PaymentRefund)
                .join(Booking, Booking.id == PaymentRefund.booking_id)
                .where(Booking.organization_id == organization_id)
            )
            or 0,
        }

    def record_venue_release(self, booking_id: uuid.UUID) -> None:
        """Compatibilidade 14C: agora apenas agenda a liberação da Fase 15."""

        from app.modules.payments.financial import FinancialService

        FinancialService(self.session).ensure_release(booking_id)

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
        payment.provider_status_detail = status.status_detail
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
        if internal == "PAID":
            self._finalize_substitution(payment)

    def _finalize_substitution(self, payment: BookingPayment) -> None:
        """Fecha a vaga quando o substituto paga e devolve a cobrança do saiu."""

        if payment.status != "PAID":
            return
        substitution = self.session.scalar(
            select(BookingSubstitution)
            .where(
                BookingSubstitution.substitute_payment_id == payment.id,
                BookingSubstitution.status == "AWAITING_PAYMENT",
            )
            .with_for_update()
        )
        if substitution is None:
            return
        substitution.status = "FILLED"
        substitution.resolved_at = utcnow()
        booking = self.session.get(Booking, payment.booking_id)
        if booking is not None and substitution.filled_by_user_id is not None:
            queue_entry = self.session.scalar(
                select(LobbySubstitute).where(
                    LobbySubstitute.lobby_id == booking.lobby_id,
                    LobbySubstitute.user_id == substitution.filled_by_user_id,
                )
            )
            if queue_entry is not None:
                queue_entry.status = "PLAYED"
                queue_entry.played_at = substitution.resolved_at
        self.refund_participant(
            payment.booking_id,
            substitution.outgoing_user_id,
            reason="participant_replaced",
            requested_by=None,
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
