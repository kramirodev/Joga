"""Testes do ledger de dupla entrada (ADR 0049 §9.2)."""

from __future__ import annotations

import importlib.util
import random
import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ledger.accounts import (
    SINGLETON_ACCOUNTS,
    ensure_chart_of_accounts,
    player_credit_code,
)
from app.modules.ledger.models import LedgerAccount, LedgerEntry, LedgerTransaction
from app.modules.ledger.service import (
    LedgerError,
    LedgerImbalance,
    LedgerPosting,
    LedgerService,
)


def accounts(session: Session) -> tuple[LedgerAccount, LedgerAccount, LedgerAccount]:
    service = LedgerService(session)
    asset = service.account("psp_clearing", "asset")
    user_id = uuid.uuid4()
    credit = service.account(
        f"player_credit:{user_id}",
        "liability",
        owner_kind="user",
        owner_id=user_id,
    )
    revenue = service.account("fee_revenue", "revenue")
    return asset, credit, revenue


def test_purchase_posts_once_and_replay_is_idempotent(db_session: Session) -> None:
    asset, credit, _revenue = accounts(db_session)
    service = LedgerService(db_session)
    reference = uuid.uuid4()
    postings = [
        LedgerPosting(asset, "D", 10_000),
        LedgerPosting(credit, "C", 10_000),
    ]

    transaction, created = service.post(
        kind="credit_purchase",
        ref_type="ticket_purchase",
        ref_id=reference,
        idempotency_key=f"credit_purchase:{reference}",
        postings=postings,
    )
    assert created is True
    assert service.balance_cents(asset) == 10_000
    assert service.balance_cents(credit) == 10_000

    replay, created_again = service.post(
        kind="credit_purchase",
        ref_type="ticket_purchase",
        ref_id=reference,
        idempotency_key=f"credit_purchase:{reference}",
        postings=postings,
    )
    assert created_again is False
    assert replay.id == transaction.id

    entries = db_session.scalar(
        select(func.count())
        .select_from(LedgerEntry)
        .where(LedgerEntry.transaction_id == transaction.id)
    )
    assert entries == 2
    assert db_session.scalar(select(func.count()).select_from(LedgerTransaction)) == 1


def test_revenue_and_liability_use_credit_natural_sign(db_session: Session) -> None:
    _asset, credit, revenue = accounts(db_session)
    service = LedgerService(db_session)
    service.post(
        kind="booking_confirmed",
        ref_type="booking",
        ref_id=uuid.uuid4(),
        idempotency_key=f"booking_confirmed:{uuid.uuid4()}",
        postings=[
            LedgerPosting(credit, "D", 3_000),
            LedgerPosting(revenue, "C", 3_000),
        ],
    )

    assert service.balance_cents(credit) == -3_000
    assert service.balance_cents(revenue) == 3_000


def test_unbalanced_transaction_is_rejected(db_session: Session) -> None:
    asset, credit, _revenue = accounts(db_session)
    service = LedgerService(db_session)

    with pytest.raises(LedgerImbalance):
        service.post(
            kind="broken",
            ref_type="test",
            ref_id=uuid.uuid4(),
            idempotency_key="broken:1",
            postings=[
                LedgerPosting(asset, "D", 100),
                LedgerPosting(credit, "C", 99),
            ],
        )

    assert db_session.scalar(select(func.count()).select_from(LedgerTransaction)) == 0


def test_duplicate_posting_and_invalid_amounts_are_rejected(db_session: Session) -> None:
    asset, credit, _revenue = accounts(db_session)
    service = LedgerService(db_session)

    with pytest.raises(LedgerError):
        service.post(
            kind="duplicate",
            ref_type="test",
            ref_id=uuid.uuid4(),
            idempotency_key="duplicate:1",
            postings=[
                LedgerPosting(asset, "D", 100),
                LedgerPosting(asset, "D", 100),
            ],
        )
    with pytest.raises(LedgerError):
        service.post(
            kind="invalid",
            ref_type="test",
            ref_id=uuid.uuid4(),
            idempotency_key="invalid:1",
            postings=[
                LedgerPosting(asset, "D", 0),
                LedgerPosting(credit, "C", 0),
            ],
        )
    with pytest.raises(LedgerError):
        service.post(
            kind="invalid",
            ref_type="test",
            ref_id=uuid.uuid4(),
            idempotency_key="   ",
            postings=[
                LedgerPosting(asset, "D", 1),
                LedgerPosting(credit, "C", 1),
            ],
        )


