# Fase 14D.16 — Consolidação financeira do ingresso

**Status:** implementado no backend em 2026-11-14.
**Depende de:** 14D.3 (ledger), 14D.4 (pacotes), 14D.5 (quitação), 14D.12 (passe), 14D.14 (temporada).
**Não inclui:** política de reembolso de pacote/passe, PSP real, repasse real ou UI.

## Problema

O saldo era único. Não havia como distinguir franquia do passe, ingresso
comprado e ingresso grátis de nível; o passe não expirava e o reembolso não
devolvia ao lote original. Isso impedia a ordem de consumo e a contabilidade do
passivo.

## Decisões

1. Cada crédito cria um `ticket_lot` com origem, saldo, referência e validade.
2. Ingressos comprados não expiram; franquia do passe expira no ciclo mensal;
   ingressos de nível expiram no fim da temporada.
3. O consumo usa primeiro `pass`, depois `free_level`, depois `purchase`.
4. Lotes expirados não contam no saldo, mas permanecem no histórico.
5. A devolução procura o consumo original da reserva e restaura o lote, se ele
   ainda estiver válido. Franquia expirada não vira ingresso comprado.
6. O saldo legado sem lotes é convertido em lote administrativo na primeira
   utilização.
7. Rotinas `deliver_pass_months` e `close_seasons` expiram lotes vencidos.
8. `GET /me/tickets` passa a devolver `lots` com origem, saldo e validade.
9. A conciliação de `purchase_payments` com o PSP ganhou rotina própria, sem
   corrigir saldo automaticamente.

## Modelo

Migração `c9f0a1b2d3e4`:

- `ticket_lots` (`source`, `original_amount`, `remaining`, `expires_at`,
  `ref_type`, `ref_id`, `ledger_entry_id`);
- `ticket_lot_consumptions` (lote, reserva, valor, ledger);
- `ticket_ledger.source` passa a aceitar `expired`.

## Superfície

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/v1/me/tickets` | Saldo, movimentos e lotes ativos com validade |

## Testes

- `tests/test_tickets.py`: ordem passe → nível → compra, expiração, devolução
  ao lote ativo e recusa de conversão de passe expirado.
- `tests/test_pass.py`: entrega mensal com expiração da franquia.
- `tests/test_season_track.py`: ingresso grátis expira no fim da temporada.
- `tests/test_purchase_reconciliation.py`: conciliação de compra pendente, paga,
  valor divergente e PSP indisponível.
- Suíte existente de quitação, reservas e financeiro preservada.

## Pendente

1. Política de reembolso de pacote/passe (hoje não aprovada).
2. Conciliação e reembolso reais com PSP/Inter.
3. Exposição dos lotes no app e no painel.
4. Migração/backfill de carteiras legadas em ambiente com dados (o local está vazio).
5. Calibração de expiração e comunicação ao jogador.
