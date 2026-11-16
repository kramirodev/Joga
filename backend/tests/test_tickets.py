"""Testes da carteira de ingressos (Fase 14D.3)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.tickets.models import TicketLedgerEntry, TicketLot
from app.modules.tickets.service import (
    InsufficientTickets,
    TicketConflict,
    consume,
    expire_due,
    get_balance,
    grant,
    refund,
)
from tests.helpers_results import make_token, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_grant_and_consume(db_session: Session) -> None:
    user_id = make_user(db_session)

    assert grant(db_session, user_id, 10, source="purchase", idempotency_key="purchase:1") == 10
    booking_id = uuid.uuid4()
    assert consume(db_session, user_id, 6, ref_type="booking", ref_id=booking_id) == 4
    assert get_balance(db_session, user_id) == 4


def test_insufficient_balance_does_not_debit(db_session: Session) -> None:
    user_id = make_user(db_session)
    grant(db_session, user_id, 3, source="purchase", idempotency_key="purchase:2")

    with pytest.raises(InsufficientTickets):
        consume(db_session, user_id, 6, ref_type="booking", ref_id=uuid.uuid4())

    assert get_balance(db_session, user_id) == 3


def test_consumption_is_idempotent(db_session: Session) -> None:
    user_id = make_user(db_session)
    grant(db_session, user_id, 10, source="purchase", idempotency_key="purchase:3")
    booking_id = uuid.uuid4()

    assert consume(db_session, user_id, 6, ref_type="booking", ref_id=booking_id) == 4
    assert consume(db_session, user_id, 6, ref_type="booking", ref_id=booking_id) == 4
    assert get_balance(db_session, user_id) == 4


def test_refund_returns_tickets(db_session: Session) -> None:
    user_id = make_user(db_session)
    grant(db_session, user_id, 6, source="purchase", idempotency_key="purchase:4")
    booking_id = uuid.uuid4()
    consume(db_session, user_id, 6, ref_type="booking", ref_id=booking_id)

    assert refund(db_session, user_id, 6, ref_type="booking", ref_id=booking_id) == 6
    assert refund(db_session, user_id, 6, ref_type="booking", ref_id=booking_id) == 6


def test_reusing_key_with_other_effect_is_rejected(db_session: Session) -> None:
    user_id = make_user(db_session)
    grant(db_session, user_id, 10, source="purchase", idempotency_key="purchase:5")

    with pytest.raises(TicketConflict):
        grant(db_session, user_id, 11, source="purchase", idempotency_key="purchase:5")


def test_consumption_uses_pass_before_purchase(db_session: Session) -> None:
    user_id = make_user(db_session)
    future = datetime.now(UTC) + timedelta(days=30)
    grant(db_session, user_id, 10, source="purchase", idempotency_key="purchase:order")
    grant(
        db_session,
        user_id,
        5,
        source="pass",
        idempotency_key="pass:month",
        expires_at=future,
    )

    assert consume(db_session, user_id, 6, ref_type="booking", ref_id=uuid.uuid4()) == 9
    lots = {
        lot.source: lot
        for lot in db_session.scalars(select(TicketLot).where(TicketLot.user_id == user_id)).all()
    }
    assert lots["pass"].remaining == 0
    assert lots["purchase"].remaining == 9


def test_expired_lot_does_not_count_in_the_balance(db_session: Session) -> None:
    user_id = make_user(db_session)
    past = datetime.now(UTC) - timedelta(minutes=1)
    grant(
        db_session,
        user_id,
        5,
        source="pass",
        idempotency_key="pass:expired",
        expires_at=past,
    )
    assert get_balance(db_session, user_id) == 5

    assert expire_due(db_session) == 1
    assert get_balance(db_session, user_id) == 0
    entry = db_session.scalar(
        select(TicketLedgerEntry).where(
            TicketLedgerEntry.user_id == user_id,
            TicketLedgerEntry.source == "expired",
        )
    )
    assert entry is not None and entry.amount == -5

    with pytest.raises(InsufficientTickets):
        consume(db_session, user_id, 1, ref_type="booking", ref_id=uuid.uuid4())


def test_refund_restores_the_active_lot(db_session: Session) -> None:
    user_id = make_user(db_session)
    booking_id = uuid.uuid4()
    grant(
        db_session,
        user_id,
        5,
        source="pass",
        idempotency_key="pass:active",
        expires_at=datetime.now(UTC) + timedelta(days=20),
    )
    consume(db_session, user_id, 5, ref_type="booking", ref_id=booking_id)

    assert refund(db_session, user_id, 5, ref_type="booking_cancel", ref_id=booking_id) == 5
    lot = db_session.scalar(select(TicketLot).where(TicketLot.user_id == user_id))
    assert lot is not None and lot.remaining == 5


def test_refund_does_not_convert_expired_pass_into_purchase(db_session: Session) -> None:
    user_id = make_user(db_session)
    booking_id = uuid.uuid4()
    grant(
        db_session,
        user_id,
        3,
        source="pass",
        idempotency_key="pass:will_expire",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    consume(db_session, user_id, 3, ref_type="booking", ref_id=booking_id)
    lot = db_session.scalar(select(TicketLot).where(TicketLot.user_id == user_id))
    assert lot is not None
    lot.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.flush()

    assert refund(db_session, user_id, 3, ref_type="booking_cancel", ref_id=booking_id) == 0
    assert get_balance(db_session, user_id) == 0


def test_wallet_endpoint_returns_balance_and_entries(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    grant(db_session, user_id, 10, source="purchase", idempotency_key=f"purchase:{user_id}")
    consume(db_session, user_id, 4, ref_type="booking", ref_id=uuid.uuid4())
    db_session.commit()

    response = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["balance"] == 6
    assert len(body["entries"]) == 2
    assert body["entries"][0]["amount"] == -4
    assert body["entries"][1]["amount"] == 10
    assert body["lots"][0]["source"] == "purchase"
    assert body["lots"][0]["remaining"] == 6


def test_wallet_is_scoped_to_the_user(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    owner_id = make_user(db_session)
    owner_token = make_token(db_session, owner_id)
    grant(db_session, owner_id, 9, source="purchase", idempotency_key=f"purchase:{owner_id}")
    db_session.commit()

    other_id = make_user(db_session)
    other_token = make_token(db_session, other_id)

    first = api.get("/api/v1/me/tickets", headers=bearer(owner_token))
    second = api.get("/api/v1/me/tickets", headers=bearer(other_token))
    assert first.json()["balance"] == 9
    assert second.json()["balance"] == 0
