"""add match results, disputes and idempotency

Revision ID: e1a4c7d9b230
Revises: d7f2b9c4e615
Create Date: 2026-11-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1a4c7d9b230"
down_revision: str | Sequence[str] | None = "d7f2b9c4e615"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria rodadas, relatos, disputas, revisão e idempotência."""
    op.add_column("matches", sa.Column("final_result", sa.String(length=8), nullable=True))
    op.add_column("matches", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("matches", sa.Column("voided_reason", sa.Text(), nullable=True))
    op.add_column(
        "matches",
        sa.Column(
            "result_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "final_result_valid",
        "matches",
        "final_result IS NULL OR final_result IN ('TEAM_1', 'TEAM_2', 'DRAW')",
    )

    op.add_column(
        "match_participants",
        sa.Column(
            "is_captain",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "match_participants",
        sa.Column("captain_selection_version", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "match_participants",
        sa.Column("captain_selected_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "match_result_eligible_participants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "frozen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_result_eligible_participants_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["match_participants.id"],
            name="fk_result_eligible_participant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_match_result_eligible_participants_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_result_eligible_participants"),
        sa.UniqueConstraint(
            "match_id",
            "participant_id",
            name="uq_result_eligible_participant",
        ),
        sa.UniqueConstraint("match_id", "user_id", name="uq_result_eligible_user"),
    )
    op.create_index(
        "ix_result_eligible_match",
        "match_result_eligible_participants",
        ["match_id"],
    )
    op.create_index(
        "ix_match_result_eligible_participants_user_id",
        "match_result_eligible_participants",
        ["user_id"],
    )

    op.create_table(
        "match_result_rounds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("round_number", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eligible_count", sa.Integer(), nullable=False),
        sa.Column("quorum", sa.Integer(), nullable=False),
        sa.Column("valid_votes", sa.Integer(), nullable=True),
        sa.Column("evaluated_outcome", sa.String(length=8), nullable=True),
        sa.Column("divergent_votes", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=True),
        sa.CheckConstraint("round_number IN (1, 2)", name="round_number_valid"),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED')", name="status_valid"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('FINALIZED', 'SECOND_ROUND', 'DISPUTED', 'REVIEW')",
            name="outcome_valid",
        ),
        sa.CheckConstraint(
            "evaluated_outcome IS NULL OR evaluated_outcome IN ('TEAM_1', 'TEAM_2', 'DRAW')",
            name="evaluated_outcome_valid",
        ),
        sa.CheckConstraint("eligible_count >= 0", name="eligible_non_negative"),
        sa.CheckConstraint("quorum >= 0", name="quorum_non_negative"),
        sa.CheckConstraint(
            "valid_votes IS NULL OR valid_votes >= 0",
            name="valid_non_negative",
        ),
        sa.CheckConstraint(
            "divergent_votes IS NULL OR divergent_votes >= 0",
            name="divergent_non_negative",
        ),
        sa.CheckConstraint("deadline > opens_at", name="time_order_valid"),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_result_rounds_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_result_rounds"),
        sa.UniqueConstraint("match_id", "round_number", name="uq_result_round_match_number"),
    )
    op.create_index("ix_match_result_rounds_match_id", "match_result_rounds", ["match_id"])
    op.create_index("ix_result_round_open_deadline", "match_result_rounds", ["status", "deadline"])

    op.create_table(
        "match_result_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('TEAM_1', 'TEAM_2', 'DRAW')",
            name="outcome_valid",
        ),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["match_result_rounds.id"],
            name="fk_match_result_reports_round_id_match_result_rounds",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["match_participants.id"],
            name="fk_match_result_reports_participant_id_match_participants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_result_reports"),
        sa.UniqueConstraint(
            "round_id",
            "participant_id",
            "idempotency_key",
            name="uq_result_report_idempotency",
        ),
    )
    op.create_index(
        "ix_match_result_reports_participant_id",
        "match_result_reports",
        ["participant_id"],
    )
    op.create_index(
        "ix_result_report_round_participant",
        "match_result_reports",
        ["round_id", "participant_id", "submitted_at"],
    )

    op.create_table(
        "match_result_captain_confirmations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('TEAM_1', 'TEAM_2', 'DRAW')",
            name="outcome_valid",
        ),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["match_result_rounds.id"],
            name="fk_result_captain_confirmation_round",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["match_participants.id"],
            name="fk_result_captain_confirmation_participant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_result_captain_confirmations"),
        sa.UniqueConstraint("round_id", "participant_id", name="uq_confirmation_round_participant"),
        sa.UniqueConstraint(
            "round_id",
            "participant_id",
            "idempotency_key",
            name="uq_confirmation_idempotency",
        ),
    )
    op.create_index(
        "ix_match_result_captain_confirmations_participant_id",
        "match_result_captain_confirmations",
        ["participant_id"],
    )

    op.create_table(
        "match_disputes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "reason IN ('QUORUM', 'DIVERGENCE', 'TIE', 'SECOND_ROUND_50', 'NO_UNIQUE_RESULT')",
            name="reason_valid",
        ),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED')", name="status_valid"),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_disputes_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["match_result_rounds.id"],
            name="fk_match_disputes_round_id_match_result_rounds",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_disputes"),
    )
    op.create_index("ix_match_disputes_match_status", "match_disputes", ["match_id", "status"])

    op.create_table(
        "match_dispute_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dispute_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "char_count BETWEEN 1 AND 2000",
            name="char_count_valid",
        ),
        sa.CheckConstraint("text <> ''", name="text_not_empty"),
        sa.ForeignKeyConstraint(
            ["dispute_id"],
            ["match_disputes.id"],
            name="fk_match_dispute_evidence_dispute_id_match_disputes",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["match_participants.id"],
            name="fk_match_dispute_evidence_participant_id_match_participants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_dispute_evidence"),
        sa.UniqueConstraint("dispute_id", "participant_id", name="uq_dispute_evidence_participant"),
    )
    op.create_index(
        "ix_match_dispute_evidence_dispute_id", "match_dispute_evidence", ["dispute_id"]
    )
    op.create_index(
        "ix_match_dispute_evidence_participant_id",
        "match_dispute_evidence",
        ["participant_id"],
    )

    op.create_table(
        "match_result_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=True),
        sa.Column("signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("conclusion", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "conclusion IN ('INCONCLUSIVE')",
            name="conclusion_valid",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_result_analyses_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["match_result_rounds.id"],
            name="fk_match_result_analyses_round_id_match_result_rounds",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_result_analyses"),
    )
    op.create_index("ix_match_result_analyses_match_id", "match_result_analyses", ["match_id"])

    op.create_table(
        "match_result_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "reason IN ('QUORUM', 'DIVERGENCE', 'TIE', 'SECOND_ROUND_50', 'NO_UNIQUE_RESULT')",
            name="reason_valid",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RESOLVED', 'CANCELLED')",
            name="status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_result_reviews_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["match_result_rounds.id"],
            name="fk_match_result_reviews_round_id_match_result_rounds",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_result_reviews"),
    )
    op.create_index("ix_result_review_match_status", "match_result_reviews", ["match_id", "status"])

    op.create_table(
        "match_result_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("operator_id", sa.String(length=100), nullable=True),
        sa.Column("origin", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('FINALIZE', 'VOID', 'REQUEST_MORE_INFO')",
            name="decision_valid",
        ),
        sa.CheckConstraint(
            "origin IN ('SYSTEM', 'HUMAN')",
            name="origin_valid",
        ),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('TEAM_1', 'TEAM_2', 'DRAW')",
            name="outcome_valid",
        ),
        sa.CheckConstraint("reason <> ''", name="reason_not_empty"),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_result_decisions_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["match_result_reviews.id"],
            name="fk_match_result_decisions_review_id_match_result_reviews",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_result_decisions"),
    )
    op.create_index(
        "ix_match_result_decisions_review_id",
        "match_result_decisions",
        ["review_id"],
    )
    op.create_index(
        "ix_result_decision_match",
        "match_result_decisions",
        ["match_id", "created_at"],
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=200), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "response_status IS NULL OR response_status BETWEEN 100 AND 599",
            name="status_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
    )


