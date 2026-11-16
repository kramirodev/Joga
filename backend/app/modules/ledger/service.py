"""Serviço do ledger de dupla entrada (ADR 0049 §9.2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.ledger.models import (
    ACCOUNT_KINDS,
    CUSTODY_MODELS,
    DIRECTIONS,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
)


class LedgerError(Exception):
    """Erro de uso do ledger."""


class LedgerImbalance(LedgerError):
    """Débitos e créditos de uma transação não fecham."""


@dataclass(frozen=True)
class LedgerPosting:
    """Uma partida: conta, direção e valor positivo em centavos."""

    account: LedgerAccount
    direction: str
    amount_cents: int


class LedgerService:
    """Cria contas e lança transações balanceadas de forma idempotente."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def account(
        self,
        code: str,
        kind: str,
        *,
        owner_kind: str | None = None,
        owner_id: uuid.UUID | None = None,
        custody_model: str = "B",
    ) -> LedgerAccount:
        """Devolve a conta existente ou cria uma nova, validando o plano."""

        normalized = code.strip()
        if not normalized:
            raise LedgerError("código da conta é obrigatório")
        if kind not in ACCOUNT_KINDS:
            raise LedgerError(f"tipo de conta inválido: {kind}")
        if custody_model not in CUSTODY_MODELS:
            raise LedgerError(f"modelo de custódia inválido: {custody_model}")
        if (owner_kind is None) != (owner_id is None):
            raise LedgerError("owner_kind e owner_id devem ser informados juntos")

        existing = self.session.scalar(
            select(LedgerAccount).where(LedgerAccount.code == normalized)
        )
        if existing is not None:
            return existing

        account = LedgerAccount(
            code=normalized,
            kind=kind,
            owner_kind=owner_kind,
            owner_id=owner_id,
            custody_model=custody_model,
        )
        self.session.add(account)
        self.session.flush()
        return account

    def post(
        self,
        *,
        kind: str,
        ref_type: str,
        ref_id: uuid.UUID,
        idempotency_key: str,
        postings: list[LedgerPosting],
        occurred_at: datetime | None = None,
        custody_model: str = "B",
        reverses_transaction_id: uuid.UUID | None = None,
    ) -> tuple[LedgerTransaction, bool]:
        """Lança uma transação balanceada; a chave de idempotência manda.

        Devolve ``(transação, criada)``. Replay devolve a transação existente e
        ``False`` sem duplicar partidas.
        """

        key = idempotency_key.strip()
        if not key:
            raise LedgerError("chave de idempotência é obrigatória")
        if custody_model not in CUSTODY_MODELS:
            raise LedgerError(f"modelo de custódia inválido: {custody_model}")

        existing = self.session.scalar(
            select(LedgerTransaction).where(LedgerTransaction.idempotency_key == key)
        )
        if existing is not None:
            return existing, False

        self._validate(postings)
        moment = ensure_utc(occurred_at or utcnow())
        transaction = LedgerTransaction(
            kind=kind,
            ref_type=ref_type,
            ref_id=ref_id,
            idempotency_key=key,
            occurred_at=moment,
            custody_model=custody_model,
            reverses_transaction_id=reverses_transaction_id,
        )
        try:
            with self.session.begin_nested():
                self.session.add(transaction)
                self.session.flush()
                for posting in postings:
                    self.session.add(
                        LedgerEntry(
                            transaction_id=transaction.id,
                            account_id=posting.account.id,
                            direction=posting.direction,
                            amount_cents=posting.amount_cents,
                        )
                    )
                self.session.flush()
        except IntegrityError:
            concurrent = self.session.scalar(
                select(LedgerTransaction).where(LedgerTransaction.idempotency_key == key)
            )
            if concurrent is not None:
                return concurrent, False
            raise
        return transaction, True

    def entries_for(self, transaction_id: uuid.UUID) -> list[LedgerEntry]:
        return list(
            self.session.scalars(
                select(LedgerEntry)
                .where(LedgerEntry.transaction_id == transaction_id)
                .order_by(LedgerEntry.created_at, LedgerEntry.id)
            ).all()
        )

    def balance_cents(self, account: LedgerAccount) -> int:
        """Saldo natural da conta: ativo/despesa D−C; demais C−D."""

        debit = func.coalesce(
            func.sum(
                case(
                    (LedgerEntry.direction == "D", LedgerEntry.amount_cents),
                    else_=0,
                )
            ),
            0,
        )
        credit = func.coalesce(
            func.sum(
                case(
                    (LedgerEntry.direction == "C", LedgerEntry.amount_cents),
                    else_=0,
                )
            ),
            0,
        )
        row = self.session.execute(
            select(debit, credit).where(LedgerEntry.account_id == account.id)
        ).one()
        debits = int(row[0] or 0)
        credits = int(row[1] or 0)
        if account.kind in {"asset", "expense"}:
            return debits - credits
        return credits - debits

    def balance_for_code(self, code: str) -> int:
        account = self.session.scalar(select(LedgerAccount).where(LedgerAccount.code == code))
        if account is None:
            raise LedgerError(f"conta inexistente: {code}")
        return self.balance_cents(account)

    def _validate(self, postings: list[LedgerPosting]) -> None:
        if len(postings) < 2:
            raise LedgerError("uma transação exige ao menos duas partidas")
        seen: set[tuple[uuid.UUID, str]] = set()
        debits = 0
        credits = 0
        for posting in postings:
            if posting.direction not in DIRECTIONS:
                raise LedgerError(f"direção inválida: {posting.direction}")
            if posting.amount_cents <= 0:
                raise LedgerError("valor da partida deve ser positivo")
            if posting.account.id is None:
                raise LedgerError("conta da partida não foi persistida")
            marker = (posting.account.id, posting.direction)
            if marker in seen:
                raise LedgerError("partida duplicada para a mesma conta e direção")
            seen.add(marker)
            if posting.direction == "D":
                debits += posting.amount_cents
            else:
                credits += posting.amount_cents
        if debits != credits:
            raise LedgerImbalance(f"transação desbalanceada: D={debits} C={credits}")
