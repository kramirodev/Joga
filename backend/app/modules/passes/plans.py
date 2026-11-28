"""Catálogo de planos da assinatura (ADR 0070 §3).

A tabela é a única fonte de preço e franquia. O cliente envia apenas o código.
As linhas semeadas reproduzem exatamente a tabela aprovada; não há desconto,
pró-rata ou preço calculado no request. O semestral de 20 e o de 60 não estão
na ADR 0070 e por isso não são inventados aqui.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.passes.models import PassPlan


@dataclass(frozen=True)
class PassPlanDefinition:
    code: str
    label: str
    months: int
    tickets_per_month: int
    unit_price_cents: int

    @property
    def monthly_cents(self) -> int:
        return self.tickets_per_month * self.unit_price_cents

    @property
    def cycle_total_cents(self) -> int:
        return self.monthly_cents * self.months


# Tabela da ADR 0070 §3. Código imutável; mudança de preço exige nova linha
# (catalog_version) e decisão de produto.
DEFAULT_PASS_PLANS: tuple[PassPlanDefinition, ...] = (
    PassPlanDefinition("mensal_20", "Mensal 20", 1, 20, 340),
    PassPlanDefinition("mensal_40", "Mensal 40", 1, 40, 320),
    PassPlanDefinition("mensal_60", "Mensal 60", 1, 60, 310),
    PassPlanDefinition("trimestral_20", "Trimestral 20", 3, 20, 320),
    PassPlanDefinition("trimestral_40", "Trimestral 40", 3, 40, 310),
    PassPlanDefinition("trimestral_60", "Trimestral 60", 3, 60, 300),
    PassPlanDefinition("semestral_40", "Semestral 40", 6, 40, 300),
)


def seed_default_plans(session: Session) -> None:
    """Semeia o catálogo aprovado. Idempotente e sem sobrescrever preço."""

    existing = set(session.scalars(select(PassPlan.code)).all())
    for definition in DEFAULT_PASS_PLANS:
        if definition.code in existing:
            continue
        session.add(
            PassPlan(
                code=definition.code,
                label=definition.label,
                months=definition.months,
                tickets_per_month=definition.tickets_per_month,
                unit_price_cents=definition.unit_price_cents,
                cycle_amount_cents=definition.cycle_total_cents,
                installments=1,
                active=True,
                catalog_version=1,
            )
        )
    session.flush()


def list_active_plans(session: Session) -> list[PassPlan]:
    return list(
        session.scalars(
            select(PassPlan)
            .where(PassPlan.active.is_(True))
            .order_by(PassPlan.months.asc(), PassPlan.tickets_per_month.asc())
        ).all()
    )


def get_active_plan(session: Session, code: str) -> PassPlan | None:
    return session.scalars(
        select(PassPlan).where(PassPlan.code == code, PassPlan.active.is_(True))
    ).first()
