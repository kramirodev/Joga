"""Serviço de resultados: rodadas, votos, disputas e decisão auditável."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.matches.models import Match, MatchParticipant
from app.modules.matches.service import MatchNotFound, MatchService, transition
from app.modules.matchmaking.models import Lobby
from app.modules.profile.models import Sport, SportFormat, UserProfile
from app.modules.results.models import (
    DECISIONS,
    MAX_EVIDENCE_CHARS,
    OUTCOMES,
    MatchDispute,
    MatchDisputeEvidence,
    MatchResultAnalysis,
    MatchResultCaptainConfirmation,
    MatchResultDecision,
    MatchResultEligibleParticipant,
    MatchResultReport,
    MatchResultReview,
    MatchResultRound,
)
from app.modules.results.policy import (
    DECISION_ANALYSIS,
    DECISION_DISPUTE,
    DECISION_FINALIZE,
    DECISION_SECOND_ROUND,
    RoundEvaluation,
    count_votes,
    evaluate_round,
    format_allows_draw,
    quorum_for,
)

RESULT_REPORT_WINDOW = timedelta(minutes=10)
SECOND_ROUND_WINDOW = timedelta(minutes=5)


class ResultWindowNotOpen(Exception):
    """A janela de relato ainda não abriu."""


class ResultWindowClosed(Exception):
    """O prazo da rodada terminou."""


class RoundNotOpen(Exception):
    """A rodada informada não é a rodada aberta atual."""


class IneligibleParticipant(Exception):
    """Participante fora do conjunto congelado de elegíveis."""


class ReportAlreadySubmitted(Exception):
    """A rodada 1 já recebeu o voto deste participante."""


class InvalidOutcome(Exception):
    """Resultado fora de TEAM_1, TEAM_2 ou DRAW."""


class DrawNotAllowed(Exception):
    """O formato não permite empate esportivo."""


class NotCaptain(Exception):
    """Participante não é capitão da partida."""


class ConfirmationAlreadySubmitted(Exception):
    """O capitão já confirmou nesta rodada."""


class DisputeNotFound(Exception):
    """Disputa inexistente para a partida."""


class EvidenceNotFound(Exception):
    """Evidência inexistente para o participante."""


class EvidenceWindowClosed(Exception):
    """A janela de evidência não está mais aberta."""


class EvidenceAlreadySubmitted(Exception):
    """O participante já enviou evidência nesta disputa."""


class EvidenceEmpty(Exception):
    """Justificativa vazia."""


class EvidenceTooLong(Exception):
    """Justificativa acima do limite."""


class InvalidRound(Exception):
    """Número de rodada inválido."""


class ReviewNotFound(Exception):
    """Não há revisão pendente para a partida."""


class InvalidDecision(Exception):
    """Decisão humana inválida."""


class InvalidResultTransition(Exception):
    """Transição de estado inválida para a decisão."""


@dataclass(frozen=True)
class ResultsAdvanceResult:
    rounds_opened: int
    rounds_closed: int
    finalized: int
    disputed: int
    reviews_opened: int


class ResultsService:
    """Ciclo de apuração controlado exclusivamente pelo backend."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # Avanço por tempo ---------------------------------------------------

    def advance(self, now: datetime | None = None) -> ResultsAdvanceResult:
        current = ensure_utc(now or utcnow())
        opened = closed = finalized = disputed = reviews = 0

        ended = list(
            self._session.scalars(
                select(Match).where(
                    Match.state == "IN_PROGRESS",
                    Match.scheduled_end_at <= current,
                )
            )
        )
        for match in ended:
            self._lock(match)
            if self._open_first_round(match):
                opened += 1

        while True:
            rounds = list(
                self._session.scalars(
                    select(MatchResultRound)
                    .where(
                        MatchResultRound.status == "OPEN",
                        MatchResultRound.deadline <= current,
                    )
                    .order_by(MatchResultRound.deadline, MatchResultRound.round_number)
                )
            )
            if not rounds:
                break
            for round_row in rounds:
                round_match = self._session.get(Match, round_row.match_id)
                if round_match is None:
                    continue
                self._lock(round_match)
                self._session.refresh(round_row)
                outcome = self._close_round(round_match, round_row, current)
                if outcome is not None:
                    closed += 1
                if outcome == "FINALIZED":
                    finalized += 1
                elif outcome == "DISPUTED":
                    disputed += 1
                elif outcome == "REVIEW":
                    reviews += 1

        self._session.flush()
        return ResultsAdvanceResult(
            rounds_opened=opened,
            rounds_closed=closed,
            finalized=finalized,
            disputed=disputed,
            reviews_opened=reviews,
        )

    def _open_first_round(self, match: Match) -> bool:
        if match.state != "IN_PROGRESS":
            return False
        existing = self._session.scalar(
            select(MatchResultRound.id).where(MatchResultRound.match_id == match.id)
        )
        if existing is not None:
            return False

        transition(self._session, match, "RESULT_PENDING", reason="scheduled_end")
        eligible = list(
            self._session.scalars(
                select(MatchParticipant)
                .where(
                    MatchParticipant.match_id == match.id,
                    MatchParticipant.status == "checked_in",
                )
                .order_by(MatchParticipant.id)
            )
        )
        opens_at = ensure_utc(match.scheduled_end_at)
        deadline = opens_at + RESULT_REPORT_WINDOW
        for participant in eligible:
            self._session.add(
                MatchResultEligibleParticipant(
                    match_id=match.id,
                    participant_id=participant.id,
                    user_id=participant.user_id,
                    frozen_at=opens_at,
                )
            )
        self._session.add(
            MatchResultRound(
                match_id=match.id,
                round_number=1,
                status="OPEN",
                opens_at=opens_at,
                deadline=deadline,
                eligible_count=len(eligible),
                quorum=quorum_for(len(eligible)),
            )
        )
        self._session.flush()
        return True

    def _close_round(self, match: Match, round_row: MatchResultRound, now: datetime) -> str | None:
        if round_row.status != "OPEN":
            return None
        if ensure_utc(round_row.deadline) > now:
            return None

        round_row.status = "CLOSED"
        round_row.closed_at = now
        votes = self.effective_votes(round_row)
        counts = count_votes([report.outcome for report in votes.values()])
        evaluation = evaluate_round(
            counts,
            eligible_count=round_row.eligible_count,
            round_number=round_row.round_number,
        )
        round_row.valid_votes = evaluation.valid_votes
        round_row.evaluated_outcome = evaluation.evaluated_outcome
        round_row.divergent_votes = evaluation.divergent_votes

        if evaluation.decision == DECISION_FINALIZE:
            round_row.outcome = "FINALIZED"
            self._finalize(match, evaluation, now, reason="result_validated")
        elif evaluation.decision == DECISION_SECOND_ROUND:
            round_row.outcome = "SECOND_ROUND"
            self._open_second_round(match, round_row)
        elif evaluation.decision == DECISION_ANALYSIS:
            round_row.outcome = "REVIEW"
            self._record_analysis(match, round_row, evaluation)
            self._open_review(match, round_row, "SECOND_ROUND_50", now)
        elif evaluation.decision == DECISION_DISPUTE:
            round_row.outcome = "DISPUTED"
            self._open_review(match, round_row, evaluation.review_reason or "DIVERGENCE", now)
        else:
            round_row.outcome = "REVIEW"
            self._open_review(match, round_row, evaluation.review_reason or "QUORUM", now)

        self._session.flush()
        return round_row.outcome

    def _open_second_round(self, match: Match, first: MatchResultRound) -> MatchResultRound:
        existing = self._session.scalar(
            select(MatchResultRound).where(
                MatchResultRound.match_id == match.id,
                MatchResultRound.round_number == 2,
            )
        )
        if existing is not None:
            return existing
        opens_at = ensure_utc(first.deadline)
        second = MatchResultRound(
            match_id=match.id,
            round_number=2,
            status="OPEN",
            opens_at=opens_at,
            deadline=opens_at + SECOND_ROUND_WINDOW,
            eligible_count=first.eligible_count,
            quorum=first.quorum,
        )
        self._session.add(second)
        self._session.flush()
        return second

    def _finalize(
        self,
        match: Match,
        evaluation: RoundEvaluation,
        now: datetime,
        *,
        reason: str,
    ) -> None:
        if match.state != "RESULT_PENDING" or evaluation.evaluated_outcome is None:
            return
        match.final_result = evaluation.evaluated_outcome
        match.finalized_at = now
        match.result_version = (match.result_version or 0) + 1
        transition(self._session, match, "FINALIZED", reason=reason)

    def _open_review(
        self,
        match: Match,
        round_row: MatchResultRound,
        reason: str,
        now: datetime,
    ) -> tuple[MatchDispute, MatchResultReview]:
        existing = self._session.scalar(
            select(MatchDispute).where(
                MatchDispute.match_id == match.id,
                MatchDispute.round_id == round_row.id,
                MatchDispute.status == "OPEN",
            )
        )
        if existing is None:
            existing = MatchDispute(
                match_id=match.id,
                round_id=round_row.id,
                reason=reason,
                status="OPEN",
                opened_at=now,
            )
            self._session.add(existing)
        elif existing.reason != reason:
            existing.reason = reason

        review = MatchResultReview(
            match_id=match.id,
            round_id=round_row.id,
            reason=reason,
            status="PENDING",
            created_at=now,
        )
        self._session.add(review)

        if reason in ("DIVERGENCE", "NO_UNIQUE_RESULT", "SECOND_ROUND_50"):
            if match.state == "RESULT_PENDING":
                transition(
                    self._session,
                    match,
                    "DISPUTED",
                    reason=f"result_{reason.lower()}",
                )
        self._session.flush()
        return existing, review

    def _record_analysis(
        self,
        match: Match,
        round_row: MatchResultRound,
        evaluation: RoundEvaluation,
    ) -> MatchResultAnalysis:
        first = self._session.scalar(
            select(MatchResultRound).where(
                MatchResultRound.match_id == match.id,
                MatchResultRound.round_number == 1,
            )
        )
        changed: list[dict[str, Any]] = []
        if first is not None:
            first_votes = self.effective_votes(first)
            second_votes = self.effective_votes(round_row)
            for participant_id, report in second_votes.items():
                previous = first_votes.get(participant_id)
                if previous is not None and previous.outcome != report.outcome:
                    changed.append(
                        {
                            "participant_id": str(participant_id),
                            "from": previous.outcome,
                            "to": report.outcome,
                        }
                    )
        confirmations = [
            {
                "participant_id": str(row.participant_id),
                "outcome": row.outcome,
                "matches_evaluated": (
                    evaluation.evaluated_outcome is not None
                    and row.outcome == evaluation.evaluated_outcome
                ),
            }
            for row in self.captain_confirmations(round_row)
        ]
        signals: dict[str, Any] = {
            "round_1": {
                "valid_votes": first.valid_votes if first is not None else None,
                "evaluated_outcome": first.evaluated_outcome if first is not None else None,
            },
            "round_2": {
                "valid_votes": evaluation.valid_votes,
                "counts": evaluation.counts,
                "evaluated_outcome": evaluation.evaluated_outcome,
            },
            "changed_votes": changed,
            "captain_confirmations": confirmations,
            "conclusion": "INCONCLUSIVE",
        }
        analysis = MatchResultAnalysis(
            match_id=match.id,
            round_id=round_row.id,
            signals=signals,
            conclusion="INCONCLUSIVE",
        )
        self._session.add(analysis)
        return analysis

    # Relatos e confirmações ---------------------------------------------

    def submit_report(
        self,
        *,
        match_id: uuid.UUID,
        user_id: uuid.UUID,
        round_number: int,
        outcome: str,
        idempotency_key: str,
        request_hash: str,
        now: datetime | None = None,
    ) -> MatchResultReport:
        current = ensure_utc(now or utcnow())
        match = MatchService(self._session).get_for_user(match_id, user_id)
        self._lock(match)
        round_row = self._round_for_submission(match, round_number, current)
        participant = self._participant(match.id, user_id)
        if participant is None:
            raise MatchNotFound("partida não encontrada")
        eligible = self._eligible(match.id, participant.id)
        if eligible is None:
            raise IneligibleParticipant("participante fora do conjunto elegível")
        self._validate_outcome(match, outcome)

        if round_row.round_number == 1:
            existing = self._session.scalar(
                select(MatchResultReport).where(
                    MatchResultReport.round_id == round_row.id,
                    MatchResultReport.participant_id == participant.id,
                )
            )
            if existing is not None:
                raise ReportAlreadySubmitted("relato já enviado nesta rodada")

        report = MatchResultReport(
            round_id=round_row.id,
            participant_id=participant.id,
            outcome=outcome,
            submitted_at=current,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        self._session.add(report)
        self._session.flush()
        return report

    def submit_confirmation(
        self,
        *,
        match_id: uuid.UUID,
        user_id: uuid.UUID,
        round_number: int,
        outcome: str,
        idempotency_key: str,
        request_hash: str,
        now: datetime | None = None,
    ) -> MatchResultCaptainConfirmation:
        current = ensure_utc(now or utcnow())
        match = MatchService(self._session).get_for_user(match_id, user_id)
        self._lock(match)
        round_row = self._round_for_submission(match, round_number, current)
        participant = self._participant(match.id, user_id)
        if participant is None:
            raise MatchNotFound("partida não encontrada")
        if not participant.is_captain:
            raise NotCaptain("participante não é capitão")
        if self._eligible(match.id, participant.id) is None:
            raise IneligibleParticipant("capitão fora do conjunto elegível")
        self._validate_outcome(match, outcome)

        existing = self._session.scalar(
            select(MatchResultCaptainConfirmation).where(
                MatchResultCaptainConfirmation.round_id == round_row.id,
                MatchResultCaptainConfirmation.participant_id == participant.id,
            )
        )
        if existing is not None:
            raise ConfirmationAlreadySubmitted("capitão já confirmou nesta rodada")

        confirmation = MatchResultCaptainConfirmation(
            round_id=round_row.id,
            participant_id=participant.id,
            outcome=outcome,
            submitted_at=current,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        self._session.add(confirmation)
        self._session.flush()
        return confirmation

    # Evidências ---------------------------------------------------------

    def submit_evidence(
        self,
        *,
        match_id: uuid.UUID,
        dispute_id: uuid.UUID,
        user_id: uuid.UUID,
        text: str,
        idempotency_key: str,
        request_hash: str,
        now: datetime | None = None,
    ) -> MatchDisputeEvidence:
        current = ensure_utc(now or utcnow())
        match = MatchService(self._session).get_for_user(match_id, user_id)
        self._lock(match)
        dispute = self._dispute_for(match, dispute_id)
        participant = self._participant(match.id, user_id)
        if participant is None or self._eligible(match.id, participant.id) is None:
            raise DisputeNotFound("disputa não encontrada")
        if dispute.status != "OPEN":
            raise EvidenceWindowClosed("janela de evidência encerrada")
        review = self._session.scalar(
            select(MatchResultReview).where(
                MatchResultReview.match_id == match.id,
                MatchResultReview.round_id == dispute.round_id,
                MatchResultReview.status == "PENDING",
            )
        )
        if review is None:
            raise EvidenceWindowClosed("janela de evidência encerrada")

        existing = self._session.scalar(
            select(MatchDisputeEvidence).where(
                MatchDisputeEvidence.dispute_id == dispute.id,
                MatchDisputeEvidence.participant_id == participant.id,
            )
        )
        if existing is not None:
            raise EvidenceAlreadySubmitted("evidência já enviada nesta disputa")

        if not text.strip():
            raise EvidenceEmpty("justificativa vazia")
        if len(text) > MAX_EVIDENCE_CHARS:
            raise EvidenceTooLong("justificativa acima do limite")

        evidence = MatchDisputeEvidence(
            dispute_id=dispute.id,
            participant_id=participant.id,
            text=text,
            char_count=len(text),
            created_at=current,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        self._session.add(evidence)
        self._session.flush()
        return evidence

    def get_evidence(
        self,
        *,
        match_id: uuid.UUID,
        dispute_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MatchDisputeEvidence:
        match = MatchService(self._session).get_for_user(match_id, user_id)
        dispute = self._dispute_for(match, dispute_id)
        participant = self._participant(match.id, user_id)
        if participant is None:
            raise EvidenceNotFound("evidência não encontrada")
        evidence = self._session.scalar(
            select(MatchDisputeEvidence).where(
                MatchDisputeEvidence.dispute_id == dispute.id,
                MatchDisputeEvidence.participant_id == participant.id,
            )
        )
        if evidence is None:
            raise EvidenceNotFound("evidência não encontrada")
        return evidence

    # Consultas ------------------------------------------------------------

    def current_round(self, match_id: uuid.UUID) -> MatchResultRound | None:
        return self._session.scalar(
            select(MatchResultRound)
            .where(MatchResultRound.match_id == match_id)
            .order_by(MatchResultRound.round_number.desc())
        )

    def round_by_number(self, match_id: uuid.UUID, round_number: int) -> MatchResultRound | None:
        return self._session.scalar(
            select(MatchResultRound).where(
                MatchResultRound.match_id == match_id,
                MatchResultRound.round_number == round_number,
            )
        )

    def effective_votes(self, round_row: MatchResultRound) -> dict[uuid.UUID, MatchResultReport]:
        eligible = self._session.scalars(
            select(MatchResultEligibleParticipant).where(
                MatchResultEligibleParticipant.match_id == round_row.match_id
            )
        )
        eligible_ids = {row.participant_id for row in eligible}
        reports = self._session.scalars(
            select(MatchResultReport)
            .where(MatchResultReport.round_id == round_row.id)
            .order_by(MatchResultReport.submitted_at, MatchResultReport.id)
        )
        deadline = ensure_utc(round_row.deadline)
        latest: dict[uuid.UUID, MatchResultReport] = {}
        for report in reports:
            if report.participant_id not in eligible_ids:
                continue
            if ensure_utc(report.submitted_at) > deadline:
                continue
            latest[report.participant_id] = report
        return latest

    def counts_for(self, round_row: MatchResultRound) -> dict[str, int]:
        return count_votes([report.outcome for report in self.effective_votes(round_row).values()])

    def captain_confirmations(
        self, round_row: MatchResultRound
    ) -> list[MatchResultCaptainConfirmation]:
        return list(
            self._session.scalars(
                select(MatchResultCaptainConfirmation)
                .where(MatchResultCaptainConfirmation.round_id == round_row.id)
                .order_by(
                    MatchResultCaptainConfirmation.submitted_at,
                    MatchResultCaptainConfirmation.id,
                )
            )
        )

    def eligible_for_user(
        self, match_id: uuid.UUID, user_id: uuid.UUID
    ) -> MatchResultEligibleParticipant | None:
        return self._session.scalar(
            select(MatchResultEligibleParticipant).where(
                MatchResultEligibleParticipant.match_id == match_id,
                MatchResultEligibleParticipant.user_id == user_id,
            )
        )

    def my_vote(self, round_row: MatchResultRound, user_id: uuid.UUID) -> MatchResultReport | None:
        participant = self._participant(round_row.match_id, user_id)
        if participant is None:
            return None
        return self.effective_votes(round_row).get(participant.id)

    def latest_dispute(self, match_id: uuid.UUID) -> MatchDispute | None:
        return self._session.scalar(
            select(MatchDispute)
            .where(MatchDispute.match_id == match_id)
            .order_by(MatchDispute.opened_at.desc(), MatchDispute.id.desc())
        )

    def latest_open_dispute(self, match_id: uuid.UUID) -> MatchDispute | None:
        return self._session.scalar(
            select(MatchDispute)
            .where(
                MatchDispute.match_id == match_id,
                MatchDispute.status == "OPEN",
            )
            .order_by(MatchDispute.opened_at.desc(), MatchDispute.id.desc())
        )

    def pending_review(self, match_id: uuid.UUID) -> MatchResultReview | None:
        return self._session.scalar(
            select(MatchResultReview)
            .where(
                MatchResultReview.match_id == match_id,
                MatchResultReview.status == "PENDING",
            )
            .order_by(MatchResultReview.created_at.desc(), MatchResultReview.id.desc())
        )

    def display_name(self, user_id: uuid.UUID) -> str | None:
        profile = self._session.get(UserProfile, user_id)
        return profile.display_name if profile else None

    def participant_for_user(
        self, match_id: uuid.UUID, user_id: uuid.UUID
    ) -> MatchParticipant | None:
        return self._participant(match_id, user_id)

    # Revisão humana -------------------------------------------------------

    def decide(
        self,
        *,
        match_id: uuid.UUID,
        decision: str,
        reason: str,
        operator_id: str,
        outcome: str | None = None,
        now: datetime | None = None,
    ) -> MatchResultDecision:
        current = ensure_utc(now or utcnow())
        if decision not in DECISIONS:
            raise InvalidDecision("decisão inválida")
        if not reason.strip() or len(reason) > 500:
            raise InvalidDecision("justificativa obrigatória de até 500 caracteres")

        match = self._session.get(Match, match_id)
        if match is None:
            raise MatchNotFound("partida não encontrada")
        self._lock(match)
        review = self.pending_review(match_id)
        if review is None:
            raise ReviewNotFound("revisão pendente não encontrada")

        if decision == "FINALIZE":
            if outcome is None:
                raise InvalidOutcome("resultado obrigatório para finalizar")
            self._validate_outcome(match, outcome)
        else:
            outcome = None

        if match.state not in ("RESULT_PENDING", "DISPUTED"):
            raise InvalidResultTransition("partida não aceita decisão")

        decision_row = MatchResultDecision(
            match_id=match.id,
            review_id=review.id,
            decision=decision,
            outcome=outcome,
            reason=reason,
            operator_id=operator_id,
            origin="HUMAN",
            created_at=current,
        )
        self._session.add(decision_row)

        if decision == "FINALIZE":
            assert outcome is not None
            review.status = "RESOLVED"
            review.resolved_at = current
            self._close_dispute(match.id, review.round_id, current)
            match.final_result = outcome
            match.finalized_at = current
            match.result_version = (match.result_version or 0) + 1
            transition(self._session, match, "FINALIZED", reason="human_finalize")
        elif decision == "VOID":
            review.status = "RESOLVED"
            review.resolved_at = current
            self._close_dispute(match.id, review.round_id, current)
            match.final_result = None
            match.voided_reason = reason
            transition(self._session, match, "VOIDED", reason="human_void")

        self._session.flush()
        return decision_row

    # Internos -------------------------------------------------------------

    def _lock(self, match: Match) -> None:
        if self._session.get_bind().dialect.name == "postgresql":
            self._session.get(Match, match.id, with_for_update=True, populate_existing=True)

    def _participant(self, match_id: uuid.UUID, user_id: uuid.UUID) -> MatchParticipant | None:
        return self._session.scalar(
            select(MatchParticipant).where(
                MatchParticipant.match_id == match_id,
                MatchParticipant.user_id == user_id,
            )
        )

    def _eligible(
        self, match_id: uuid.UUID, participant_id: uuid.UUID
    ) -> MatchResultEligibleParticipant | None:
        return self._session.scalar(
            select(MatchResultEligibleParticipant).where(
                MatchResultEligibleParticipant.match_id == match_id,
                MatchResultEligibleParticipant.participant_id == participant_id,
            )
        )

    def _round_for_submission(
        self, match: Match, round_number: int, now: datetime
    ) -> MatchResultRound:
        if match.state in ("PENDING_CONFIRMATION", "READY", "IN_PROGRESS"):
            raise ResultWindowNotOpen("janela de relato ainda não abriu")
        if match.state != "RESULT_PENDING":
            raise ResultWindowClosed("janela de relato encerrada")
        if round_number not in (1, 2):
            raise InvalidRound("rodada inválida")
        round_row = self.round_by_number(match.id, round_number)
        if round_row is None:
            raise RoundNotOpen("rodada não encontrada")
        current = self.current_round(match.id)
        if current is None or current.id != round_row.id or round_row.status != "OPEN":
            raise RoundNotOpen("rodada não está aberta")
        if now < ensure_utc(round_row.opens_at):
            raise ResultWindowNotOpen("janela de relato ainda não abriu")
        if now > ensure_utc(round_row.deadline):
            raise ResultWindowClosed("prazo da rodada encerrado")
        return round_row

    def _validate_outcome(self, match: Match, outcome: str) -> None:
        if outcome not in OUTCOMES:
            raise InvalidOutcome("resultado inválido")
        if outcome == "DRAW" and not self._format_allows_draw(match):
            raise DrawNotAllowed("formato não permite empate")

    def _format_allows_draw(self, match: Match) -> bool:
        lobby = self._session.get(Lobby, match.lobby_id)
        if lobby is None:
            return False
        sport_format = self._session.get(SportFormat, lobby.format_id)
        if sport_format is None:
            return False
        sport = self._session.get(Sport, sport_format.sport_id)
        return format_allows_draw(sport.slug if sport else None)

    def _dispute_for(self, match: Match, dispute_id: uuid.UUID) -> MatchDispute:
        dispute = self._session.get(MatchDispute, dispute_id)
        if dispute is None or dispute.match_id != match.id:
            raise DisputeNotFound("disputa não encontrada")
        return dispute

    def _close_dispute(
        self,
        match_id: uuid.UUID,
        round_id: uuid.UUID | None,
        now: datetime,
    ) -> None:
        disputes: Sequence[MatchDispute] = self._session.scalars(
            select(MatchDispute).where(
                MatchDispute.match_id == match_id,
                MatchDispute.status == "OPEN",
            )
        ).all()
        for dispute in disputes:
            if round_id is not None and dispute.round_id != round_id:
                continue
            dispute.status = "CLOSED"
            dispute.closed_at = now
