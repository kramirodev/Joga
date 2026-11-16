# ADR 0048 — Mercado Pago como PSP do protótipo com jogadores reais

- **Status:** Aprovado em 2026-11-15. Supera em parte a ADR 0034 e a nota de escopo da ADR 0035. A centralização do valor na conta da JOGA é condicionada pela **ADR 0049 §2.8** (modelo B no protótipo, C na fase comercial).
- **Data:** 2026-11-15
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0034 (Mercado Pago no protótipo/beta), ADR 0035 (Orders API, webhook e ledger), ADR 0040 (repasse), ADR 0042 (ingresso), `PLANS.md` Fase 14, `docs/PENDENCIAS.md`.

## Contexto

O protótipo deixa de ser uma vitrine sem jogadores. Pessoas reais vão reservar
quadras e comprar pacotes/passe, e o Pix precisa funcionar de ponta a ponta. A
ADR 0034 tratava o Mercado Pago como PSP restrito a sandbox, com Inter PJ como
produção futura; essa separação criava uma dependência que não existe no
protótipo e levava configuração de sandbox a ambientes com dinheiro real.

## Decisão

1. O **Mercado Pago (Orders API, Pix)** é o PSP do protótipo **com jogadores
   reais**, usando credenciais de produção do ambiente quando este não for
   local/teste.
2. **Inter PJ, Pagar.me e adaptadores equivalentes não são dependência** do
   protótipo. Ficam para o futuro, quando houver decisão comercial própria.
3. Fora do ambiente local/teste, o backend **não sobe** sem:
   `JOGA_PSP_PROVIDER=mercadopago`, access token, `JOGA_MERCADO_PAGO_WEBHOOK_SECRET`
   e `JOGA_MERCADO_PAGO_NOTIFICATION_URL` pública em HTTPS.
4. Não há e-mail de pagador fictício nem global. A cobrança usa o e-mail da
   própria conta (`users.email`, normalizado) e o snapshot fica em
   `booking_payments.payer_email`/`purchase_payments.payer_email`; sem e-mail, a
   abertura responde `422 payer_email_required`.
5. O Mercado Pago **centraliza o valor**. O JOGA mantém ledger interno e o
   repasse ao estabelecimento continua manual/registrado no ledger, conforme a
   ADR 0040. **Não há split, recebedor automático nem promessa de repasse
   automático.**
6. Webhook público valida assinatura HMAC, persiste o evento bruto e aplica
   status somente após consulta server-to-server. A URL e o segredo são
   configuração de ambiente, não payload.
7. Confirmação local de pagamento (`/tickets/purchases/{id}/confirm` e
   `/pass/subscriptions/{id}/confirm`) permanece **dev-only** e responde `403`
   fora de local/teste.
8. MED/chargeback, conciliação real e retry de webhook são tratados como
   operação do protótipo (MP-05, MP-08, MP-10), sem score de risco nem promessa
   de custódia regulada.

## Alternativas consideradas

### A. Manter sandbox e adiar jogadores reais

Evita risco operacional, mas impede validar a jornada que o produto precisa
testar. Rejeitada para o protótipo atual.

### B. Esperar Inter PJ ou Pagar.me

Acopla o protótipo a uma contratação futura e não resolve a cobrança agora.
Rejeitada; os adaptadores continuam possíveis no futuro.

### C. Split/recebedor no Mercado Pago

Credita o estabelecimento diretamente e muda o modelo de custódia, reembolso e
conciliação. Fora do escopo; o modelo aprovado é conta centralizada + ledger.

## Consequências

- Ambientes não locais exigem configuração completa de PSP; o startup falha
  cedo em vez de cair em simulador silenciosamente.
- O e-mail do pagador passa a ser requisito de cobrança e precisa de fluxo no
  app/perfil.
- Webhook, conciliação e reembolso reais precisam de validação com credenciais
  do Mercado Pago antes do go-live.
- O ledger e a máquina de estados continuam independentes do PSP.
- Inter/Pagar.me deixam de ser pendência bloqueante do protótipo.

## Critérios para revisão

- Início de operação com dinheiro real em escala comercial.
- Exigência regulatória, de custódia ou de split pelo modelo de negócio.
- Mudança de PSP por custo, cobertura ou contrato.
- Incidente de MED/chargeback que exija retenção ou garantia adicional.
