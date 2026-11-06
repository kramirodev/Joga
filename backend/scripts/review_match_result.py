"""CLI interna e auditável para decidir uma revisão de resultado.

Uso:
    python -m scripts.review_match_result \
        --match-id <uuid> \
        --operator <operator_id> \
        --reason "Justificativa auditável" \
        --decision FINALIZE \
        --outcome TEAM_1

O operador precisa constar em JOGA_REVIEW_OPERATORS (lista separada por vírgula).
Não existe endpoint público de moderação nesta fase.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.matches.service import MatchNotFound
from app.modules.results.models import DECISIONS, OUTCOMES
from app.modules.results.service import (
    DrawNotAllowed,
    InvalidDecision,
    InvalidOutcome,
    InvalidResultTransition,
    ResultsService,
    ReviewNotFound,
)

EXIT_OK = 0
EXIT_INVALID_ARGUMENT = 2
EXIT_UNAUTHORIZED_OPERATOR = 3
EXIT_REVIEW_NOT_FOUND = 4
EXIT_INVALID_TRANSITION = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-id", type=uuid.UUID, required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--decision", choices=DECISIONS, required=True)
    parser.add_argument("--outcome", choices=OUTCOMES)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()

    operator = args.operator.strip()
    if not operator or operator not in settings.review_operator_ids:
        print("operador não autorizado", file=sys.stderr)
        return EXIT_UNAUTHORIZED_OPERATOR

    reason = args.reason.strip()
    if not reason or len(reason) > 500:
        print("justificativa obrigatória de até 500 caracteres", file=sys.stderr)
        return EXIT_INVALID_ARGUMENT
    if args.decision == "FINALIZE" and args.outcome is None:
        print("--outcome é obrigatório para FINALIZE", file=sys.stderr)
        return EXIT_INVALID_ARGUMENT
    if args.decision != "FINALIZE" and args.outcome is not None:
        print("--outcome só é aceito para FINALIZE", file=sys.stderr)
        return EXIT_INVALID_ARGUMENT

    engine = build_engine(settings)
    try:
        with Session(engine) as session:
            service = ResultsService(session)
            try:
                decision = service.decide(
                    match_id=args.match_id,
                    decision=args.decision,
                    outcome=args.outcome,
                    reason=reason,
                    operator_id=operator,
                )
            except (ReviewNotFound, MatchNotFound):
                print("revisão pendente não encontrada", file=sys.stderr)
                return EXIT_REVIEW_NOT_FOUND
            except InvalidResultTransition:
                print("transição de estado inválida", file=sys.stderr)
                return EXIT_INVALID_TRANSITION
            except (InvalidDecision, InvalidOutcome, DrawNotAllowed) as exc:
                print(str(exc), file=sys.stderr)
                return EXIT_INVALID_ARGUMENT

            if args.dry_run:
                decision_name = decision.decision
                session.rollback()
                print(
                    f"dry-run ok: match={args.match_id} decision={decision_name} "
                    f"operator={operator}"
                )
            else:
                session.commit()
                print(
                    f"decisão registrada: match={args.match_id} "
                    f"decision={decision.decision} operator={operator}"
                )
    finally:
        engine.dispose()
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
