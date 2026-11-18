"""Abertura do ledger no cutover (ADR 0049 §13.7).

Lê `ticket_lots.remaining × unit_price_cents` — nunca `ticket_balances` — e
lança uma única transação `opening:{user}` por jogador, contra
`opening_equity`. Passe, grátis e admin ficam fora porque não têm valor
monetário.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ledger.accounts import OPENING_EQUITY, player_credit_code
from app.modules.ledger.service import LedgerError, LedgerPosting, LedgerService
from app.modules.tickets.models import TicketLot
from app.modules.tickets.service import PAID_SOURCES


@dataclass(frozen=True)
class OpeningLine:
    user_id: uuid.UUID
    cents: int
    lots: int


@dataclass
class OpeningReport:
    lines: list[OpeningLine] = field(default_factory=list)
    total_cents: int = 0
    created: int = 0


def compute_opening(session: Session) -> OpeningReport:
    """Calcula a abertura por jogador, sem gravar nada."""

    lots = list(
        session.scalars(
            select(TicketLot)
            .where(
                TicketLot.source.in_(PAID_SOURCES),
                TicketLot.remaining > 0,
            )
            .order_by(TicketLot.user_id, TicketLot.created_at, TicketLot.id)
        ).all()
    )
    missing = [lot.id for lot in lots if lot.unit_price_cents is None]
    if missing:
        raise LedgerError("opening_lot_without_unit_price")

    by_user: dict[uuid.UUID, OpeningLine] = {}
    for lot in lots:
        cents = lot.remaining * int(lot.unit_price_cents or 0)
        current = by_user.get(lot.user_id)
        if current is None:
            by_user[lot.user_id] = OpeningLine(user_id=lot.user_id, cents=cents, lots=1)
        else:
            by_user[lot.user_id] = OpeningLine(
                user_id=lot.user_id,
                cents=current.cents + cents,
                lots=current.lots + 1,
            )
    report = OpeningReport(lines=sorted(by_user.values(), key=lambda item: str(item.user_id)))
    report.total_cents = sum(line.cents for line in report.lines)
    return report


def open_ledger(
    session: Session,
    *,
    dry_run: bool = True,
    now: datetime | None = None,
) -> OpeningReport:
    """Executa a abertura de forma idempotente por `opening:{user}`."""

    report = compute_opening(session)
    if dry_run:
        return report
    service = LedgerService(session)
    equity = service.account(OPENING_EQUITY, "equity")
    for line in report.lines:
        credit = service.account(
            player_credit_code(line.user_id),
            "liability",
            owner_kind="user",
            owner_id=line.user_id,
        )
        _, created = service.post(
            kind="opening_balance",
            ref_type="ledger_opening",
            ref_id=line.user_id,
            idempotency_key=f"opening:{line.user_id}",
            postings=[
                LedgerPosting(equity, "D", line.cents),
                LedgerPosting(credit, "C", line.cents),
            ],
            occurred_at=now,
        )
        if created:
            report.created += 1
    return report


__all__ = ["OpeningLine", "OpeningReport", "compute_opening", "open_ledger"]