def test_one_hundred_transactions_balance_and_do_not_duplicate(db_session: Session) -> None:
    asset, credit, revenue = accounts(db_session)
    service = LedgerService(db_session)
    rng = random.Random(2026)

    for index in range(100):
        amount = rng.randint(1, 100_000)
        reference = uuid.uuid4()
        target = credit if index % 2 == 0 else revenue
        transaction, created = service.post(
            kind="random",
            ref_type="test",
            ref_id=reference,
            idempotency_key=f"random:{reference}",
            postings=[
                LedgerPosting(asset, "D", amount),
                LedgerPosting(target, "C", amount),
            ],
        )
        assert created is True
        entries = service.entries_for(transaction.id)
        assert sum(item.amount_cents for item in entries if item.direction == "D") == sum(
            item.amount_cents for item in entries if item.direction == "C"
        )

    assert db_session.scalar(select(func.count()).select_from(LedgerTransaction)) == 100
    assert db_session.scalar(select(func.count()).select_from(LedgerEntry)) == 200
    assert service.balance_cents(asset) == service.balance_cents(credit) + service.balance_cents(
        revenue
    )


def test_balance_for_code_and_missing_account(db_session: Session) -> None:
    asset, _credit, _revenue = accounts(db_session)
    service = LedgerService(db_session)
    service.post(
        kind="deposit",
        ref_type="test",
        ref_id=uuid.uuid4(),
        idempotency_key="deposit:1",
        postings=[LedgerPosting(asset, "D", 500), LedgerPosting(_credit, "C", 500)],
    )

    assert service.balance_for_code("psp_clearing") == 500
    with pytest.raises(LedgerError):
        service.balance_for_code("missing")


def test_chart_of_accounts_seed_is_idempotent(db_session: Session) -> None:
    ensure_chart_of_accounts(db_session)
    ensure_chart_of_accounts(db_session)
    codes = set(db_session.scalars(select(LedgerAccount.code)).all())
    assert set(SINGLETON_ACCOUNTS) <= codes
    assert len([code for code in codes if code in SINGLETON_ACCOUNTS]) == len(SINGLETON_ACCOUNTS)

    service = LedgerService(db_session)
    user_id = uuid.uuid4()
    credit = service.account(
        player_credit_code(user_id),
        "liability",
        owner_kind="user",
        owner_id=user_id,
    )
    service.post(
        kind="credit_purchase",
        ref_type="ticket_purchase",
        ref_id=uuid.uuid4(),
        idempotency_key="chart:1",
        postings=[
            LedgerPosting(service.account("psp_clearing", "asset"), "D", 1_000),
            LedgerPosting(credit, "C", 1_000),
        ],
    )
    assert service.balance_cents(credit) == 1_000


def _load_migration(filename: str):
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / filename
    spec = importlib.util.spec_from_file_location(f"migration_{filename}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_migration_matches_chart_of_accounts() -> None:
    """As migrações de seed e o módulo de contas não podem divergir."""

    seed = _load_migration("l6c7d8e9f0a1_seed_ledger_accounts.py")
    premium = _load_migration("n8e9f0a1b2c3_credit_cents_and_premium.py")
    accounts = dict(seed.ACCOUNTS)
    code, kind = premium.PREMIUM_ACCOUNT
    accounts[code] = kind
    assert accounts == SINGLETON_ACCOUNTS


def test_every_owner_prefix_has_a_declared_kind() -> None:
    from app.modules.ledger import accounts

    prefixes = {
        accounts.PLAYER_CREDIT_PREFIX,
        accounts.VENUE_PAYABLE_PREFIX,
        accounts.CHARGEBACK_RECEIVABLE_PREFIX,
        accounts.VENUE_RECEIVABLE_PREFIX,
    }
    assert prefixes == set(accounts.OWNER_ACCOUNT_KINDS)
    assert not prefixes & set(SINGLETON_ACCOUNTS)
    assert all(code.endswith(":") for code in prefixes)
