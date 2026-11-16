"""Plano de contas do ledger (ADR 0049 §9.2)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.ledger.service import LedgerService

PSP_CLEARING = "psp_clearing"
BANK = "bank"
FEE_REVENUE = "fee_revenue"
PASS_DEFERRED_REVENUE = "pass_deferred_revenue"
PASS_REVENUE = "pass_revenue"
TAX_PAYABLE = "tax_payable"
TAX_EXPENSE = "tax_expense"
PSP_FEE_EXPENSE = "psp_fee_expense"
WRITEOFF_EXPENSE = "writeoff_expense"
OPENING_EQUITY = "opening_equity"

PLAYER_CREDIT_PREFIX = "player_credit:"
VENUE_PAYABLE_PREFIX = "venue_payable:"
CHARGEBACK_RECEIVABLE_PREFIX = "chargeback_receivable_player:"
VENUE_RECEIVABLE_PREFIX = "venue_receivable:"

SINGLETON_ACCOUNTS: dict[str, str] = {
    PSP_CLEARING: "asset",
    BANK: "asset",
    FEE_REVENUE: "revenue",
    PASS_DEFERRED_REVENUE: "liability",
    PASS_REVENUE: "revenue",
    TAX_PAYABLE: "liability",
    TAX_EXPENSE: "expense",
    PSP_FEE_EXPENSE: "expense",
    WRITEOFF_EXPENSE: "expense",
    OPENING_EQUITY: "equity",
}

OWNER_ACCOUNT_KINDS: dict[str, str] = {
    PLAYER_CREDIT_PREFIX: "liability",
    VENUE_PAYABLE_PREFIX: "liability",
    CHARGEBACK_RECEIVABLE_PREFIX: "asset",
    VENUE_RECEIVABLE_PREFIX: "asset",
}


def player_credit_code(user_id: uuid.UUID) -> str:
    return f"{PLAYER_CREDIT_PREFIX}{user_id}"


def venue_payable_code(venue_id: uuid.UUID) -> str:
    return f"{VENUE_PAYABLE_PREFIX}{venue_id}"


def chargeback_receivable_code(user_id: uuid.UUID) -> str:
    return f"{CHARGEBACK_RECEIVABLE_PREFIX}{user_id}"


def venue_receivable_code(venue_id: uuid.UUID) -> str:
    return f"{VENUE_RECEIVABLE_PREFIX}{venue_id}"


def ensure_chart_of_accounts(session: Session) -> None:
    """Garante as contas singleton; contas por dono são criadas sob demanda."""

    service = LedgerService(session)
    for code, kind in SINGLETON_ACCOUNTS.items():
        service.account(code, kind)


__all__ = [
    "BANK",
    "CHARGEBACK_RECEIVABLE_PREFIX",
    "FEE_REVENUE",
    "OPENING_EQUITY",
    "OWNER_ACCOUNT_KINDS",
    "PASS_DEFERRED_REVENUE",
    "PASS_REVENUE",
    "PLAYER_CREDIT_PREFIX",
    "PSP_CLEARING",
    "PSP_FEE_EXPENSE",
    "SINGLETON_ACCOUNTS",
    "TAX_EXPENSE",
    "TAX_PAYABLE",
    "VENUE_PAYABLE_PREFIX",
    "VENUE_RECEIVABLE_PREFIX",
    "WRITEOFF_EXPENSE",
    "chargeback_receivable_code",
    "ensure_chart_of_accounts",
    "player_credit_code",
    "venue_payable_code",
    "venue_receivable_code",
]
