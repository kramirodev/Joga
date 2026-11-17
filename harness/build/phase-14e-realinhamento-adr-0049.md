# Fase 14E — Realinhamento da ADR 0049

**Status:** **implementada, pendente de revisão/commit**. Etapas 0–11 e 6b entregues; commit e push autorizados em 17/11/2026 e publicados em `65d9ff5`, `7c56da5` e `5afd32c`. 14B e 18 não iniciadas.
**Depende de:** 14, 14D congeladas e estabilização do repositório.
**Bloqueia:** 14B, 15, 19A e qualquer dinheiro real.
**Referência:** `docs/ADR/0049-modelo-tributario-da-intermediacao.md`, `docs/DECISOES_BACKEND_ADR_0049.md`, `docs/DATA_MODEL.md`.

## Objetivo

Fazer o código refletir a decisão vigente: crédito em reais como substância, ticket como unidade de exibição 1:1, preço em duas linhas, ledger de dupla entrada, CPF, NFS-e placeholder e custódia B→C.

## Escopo

- Saldo e ledger em centavos/reais como fonte da verdade.
- Ticket como unidade de exibição; saldo em reais não exibido como carteira.
- Persistir `venue_price_cents`, `fee_cents`, `fee_percent_applied`, `total_cents` por reserva.
- Integrar `LedgerService` em reserva, compra, passe, reembolso e repasse.
- Migrar lotes existentes pelo preço unitário pago; crédito comprado sem expiração.
- Passe com período mensal não acumulável e fora do escrow.
- CPF cifrado e NFS-e como intenção/documento por reserva.
- Remover o uso dos ledgers legados como fonte principal.
- Corrigir os P0 financeiros identificados na auditoria de 16/11 (T3 sem devolução, Pix + crédito, repasse após reembolso, `EXPIRED`, idempotência de compra).

## Fora do escopo

- Escolher fornecedor de escrow.
- Dinheiro real.
- Fixar alíquota, taxa final ou NFS-e operacional.
- Implementar UI nova fora do necessário para exibir preço/tickets.

## Plano

1. **Red:** testes que falham para saldo em reais, preço em duas linhas, ticket 1:1, ausência de expiração, devolução no T3 e bloqueio de cobrança dupla.
2. **Green:** migrations aditivas, serviços e ledger; migração de lotes idempotente.
3. **Refactor:** remover caminhos legados, sem manter dois saldos.
4. **Verify:** migrations do zero, `alembic check`, testes de concorrência e conciliação, revisão de dados.

## Critérios observáveis

- Nenhuma obrigação financeira fora do ledger em reais.
- Reserva guarda preço/taxa/percentual/total.
- Ticket exibido é 1:1 e o saldo em reais não é exibido.
- Preço do espaço, taxa e tabela de conversão aparecem antes da confirmação.
- NFS-e registrada por reserva.
- Crédito comprado não expira; passe tem período.
- T3 devolve crédito; Pix pago impede quitação por crédito.
- Reembolso bloqueia/reverte repasse.
- Migração de lotes idempotente e auditável.

## Comandos reais

```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy app
```

## Condição de parada

A fase termina quando os critérios acima estão verdes, a documentação está reconciliada e o usuário autoriza o commit/merge. Não iniciar 14B/15 automaticamente.

## Etapa 8 — conformidade (14E-E)

- **CPF:** `user_profiles.cpf_ciphertext`/`cpf_key_id`/`cpf_last2`/`cpf_updated_at` com AES-256-GCM, AAD = `user_id`, chave em `JOGA_CPF_KEY` e rotação por `JOGA_CPF_PREVIOUS_KEYS`. Endpoints `GET/PUT/DELETE /api/v1/me/cpf` só devolvem presença e máscara.
- **Fiscal:** `fiscal_documents` continua uma intenção por reserva; `fiscal_document_takers` guarda um tomador por jogador com cota e CPF cifrado. A confirmação grava `pending_manual` com `JOGA_FISCAL_MODE=placeholder`, sem emissor, município ou alíquota.
- **Termos:** `terms_acceptances` (versão, contexto, `terms_hash`, `ip_hash` HMAC e `user_agent_hash` SHA-256). `GET /legal/terms/current` e `POST /legal/terms/accept`; a compra exige aceite apenas quando existe versão `approved`.
- **Reembolso:** `refund_type FULL|PARTIAL`, `idempotency_key` e índice parcial de um único `FULL` por cobrança; nenhum fluxo cria `PARTIAL` nesta etapa.
- **Verificação:** `ruff`, `ruff format --check` e `mypy app` limpos; suíte **587 passed, 30 skipped**; `upgrade head` → `downgrade base` → `upgrade head` e `alembic check` sem diff no PostgreSQL local, head `s3d4e5f6a7b8`.

