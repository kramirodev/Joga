"""Bloqueio operacional da compra de tickets (flag desligada por padrão)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.ledger.models import LedgerEntry
from app.modules.payments.models import PurchasePayment
from app.modules.tickets.models import TicketLedgerEntry, TicketLot, TicketPurchase
from tests.helpers_results import make_token, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    settings = Settings(_env_file=None, ticket_purchase_enabled=False)
    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_settings] = lambda: settings
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _counts(session: Session) -> tuple[int, int, int, int, int]:
    return (
        int(session.scalar(select(func.count()).select_from(TicketPurchase)) or 0),
        int(session.scalar(select(func.count()).select_from(PurchasePayment)) or 0),
        int(session.scalar(select(func.count()).select_from(TicketLedgerEntry)) or 0),
        int(session.scalar(select(func.count()).select_from(TicketLot)) or 0),
        int(session.scalar(select(func.count()).select_from(LedgerEntry)) or 0),
    )


def test_disabled_flag_blocks_writes_but_not_reads(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    before = _counts(db_session)

    wallet = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert wallet.status_code == 200, wallet.text
    packs = api.get("/api/v1/me/tickets/packs", headers=bearer(token))
    assert packs.status_code == 200, packs.text
    assert len(packs.json()["packs"]) == 4

    purchase = api.post(
        "/api/v1/me/tickets/purchases",
        headers=bearer(token),
        json={"pack_code": "pequeno"},
    )
    assert purchase.status_code == 503
    assert purchase.json() == {"detail": {"code": "ticket_purchase_disabled"}}

    random_id = uuid.uuid4()
    synced = api.post(
        f"/api/v1/me/tickets/purchases/{random_id}/sync",
        headers=bearer(token),
    )
    assert synced.status_code == 503
    assert synced.json() == {"detail": {"code": "ticket_purchase_disabled"}}

    confirmed = api.post(
        f"/api/v1/me/tickets/purchases/{random_id}/confirm",
        headers=bearer(token),
    )
    assert confirmed.status_code == 503
    assert confirmed.json() == {"detail": {"code": "ticket_purchase_disabled"}}

    assert _counts(db_session) == before


def test_flag_default_is_disabled() -> None:
    assert Settings(_env_file=None, ticket_purchase_enabled=False).ticket_purchase_enabled is False
