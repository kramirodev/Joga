# ADR 0040 — Repasse à quadra no horário da partida

- **Status:** Aprovado e implementado em 2026-11-09.
- **Data:** 2026-11-09
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0039 (cancelamento/substituição/presença), ADR 0037 (reembolsos), ADR 0034 (Mercado Pago no beta), ADR 0021 (Pagar.me em produção); `docs/JOGA_DOCUMENTACAO_TECNICA.md` §14.7/§16.

## Contexto

A política anterior condicionava a liberação à reserva `COMPLETED` e mantinha `N` horas de espera. Isso fazia o repasse depender da conclusão da partida e da ação do estabelecimento, embora o serviço contratado seja a reserva da quadra.

## Decisão

1. O valor devido ao estabelecimento é liberado **2 horas após o início da reserva** (`starts_at + 2h`), não mais após `COMPLETED + N`. A retenção curta reduz tentativa de fraude da quadra.
2. `JOGA_RELEASE_DELAY_HOURS` passa a ser **2** por padrão.
3. Reserva `CONFIRMED` ou `COMPLETED` com pagamentos `PAID` gera liberação `PENDING` e o worker libera quando `eligible_at <= now`.
4. Reserva cancelada antes do início (falha da coletiva, quadra/JOGA) **não** gera repasse; o hold é liberado e os reembolsos seguem a ADR 0039.
5. No-show ou desistência depois do cutoff mantém a reserva `CONFIRMED`; a quadra recebe normalmente no horário, independentemente da partida acontecer.
6. O estabelecimento não é responsável pela organização da partida. O JOGA faz esforços de matchmaking/substituição, mas não garante comparecimento.
7. A janela de contestação após a liberação, MED/chargeback e conciliação com PSP continuam pendentes.

## Consequências

- `FinancialService.ensure_release` aceita `CONFIRMED`/`COMPLETED` e usa `starts_at + 2h` como referência.
- O worker `scripts.release_payments.py` cria liberações faltantes para reservas confirmadas/concluídas e libera as vencidas.
- O ledger `VENUE_RELEASE` é gravado uma única vez por reserva.
- `N = 24 h` deixa de existir como padrão; a variável permanece apenas como atraso opcional.
- Se a quadra falhar ou o JOGA não entregar a reserva, não há repasse e o reembolso é integral.
- O risco de a partida não acontecer por ausência de jogadores é comercialmente assumido; o valor da reserva pertence à quadra após o horário.
- Contestação depois do repasse e recuperação de valor continuam dependentes da política de MED/PSP.

## Evidências

- Implementação em `backend/app/modules/payments/financial.py` e `scripts/release_payments.py`.
- `JOGA_RELEASE_DELAY_HOURS=2` em `.env.example`.
- Testes de liberação em `tests/test_financials.py`: `eligible_at == starts_at`, liberação antes/depois, idempotência e conciliação.
- Migrações já existentes de `venue_releases`; sem nova tabela.
