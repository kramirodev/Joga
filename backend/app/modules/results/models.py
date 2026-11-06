"""Modelos de relatos, rodadas, disputas e decisões de resultado."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.modules.identity.clock import utcnow

OUTCOMES = ("TEAM_1", "TEAM_2", "DRAW")
ROUND_STATUSES = ("OPEN", "CLOSED")
ROUND_OUTCOMES = ("FINALIZED", "SECOND_ROUND", "DISPUTED", "REVIEW")
REVIEW_REASONS = ("QUORUM", "DIVERGENCE", "TIE", "SECOND_ROUND_50", "NO_UNIQUE_RESULT")
REVIEW_STATUSES = ("PENDING", "RESOLVED", "CANCELLED")
DISPUTE_STATUSES = ("OPEN", "CLOSED")
DECISIONS = ("FINALIZE", "VOID", "REQUEST_MORE_INFO")
DECISION_ORIGINS = ("SYSTEM", "HUMAN")
ANALYSIS_CONCLUSIONS = ("INCONCLUSIVE",)

MAX_EVIDENCE_CHARS = 2000


class MatchResultEligibleParticipant(Base):
    """Conjunto de elegíveis congelado na abertura da primeira rodada."""

    __tablename__ = "match_result_eligible_participants"
    __table_args__ = (
        UniqueConstraint("match_id", "participant_id", name="uq_result_eligible_participant"),
        UniqueConstraint("match_id", "user_id", name="uq_result_eligible_user"),
        Index("ix_result_eligible_match", "match_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "match_participants.id",
            ondelete="CASCADE",
            name="fk_result_eligible_participant",
        ),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frozen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class MatchResultRound(Base):
    """Rodada de relato (1 ou 2) e seu resultado consolidado."""

    __tablename__ = "match_result_rounds"
    __table_args__ = (
        CheckConstraint("round_number IN (1, 2)", name="round_number_valid"),
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="status_valid"),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('FINALIZED', 'SECOND_ROUND', 'DISPUTED', 'REVIEW')",
            name="outcome_valid",
        ),
        CheckConstraint(
            "evaluated_outcome IS NULL OR evaluated_outcome IN ('TEAM_1', 'TEAM_2', 'DRAW')",
            name="evaluated_outcome_valid",
        ),
        CheckConstraint("eligible_count >= 0", name="eligible_non_negative"),
        CheckConstraint("quorum >= 0", name="quorum_non_negative"),
        CheckConstraint("valid_votes IS NULL OR valid_votes >= 0", name="valid_non_negative"),
        CheckConstraint(
            "divergent_votes IS NULL OR divergent_votes >= 0", name="divergent_non_negative"
        ),
        CheckConstraint("deadline > opens_at", name="time_order_valid"),
        UniqueConstraint("match_id", "round_number", name="uq_result_round_match_number"),
        Index("ix_result_round_open_deadline", "status", "deadline"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    round_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="OPEN")
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eligible_count: Mapped[int] = mapped_column(Integer, nullable=False)
    quorum: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluated_outcome: Mapped[str | None] = mapped_column(String(8), nullable=True)
    divergent_votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)


class MatchResultReport(Base):
    """Relato individual append-only; na rodada 2 o último envio é o efetivo."""

    __tablename__ = "match_result_reports"
    __table_args__ = (
        CheckConstraint("outcome IN ('TEAM_1', 'TEAM_2', 'DRAW')", name="outcome_valid"),
        UniqueConstraint(
            "round_id",
            "participant_id",
            "idempotency_key",
            name="uq_result_report_idempotency",
        ),
        Index("ix_result_report_round_participant", "round_id", "participant_id", "submitted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("match_result_rounds.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("match_participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class MatchResultCaptainConfirmation(Base):
    """Confirmação do capitão; registro separado, não conta como voto."""

    __tablename__ = "match_result_captain_confirmations"
    __table_args__ = (
        CheckConstraint("outcome IN ('TEAM_1', 'TEAM_2', 'DRAW')", name="outcome_valid"),
        UniqueConstraint("round_id", "participant_id", name="uq_confirmation_round_participant"),
        UniqueConstraint(
            "round_id",
            "participant_id",
            "idempotency_key",
            name="uq_confirmation_idempotency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "match_result_rounds.id",
            ondelete="CASCADE",
            name="fk_result_captain_confirmation_round",
        ),
        nullable=False,
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "match_participants.id",
            ondelete="CASCADE",
            name="fk_result_captain_confirmation_participant",
        ),
        nullable=False,
        index=True,
    )
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class MatchDispute(Base):
    """Disputa aberta para todo caso encaminhado à revisão humana."""

    __tablename__ = "match_disputes"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('QUORUM', 'DIVERGENCE', 'TIE', 'SECOND_ROUND_50', 'NO_UNIQUE_RESULT')",
            name="reason_valid",
        ),
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="status_valid"),
        Index("ix_match_disputes_match_status", "match_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    round_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("match_result_rounds.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="OPEN")
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchDisputeEvidence(Base):
    """Justificativa textual privada, uma por participante por disputa."""

    __tablename__ = "match_dispute_evidence"
    __table_args__ = (
        UniqueConstraint("dispute_id", "participant_id", name="uq_dispute_evidence_participant"),
        CheckConstraint("char_count BETWEEN 1 AND 2000", name="char_count_valid"),
        CheckConstraint("text <> ''", name="text_not_empty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dispute_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("match_disputes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("match_participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class MatchResultAnalysis(Base):
    """Parecer interno da Fase 7; sempre inconclusivo e enviado à revisão."""

    __tablename__ = "match_result_analyses"
    __table_args__ = (CheckConstraint("conclusion IN ('INCONCLUSIVE')", name="conclusion_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    round_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("match_result_rounds.id", ondelete="SET NULL"), nullable=True
    )
    signals: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    conclusion: Mapped[str] = mapped_column(String(20), nullable=False, default="INCONCLUSIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class MatchResultReview(Base):
    """Revisão humana pendente ou resolvida para uma partida."""

    __tablename__ = "match_result_reviews"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('QUORUM', 'DIVERGENCE', 'TIE', 'SECOND_ROUND_50', 'NO_UNIQUE_RESULT')",
            name="reason_valid",
        ),
        CheckConstraint("status IN ('PENDING', 'RESOLVED', 'CANCELLED')", name="status_valid"),
        Index("ix_result_review_match_status", "match_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    round_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("match_result_rounds.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchResultDecision(Base):
    """Decisão auditável tomada por operador humano."""

    __tablename__ = "match_result_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('FINALIZE', 'VOID', 'REQUEST_MORE_INFO')", name="decision_valid"
        ),
        CheckConstraint("origin IN ('SYSTEM', 'HUMAN')", name="origin_valid"),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('TEAM_1', 'TEAM_2', 'DRAW')",
            name="outcome_valid",
        ),
        CheckConstraint("reason <> ''", name="reason_not_empty"),
        Index("ix_result_decision_match", "match_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("match_result_reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(8), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    operator_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    origin: Mapped[str] = mapped_column(String(10), nullable=False, default="HUMAN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
