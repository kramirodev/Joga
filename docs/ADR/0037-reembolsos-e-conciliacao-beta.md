# ADR 0037 — Reembolsos e conciliação no beta com PSP simulado

- **Status:** Aprovado para a 14C em 2026-11-07; reembolso real e conciliação com PSP ficam para a 14B. Emendado pelas **ADRs 0038 e 0039**; para desistência após confirmação, prevalece a **ADR 0039**.
- **Data:** 2026-11-07
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0021 (Pagar.me em produção); ADR 0034 (Mercado Pago no beta); ADR 0035 (Orders API/ledger); `docs/JOGA_DOCUMENTACAO_TECNICA.md` §15 e §16.

## Contexto

A 14A criou cobranças Pix, webhook e ledger, mas ainda não havia reembolso quando a reserva era cancelada ou expirava. Sem isso, o ledger ficaria incompleto e o beta não conseguiria simular o ciclo financeiro real.

## Decisão

1. Toda reserva que chega a um estado terminal não confirmado — `CANCELLED`, `CANCELLED_BY_VENUE`, `CANCELLED_BY_PLAYER`, `EXPIRED` ou `DECLINED` — reembolsa integralmente as cobranças pagas no beta.
2. O reembolso é registrado em `payment_refunds`, com um registro único por cobrança e status `PENDING`, `PROCESSED` ou `FAILED`.
3. O processo é idempotente: repetir cancelamento/reembolso não duplica registro, ledger ou evento.
4. O ledger registra `PAYMENT_REFUNDED` e o adaptador simulado processa o estorno sem rede.
5. O repasse ao estabelecimento (`VENUE_RELEASE`) segue a ADR 0040: reserva `CONFIRMED`/`COMPLETED` com pagamento, liberação no horário da partida, simulado/manual no beta.
6. A substituição de participante reembolsa apenas a cobrança do participante substituído; a nova vaga gera nova cobrança e mantém o prazo de T3.
7. A política de reembolso real e conciliação com PSP continua pendente para a 14B; a desistência após confirmação é definida pela ADR 0039.
8. O worker `advance_bookings` expira prazos e reembolsa reservas pagas que chegaram a estado terminal.
9. A organização consulta resumo financeiro e extrato por reserva; não há conciliação externa com PSP nesta fase.

> **Emenda (ADRs 0038 e 0039):** o item 1 vale para estados anteriores à confirmação. Após `CONFIRMED`, o desfecho segue a ADR 0039: com substituto pagante, o substituído é reembolsado; sem substituto, o lobby é cancelado, os demais pagantes são reembolsados e quem cancelou não recebe; no-show não recebe reembolso.

## Alternativas consideradas

### A. Não reembolsar no beta

Deixaria o ledger incompleto e não testaria o fluxo de cancelamento. Rejeitada.

### B. Reembolso manual

Seria possível, mas não exercita idempotência, ledger e automação. Rejeitada para o beta.

### C. Reembolso automático com PSP simulado (adotada)

Permite testar o ciclo completo sem dinheiro real e prepara o domínio para o PSP de produção.

## Consequências

- Cancelamentos e expirações deixam o ledger consistente.
- O beta consegue testar reembolso de jogador, de estabelecimento e de substituto.
- O adaptador real precisa implementar estorno e conciliação na 14B.
- A política definitiva de reembolso após confirmação continua pendente.
- O resumo financeiro interno não substitui extrato ou conciliação do PSP.

## Critérios para revisão

- Contrato do PSP de produção e regras de estorno/MED.
- Definição da política de cancelamento após confirmação.
- Conciliação periódica e comprovantes reais.
- Volume de disputas e reembolsos no piloto.