## Etapa 9 — aposentadoria dos ledgers legados

- **9a (leitura):** `get_balance` lê exclusivamente lotes + ledger. Removidos o modo `cache` e `JOGA_TICKET_BALANCE_SOURCE`; a API mantém `source` com valor constante `ledger`.
- **9b (escrita):** `ticket_balances` deixou de ser escrita e virou **view** sobre `ticket_lots` (`t4e5f6a7b8c9`). O lock de carteira é a linha de `users` (`SELECT ... FOR UPDATE`). Saldo legado sem lote é convertido em lote `admin` auditável com evento em `ticket_ledger`.
- **9c (extrato):** `booking_ledger_entries` foi removido (`u5f6a7b8c9d0`). O extrato do fornecedor e o `booking_ledger` são projeções de `ledger_transactions` + `ledger_entries`; `CHARGE_CREATED` deixou de existir, `PAYMENT_CONFIRMED` representa a parte da quadra e `booking_payment_id` vem nulo.
- **Conciliação:** tickets reconstruídos por `Σ original_amount` + débitos + devoluções que reabriram lote; caixa conferido só para reservas com `confirmed_at` (o débito ocorre na confirmação, não na quitação individual); pagamentos conferem `booking_confirmed`, `booking_refund`, `payment_refund` e `venue_release`, incluindo `VenueRelease.amount_cents == Booking.venue_price_cents`.
- **Verificação:** `ruff`, `ruff format --check` e `mypy app` limpos; suíte **587 passed, 30 skipped**; ciclo `upgrade head` → `downgrade base` → `upgrade head` + `alembic check` sem diff; conversão de saldo legado validada no PostgreSQL local; head `u5f6a7b8c9d0`.

## Etapa 10 — Fase 15 sobre o ledger em reais

- **Extrato:** `payments/statement.py` passou a devolver `release_id`, `venue_price_cents`, `fee_cents` e `total_cents` em cada linha, inclusive nas de `VENUE_RELEASE` (join extra pela reserva). `booking_payment_id` continua nulo; `PAYMENT_CONFIRMED` é a parte da quadra.
- **Recebíveis:** `GET financial/receivables` expõe o preço em duas linhas, `receipt_reference` (comprovante simulado `simulated:<release_id>`, nulo enquanto pendente), `dispute_deadline` e `reason`. O valor do repasse vem de `Booking.venue_price_cents`.
- **Comissão:** novo `GET financial/commission?from=&to=` por reserva confirmada, com `venue_price_cents`, `fee_cents` e `total_cents`; `totals.joga_fee_cents` soma só a comissão. O resumo ganhou `venue_price_cents`/`joga_fee_cents` separados e `reversed_cents`/`failed_cents`.
- **Detalhe da reserva:** `GET organizations/{org}/bookings/{booking}/financial` agora devolve `pricing`, `release`, `dispute` e `fiscal_document` (placeholder `pending_manual`), além de `ledger` e `refunds`.
- **Contestação:** prazo `eligible_at + JOGA_DISPUTE_WINDOW_HOURS` (na Etapa 10 o default técnico era 24 h; **corrigido na Etapa 12 para 72 h persistidas**); só liberação `PENDING` é contestável (`release_not_contestable`/`dispute_window_expired`). Nova `POST .../financial/disputes/{id}/decision` exige `financial:manage` + `JOGA_REVIEW_OPERATORS`, grava `decided_by`/`decided_at` e auditoria `financial.dispute_decided`. O fornecedor não decide a própria contestação.
- **Bloqueio/reversão:** `block_for_chargeback` marca `PENDING` como `FAILED` e `RELEASED` como `REVERSED`, com auditoria, sem tocar saldo. Reembolso continua revertendo via `reverse_for_refund`. MED real permanece em 14B.
- **Sem schema novo:** nenhuma tabela, coluna ou migração; tudo é projeção/derivação do ledger e de `bookings`.
- **Verificação:** `ruff`, `ruff format --check` e `mypy app` limpos; suíte **595 passed, 30 skipped**; testes novos de preço em duas linhas, comissão separada, prazo, decisão autorizada/negada, bloqueio por chargeback, NFS-e placeholder e projeção do extrato contra o ledger.

