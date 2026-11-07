# ADR 0035 — Orders API, webhook e ledger na Fase 14A

- **Status:** Aprovado para a 14A em 2026-11-07.
- **Data:** 2026-11-07
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0034 (Mercado Pago no beta); ADR 0021 (Pagar.me na produção); `docs/JOGA_DOCUMENTACAO_TECNICA.md` §15; `PLANS.md` Fase 14.

## Contexto

O Mercado Pago atualiza o Checkout Transparente para Pix via **Orders API** (`/v1/orders`), com uma ordem contendo transações/pagamentos. A API antiga de `/v1/payments` continua existindo, mas não é o fluxo principal documentado para Pix. O JOGA precisa de uma cobrança por participante, idempotência, webhook confiável e um ledger interno que não dependa do PSP.

## Decisão

1. A 14A usa **Orders API** do Mercado Pago para criar uma ordem Pix por participante.
2. `external_reference` é o ID interno da cobrança (`booking_payments`), e `X-Idempotency-Key` usa o mesmo valor.
3. O `payer.email` é obrigatório. No sandbox, usar `JOGA_MERCADO_PAGO_PAYER_EMAIL`; em produção, coletar e-mail real ou definir identidade de pagamento.
4. O adaptador `simulator` é o padrão em local/test/CI; o adaptador `mercadopago` exige token sandbox e não pode operar dinheiro real.
5. O webhook é público em `/api/v1/payments/mercadopago/webhook`, valida HMAC quando o segredo estiver configurado e usa `psp_webhook_events` para idempotência por evento.
6. O status só é aplicado após consulta server-to-server da ordem/pagamento; o payload do webhook não é prova suficiente.
7. A confirmação da reserva continua no domínio de reservas e só ocorre com todas as vagas ativas pagas.
8. O ledger é append-only: `CHARGE_CREATED`, `PAYMENT_CONFIRMED`, `PAYMENT_REFUNDED` e `VENUE_RELEASE`.
9. `VENUE_RELEASE` no beta é um registro simulado/manual após `COMPLETED`; não movimenta dinheiro.
10. Não há split, retenção ou reembolso real na 14A.

## Alternativas consideradas

### A. Payments API (`/v1/payments`)

Compatível com cartões e legado, mas o fluxo Pix atual do Checkout Transparente recomenda Orders API. Não adotada como principal.

### B. Webhook como prova de pagamento

Rejeitada: o evento pode ser forjado/repetido. A consulta server-to-server é obrigatória.

### C. Ledger somente no PSP

Rejeitada: o JOGA precisa de direitos e obrigações internos, inclusive quando trocar de PSP.

## Consequências

- O adaptador fica desacoplado do formato exato da Orders API.
- O webhook pode ser reenviado sem duplicar pagamento/ledger.
- O beta não movimenta dinheiro real e não promete retenção de produção.
- A 14B precisará trocar o adaptador para Pagar.me e implementar split/retenção/reembolso real.
- O e-mail do pagador continua pendente no cadastro por telefone.

## Critérios para revisão

- Credenciais sandbox validadas com uma ordem real de teste.
- Definição do e-mail real do pagador.
- Início do beta com dinheiro real (CNPJ/MEI e revisão jurídica).
- Migração para Pagar.me na 14B.
