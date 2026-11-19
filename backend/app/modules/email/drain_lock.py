"""Lock de drenagem compartilhado entre a API e o worker do GitHub.

A Outbox de e-mail pode ser drenada por dois caminhos: a task inline da API e o
workflow agendado. O advisory lock do PostgreSQL garante que apenas um ciclo
seleciona e envia mensagens por vez, sem tabela de coordenação nem transação
longa. Em SQLite (suíte de testes) o lock não existe e o ciclo é sempre
concedido.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger("joga.email")

# Chave estável (int8) exclusiva da drenagem de e-mail. Não reutilizar.
EMAIL_DRAIN_LOCK_KEY = 4_426_433_101


def _lock_engine(bind: Engine | Connection) -> Engine:
    return bind.engine if isinstance(bind, Connection) else bind


@contextmanager
def email_drain_lock(bind: Engine | Connection) -> Iterator[bool]:
    """Tenta o lock; devolve ``False`` quando outro processo já está drenando.

    O lock é de sessão no PostgreSQL e precisa ser liberado explicitamente: sem
    isso, a conexão devolvida ao pool continuaria segurando a drenagem.
    """
    engine = _lock_engine(bind)
    if engine.dialect.name != "postgresql":
        yield True
        return

    with engine.connect() as connection:
        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": EMAIL_DRAIN_LOCK_KEY},
            ).scalar()
        )
        if not acquired:
            connection.rollback()
            yield False
            return
        try:
            yield True
        finally:
            try:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"),
                    {"key": EMAIL_DRAIN_LOCK_KEY},
                )
                connection.commit()
            except Exception:
                # A conexão caiu: o servidor libera o lock ao encerrar a sessão.
                logger.warning("e-mail: falha ao liberar o lock de drenagem", exc_info=True)


__all__ = ["EMAIL_DRAIN_LOCK_KEY", "email_drain_lock"]
