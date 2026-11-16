# Fase 13D/15C — Painel JOGA y QUADRA alinhado ao fornecedor

**Status:** implementado no painel web em 2026-11-14.
**Depende de:** 11B/11C (painel), 12A (quadras), 13C (reserva), 14D.1 (faixa), 14D.2 (payout), 15A/15B (financeiro local).
**Não inclui:** PSP real, KYC contratual, recibos fiscais, notificações em tempo real ou ERP.

## Problema

O painel ainda falava em “recebíveis/liberação” e não permitia cadastrar o
destino de repasse, editar o preço da janela, marcar cobertura ou operar
cancelamento, reembolso e presença. O financeiro também não refletia o modelo de
fornecedor pago por Pix.

## Decisões

1. O painel mostra o status de repasse e permite que proprietário/administrador
   cadastrem CNPJ e chave Pix.
2. O operador continua lendo o financeiro, mas não altera o destino de repasse.
3. A quadra ganhou o atributo visível “coberta”, editável.
4. A janela semanal exibe a faixa calculada pelo backend e permite reajuste; a
   reserva existente mantém o preço congelado.
5. Reservas mostram formato, quadra, faixa, ingressos por vaga e participantes.
6. O estabelecimento pode cancelar, reembolsar cobranças pagas e confirmar
   presença de participante não verificado.
7. A linguagem financeira passa de “recebível/liberação” para “repasse a
   receber/repassado”.
8. Nenhuma tela cria reserva ou altera regra competitiva.

## Superfície consumida

- `PUT /organizations/{id}/payout`
- `PATCH /organizations/{id}/venues/{venue}/spaces/{space}/availability/{id}`
- `PATCH /organizations/{id}/venues/{venue}/spaces/{id}`
- `POST /organizations/{id}/bookings/{booking}/cancel`
- `POST /organizations/{id}/bookings/{booking}/refund`
- `POST /bookings/{booking}/presence`
- `GET /pricing/bands`

## Validação

- `pnpm typecheck`, `pnpm lint`, `pnpm format:check` e `pnpm test`: **20 testes**
  passando.
- Teste novo cobre o cadastro de destino de repasse.
- Teste existente de contestação e aceite de reserva preservado.

## Pendente

1. Convite de membros por telefone/QR (backend ainda só aceita UUID).
2. Notificações de nova reserva e prazos no painel.
3. Comprovantes, exportação e conciliação com PSP real.
4. KYC contratual e transferência real.
5. Revisão visual/acessibilidade e testes E2E com API real.
