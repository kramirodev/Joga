"""Reverifica o CNPJ das organizações vencidas (ADR 0062).

Cada organização tem seu próprio ``cnpj_next_check_at``; o worker processa
apenas um lote pequeno por execução para não varrer a base inteira.

Uso:
    python -m scripts.recheck_organization_cnpj
    python -m scripts.recheck_organization_cnpj --limit 10
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.organizations.cnpj import BrasilApiCnpjLookup
from app.modules.organizations.verification import OrganizationVerificationService


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    if args.limit <= 0:
        parser.error("--limit deve ser positivo")

    settings = get_settings()
    lookup = BrasilApiCnpjLookup(
        settings.cnpj_api_base_url,
        timeout_seconds=settings.cnpj_timeout_seconds,
        attempts=settings.cnpj_lookup_attempts,
        cache_ttl_seconds=settings.cnpj_cache_ttl_seconds,
    )
    engine = build_engine(settings)
    with Session(engine) as session:
        report = OrganizationVerificationService(session, settings, lookup).recheck_due(
            limit=args.limit
        )
        session.commit()
    engine.dispose()
    print(
        "reverificação de CNPJ concluída: "
        f"checked={report.checked} verified={report.verified} "
        f"invalid={report.invalid} unavailable={report.unavailable}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
