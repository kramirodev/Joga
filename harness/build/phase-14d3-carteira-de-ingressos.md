# Fase 14D.3 — Carteira de ingressos e ledger

**Status:** implementado localmente em 2026-11-12.
**Branch:** `main`

## Fontes e contexto

- `PLANS.md` Fase 14D
- ADR 0042 §2 (ingresso como unidade de acesso) e §4 (passe e franquia)
- ADR 0043 §2.1 (ingressos grátis por nível)
- Fase 14A (ledger financeiro e adaptador de PSP)

## Objetivo

Dar ao jogador um saldo de ingressos com rastro contábil. O saldo é **projeção**; a
verdade é o ledger. Nada é editável pelo cliente.

## Decisões desta fatia

| Tema | Decisão | Motivo |
|---|---|---|
| Fonte da verdade | `ticket_ledger` append-only | Correção é evento novo, nunca update |
| Saldo | `ticket_balances` reconstruível | Consulta rápida sem somar o ledger inteiro |
| Idempotência | `idempotency_key` única por movimento | Reenvio não duplica crédito nem débito |
| Consumo | Chave `consume:{ref_type}:{ref_id}:{user}` | Duas confirmações da mesma reserva não debitam duas vezes |
| Devolução | Chave `refund:{ref_type}:{ref_id}:{user}` | Idem, simétrico |
| Saldo negativo | `CHECK balance >= 0` + trava de linha | Concorrência não fura o saldo |
| Tipos de origem | `purchase`, `pass`, `free_level`, `consumption`, `refund`, `admin` | Cobre os fluxos previstos nas ADRs 0042/0043 |

## Implementação

- `app/modules/tickets/models.py` — `TicketLedgerEntry`, `TicketBalance`.
- `app/modules/tickets/service.py` — `grant`, `consume`, `refund`, `apply_entry`, `get_balance`, `list_entries`.
- `app/api/v1/tickets.py` — `GET /api/v1/me/tickets` com saldo e últimos movimentos.
- Migração `d3e4f5061927`.

## Testes

`tests/test_tickets.py`:

- crédito e débito alteram o saldo;
- saldo insuficiente não debita;
- consumo repetido não debita duas vezes;
- devolução repetida não credita duas vezes;
- reutilizar chave com efeito diferente retorna conflito;
- `GET /me/tickets` devolve saldo e movimentos;
- carteira é escopada por usuário.

Suíte completa, `ruff`, `mypy --strict` e `alembic check` verdes; migração testada em
upgrade, downgrade e novo upgrade.

## Ainda não ligado

1. **Compra não gera ingresso.** O crédito existe, mas quem chama `grant` é a compra
   (14D.4).
2. **Consumo não acontece na confirmação.** A reserva ainda cobra por participante.
3. **Devolução em ingresso não substituiu o estorno em dinheiro.**
4. **Franquia do passe** ainda não expira por mês: o ledger não distingue ingresso de passe
   de ingresso comprado.

## Próxima fatia

**14D.4 — Compra, consumo na confirmação e devolução em ingresso.** Liga a carteira ao
fluxo de reserva e substitui a cobrança por participante.