## Etapa 11 — contrato publicado e parada

- `docs/CONTRATO_RESERVAS_APP.md` ganhou a seção 10 com endpoints, campos, capacidades, erros, semântica de exibição e o aviso explícito de que `participant_id` em `payments[]` é o id da vaga, não o `user_id`.
- `tests/test_openapi_financial.py` confirma que o OpenAPI gerado expõe a rota de comissão, a decisão, os campos novos de recebível/extrato/resumo e o detalhe da reserva.
- `docs/DATA_MODEL.md`, `docs/PENDENCIAS.md`, `docs/JOGA_DOCUMENTACAO_TECNICA.md`, `backend/.env.example` e `harness/build-log.md` atualizados.
- **Pendente:** consumir os campos no painel (15B), comprovante/NFS-e reais, MED/chargeback real, PSP de produção e 14B. 18 não iniciada.

## Correções finais de 17/11/2026

- **Tabela 2D:** confirmadas as 18 células padrão (5x5, 6x6, 3x3) e as quatro correções — Coberta 5x5 11, Padrão noite 6x6 8, Padrão noite 3x3 15, Premium 3x3 20. Teste: `k × 310 ≥ (venue_price + fee) / n`.
- **Consumo e ledger:** `settle_with_tickets` baixa `tickets_per_seat`; o ledger de crédito debita `k × 310` (não `contribution_cents`), credita `venue_payable = space_charge_cents` e `fee_revenue = (k × 310) − space_charge_cents`. Pix mantém `psp_clearing` e taxa de 20%.
- **Notificação `booking_confirmed`:** quadra = `space_charge_cents`, JOGA = `(tickets_consumed × 310) − space_charge_cents`, total = `tickets_consumed × 310`; para Pix, total = `contribution_cents` e JOGA = `fee_charge_cents`. Nunca 20% sobre o total.
- **Invariantes:** conciliação confere espaço somado = `venue_price_cents`, taxa somada = `Σ k×310 − venue_price` em reservas só-crédito, contribuição de crédito = `k×310`, taxa por participante e saldos não negativos. O antigo `ledger == remaining × preço pago` não existe.
- **Cancelamento:** antes do cutoff, devolução integral (inclusive do desistente) e repasse revertido; depois do cutoff, o cancelamento do jogador é bloqueado e o no-show não reembolsa, mantendo a quadra integral e o repasse; quadra que cancela devolve tudo e não recebe; disputa aberta congela o repasse. Não existe reembolso parcial.
- **Janela de contestação:** 72 h (`JOGA_DISPUTE_WINDOW_HOURS=72`), persistida em `venue_releases.dispute_deadline` e `financial_disputes.deadline_at`; `DisputeView` expõe `deadline_at`. Migração `v6a7b8c9d0e1`.
- **Decisões registradas:** custódia B com Inter PJ (sem escrow agora); MED bloqueia repasse + receivable + evidência + prazo, sem clawback (fluxo real 14B); NFS-e terá duas notas por jogador, JOGA no Rio, parâmetros versionados e automação posterior; CPF valida formato no perfil e existência antes da 1ª confirmação; comprovante real `bank:<e2e_id>` + PDF privado.
- **Gate final:** suíte **596 passed, 30 skipped**; `ruff`, `ruff format --check` e `mypy app` limpos; `alembic check` sem diff e ciclo `downgrade -1`/`upgrade head` validado; head `v6a7b8c9d0e1`.
