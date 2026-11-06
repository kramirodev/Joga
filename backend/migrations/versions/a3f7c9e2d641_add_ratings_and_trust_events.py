"""add ratings and trust events

Revision ID: a3f7c9e2d641
Revises: f2b5d8e1a7c3
Create Date: 2026-11-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3f7c9e2d641"
down_revision: str | Sequence[str] | None = "f2b5d8e1a7c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria contas de rating, eventos e sinais de confiança."""
    op.create_table(
        "rating_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("format_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("rating_deviation", sa.Float(), nullable=False),
        sa.Column("volatility", sa.Float(), nullable=False),
        sa.Column("matches_played", sa.Integer(), nullable=False),
        sa.Column("last_rated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("algorithm_version", sa.String(length=40), nullable=False),
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
        sa.CheckConstraint("rating_deviation >= 0", name="rating_deviation_non_negative"),
        sa.CheckConstraint("volatility > 0", name="volatility_positive"),
        sa.CheckConstraint("matches_played >= 0", name="matches_played_non_negative"),
        sa.ForeignKeyConstraint(
            ["format_id"],
            ["sport_formats.id"],
            name="fk_rating_accounts_format_id_sport_formats",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_rating_accounts_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rating_accounts"),
        sa.UniqueConstraint(
            "user_id",
            "format_id",
            name="uq_rating_account_user_format",
        ),
    )
    op.create_index("ix_rating_accounts_user_id", "rating_accounts", ["user_id"])
    op.create_index("ix_rating_accounts_format_id", "rating_accounts", ["format_id"])
    op.create_index(
        "ix_rating_account_format_rating",
        "rating_accounts",
        ["format_id", "rating"],
    )

    op.create_table(
        "rating_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("format_id", sa.Uuid(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=40), nullable=False),
        sa.Column("result", sa.String(length=10), nullable=False),
        sa.Column("expected_score", sa.Float(), nullable=False),
        sa.Column("rating_before", sa.Float(), nullable=False),
        sa.Column("rating_after", sa.Float(), nullable=False),
        sa.Column("rating_deviation_before", sa.Float(), nullable=False),
        sa.Column("rating_deviation_after", sa.Float(), nullable=False),
        sa.Column("volatility_before", sa.Float(), nullable=False),
        sa.Column("volatility_after", sa.Float(), nullable=False),
        sa.Column("delta", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("result IN ('WIN', 'LOSS', 'DRAW')", name="result_valid"),
        sa.CheckConstraint(
            "rating_deviation_before >= 0",
            name="rd_before_non_negative",
        ),
        sa.CheckConstraint(
            "rating_deviation_after >= 0",
            name="rd_after_non_negative",
        ),
        sa.CheckConstraint("volatility_before > 0", name="volatility_before_positive"),
        sa.CheckConstraint("volatility_after > 0", name="volatility_after_positive"),
        sa.ForeignKeyConstraint(
            ["format_id"],
            ["sport_formats.id"],
            name="fk_rating_events_format_id_sport_formats",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_rating_events_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_rating_events_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rating_events"),
        sa.UniqueConstraint(
            "match_id",
            "user_id",
            "algorithm_version",
            name="uq_rating_event_match_user_version",
        ),
    )
    op.create_index("ix_rating_events_match_id", "rating_events", ["match_id"])
    op.create_index("ix_rating_events_user_id", "rating_events", ["user_id"])
    op.create_index("ix_rating_events_format_id", "rating_events", ["format_id"])
    op.create_index(
        "ix_rating_event_user_format_created",
        "rating_events",
        ["user_id", "format_id", "created_at"],
    )

    op.create_table(
        "trust_accounts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="score_range_valid"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_trust_accounts_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_trust_accounts"),
    )

    op.create_table(
        "trust_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.SmallInteger(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("severity BETWEEN 0 AND 5", name="severity_range_valid"),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_trust_events_match_id_matches",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_trust_events_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trust_events"),
    )
    op.create_index("ix_trust_events_user_id", "trust_events", ["user_id"])
    op.create_index(
        "ix_trust_event_user_created",
        "trust_events",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    """Remove tabelas de rating e confiança."""
    op.drop_index("ix_trust_event_user_created", table_name="trust_events")
    op.drop_index("ix_trust_events_user_id", table_name="trust_events")
    op.drop_table("trust_events")
    op.drop_table("trust_accounts")
    op.drop_index("ix_rating_event_user_format_created", table_name="rating_events")
    op.drop_index("ix_rating_events_format_id", table_name="rating_events")
    op.drop_index("ix_rating_events_user_id", table_name="rating_events")
    op.drop_index("ix_rating_events_match_id", table_name="rating_events")
    op.drop_table("rating_events")
    op.drop_index("ix_rating_account_format_rating", table_name="rating_accounts")
    op.drop_index("ix_rating_accounts_format_id", table_name="rating_accounts")
    op.drop_index("ix_rating_accounts_user_id", table_name="rating_accounts")
    op.drop_table("rating_accounts")
