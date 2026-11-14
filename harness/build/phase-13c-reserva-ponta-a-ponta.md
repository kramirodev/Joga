# Fase 13C — Reserva ponta a ponta (vitrine e contrato)

**Status:** implementado no backend em 2026-11-14.
**Depende de:** 13A (reservas), 14D.1 (faixas), 14D.2 (fornecedor), 14D.5 (quitação por ingressos).
**Não inclui:** telas do app, painel de payout, PSP real ou repasse real.

## Problema

O app tinha telas de reserva, mas não conseguia descobrir uma quadra comercial
reservável nem obter os identificadores necessários para chamar `POST /bookings`.
O backend também permitia abrir reserva para estabelecimento sem chave de
repasse e não registrava a obrigação com o fornecedor quando a quitação era por
ingressos.

## Decisões

1. A vitrine é autenticada e expõe apenas estabelecimentos ativos com quadra
   ativa e ao menos uma janela de agenda. Nenhum dado financeiro, de payout,
   CNPJ, chave Pix ou auditoria é retornado.
2. A listagem aceita cidade e paginação; usa a região do jogador apenas para
   calcular distância, nunca para revelar coordenada residencial.
3. O detalhe devolve quadras, modalidades, formatos, faixas, agenda semanal,
   fotos aprovadas e próximos horários dos 7 dias seguintes.
4. Fotos só são servidas quando aprovadas e quando estabelecimento/organização
   estão ativos.
5. `POST /bookings` passa a exigir `payout_ready` do estabelecimento
   (`payout_not_ready` em 409). A chave Pix/CNPJ continua sendo cadastrada pelo
   painel ou pela API de organização.
6. A reserva congela `band_id` e `tickets_per_seat` no momento da criação.
   Reajuste posterior da janela não altera reserva existente.
7. A obrigação de repasse nasce na confirmação da reserva, com valor
   `booking.price_cents`, independentemente de Pix, ingressos ou composição
   mista. O worker continua liberando em `starts_at + 2h` (ADR 0040).
8. `BookingView` ganhou campos aditivos: nome do estabelecimento/quadra,
   formato, faixa, ingressos por vaga e, por participante, `settled_with` e
   `tickets_consumed`.

## Superfície

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/v1/discovery/bookable-venues` | Lista estabelecimentos reserváveis com filtro de cidade e paginação |
| GET | `/api/v1/discovery/bookable-venues/{venue_id}` | Detalhe de quadras, formatos, faixas, agenda e próximos horários |
| GET | `/api/v1/discovery/bookable-venues/{venue_id}/photos/{photo_id}/content` | Foto aprovada, autenticada |
| POST | `/api/v1/bookings` | Cria reserva após validar disponibilidade, faixa e `payout_ready` |

## Modelo

Migração `b8e1f2a3c4d5` adiciona a `bookings`:

- `band_id` — FK opcional para `pricing_bands`;
- `tickets_per_seat` — inteiro opcional, não negativo;
- índice `ix_bookings_band_id`.

## Testes

- `tests/test_discovery_api.py`: listagem sem dados financeiros, detalhe com
  faixa e ingressos, foto não exposta, `payout_not_ready`, criação com contexto
  de ingresso e snapshot imutável após reajuste.
- `tests/test_ticket_settlement.py`: reserva quitada com ingressos gera
  `VenueRelease` de valor integral e liberação idempotente.
- Testes existentes de reservas, pagamentos, financeiro e conciliação ajustados
  para o novo portão e para a obrigação de repasse.

## Pendente

1. Ligar a tela de reserva do app a `discovery` e a `POST /bookings`.
2. Expor no painel o cadastro de payout, faixa/cobertura e a nova leitura de
   repasse.
3. Revisão independente de fotos e política de retenção (Fase 17/19).
4. T2 em horário comercial, feriados e pausa com reserva confirmada.
5. Repasse real, Inter PJ, KYC contratual e conciliação com PSP (Fase 14B).
6. Paginação eficiente da vitrine e cache quando houver volume.
