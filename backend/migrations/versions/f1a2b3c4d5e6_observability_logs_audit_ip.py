"""observabilidade: log_events, contexto em segurança/auditoria

Revision ID: f1a2b3c4d5e6
Revises: e2f3a4b5c6d7
Create Date: 2026-11-25 00:00:00.000000

Adiciona a tabela ``log_events`` (eventos operacionais com retenção curta),
estende ``security_events`` e ``audit_logs`` com contexto de requisição (IP
completo + hash, request_id, endpoint, user-agent e resultado) e impede
UPDATE/DELETE em ``audit_logs`` no PostgreSQL. Migração aditiva: todas as
colunas novas são anuláveis e não há backfill obrigatório.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_TRIGGER = "trg_audit_logs_append_only"
AUDIT_FUNCTION = "prevent_audit_log_mutation"


def audit_guard_function_sql(*, schema: str | None = None) -> str:
    """Função do gatilho append-only (compatível com schema de migração).

    A única mutação permitida é a integridade referencial: ``ON DELETE SET
    NULL`` pode anular ``actor_user_id`` e/ou ``organization_id``. Qualquer
    outra alteração — inclusive DELETE — é recusada. A comparação usa
    ``to_jsonb`` para exigir que todas as demais colunas permaneçam idênticas.
    """
    prefix = f"{schema}." if schema else ""
    return f"""
        CREATE OR REPLACE FUNCTION {prefix}{AUDIT_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'audit_logs is append-only';
            END IF;

            -- Cada FK só pode mudar para NULL; NULL -> valor continua proibido.
            IF (NEW.actor_user_id IS NULL OR NEW.actor_user_id = OLD.actor_user_id)
               AND (NEW.organization_id IS NULL
                    OR NEW.organization_id = OLD.organization_id)
               AND (to_jsonb(OLD) - 'actor_user_id' - 'organization_id')
                   = (to_jsonb(NEW) - 'actor_user_id' - 'organization_id')
            THEN
                RETURN NEW;
            END IF;

            RAISE EXCEPTION 'audit_logs is append-only';
        END;
        $$;
    """


def audit_guard_trigger_sql(*, schema: str | None = None) -> str:
    prefix = f"{schema}." if schema else ""
    return f"""
        CREATE TRIGGER {AUDIT_TRIGGER}
        BEFORE UPDATE OR DELETE ON {prefix}audit_logs
        FOR EACH ROW EXECUTE FUNCTION {prefix}{AUDIT_FUNCTION}();
    """


def _revoke_from_api_roles(statement: str) -> None:
    """Revoga de ``anon``/``authenticated`` quando esses papéis existirem."""
    op.execute(
        f"""
        DO $$
        DECLARE role_name text;
        BEGIN
            FOREACH role_name IN ARRAY ARRAY['anon'::text, 'authenticated'::text] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                    EXECUTE format('{statement}', role_name);
                END IF;
            END LOOP;
        END $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        "log_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("level", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("endpoint", sa.String(length=255), nullable=True),
        sa.Column("status", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("stack", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "level IN ('debug', 'info', 'warn', 'error', 'fatal')",
            name="ck_log_events_level_valid",
        ),
        sa.CheckConstraint(
            "category IN ('http', 'app', 'security', 'audit', 'job', 'client')",
            name="ck_log_events_category_valid",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_log_events_occurred_at",
        "log_events",
        ["occurred_at"],
        postgresql_using="brin",
    )
    op.create_index("ix_log_events_level_occurred_at", "log_events", ["level", "occurred_at"])
    op.create_index(
        "ix_log_events_category_occurred_at",
        "log_events",
        ["category", "occurred_at"],
    )
    op.create_index("ix_log_events_request_id", "log_events", ["request_id"])
    op.create_index("ix_log_events_user_occurred_at", "log_events", ["user_id", "occurred_at"])
    op.create_index("ix_log_events_ip_hash_occurred_at", "log_events", ["ip_hash", "occurred_at"])
    op.create_index("ix_log_events_status_occurred_at", "log_events", ["status", "occurred_at"])
    op.execute("ALTER TABLE log_events ENABLE ROW LEVEL SECURITY")
    _revoke_from_api_roles("REVOKE ALL ON TABLE log_events FROM %I")

    for table in ("security_events", "audit_logs"):
        op.add_column(table, sa.Column("ip", sa.String(length=45), nullable=True))
        if table == "audit_logs":
            op.add_column(table, sa.Column("ip_hash", sa.String(length=64), nullable=True))
        op.add_column(table, sa.Column("request_id", sa.String(length=64), nullable=True))
        op.add_column(table, sa.Column("endpoint", sa.String(length=255), nullable=True))
        op.add_column(table, sa.Column("user_agent", sa.String(length=512), nullable=True))
        op.add_column(table, sa.Column("result", sa.String(length=20), nullable=True))

    op.create_index("ix_security_events_ip_created", "security_events", ["ip", "created_at"])
    op.create_index("ix_security_events_request_id", "security_events", ["request_id"])
    op.create_index("ix_audit_logs_ip_created", "audit_logs", ["ip", "created_at"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])

    op.execute(audit_guard_function_sql())
    op.execute(audit_guard_trigger_sql())
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_FUNCTION}() FROM PUBLIC")
    _revoke_from_api_roles(f"REVOKE ALL ON FUNCTION {AUDIT_FUNCTION}() FROM %I")


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {AUDIT_TRIGGER} ON audit_logs")
    op.execute(f"DROP FUNCTION IF EXISTS {AUDIT_FUNCTION}()")

    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_ip_created", table_name="audit_logs")
    op.drop_index("ix_security_events_request_id", table_name="security_events")
    op.drop_index("ix_security_events_ip_created", table_name="security_events")

    for table in ("audit_logs", "security_events"):
        op.drop_column(table, "result")
        op.drop_column(table, "user_agent")
        op.drop_column(table, "endpoint")
        op.drop_column(table, "request_id")
        if table == "audit_logs":
            op.drop_column(table, "ip_hash")
        op.drop_column(table, "ip")

    op.drop_index("ix_log_events_status_occurred_at", table_name="log_events")
    op.drop_index("ix_log_events_ip_hash_occurred_at", table_name="log_events")
    op.drop_index("ix_log_events_user_occurred_at", table_name="log_events")
    op.drop_index("ix_log_events_request_id", table_name="log_events")
    op.drop_index("ix_log_events_category_occurred_at", table_name="log_events")
    op.drop_index("ix_log_events_level_occurred_at", table_name="log_events")
    op.drop_index("ix_log_events_occurred_at", table_name="log_events")
    op.drop_table("log_events")