def downgrade() -> None:
    """Remove tabelas e colunas de resultado."""
    op.drop_table("idempotency_records")
    op.drop_index("ix_result_decision_match", table_name="match_result_decisions")
    op.drop_index("ix_match_result_decisions_review_id", table_name="match_result_decisions")
    op.drop_table("match_result_decisions")
    op.drop_index("ix_result_review_match_status", table_name="match_result_reviews")
    op.drop_table("match_result_reviews")
    op.drop_index("ix_match_result_analyses_match_id", table_name="match_result_analyses")
    op.drop_table("match_result_analyses")
    op.drop_index("ix_match_dispute_evidence_participant_id", table_name="match_dispute_evidence")
    op.drop_index("ix_match_dispute_evidence_dispute_id", table_name="match_dispute_evidence")
    op.drop_table("match_dispute_evidence")
    op.drop_index("ix_match_disputes_match_status", table_name="match_disputes")
    op.drop_table("match_disputes")
    op.drop_index(
        "ix_match_result_captain_confirmations_participant_id",
        table_name="match_result_captain_confirmations",
    )
    op.drop_table("match_result_captain_confirmations")
    op.drop_index("ix_result_report_round_participant", table_name="match_result_reports")
    op.drop_index("ix_match_result_reports_participant_id", table_name="match_result_reports")
    op.drop_table("match_result_reports")
    op.drop_index("ix_result_round_open_deadline", table_name="match_result_rounds")
    op.drop_index("ix_match_result_rounds_match_id", table_name="match_result_rounds")
    op.drop_table("match_result_rounds")
    op.drop_index(
        "ix_match_result_eligible_participants_user_id",
        table_name="match_result_eligible_participants",
    )
    op.drop_index("ix_result_eligible_match", table_name="match_result_eligible_participants")
    op.drop_table("match_result_eligible_participants")

    op.drop_column("match_participants", "captain_selected_at")
    op.drop_column("match_participants", "captain_selection_version")
    op.drop_column("match_participants", "is_captain")

    op.drop_constraint("final_result_valid", "matches", type_="check")
    op.drop_column("matches", "result_version")
    op.drop_column("matches", "voided_reason")
    op.drop_column("matches", "finalized_at")
    op.drop_column("matches", "final_result")
