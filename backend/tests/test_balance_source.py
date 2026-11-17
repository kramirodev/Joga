"""Inversão da leitura do saldo (ADR 0049 §11, Etapa 7).

A flag `JOGA_TICKET_BALANCE_SOURCE` alterna `cache` e `ledger` sem deploy. No
modo ledger, conta ausente ou divergência ledger × lotes falha alto.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.identity.clock import utcnow
from app.modules.ledger.accounts import FEE_REVENUE, player_credit_code
from app.modules.ledger.opening import open_ledger
from app.modules.ledger.reconciliation import ledger_health, reconcile_credit
from app.modules.ledger.service import LedgerPosting, LedgerService
from app.modules.tickets.models import TicketBalance
from app.modules.tickets.service import (
    BalanceUnavailable,
    LedgerInconsistency,
    current_period,
    get_balance,
    grant,
)
from tests.helpers_results import make_token, make_user
from tests.test_ticket_settlement import api_client, bearer


def ledger_settings(source: str = "ledger") -> Settings:
    return Settings(_env_file=None, environment="local", ticket_balance_source=source)


def test_ledger_source_composes_purchased_pass_and_free(db_session: Session) -> None:
    user_id = make_user(db_session)
    grant(
        db_session,
        user_id,
        10,
        source="purchase",
        idempotency_key="balance:purchase",
    )
    grant(
        db_session,
        user_id,
        3,
        source="pass",
        idempotency_key="balance:pass",
        period=current_period(utcnow()),
    )
    grant(
        db_session,
        user_id,
        2,
        source="free_level",
        idempotency_key="balance:free",
    )
    db_session.flush()
    open_ledger(db_session, dry_run=False)

    assert get_balance(db_session, user_id, source="ledger") == 15
    assert get_balance(db_session, user_id, source="cache") == 15
    assert reconcile_credit(db_session).clean


def test_ledger_source_fails_when_account_is_missing(db_session: Session) -> None:
    user_id = make_user(db_session)
    grant(
        db_session,
        user_id,
        10,
        source="purchase",
        idempotency_key="balance:missing",
    )
    db_session.flush()

    with pytest.raises(BalanceUnavailable):
        get_balance(db_session, user_id, source="ledger")


def test_ledger_source_fails_on_deliberate_divergence(db_session: Session) -> None:
    user_id = make_user(db_session)
    grant(
        db_session,
        user_id,
        10,
        source="purchase",
        idempotency_key="balance:divergence",
    )
    db_session.flush()
    open_ledger(db_session, dry_run=False)

    service = LedgerService(db_session)
    service.post(
        kind="test_divergence",
        ref_type="test",
        ref_id=uuid.uuid4(),
        idempotency_key="test_divergence:1",
        postings=[
            LedgerPosting(
                service.account(
                    player_credit_code(user_id),
                    "liability",
                    owner_kind="user",
                    owner_id=user_id,
                ),
                "D",
                10,
            ),
            LedgerPosting(service.account(FEE_REVENUE, "revenue"), "C", 10),
        ],
    )
    db_session.flush()

    with pytest.raises(LedgerInconsistency):
        get_balance(db_session, user_id, source="ledger")

    report = reconcile_credit(db_session)
    assert report.divergence_count == 1
    health = ledger_health(db_session)
    assert health["clean"] is False
    assert health["divergence_count"] == 1


def test_wallet_api_respects_flag_and_does_not_mask(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    grant(
        db_session,
        user_id,
        8,
        source="purchase",
        idempotency_key="balance:api",
    )
    db_session.flush()
    open_ledger(db_session, dry_run=False)
    token = make_token(db_session, user_id)
    client.app.dependency_overrides[get_settings] = ledger_settings

    response = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "ledger"
    assert response.json()["balance"] == 8

    service = LedgerService(db_session)
    service.post(
        kind="test_divergence",
        ref_type="test",
        ref_id=uuid.uuid4(),
        idempotency_key="test_divergence:api",
        postings=[
            LedgerPosting(
                service.account(
                    player_credit_code(user_id),
                    "liability",
                    owner_kind="user",
                    owner_id=user_id,
                ),
                "D",
                10,
            ),
            LedgerPosting(service.account(FEE_REVENUE, "revenue"), "C", 10),
        ],
    )
    db_session.flush()

    cached = db_session.get(TicketBalance, user_id)
    assert cached is not None and cached.balance == 8
    failed = api.get("/api/v1/me/tickets", headers=bearer(token))
    assert failed.status_code == 503, failed.text
    assert failed.json()["detail"]["code"] == "balance_unavailable"


def test_cache_is_still_written_in_the_same_transaction(db_session: Session) -> None:
    user_id = make_user(db_session)
    grant(
        db_session,
        user_id,
        4,
        source="purchase",
        idempotency_key="balance:cache",
    )
    db_session.flush()
    cached = db_session.scalar(select(TicketBalance).where(TicketBalance.user_id == user_id))
    assert cached is not None and cached.balance == 4
