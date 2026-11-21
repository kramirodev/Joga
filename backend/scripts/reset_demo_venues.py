"""Apaga e permite recriar as quadras do demo (dados de teste).

Uso (a partir de ``backend/``):

    python -m scripts.reset_demo_venues --yes

O script só roda com ``JOGA_ENVIRONMENT=demo`` (ou ``development`` no host do
demo) e exige ``--yes``. Ele remove, em ordem de dependência:

- reservas ligadas às quadras e seus pagamentos/eventos/estornos simulados;
- disponibilidade, bloqueios, horários, fechamentos e fotos;
- espaços e quadras (``organization_venues``);
- organizações que não são a organização da plataforma.

Preserva usuários, credenciais, perfis, sessões, tickets/carteira, notificações,
partidas/lobbies, auditoria e a organização da plataforma. ``lobbies.venue_id``
aponta para o catálogo ``venues``, não para ``organization_venues``; por isso os
lobbies e partidas são preservados sem órfãos. É idempotente e imprime um resumo
por tabela.

Nunca rode este script contra o banco do Render por conta própria; o deploy do
demo é operado pelo responsável.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.bookings.models import (
    Booking,
    BookingEvent,
    BookingHold,
    BookingParticipant,
    BookingPayment,
    BookingRefundExclusion,
    BookingSubstitution,
    BookingTimer,
)
from app.modules.fiscal.models import FiscalDocument, FiscalDocumentTaker
from app.modules.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationVenue,
)
from app.modules.payments.models import (
    FinancialDispute,
    PaymentEvent,
    PaymentRefund,
    VenueRelease,
)
from app.modules.venues.models import (
    VenueAvailability,
    VenueBlackout,
    VenueBusinessHour,
    VenueClosure,
    VenuePhoto,
    VenueSpace,
    VenueSport,
)

ALLOWED_ENVIRONMENTS = frozenset({"demo", "development"})


def reset_demo_venues(session: Session) -> dict[str, int]:
    """Remove o grafo de quadras de teste; devolve a contagem por tabela."""
    organization_ids = list(
        session.scalars(select(Organization.id).where(Organization.is_platform.is_(False)))
    )
    venue_ids = (
        list(
            session.scalars(
                select(OrganizationVenue.id).where(
                    OrganizationVenue.organization_id.in_(organization_ids)
                )
            )
        )
        if organization_ids
        else []
    )
    space_ids = (
        list(
            session.scalars(
                select(VenueSpace.id).where(VenueSpace.organization_venue_id.in_(venue_ids))
            )
        )
        if venue_ids
        else []
    )

    booking_conditions = []
    if organization_ids:
        booking_conditions.append(Booking.organization_id.in_(organization_ids))
    if venue_ids:
        booking_conditions.append(Booking.organization_venue_id.in_(venue_ids))
    if space_ids:
        booking_conditions.append(Booking.venue_space_id.in_(space_ids))
    booking_ids = (
        list(session.scalars(select(Booking.id).where(or_(*booking_conditions))))
        if booking_conditions
        else []
    )

    plan: list[tuple[str, Any, Any]] = []

    def add(label: str, model: Any, criterion: Any) -> None:
        plan.append((label, model, criterion))

    if booking_ids:
        payment_ids = select(BookingPayment.id).where(BookingPayment.booking_id.in_(booking_ids))
        document_ids = select(FiscalDocument.id).where(FiscalDocument.booking_id.in_(booking_ids))
        add(
            "payment_events",
            PaymentEvent,
            PaymentEvent.booking_payment_id.in_(payment_ids),
        )
        add("payment_refunds", PaymentRefund, PaymentRefund.booking_id.in_(booking_ids))
        add(
            "booking_substitutions",
            BookingSubstitution,
            BookingSubstitution.booking_id.in_(booking_ids),
        )
        add("booking_payments", BookingPayment, BookingPayment.booking_id.in_(booking_ids))
        add(
            "fiscal_document_takers",
            FiscalDocumentTaker,
            FiscalDocumentTaker.fiscal_document_id.in_(document_ids),
        )
        add("fiscal_documents", FiscalDocument, FiscalDocument.booking_id.in_(booking_ids))
        dispute_conditions = [FinancialDispute.booking_id.in_(booking_ids)]
        release_conditions = [VenueRelease.booking_id.in_(booking_ids)]
        if organization_ids:
            dispute_conditions.append(FinancialDispute.organization_id.in_(organization_ids))
            release_conditions.append(VenueRelease.organization_id.in_(organization_ids))
        add("financial_disputes", FinancialDispute, or_(*dispute_conditions))
        add("venue_releases", VenueRelease, or_(*release_conditions))
        add(
            "booking_refund_exclusions",
            BookingRefundExclusion,
            BookingRefundExclusion.booking_id.in_(booking_ids),
        )
        add("booking_events", BookingEvent, BookingEvent.booking_id.in_(booking_ids))
        add("booking_holds", BookingHold, BookingHold.booking_id.in_(booking_ids))
        add(
            "booking_participants",
            BookingParticipant,
            BookingParticipant.booking_id.in_(booking_ids),
        )
        add("booking_timers", BookingTimer, BookingTimer.booking_id.in_(booking_ids))
        add("bookings", Booking, Booking.id.in_(booking_ids))

    if space_ids:
        add(
            "venue_availability",
            VenueAvailability,
            VenueAvailability.venue_space_id.in_(space_ids),
        )
        add("venue_blackouts", VenueBlackout, VenueBlackout.venue_space_id.in_(space_ids))
        add("venue_sports", VenueSport, VenueSport.venue_space_id.in_(space_ids))
        photo_conditions = [
            VenuePhoto.organization_venue_id.in_(venue_ids),
            VenuePhoto.venue_space_id.in_(space_ids),
        ]
        add("venue_photos", VenuePhoto, or_(*photo_conditions))
    if venue_ids:
        add(
            "venue_business_hours",
            VenueBusinessHour,
            VenueBusinessHour.organization_venue_id.in_(venue_ids),
        )
        add(
            "venue_closures",
            VenueClosure,
            VenueClosure.organization_venue_id.in_(venue_ids),
        )
        if not space_ids:
            add(
                "venue_photos",
                VenuePhoto,
                VenuePhoto.organization_venue_id.in_(venue_ids),
            )
        add("venue_spaces", VenueSpace, VenueSpace.organization_venue_id.in_(venue_ids))
        add(
            "organization_venues",
            OrganizationVenue,
            OrganizationVenue.id.in_(venue_ids),
        )
    if organization_ids:
        add(
            "organization_memberships",
            OrganizationMembership,
            OrganizationMembership.organization_id.in_(organization_ids),
        )
        add(
            "organizations",
            Organization,
            Organization.id.in_(organization_ids),
        )

    counts = {
        label: int(session.scalar(select(func.count()).select_from(model).where(criterion)) or 0)
        for label, model, criterion in plan
    }
    for _label, model, criterion in plan:
        session.execute(delete(model).where(criterion))
    return counts


def _database_label(database_url: str) -> str:
    url = make_url(database_url)
    return f"{url.host or '?'}:{url.port or '?'}/{url.database or '?'}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apaga as quadras/organizações de teste do demo, preservando contas.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="confirma a exclusão dos dados de quadra do demo (obrigatório)",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if settings.environment not in ALLOWED_ENVIRONMENTS:
        print(
            "recusado: JOGA_ENVIRONMENT deve ser 'demo' ou 'development' "
            f"(atual: {settings.environment!r})",
            file=sys.stderr,
        )
        return 2
    if not args.yes:
        print(
            "nada foi apagado: repita com --yes para confirmar",
            file=sys.stderr,
        )
        return 2

    print(
        "reset de quadras: ambiente="
        f"{settings.environment} banco={_database_label(settings.database_url)}"
    )
    if settings.environment == "development":
        print("atenção: 'development' só deve ser usado no host do demo")

    engine = build_engine(settings)
    try:
        with Session(engine) as session:
            counts = reset_demo_venues(session)
            session.commit()
    finally:
        engine.dispose()

    print("reset concluído:")
    for table, count in counts.items():
        print(f"  {table}: {count}")
    print(
        "preservados: usuários, credenciais, perfis, sessões, tickets/carteira, "
        "notificações, lobbies/partidas, auditoria e a organização da plataforma"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
