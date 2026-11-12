# Fase 14D.6 — Devolução em ingresso no cancelamento

**Status:** implementado localmente em 2026-11-12.
**Branch:** `main`

## Fontes e contexto

- ADR 0039 (matriz consolidada de cancelamento, substituição e ausência)
- ADR 0042 §2 item 4 (devolução é sempre em ingresso)
- Fase 14D.5 (quitação por ingressos)

## Objetivo

Fazer a matriz da ADR 0039 valer sobre a carteira, não sobre o dinheiro.

## Regra aplicada

| Desfecho | Ingressos |
|---|---|
| Cancelamento pelo estabelecimento | **Todos** recebem de volta |
| Cancelamento pelo sistema (sem substituto) | **Todos** recebem de volta |
| Cancelamento pelo jogador, antes do cutoff | **Os demais** recebem; quem cancelou perde |
| No-show | Ninguém recebe (já tratado pela ADR 0039) |

O corte do cutoff continua no `cancel`, não no serviço: depois do prazo, a API recusa o
cancelamento e ninguém é reembolsado.

## Implementação

- `BookingService._refund_tickets` — percorre as vagas ativas, devolve `tickets_consumed` e
  marca `payment_status = REFUNDED`.
- Chamado em `cancel(by_venue=True)`, `cancel(by_player)` (excluindo o autor) e
  `cancel_by_system`.
- A devolução usa `refund` com chave `booking_cancel:{booking_id}:{user}`, portanto repetir o
  cancelamento não devolve duas vezes.

## Testes

`tests/test_ticket_settlement.py` (seis casos):

- quitação por participante confirma a reserva;
- quitação repetida não debita duas vezes;
- saldo insuficiente bloqueia sem alterar a reserva;
- cancelamento pela quadra devolve para todos;
- cancelamento pelo jogador devolve só para os outros;
- cancelamento pelo sistema devolve para todos.

Suíte completa, `ruff`, `mypy --strict` e `alembic check` verdes.

## Limitações conhecidas

1. **Cobranças Pix não são canceladas.** No aceite da quadra são criadas cobranças para todos;
   quem quita por ingresso deixa a cobrança `PENDING`. Falta encerrá-las.
2. **Substituição não devolve o ingresso do substituto.** O fluxo de substituto ainda não
   conhece a carteira.
3. **No-show não consome nem devolve nada além do já consumido** — está correto pela ADR 0039,
   mas não há teste específico de carteira para ele.

## Próxima fatia

**14D.7 — Temporada, XP e trilha**, ou o fechamento das cobranças pendentes. A escolha depende
de prioridade de produto.
