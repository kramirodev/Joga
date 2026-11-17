"""Sombra de escrita do ledger (ADR 0049 §13).

A tabela 2D é a unidade de consumo; o preço em reais é a autoridade monetária.
Nenhuma leitura pública depende destes lançamentos.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.bookings.models import BookingParticipant
from app.modules.bookings.service import BookingService
from app.modules.identity.clock import ensure_utc
from app.modules.ledger.accounts import (
    BANK,
    FEE_REVENUE,
    PASS_DEFERRED_REVENUE,
    PASS_REVENUE,
    PROMO_EXPENSE,
    VENUE_PAYABLE_PREFIX,
    player_credit_code,
)
from app.modules.ledger.models import LedgerAccount, LedgerEntry, LedgerTransaction
from app.modules.ledger.opening import open_ledger
from app.modules.ledger.reconciliation import reconcile_credit
from app.modules.ledger.service import LedgerService
from app.modules.passes.service import activate_subscription, create_subscription
from app.modules.payments.financial import FinancialService
from app.modules.payments.models import VenueRelease
from app.modules.pricing.service import TICKET_CALIBRATION_CENTS
from app.modules.tickets.models import TicketBalance
from app.modules.tickets.service import (
    confirm_purchase,
    create_purchase,
    grant,
    player_credit_cents,
    revoke_purchase,
)
from tests.helpers_results import make_user
from tests.test_ticket_settlement import (
    PRICE_CENTS,
    TICKETS_PER_SEAT,
    api_client,
    bearer,
    open_booking,
    setup_context,
)


def transaction(session: Session, key: str) -> LedgerTransaction:
    row = session.scalar(select(LedgerTransaction).where(LedgerTransaction.idempotency_key == key))
    assert row is not None, key
    return row


def entries(session: Session, tx: LedgerTransaction) -> dict[tuple[str, str], int]:
    rows = session.execute(
        select(LedgerAccount.code, LedgerEntry.direction, LedgerEntry.amount_cents)
        .join(LedgerEntry, LedgerEntry.account_id == LedgerAccount.id)
        .where(LedgerEntry.transaction_id == tx.id)
    ).all()
    result: dict[tuple[str, str], int] = {}
    for code, direction, amount in rows:
        result[(str(code), str(direction))] = int(amount)
    return result


def test_purchase_credits_cash_and_tickets(db_session: Session) -> None:
    user_id = make_user(db_session)
    purchase = create_purchase(db_session, user_id, "avulso")
    confirm_purchase(db_session, user_id, purchase.id)
    db_session.flush()

    service = LedgerService(db_session)
    assert service.balance_for_code("psp_clearing") == purchase.amount_cents
    assert service.balance_for_code(player_credit_code(user_id)) == purchase.amount_cents
    assert player_credit_cents(db_session, user_id) == purchase.amount_cents
    cached = db_session.get(TicketBalance, user_id)
    assert cached is not None and cached.balance == purchase.tickets
    assert reconcile_credit(db_session).clean


def test_booking_confirmation_posts_rule_4(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    db_session.flush()
    open_ledger(db_session, dry_run=False)

    booking = open_booking(api, context)
    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
            headers=bearer(token),
        )
        assert response.status_code == 200, response.text

    booking_id = uuid.UUID(booking["id"])
    participants = db_session.scalars(
        select(BookingParticipant).where(BookingParticipant.booking_id == booking_id)
    ).all()
    assert {item.funding_source for item in participants} == {"credit"}
    assert {item.tickets_consumed for item in participants} == {TICKETS_PER_SEAT}

    ticket_total = TICKETS_PER_SEAT * TICKET_CALIBRATION_CENTS * len(participants)
    tx = transaction(db_session, f"booking:{booking_id}:confirm")
    posted = entries(db_session, tx)
    assert posted[(f"{VENUE_PAYABLE_PREFIX}{context['venue'].id}", "C")] == PRICE_CENTS
    assert posted[(FEE_REVENUE, "C")] == ticket_total - PRICE_CENTS
    for participant in participants:
        assert (
            posted[(player_credit_code(participant.user_id), "D")]
            == TICKETS_PER_SEAT * TICKET_CALIBRATION_CENTS
        )
        assert player_credit_cents(db_session, participant.user_id) == 0

    report = reconcile_credit(db_session)
    assert report.clean, (report.mismatches, report.balance_mismatches)


def test_booking_refund_restores_credit(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    db_session.flush()
    open_ledger(db_session, dry_run=False)
    booking = open_booking(api, context)
    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
            headers=bearer(token),
        )
        assert response.status_code == 200, response.text

    BookingService(db_session).cancel(
        context["users"][0],
        uuid.UUID(booking["id"]),
        reason="teste de devolução",
    )
    db_session.flush()

    tx = transaction(db_session, f"booking:{booking['id']}:refund")
    posted = entries(db_session, tx)
    assert posted[(FEE_REVENUE, "D")] == 5 * 480
    assert posted[(f"{VENUE_PAYABLE_PREFIX}{context['venue'].id}", "D")] == 10_000
    canceller = context["users"][0]
    for user_id in context["users"]:
        if user_id == canceller:
            assert (player_credit_code(user_id), "C") not in posted
            assert player_credit_cents(db_session, user_id) == 0
            continue
        assert (
            posted[(player_credit_code(user_id), "C")]
            == TICKETS_PER_SEAT * TICKET_CALIBRATION_CENTS
        )
        assert player_credit_cents(db_session, user_id) == (
            TICKETS_PER_SEAT * TICKET_CALIBRATION_CENTS
        )

    assert reconcile_credit(db_session).clean


def test_release_posts_rule_5(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    db_session.flush()
    open_ledger(db_session, dry_run=False)
    booking = open_booking(api, context)
    for token in context["tokens"]:
        api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
            headers=bearer(token),
        )

    release = db_session.scalar(
        select(VenueRelease).where(VenueRelease.booking_id == uuid.UUID(booking["id"]))
    )
    assert release is not None
    FinancialService(db_session).release_due(
        now=ensure_utc(release.eligible_at) + timedelta(minutes=1)
    )
    db_session.flush()

    posted = entries(db_session, transaction(db_session, f"release:{release.id}"))
    assert posted[(f"{VENUE_PAYABLE_PREFIX}{context['venue'].id}", "D")] == PRICE_CENTS
    assert posted[(BANK, "C")] == PRICE_CENTS


def test_purchase_reversal_uses_receivable(db_session: Session) -> None:
    user_id = make_user(db_session)
    purchase = create_purchase(db_session, user_id, "avulso")
    confirm_purchase(db_session, user_id, purchase.id)
    revoke_purchase(db_session, user_id, purchase.id)
    db_session.flush()

    posted = entries(db_session, transaction(db_session, f"purchase_refund:{purchase.id}"))
    assert posted[("psp_clearing", "C")] == purchase.amount_cents
    assert posted[(player_credit_code(user_id), "D")] == purchase.amount_cents
    assert player_credit_cents(db_session, user_id) == 0
    assert reconcile_credit(db_session).clean


def test_pix_confirmation_uses_psp_clearing(
    client: TestClient,
    db_session: Session,
) -> None:
    from tests.test_bookings_api import setup_booking
    from tests.test_payments_service import accepted_booking, pay_all

    api = api_client(client, db_session)
    context = setup_booking(db_session)
    accepted = accepted_booking(api, context)
    pay_all(api, context, accepted["id"])

    booking_id = uuid.UUID(accepted["id"])
    posted = entries(db_session, transaction(db_session, f"booking:{booking_id}:confirm"))
    assert posted[("psp_clearing", "D")] == 48_000
    assert posted[(f"{VENUE_PAYABLE_PREFIX}{context['venue'].id}", "C")] == 40_000
    assert posted[(FEE_REVENUE, "C")] == 8_000


def test_pass_sale_and_month_posts(
    db_session: Session,
) -> None:
    user_id = make_user(db_session)
    subscription = create_subscription(
        db_session, user_id, "time", now=datetime(2026, 11, 13, 12, tzinfo=UTC)
    )
    activate_subscription(db_session, subscription.id, now=datetime(2026, 11, 13, 12, tzinfo=UTC))
    db_session.flush()

    sale = entries(db_session, transaction(db_session, f"pass:{subscription.id}:sale"))
    assert sale[("psp_clearing", "D")] == subscription.amount_cents
    assert sale[(PASS_DEFERRED_REVENUE, "C")] == subscription.amount_cents

    month = entries(db_session, transaction(db_session, f"pass:{subscription.id}:month:1"))
    monthly = subscription.amount_cents // 3
    assert month[(PASS_DEFERRED_REVENUE, "D")] == monthly
    assert month[(PASS_REVENUE, "C")] == monthly


def test_free_level_seat_posts_promo_expense(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    user_id = context["users"][0]
    from app.modules.tickets.models import TicketLot

    lot = db_session.scalar(select(TicketLot).where(TicketLot.user_id == user_id))
    assert lot is not None
    lot.remaining = 0
    balance = db_session.get(TicketBalance, user_id)
    assert balance is not None
    balance.balance = 0
    grant(
        db_session,
        user_id,
        TICKETS_PER_SEAT,
        source="free_level",
        idempotency_key=f"free:test:{user_id}",
    )
    db_session.flush()
    open_ledger(db_session, dry_run=False)
    booking = open_booking(api, context)
    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
            headers=bearer(token),
        )
        assert response.status_code == 200, response.text

    participant = db_session.scalar(
        select(BookingParticipant).where(
            BookingParticipant.booking_id == uuid.UUID(booking["id"]),
            BookingParticipant.user_id == user_id,
        )
    )
    assert participant is not None
    assert participant.funding_source == "free_level"
    posted = entries(
        db_session,
        transaction(db_session, f"booking:{booking['id']}:confirm"),
    )
    assert posted[(PROMO_EXPENSE, "D")] == participant.space_charge_cents
    assert posted[(f"{VENUE_PAYABLE_PREFIX}{context['venue'].id}", "C")] == PRICE_CENTS
    assert reconcile_credit(db_session).clean


def test_reconciler_covers_non_credit_seat(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    user_id = context["users"][0]
    from app.modules.tickets.models import TicketLot

    lot = db_session.scalar(select(TicketLot).where(TicketLot.user_id == user_id))
    assert lot is not None
    lot.remaining = 0
    balance = db_session.get(TicketBalance, user_id)
    assert balance is not None
    balance.balance = 0
    grant(
        db_session,
        user_id,
        TICKETS_PER_SEAT,
        source="pass",
        idempotency_key=f"pass:test:{user_id}",
        period=datetime.now(UTC).strftime("%Y-%m"),
    )
    db_session.flush()
    open_ledger(db_session, dry_run=False)

    booking = open_booking(api, context)
    for token in context["tokens"]:
        response = api.post(
            f"/api/v1/bookings/{booking['id']}/settle-with-tickets",
            headers=bearer(token),
        )
        assert response.status_code == 200, response.text

    report = reconcile_credit(db_session)
    assert report.clean, (report.mismatches, report.balance_mismatches)
    assert report.missing_non_credit_postings == []
    non_credit = {item.participant_id for item in report.non_credit_seats}
    participant = db_session.scalar(
        select(BookingParticipant).where(
            BookingParticipant.booking_id == uuid.UUID(booking["id"]),
            BookingParticipant.user_id == user_id,
        )
    )
    assert participant is not None
    assert participant.funding_source == "pass"
    assert participant.id in non_credit

    posted = entries(
        db_session,
        transaction(db_session, f"booking:{booking['id']}:confirm"),
    )
    assert posted[(PASS_REVENUE, "D")] == participant.space_charge_cents
    assert posted[(f"{VENUE_PAYABLE_PREFIX}{context['venue'].id}", "C")] == PRICE_CENTS


def test_opening_is_idempotent(db_session: Session) -> None:
    user_id = make_user(db_session)
    grant(
        db_session,
        user_id,
        TICKETS_PER_SEAT,
        source="purchase",
        idempotency_key=f"open:test:{user_id}",
        unit_price_cents=310,
    )
    db_session.flush()

    first = open_ledger(db_session, dry_run=False)
    db_session.flush()
    second = open_ledger(db_session, dry_run=False)
    assert first.created == 1
    assert second.created == 0
    assert player_credit_cents(db_session, user_id) == TICKETS_PER_SEAT * 310
