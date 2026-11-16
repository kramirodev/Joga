"""Cálculo de taxa e rateio em centavos (ADR 0049 §9.10).

Funções puras: sem banco, sem configuração global e sem arredondamento
dependente de ponto flutuante. Toda a aritmética é inteira.
"""

from __future__ import annotations

BPS_DENOMINATOR = 10_000


def compute_fee_cents(
    venue_price_cents: int,
    fee_percent_bps: int,
    fee_min_cents: int,
) -> int:
    """Calcula a taxa de intermediação congelada na reserva.

    - `round_half_up`: 0,5 centavo sobe.
    - aplica o piso `fee_min_cents`;
    - nunca devolve mais que o preço do espaço.
    """

    if venue_price_cents < 0:
        raise ValueError("preço do espaço não pode ser negativo")
    if not 0 <= fee_percent_bps <= BPS_DENOMINATOR:
        raise ValueError("percentual da taxa deve estar entre 0 e 10000 bps")
    if fee_min_cents < 0:
        raise ValueError("piso da taxa não pode ser negativo")

    fee = (venue_price_cents * fee_percent_bps + BPS_DENOMINATOR // 2) // BPS_DENOMINATOR
    fee = max(fee, fee_min_cents)
    return min(fee, venue_price_cents)


def allocate_cents(total_cents: int, parts: int) -> list[int]:
    """Divide um inteiro em `parts` cotas que somam exatamente o total.

    O resto é distribuído um centavo por vez, na ordem das cotas. Nenhuma cota
    é arredondada isoladamente, então não existe centavo perdido.
    """

    if total_cents < 0:
        raise ValueError("total não pode ser negativo")
    if parts < 1:
        raise ValueError("é preciso ao menos uma parte")

    base, remainder = divmod(total_cents, parts)
    return [base + 1 if index < remainder else base for index in range(parts)]


__all__ = ["allocate_cents", "compute_fee_cents"]
