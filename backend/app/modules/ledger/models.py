"""Ledger de dupla entrada em centavos (ADR 0049 §9.2).

As tabelas são append-only: correção é transação compensatória, nunca UPDATE.
`booking_payments` continua sendo o registro do PSP; este módulo é o ledger
contábil independente do provedor.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

ACCOUNT_KINDS = ("asset", "liability", "revenue", "expense", "equity")
OWNER_KINDS = ("user", "venue", "joga")
CUSTODY_MODELS = ("B", "C")
DIRECTIONS = ("D", "C")


class LedgerAccount(Base):
    """Conta do plano de contas; contas por dono usam código com UUID."""

    __tablename__ = "ledger_accounts"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('asset', 'liability', 'revenue', 'expense', 'equity')",
            name="kind_valid",
        ),
        CheckConstraint(
            "owner_kind IS NULL OR owner_kind IN ('user', 'venue', 'joga')",
            name="owner_kind_valid",
        ),
        CheckConstraint(
            "(owner_kind IS NULL) = (owner_id IS NULL)",
            name="owner_pair_valid",
        ),
        CheckConstraint("custody_model IN ('B', 'C')", name="custody_model_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    owner_kind: Mapped[str | None] = mapped_column(String(10), nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    custody_model: Mapped[str] = mapped_column(
        String(1), nullable=False, default="B", server_default=text("'B'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class LedgerTransaction(Base):
    """Evento contábil idempotente; agrupa as partidas de débito e crédito."""

    __tablename__ = "ledger_transactions"
    __table_args__ = (
        CheckConstraint("custody_model IN ('B', 'C')", name="custody_model_valid"),
        Index("ix_ledger_transactions_ref", "ref_type", "ref_id"),
        Index("ix_ledger_transactions_occurred", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    ref_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ref_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    custody_model: Mapped[str] = mapped_column(String(1), nullable=False, default="B")
    reverses_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class LedgerEntry(Base):
    """Partida de uma transação; sinal é a direção, nunca valor negativo."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("direction IN ('D', 'C')", name="direction_valid"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        Index("ix_ledger_entries_account", "account_id"),
        Index("ix_ledger_entries_transaction", "transaction_id"),
        Index(
            "uq_ledger_entries_transaction_account_direction",
            "transaction_id",
            "account_id",
            "direction",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(1), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
