"""Planos do passe (ADR 0042 §2 e ADR 0043 §2).

O preço é por ingresso (R$ 3,25), acima do pacote grande. A cobrança é única
por trimestre e a franquia é entregue mês a mês, sem acúmulo.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.passes.models import PassSubscription


@dataclass(frozen=True)
class PassPlan:
    code: str
    label: str
    tickets_per_month: int
    unit_price_cents: int

    @property
    def price_per_month_cents(self) -> int:
        return self.tickets_per_month * self.unit_price_cents

    @property
    def quarter_cents(self) -> int:
        return self.price_per_month_cents * 3


PASS_PLANS: tuple[PassPlan, ...] = (
    PassPlan("jogador", "Jogador", 10, 325),
    PassPlan("craque", "Craque", 20, 325),
    PassPlan("time", "Time", 30, 325),
    PassPlan("elenco", "Elenco", 50, 325),
)

PASS_MONTHS = 3


def list_plans() -> tuple[PassPlan, ...]:
    return PASS_PLANS


def get_plan(code: str) -> PassPlan | None:
    return next((plan for plan in PASS_PLANS if plan.code == code), None)


def plan_for_subscription(subscription: PassSubscription) -> PassPlan | None:
    return get_plan(subscription.plan_code)
