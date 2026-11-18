"""add cpf columns and fiscal document takers

Revision ID: q1b2c3d4e5f6
Revises: p0a1b2c3d4e5
Create Date: 2026-11-17 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "q1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "p0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # CPF cifrado no perfil (ADR 0049 §9.3). Nenhuma coluna guarda texto claro.
    op.add_column("user_profiles", sa.Column("cpf_ciphertext", sa.LargeBinary(), nullable=True))
    op.add_column("user_profiles", sa.Column("cpf_key_id", sa.String(length=20), nullable=True))
    op.add_column("user_profiles", sa.Column("cpf_last2", sa.String(length=2), nullable=True))
    op.add_column(
        "user_profiles",
        sa.Column("cpf_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "cpf_present_consistent",
        "user_profiles",
        "(cpf_ciphertext IS NULL AND cpf_key_id IS NULL AND cpf_last2 IS NULL) "
        "OR (cpf_ciphertext IS NOT NULL AND cpf_key_id IS NOT NULL AND cpf_last2 IS NOT NULL)",
    )

    # A intenção fiscal continua uma por reserva; os tomadores efetivos são um
    # por jogador, com a cota e o CPF cifrado no instante da emissão.
    op.create_table(
        "fiscal_document_takers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_document_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("cpf_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("cpf_key_id", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount_cents >= 0", name="amount_non_negative"),
        sa.ForeignKeyConstraint(
            ["fiscal_document_id"], ["fiscal_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fiscal_document_id",
            "user_id",
            name="uq_fiscal_document_takers_document_user",
        ),
    )
    op.create_index(
        "ix_fiscal_document_takers_user_created",
        "fiscal_document_takers",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fiscal_document_takers_user_created",
        table_name="fiscal_document_takers",
    )
    op.drop_table("fiscal_document_takers")
    op.drop_constraint("cpf_present_consistent", "user_profiles", type_="check")
    op.drop_column("user_profiles", "cpf_updated_at")
    op.drop_column("user_profiles", "cpf_last2")
    op.drop_column("user_profiles", "cpf_key_id")
    op.drop_column("user_profiles", "cpf_ciphertext")
