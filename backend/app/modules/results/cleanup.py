"""Limpeza de dados de resultado conforme retenção provisória."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.matches.models import Match
from app.modules.ratelimit.models import RateLimitCounter
from app.modules.results.models import (
    MatchDispute,
    MatchDisputeEvidence,
    MatchResultAnalysis,
    MatchResultCaptainConfirmation,
    MatchResultDecision,
    MatchResultReport,
    MatchResultReview,
    MatchResultRound,
)

REPORT_RETENTION_DAYS = 730
EVIDENCE_RETENTION_DAYS = 365
DECISION_RETENTION_DAYS = 730
RATE_LIMIT_RETENTION_HOURS = 24


@dataclass(frozen=True)
class CleanupResult:
    """Contagem de linhas removidas por categoria."""

    reports: int
    confirmations: int
    evidence: int
    decisions: int
    reviews: int
    analyses: int
    rate_limits: int


def cleanup_results(
    session: Session,
    *,
    report_days: int = REPORT_RETENTION_DAYS,
    evidence_days: int = EVIDENCE_RETENTION_DAYS,
    decision_days: int = DECISION_RETENTION_DAYS,
    rate_limit_hours: int = RATE_LIMIT_RETENTION_HOURS,
    now: datetime | None = None,
) -> CleanupResult:
    """Remove dados acima do prazo provisório, em ordem compatível com FKs.

    Só remove dados de partidas ``FINALIZED``/``VOIDED`` e de revisões já
    resolvidas ou canceladas. Partidas em andamento, em disputa ou pendentes de
    revisão são preservadas.
    """
    if report_days < 0 or evidence_days < 0 or decision_days < 0 or rate_limit_hours < 0:
        raise ValueError("prazos de retenção não podem ser negativos")

    moment = ensure_utc(now or utcnow())
    report_cutoff = moment - timedelta(days=report_days)
    evidence_cutoff = moment - timedelta(days=evidence_days)
    decision_cutoff = moment - timedelta(days=decision_days)
    rate_limit_cutoff = moment - timedelta(hours=rate_limit_hours)

    closed_matches = select(Match.id).where(
        Match.state.in_(("FINALIZED", "VOIDED")),
        func.coalesce(Match.finalized_at, Match.updated_at) < report_cutoff,
    )
    closed_rounds = select(MatchResultRound.id).where(MatchResultRound.match_id.in_(closed_matches))

    reports = _rowcount(
        session,
        delete(MatchResultReport).where(MatchResultReport.round_id.in_(closed_rounds)),
    )
    confirmations = _rowcount(
        session,
        delete(MatchResultCaptainConfirmation).where(
            MatchResultCaptainConfirmation.round_id.in_(closed_rounds)
        ),
    )

    closed_disputes = select(MatchDispute.id).where(
        MatchDispute.status == "CLOSED",
        MatchDispute.closed_at < evidence_cutoff,
    )
    evidence = _rowcount(
        session,
        delete(MatchDisputeEvidence).where(MatchDisputeEvidence.dispute_id.in_(closed_disputes)),
    )

    old_reviews = select(MatchResultReview.id).where(
        MatchResultReview.status.in_(("RESOLVED", "CANCELLED")),
        func.coalesce(
            MatchResultReview.resolved_at,
            MatchResultReview.created_at,
        )
        < decision_cutoff,
    )
    decisions = _rowcount(
        session,
        delete(MatchResultDecision).where(MatchResultDecision.review_id.in_(old_reviews)),
    )
    reviews = _rowcount(
        session,
        delete(MatchResultReview).where(MatchResultReview.id.in_(old_reviews)),
    )

    decision_matches = select(Match.id).where(
        Match.state.in_(("FINALIZED", "VOIDED")),
        func.coalesce(Match.finalized_at, Match.updated_at) < decision_cutoff,
    )
    analyses = _rowcount(
        session,
        delete(MatchResultAnalysis).where(MatchResultAnalysis.match_id.in_(decision_matches)),
    )

    rate_limits = _rowcount(
        session,
        delete(RateLimitCounter).where(RateLimitCounter.window_start < rate_limit_cutoff),
    )

    session.flush()
    return CleanupResult(
        reports=reports,
        confirmations=confirmations,
        evidence=evidence,
        decisions=decisions,
        reviews=reviews,
        analyses=analyses,
        rate_limits=rate_limits,
    )


def _rowcount(session: Session, statement: Any) -> int:
    result = cast(CursorResult[Any], session.execute(statement))
    return int(result.rowcount or 0)
