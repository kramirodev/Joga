# Fase 14D.5 — Quitação da vaga por ingressos

**Status:** implementado localmente em 2026-11-12.
**Branch:** `main`

## Fontes e contexto

- `PLANS.md` Fase 14D
- ADR 0042 §2 item 8 (o débito é do saldo do próprio jogador)
- ADR 0042 §3 (tabela 2D: faixa × formato)
- Fase 14D.3 (carteira) e 14D.4 (compra)

## Decisão de produto

**Modelo A:** cada participante quita a própria vaga com os próprios ingressos. A reserva
confirma quando todas as vagas ativas estão quitadas — por ingresso ou por Pix. O ingresso é
pessoal e intransferível; ninguém paga pela vaga de outro.

Essa decisão está registrada na ADR 0042 §2 item 8.

## Implementação

- `pricing_band_tickets` — matriz faixa × tamanho de time, semeada com os 24 valores da ADR 0042 §3.
- `booking_participants.settled_with` (`pix`/`tickets`) e `tickets_consumed`.
- `BookingService.settle_with_tickets` — resolve a tabela 2D para a reserva, consome do saldo do
  participante e marca a vaga como quitada; `_confirm_if_all_paid` confirma a reserva na última vaga.
- `POST /api/v1/bookings/{id}/settle-with-tickets`.

## Resolução da tabela 2D

1. Localiza a janela de disponibilidade da reserva (dia da semana e horário no fuso da quadra).
2. Lê `band_id` da janela.
3. Lê o `team_size` do formato do lobby.
4. Consulta `pricing_band_tickets`.

Se a janela não tiver faixa, ou a matriz não cobrir o formato, a operação falha com
`409 tickets_not_configured` — nunca cobra um número inventado.

## Testes

`tests/test_ticket_settlement.py`:

- cada participante quita a própria vaga e a reserva confirma na última;
- saldo chega a zero e `tickets_consumed` é gravado;
- quitar duas vezes não debita duas vezes;
- saldo insuficiente retorna `409 insufficient_tickets` e a reserva continua `PAYMENT_PENDING`.

Suíte completa, `ruff`, `mypy --strict` e `alembic check` verdes; migração `f5a6172b3949`
testada em upgrade, downgrade e novo upgrade.

## Limitações conhecidas

1. **Consumo na quitação, não na confirmação.** O débito acontece quando o participante quita,
   que é antes da confirmação. A reserva pode expirar depois e devolver — o que é seguro, mas
   não é literalmente "consumido na confirmação".
2. **T3 ainda existe.** A janela de pagamento continua abrindo; quem não quitar expira, igual a
   quem não paga.
3. **Devolução em ingresso não está ligada ao cancelamento.** `refund` existe e é idempotente,
   mas o fluxo da ADR 0039 ainda estorna em dinheiro.
4. **Cobranças Pix continuam sendo criadas** no aceite da quadra, mesmo quando todos quitam por
   ingresso. Elas ficam `PENDING` e não são canceladas.

## Próxima fatia

**14D.6 — Devolução em ingresso e cancelamento:** aplicar a matriz da ADR 0039 sobre a carteira
e parar de criar cobranças quando a quitação é por ingresso.
