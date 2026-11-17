"""Lançamentos do ledger por evento de domínio (ADR 0049 §11).

Um ponto de lançamento por evento, na mesma transação do domínio. Nenhuma
leitura pública depende deste módulo. As chaves de idempotência são
determinísticas e repetir o evento devolve a transação existente.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking, BookingParticipant, BookingPayment
from app.modules.ledger.accounts import (
    BANK,
    CHARGEBACK_RECEIVABLE_PREFIX,
    FEE_REVENUE,
    PASS_DEFERRED_REVENUE,
    PASS_REVENUE,
    PLAYER_CREDIT_PREFIX,
    PSP_CLEARING,
    PURCHASE_PREMIUM_DEFERRED,
    VENUE_PAYABLE_PREFIX,
    VENUE_RECEIVABLE_PREFIX,
)
from app.modules.ledger.models import LedgerAccount
from app.modules.ledger.service import LedgerError, LedgerPosting, LedgerService
from app.modules.passes.models import PassSubscription
from app.modules.payments.models import VenueRelease
from app.modules.tickets.models import TicketPurchase
from app.modules.tickets.service import TICKET_VALUE_CENTS


def _account(
    service: LedgerService,
    code: str,
    kind: str,
    *,
    owner_kind: str | None = None,
    owner_id: uuid.UUID | None = None,
) -> LedgerAccount:
    return service.account(code, kind, owner_kind=owner_kind, owner_id=owner_id)


def post_credit_purchase(
    session: Session,
    purchase: TicketPurchase,
    *,
    now: datetime | None = None,
) -> None:
    """Regra 1 + prêmio: caixa entra, crédito e prêmio ficam separados."""

    credit_cents = purchase.tickets * TICKET_VALUE_CENTS
    premium_cents = purchase.amount_cents - credit_cents
    if premium_cents < 0:
        raise LedgerError("purchase_below_ticket_value")

    service = LedgerService(session)
    postings = [
        LedgerPosting(_account(service, PSP_CLEARING, "asset"), "D", purchase.amount_cents),
        LedgerPosting(
            _account(
                service,
                f"{PLAYER_CREDIT_PREFIX}{purchase.user_id}",
                "liability",
                owner_kind="user",
                owner_id=purchase.user_id,
            ),
            "C",
            credit_cents,
        ),
    ]
    if premium_cents > 0:
        postings.append(
            LedgerPosting(
                _account(service, PURCHASE_PREMIUM_DEFERRED, "liability"),
                "C",
                premium_cents,
            )
        )
    service.post(
        kind="credit_purchase",
        ref_type="ticket_purchase",
        ref_id=purchase.id,
        idempotency_key=f"purchase:{purchase.id}",
        postings=postings,
        occurred_at=purchase.paid_at or now,
    )


def post_purchase_refund(
    session: Session,
    purchase: TicketPurchase,
    *,
    remaining_cents: int,
    now: datetime | None = None,
) -> None:
    """Reversão de compra/chargeback: crédito restante + prêmio + receivable."""

    credit_cents = purchase.tickets * TICKET_VALUE_CENTS
    premium_cents = max(0, purchase.amount_cents - credit_cents)
    removed = min(max(0, remaining_cents), credit_cents)
    receivable = credit_cents - removed

    service = LedgerService(session)
    postings: list[LedgerPosting] = []
    if removed > 0:
        postings.append(
            LedgerPosting(
                _account(
                    service,
                    f"{PLAYER_CREDIT_PREFIX}{purchase.user_id}",
                    "liability",
                    owner_kind="user",
                    owner_id=purchase.user_id,
                ),
                "D",
                removed,
            )
        )
    if receivable > 0:
        postings.append(
            LedgerPosting(
                _account(
                    service,
                    f"{CHARGEBACK_RECEIVABLE_PREFIX}{purchase.user_id}",
                    "asset",
                    owner_kind="user",
                    owner_id=purchase.user_id,
                ),
                "D",
                receivable,
            )
        )
    if premium_cents > 0:
        postings.append(
            LedgerPosting(
                _account(service, PURCHASE_PREMIUM_DEFERRED, "liability"),
                "D",
                premium_cents,
            )
        )
    postings.append(
        LedgerPosting(_account(service, PSP_CLEARING, "asset"), "C", purchase.amount_cents)
    )
    service.post(
        kind="purchase_refund",
        ref_type="ticket_purchase",
        ref_id=purchase.id,
        idempotency_key=f"purchase_refund:{purchase.id}",
        postings=postings,
        occurred_at=now,
    )


def post_booking_confirmed(
    session: Session,
    booking: Booking,
    participants: Iterable[BookingParticipant],
    *,
    now: datetime | None = None,
) -> None:
    """Regra 4: debita a cota e credita quadra + taxa, na confirmação."""

    debit_by_user: dict[uuid.UUID, int] = {}
    psp_total = 0
    space_total = 0
    fee_total = 0
    for participant in participants:
        if participant.funding_source == "credit":
            debit_by_user[participant.user_id] = (
                debit_by_user.get(participant.user_id, 0) + participant.contribution_cents
            )
        elif participant.funding_source == "pix":
            psp_total += participant.contribution_cents
        else:
            # Passe/grátis/admin: Etapa 6b. Fica fora deste lançamento e o
            # reconciliador lista a vaga como excluída.
            continue
        space_total += participant.space_charge_cents
        fee_total += participant.fee_charge_cents

    if not debit_by_user and psp_total == 0:
        return

    service = LedgerService(session)
    postings: list[LedgerPosting] = [
        LedgerPosting(
            _account(
                service,
                f"{PLAYER_CREDIT_PREFIX}{user_id}",
                "liability",
                owner_kind="user",
                owner_id=user_id,
            ),
            "D",
            amount,
        )
        for user_id, amount in debit_by_user.items()
    ]
    if psp_total:
        postings.append(LedgerPosting(_account(service, PSP_CLEARING, "asset"), "D", psp_total))
    if space_total:
        postings.append(
            LedgerPosting(
                _account(
                    service,
                    f"{VENUE_PAYABLE_PREFIX}{booking.organization_venue_id}",
                    "liability",
                    owner_kind="venue",
                    owner_id=booking.organization_venue_id,
                ),
                "C",
                space_total,
            )
        )
    if fee_total:
        postings.append(LedgerPosting(_account(service, FEE_REVENUE, "revenue"), "C", fee_total))
    service.post(
        kind="booking_confirmed",
        ref_type="booking",
        ref_id=booking.id,
        idempotency_key=f"booking:{booking.id}:confirm",
        postings=postings,
        occurred_at=booking.confirmed_at or now,
    )


def _release_is_done(session: Session, booking_id: uuid.UUID) -> bool:
    release = session.scalar(select(VenueRelease).where(VenueRelease.booking_id == booking_id))
    return release is not None and release.status in {"RELEASED", "REVERSED"}


def post_booking_refund(
    session: Session,
    booking: Booking,
    participants: Iterable[BookingParticipant],
    *,
    now: datetime | None = None,
) -> None:
    """Regras 6/7: devolve a cota e estorna quadra + taxa."""

    credit_by_user: dict[uuid.UUID, int] = {}
    space_total = 0
    fee_total = 0
    for participant in participants:
        if participant.funding_source != "credit" or participant.tickets_consumed <= 0:
            continue
        credit_by_user[participant.user_id] = (
            credit_by_user.get(participant.user_id, 0) + participant.contribution_cents
        )
        space_total += participant.space_charge_cents
        fee_total += participant.fee_charge_cents
    if not credit_by_user:
        return

    service = LedgerService(session)
    released = _release_is_done(session, booking.id)
    debit_code = (
        f"{VENUE_RECEIVABLE_PREFIX}{booking.organization_venue_id}"
        if released
        else f"{VENUE_PAYABLE_PREFIX}{booking.organization_venue_id}"
    )
    debit_kind = "asset" if released else "liability"
    postings: list[LedgerPosting] = []
    if space_total:
        postings.append(
            LedgerPosting(
                _account(
                    service,
                    debit_code,
                    debit_kind,
                    owner_kind="venue",
                    owner_id=booking.organization_venue_id,
                ),
                "D",
                space_total,
            )
        )
    if fee_total:
        postings.append(LedgerPosting(_account(service, FEE_REVENUE, "revenue"), "D", fee_total))
    postings.extend(
        LedgerPosting(
            _account(
                service,
                f"{PLAYER_CREDIT_PREFIX}{user_id}",
                "liability",
                owner_kind="user",
                owner_id=user_id,
            ),
            "C",
            amount,
        )
        for user_id, amount in credit_by_user.items()
    )
    service.post(
        kind="booking_refund",
        ref_type="booking",
        ref_id=booking.id,
        idempotency_key=f"booking:{booking.id}:refund",
        postings=postings,
        occurred_at=now,
    )


def post_release(
    session: Session,
    release: VenueRelease,
    *,
    now: datetime | None = None,
) -> None:
    """Regra 5: baixa a obrigação com a quadra contra o banco."""

    booking = session.get(Booking, release.booking_id)
    if booking is None:
        raise LedgerError("booking_missing")
    service = LedgerService(session)
    service.post(
        kind="venue_release",
        ref_type="venue_release",
        ref_id=release.id,
        idempotency_key=f"release:{release.id}",
        postings=[
            LedgerPosting(
                _account(
                    service,
                    f"{VENUE_PAYABLE_PREFIX}{booking.organization_venue_id}",
                    "liability",
                    owner_kind="venue",
                    owner_id=booking.organization_venue_id,
                ),
                "D",
                release.amount_cents,
            ),
            LedgerPosting(_account(service, BANK, "asset"), "C", release.amount_cents),
        ],
        occurred_at=now,
    )


def post_payment_refund(
    session: Session,
    payment: BookingPayment,
    participant: BookingParticipant,
    *,
    now: datetime | None = None,
) -> None:
    """Regra 16/17 para vaga paga por Pix."""

    service = LedgerService(session)
    booking = session.get(Booking, payment.booking_id)
    if booking is None:
        raise LedgerError("booking_missing")
    released = _release_is_done(session, booking.id)
    debit_code = (
        f"{VENUE_RECEIVABLE_PREFIX}{booking.organization_venue_id}"
        if released
        else f"{VENUE_PAYABLE_PREFIX}{booking.organization_venue_id}"
    )
    debit_kind = "asset" if released else "liability"
    postings = [
        LedgerPosting(
            _account(
                service,
                debit_code,
                debit_kind,
                owner_kind="venue",
                owner_id=booking.organization_venue_id,
            ),
            "D",
            participant.space_charge_cents,
        ),
        LedgerPosting(
            _account(service, FEE_REVENUE, "revenue"),
            "D",
            participant.fee_charge_cents,
        ),
        LedgerPosting(_account(service, PSP_CLEARING, "asset"), "C", payment.amount_cents),
    ]
    filtered = [item for item in postings if item.amount_cents > 0]
    if len(filtered) < 2:
        return
    service.post(
        kind="payment_refund",
        ref_type="booking_payment",
        ref_id=payment.id,
        idempotency_key=f"payment_refund:{payment.id}",
        postings=filtered,
        occurred_at=now,
    )


def post_pass_sale(
    session: Session,
    subscription: PassSubscription,
    *,
    now: datetime | None = None,
) -> None:
    """Regra 10: venda do passe vira receita diferida."""

    service = LedgerService(session)
    service.post(
        kind="pass_sale",
        ref_type="pass_subscription",
        ref_id=subscription.id,
        idempotency_key=f"pass:{subscription.id}:sale",
        postings=[
            LedgerPosting(_account(service, PSP_CLEARING, "asset"), "D", subscription.amount_cents),
            LedgerPosting(
                _account(service, PASS_DEFERRED_REVENUE, "liability"),
                "C",
                subscription.amount_cents,
            ),
        ],
        occurred_at=subscription.paid_at or now,
    )


def post_pass_month(
    session: Session,
    subscription: PassSubscription,
    month_index: int,
    *,
    amount_cents: int,
    now: datetime | None = None,
) -> None:
    """Regra 11: disponibilização mensal reconhece a receita do mês."""

    service = LedgerService(session)
    service.post(
        kind="pass_month",
        ref_type="pass_subscription",
        ref_id=subscription.id,
        idempotency_key=f"pass:{subscription.id}:month:{month_index}",
        postings=[
            LedgerPosting(_account(service, PASS_DEFERRED_REVENUE, "liability"), "D", amount_cents),
            LedgerPosting(_account(service, PASS_REVENUE, "revenue"), "C", amount_cents),
        ],
        occurred_at=now,
    )


def post_pass_refund(
    session: Session,
    subscription: PassSubscription,
    *,
    amount_cents: int,
    now: datetime | None = None,
) -> None:
    """Regra 18: devolve meses ainda não disponibilizados do passe."""

    if amount_cents <= 0:
        return
    service = LedgerService(session)
    service.post(
        kind="pass_refund",
        ref_type="pass_subscription",
        ref_id=subscription.id,
        idempotency_key=f"pass:{subscription.id}:refund",
        postings=[
            LedgerPosting(
                _account(service, PASS_DEFERRED_REVENUE, "liability"),
                "D",
                amount_cents,
            ),
            LedgerPosting(_account(service, PSP_CLEARING, "asset"), "C", amount_cents),
        ],
        occurred_at=now,
    )


__all__ = [
    "post_booking_confirmed",
    "post_booking_refund",
    "post_credit_purchase",
    "post_pass_month",
    "post_pass_sale",
    "post_payment_refund",
    "post_purchase_refund",
    "post_release",
]
