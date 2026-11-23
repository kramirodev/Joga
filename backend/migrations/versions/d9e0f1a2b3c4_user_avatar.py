"""avatar do jogador com importação do Instagram

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-11-23 20:00:00.000000

Cria ``user_avatars`` como tabela dedicada (uma linha por usuário). O avatar de
presets continua na identidade visual existente; esta tabela guarda apenas a
foto real e os metadados da importação temporária. ``source_url`` é a página
pública informada pelo jogador, nunca a URL assinada da CDN.

O downgrade remove a tabela. Os arquivos físicos do storage privado não são
gerenciados pela migração; a remoção normal passa pelo endpoint autenticado.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: str | Sequence[str] | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_avatars",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("source_url", sa.String(length=300), nullable=True),
        sa.Column("storage_key", sa.String(length=64), nullable=True),
        sa.Column("content_type", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "source IN ('instagram_scrape', 'preset', 'upload')",
            name="source_valid",
        ),
        sa.CheckConstraint(
            "source <> 'instagram_scrape' OR (storage_key IS NOT NULL AND imported_at IS NOT NULL)",
            name="instagram_scrape_complete",
        ),
        sa.CheckConstraint(
            "storage_key IS NULL OR "
            "(content_type IS NOT NULL AND size_bytes IS NOT NULL "
            "AND width IS NOT NULL AND height IS NOT NULL)",
            name="storage_fields_complete",
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="size_non_negative",
        ),
        sa.CheckConstraint(
            "width IS NULL OR width > 0",
            name="width_positive",
        ),
        sa.CheckConstraint(
            "height IS NULL OR height > 0",
            name="height_positive",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_avatars_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_avatars"),
    )


def downgrade() -> None:
    op.drop_table("user_avatars")
