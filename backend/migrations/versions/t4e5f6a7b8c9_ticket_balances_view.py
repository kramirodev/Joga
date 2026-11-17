"""ticket balances as a view over ticket lots

Revision ID: t4e5f6a7b8c9
Revises: s3d4e5f6a7b8
Create Date: 2026-11-17 12:00:00.000000

A Etapa 9 aposenta ``ticket_balances`` como tabela. O saldo legado sem lote é
convertido em lote ``admin`` (com evento em ``ticket_ledger``) e a tabela vira
uma view somente leitura sobre os lotes utilizáveis.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "t4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "s3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LEGACY_LOTS = """
INSERT INTO ticket_lots (
    id, user_id, source, original_amount, remaining, ref_type, ledger_entry_id, created_at
)
SELECT
    gen_random_uuid(),
    tb.user_id,
    'admin',
    tb.balance,
    tb.balance,
    'legacy_balance',
    (
        SELECT tl.id
        FROM ticket_ledger tl
        WHERE tl.idempotency_key = 'legacy_lot:' || tb.user_id::text || ':' || tb.balance::text
          AND NOT EXISTS (SELECT 1 FROM ticket_lots used WHERE used.ledger_entry_id = tl.id)
        LIMIT 1
    ),
    now()
FROM ticket_balances tb
WHERE tb.balance > 0
  AND NOT EXISTS (
      SELECT 1 FROM ticket_lots l WHERE l.user_id = tb.user_id AND l.remaining > 0
  );
"""

TICKET_BALANCES_VIEW = """
CREATE VIEW ticket_balances AS
SELECT
    l.user_id,
    SUM(l.remaining)::integer AS balance,
    MAX(l.created_at) AS updated_at
FROM ticket_lots l
WHERE l.remaining > 0
  AND (
      (l.source = 'pass' AND l.period = to_char((now() AT TIME ZONE 'UTC'), 'YYYY-MM'))
      OR (l.source IN ('purchase', 'refund') AND l.expires_at IS NULL)
      OR (
          l.source IN ('free_level', 'admin')
          AND (l.expires_at IS NULL OR l.expires_at > now())
      )
  )
GROUP BY l.user_id;
"""


def upgrade() -> None:
    # 1. Todo saldo legado sem lote ganha lote administrativo auditável.
    op.execute(
        """
        INSERT INTO ticket_ledger (
            id, user_id, amount, source, ref_type, idempotency_key, created_at
        )
        SELECT
            gen_random_uuid(),
            tb.user_id,
            tb.balance,
            'admin',
            'legacy_balance',
            'legacy_lot:' || tb.user_id::text || ':' || tb.balance::text,
            now()
        FROM ticket_balances tb
        WHERE tb.balance > 0
          AND NOT EXISTS (
              SELECT 1 FROM ticket_lots l
              WHERE l.user_id = tb.user_id AND l.remaining > 0
          )
        ON CONFLICT (idempotency_key) DO NOTHING;
        """
    )
    op.execute(LEGACY_LOTS)

    # 2. A tabela deixa de existir; a view preserva a leitura de compatibilidade.
    op.execute("DROP TABLE ticket_balances")
    op.execute(TICKET_BALANCES_VIEW)


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE ticket_balances_restore (
            user_id uuid NOT NULL,
            balance integer NOT NULL DEFAULT 0,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ticket_balances_restore_pkey PRIMARY KEY (user_id),
            CONSTRAINT ticket_balances_restore_balance_check CHECK (balance >= 0),
            CONSTRAINT ticket_balances_restore_user_fk
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """
    )
    op.execute(
        """
        INSERT INTO ticket_balances_restore (user_id, balance, updated_at)
        SELECT user_id, balance, updated_at FROM ticket_balances;
        """
    )
    op.execute("DROP VIEW ticket_balances")
    op.execute("ALTER TABLE ticket_balances_restore RENAME TO ticket_balances")
    op.execute(
        "ALTER TABLE ticket_balances RENAME CONSTRAINT ticket_balances_restore_pkey "
        "TO pk_ticket_balances"
    )
    op.execute(
        "ALTER TABLE ticket_balances RENAME CONSTRAINT ticket_balances_restore_balance_check "
        "TO ck_ticket_balances_balance_non_negative"
    )
    op.execute(
        "ALTER TABLE ticket_balances RENAME CONSTRAINT ticket_balances_restore_user_fk "
        "TO fk_ticket_balances_user_id_users"
    )
