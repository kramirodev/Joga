"""add substitution queue and refund exclusions

Revision ID: f4b5c6d7e8f9
Revises: c15a1b2c3d4e
Create Date: 2026-11-09 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4b5c6d7e8f9"
down_revision: str | Sequence[str] | None = "c15a1b2c3d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "booking_participants",
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "lobby_substitutes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lobby_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="STANDBY", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('STANDBY', 'CALLED', 'CONFIRMED', 'PLAYED', 'DECLINED', 'NO_SHOW')",
            name=op.f("ck_lobby_substitutes_status_valid"),
        ),
        sa.CheckConstraint("position > 0", name=op.f("ck_lobby_substitutes_position_positive")),
        sa.ForeignKeyConstraint(
            ["lobby_id"],
            ["lobbies.id"],
            name=op.f("fk_lobby_substitutes_lobby_id_lobbies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_lobby_substitutes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lobby_substitutes")),
        sa.UniqueConstraint("lobby_id", "user_id", name="uq_lobby_substitutes_user"),
    )
    op.create_index(
        "ix_lobby_substitutes_lobby_status",
        "lobby_substitutes",
        ["lobby_id", "status", "position"],
        unique=False,
    )
    op.create_index(
        "ix_lobby_substitutes_user_id",
        "lobby_substitutes",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "booking_substitutions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("seat", sa.SmallInteger(), nullable=False),
        sa.Column("outgoing_user_id", sa.Uuid(), nullable=False),
        sa.Column("filled_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'FILLED', 'EXPIRED', 'CANCELLED')",
            name=op.f("ck_booking_substitutions_status_valid"),
        ),
        sa.CheckConstraint("seat > 0", name=op.f("ck_booking_substitutions_seat_positive")),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_booking_substitutions_booking_id_bookings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["filled_by_user_id"],
            ["users.id"],
            name=op.f("fk_booking_substitutions_filled_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["outgoing_user_id"],
            ["users.id"],
            name=op.f("fk_booking_substitutions_outgoing_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_substitutions")),
    )
    op.create_index(
        "ix_booking_substitutions_booking_status",
        "booking_substitutions",
        ["booking_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_booking_substitutions_deadline",
        "booking_substitutions",
        ["status", "deadline_at"],
        unique=False,
    )
    op.create_index(
        "uq_booking_substitutions_open_seat",
        "booking_substitutions",
        ["booking_id", "seat"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )

    op.create_table(
        "booking_refund_exclusions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_booking_refund_exclusions_booking_id_bookings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_booking_refund_exclusions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_refund_exclusions")),
        sa.UniqueConstraint(
            "booking_id",
            "user_id",
            name="uq_booking_refund_exclusions_user",
        ),
    )
    op.create_index(
        "ix_booking_refund_exclusions_booking",
        "booking_refund_exclusions",
        ["booking_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_booking_refund_exclusions_booking",
        table_name="booking_refund_exclusions",
    )
    op.drop_table("booking_refund_exclusions")
    op.drop_index(
        "uq_booking_substitutions_open_seat",
        table_name="booking_substitutions",
    )
    op.drop_index(
        "ix_booking_substitutions_deadline",
        table_name="booking_substitutions",
    )
    op.drop_index(
        "ix_booking_substitutions_booking_status",
        table_name="booking_substitutions",
    )
    op.drop_table("booking_substitutions")
    op.drop_index("ix_lobby_substitutes_user_id", table_name="lobby_substitutes")
    op.drop_index(
        "ix_lobby_substitutes_lobby_status",
        table_name="lobby_substitutes",
    )
    op.drop_table("lobby_substitutes")
    op.drop_column("booking_participants", "left_at")
