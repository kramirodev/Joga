"""Limpeza manual de dados de resultado por retenção provisória.

Uso:
    python -m scripts.cleanup_results
    python -m scripts.cleanup_results --dry-run
    python -m scripts.cleanup_results --report-days 730 --evidence-days 365

A política é provisória e está registrada em docs/ADR/0024. Não há agendamento
automático; a execução em produção depende da revisão LGPD da Fase 10/19.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.results.cleanup import (
    DECISION_RETENTION_DAYS,
    EVIDENCE_RETENTION_DAYS,
    RATE_LIMIT_RETENTION_HOURS,
    REPORT_RETENTION_DAYS,
    CleanupResult,
    cleanup_results,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-days", type=int, default=REPORT_RETENTION_DAYS)
    parser.add_argument("--evidence-days", type=int, default=EVIDENCE_RETENTION_DAYS)
    parser.add_argument("--decision-days", type=int, default=DECISION_RETENTION_DAYS)
    parser.add_argument(
        "--rate-limit-hours",
        type=int,
        default=RATE_LIMIT_RETENTION_HOURS,
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    engine = build_engine(get_settings())
    try:
        with Session(engine) as session:
            try:
                result = cleanup_results(
                    session,
                    report_days=args.report_days,
                    evidence_days=args.evidence_days,
                    decision_days=args.decision_days,
                    rate_limit_hours=args.rate_limit_hours,
                )
            except ValueError as exc:
                session.rollback()
                print(f"argumento inválido: {exc}")
                return 2

            if args.dry_run:
                session.rollback()
                print(f"dry-run: {_format(result)}")
            else:
                session.commit()
                print(f"limpeza concluída: {_format(result)}")
    finally:
        engine.dispose()
    return 0


def _format(result: CleanupResult) -> str:
    return (
        f"reports={result.reports} "
        f"confirmations={result.confirmations} "
        f"evidence={result.evidence} "
        f"decisions={result.decisions} "
        f"reviews={result.reviews} "
        f"analyses={result.analyses} "
        f"rate_limits={result.rate_limits}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
