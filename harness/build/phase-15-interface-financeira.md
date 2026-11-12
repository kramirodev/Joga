# Fase 15 — Interface financeira e conciliação

**Status:** 15A (backend financeiro) e 15B (painel) implementados como **proposta técnica local**
em 2026-11-09. Este arquivo **não registra aprovação** de prazo de liberação, modelo de repasse,
forma de moderação financeira nem tratamento de divergência.
**Branch:** `feat/15-interface-financeira`

## Fontes e contexto

- `AGENTS.md`, `GOALS.md`, `PLANS.md` Fase 15
- `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §12.6 e §14
- `docs/JOGA_DOCUMENTACAO_TECNICA.md` §14.7 e §16
- ADR 0021 (Pagar.me em produção) e ADR 0034 (Mercado Pago no protótipo/beta)
- Fases 13A/13B (reservas), 14A/14C (Pix, webhook, ledger e reembolsos)

## Objetivo

Dar ao estabelecimento uma visão financeira auditável das reservas originadas no JOGA:
extrato, agenda de recebíveis, estado de liberação, contestação de valores e conciliação
interna. Nenhum dinheiro real, split ou repasse real é movimentado nesta fase.

## Decisões NÃO aprovadas

Os itens abaixo são **propostas técnicas** desta implementação. Não devem ser tratados como
regra de produto, política financeira ou decisão de arquitetura aprovada.

| Tema | Situação | Observação |
|---|---|---|
| `N = 24 h` para liberação | **Não aprovado** | Default técnico configurável; prazo comercial em aberto |
| Liberação/repasse simulados no ledger | **Não aprovado** | Requisitos financeiros existem; modelo final não foi decidido |
| Contestação decidida por CLI | **Não aprovado** | A CLI foi aceita provisoriamente para resultados esportivos, não para moderação financeira |
| Divergência de valor marcada como `FAILED` | **Não aprovado** | Salvaguarda técnica; procedimento oficial de divergência não definido |
| Ausência de PSP real/conciliação externa | **Parcialmente definido** | PSP e provedor continuam pendentes |
| Sem alteração em mobile, MMR e Trust Factor | **Compatível** | Mantido o escopo já estabelecido |

## Três relógios distintos

Não misturar prazo de pagamento, prazo de contestação e prazo de repasse.

| Relógio | O que mede | Estado atual |
|---|---|---|
| Pagamento (T3) | Janela para os participantes pagarem dentro do bloqueio da quadra | Definido como requisito (estimativa inicial de 60 min) |
| Contestação | Janela para o estabelecimento contestar valores/repasse | **Não definido** |
| Repasse/liberação | Quando o valor fica disponível e quando é transferido | **Não definido**; o default técnico de 24 h não é aprovação |

A implementação atual usa um único `eligible_at` derivado de `completed_at + N` e permite
contestação enquanto a liberação está `PENDING`. Isso **não** substitui a definição dos três
relógios e deve ser revisado quando a política for aprovada.

## Escopo 15A — backend (proposta técnica)

- `venue_releases`: registro por reserva do valor a liberar, com `PENDING`, `RELEASED`,
  `FAILED` e `REVERSED`, data elegível e referência.
- Liberação simulada: somente reserva `COMPLETED`; `eligible_at = completed_at + N horas`,
  com `N` configurável em `JOGA_RELEASE_DELAY_HOURS`. O default 24 h é **técnico e não
  aprovado**. A gravação de `VENUE_RELEASE` no ledger é idempotente.
- Worker `scripts/release_payments.py` libera o que venceu, cria registros faltantes para
  reservas concluídas e é seguro para reexecução. O modelo de repasse real não está definido.
- `financial_disputes`: canal de contestação do estabelecimento por reserva, com valor,
  motivo, evidência, decisão, justificativa, operador e timestamps append-only. Prazos e
  efeitos após a liberação continuam pendentes.
- Contestação `OPEN` suspende a liberação no protótipo; esse comportamento também é proposta
  técnica, não regra aprovada.
- Decisão por CLI interna (`scripts/review_financial_dispute.py`) com operadores de
  `JOGA_REVIEW_OPERATORS`. **Provisória para teste**; não é o modelo aprovado de moderação
  financeira.
- Endpoints:
  - `GET /api/v1/organizations/{org}/financial/summary` (estendido)
  - `GET /api/v1/organizations/{org}/financial/receivables`
  - `GET /api/v1/organizations/{org}/financial/statement`
  - `GET/POST /api/v1/organizations/{org}/financial/disputes`
  - `GET /api/v1/organizations/{org}/financial/disputes/{id}`
  - `GET /api/v1/organizations/{org}/bookings/{booking}/financial` (mantido)
- Capacidades novas `financial:read` e `financial:manage`; `OWNER`/`ADMIN` gerenciam,
  `OPERATOR` apenas lê. Toda consulta é escopada pela organização.
- `scripts/reconcile_financials.py` compara pagamentos, reembolsos, liberações e ledger e
  reporta divergências para investigação. O tratamento oficial de divergência **não foi
  definido**; marcar como `FAILED` é apenas uma salvaguarda técnica.

## Escopo 15B — painel web (proposta técnica)

- Aba **Financeiro** na organização com resumo, agenda de recebíveis, extrato e
  contestações.
- Contestação aberta pelo `OWNER`/`ADMIN` com motivo obrigatório; listagem do histórico e
  da decisão.
- `OPERATOR` vê os dados financeiros, mas não abre contestação.
- Invalidação de cache após contestação/ações de reserva para manter os números coerentes.
- A tela deve deixar explícito que prazos e regras de liberação são configuráveis e
  pendentes de aprovação.

## Fora do escopo

- Dinheiro real, Pagar.me, split, retenção e transferência real (14B).
- MED, chargeback e estorno sem saldo (14B/15 futura).
- KYC do recebedor e dados contratuais (12B).
- Comprovantes/notas em PDF, exportação fiscal e ERP.
- Painel interno de moderação financeira; a CLI é apenas provisória de teste.
- Definição comercial de `N`, janela de contestação e janela de repasse. A política de
  cancelamento/substituição/presença foi definida na ADR 0039; a implementação (fila, timers,
  presença, adaptação e reversão da ADR 0038) é tarefa separada.
- Alteração automática de MMR, Trust Factor ou qualquer regra competitiva.

## Arquivos/componentes

- `backend/app/modules/payments/models.py` — liberações e contestações.
- `backend/app/modules/payments/financial.py` — casos de uso financeiros.
- `backend/app/modules/payments/reconciliation.py` — conciliação interna.
- `backend/app/modules/payments/service.py` — resumo estendido e compatibilidade.
- `backend/app/modules/organizations/permissions.py` — capacidades.
- `backend/app/api/v1/payments.py` — contratos HTTP.
- `backend/app/core/config.py` — `JOGA_RELEASE_DELAY_HOURS` (default técnico).
- Migração Alembic revisável com backfill do ledger existente.
- `backend/scripts/release_payments.py`, `backend/scripts/review_financial_dispute.py`,
  `backend/scripts/reconcile_financials.py`.
- `web/src/pages/OrganizationPage.tsx`, `web/src/lib/api.ts`, `web/src/lib/query.ts`,
  `web/src/types.ts`, estilos e testes.
- `docs/RUNBOOK.md`, `PLANS.md`, `docs/PENDENCIAS.md`, `harness/build-log.md`.

## Riscos

- **Alto:** implementação ser confundida com política aprovada. Todo artefato deve rotular
  prazo, repasse, CLI e `FAILED` como proposta/pendência.
- **Alto:** liberar valor sem reserva concluída ou com pagamento incompleto. Só liberar
  `COMPLETED` com cobrança `PAID` e valor > 0.
- **Alto:** dupla liberação. Constraint única por reserva + ledger idempotente + worker
  reentrante.
- **Alto:** vazamento financeiro entre organizações. Consulta sempre filtrada por
  `organization_id` e capacidade verificada no servidor.
- **Médio:** contestação usada para travar liberação indefinidamente, pois não há prazo de
  contestação aprovado.
- **Médio:** divergência entre ledger, PSP simulado e reserva. A conciliação reporta; o
  procedimento oficial não está definido.
- **Pendente:** PSP real, MED, KYC, os três relógios, modelo de moderação e revisão jurídica.

## Plano de verificação

- **Red:** testes para liberação antes do prazo configurado, dupla liberação, contestação
  bloqueando liberação, decisão não autorizada, acesso cruzado entre organizações e
  divergência de conciliação.
- **Green:** modelos, serviço, endpoints, worker, CLI e conciliação.
- **Refactor:** manter rotas finas, schemas explícitos e regra de negócio no serviço.
- **Verify:** ruff, format, mypy, pytest com PostgreSQL, Alembic upgrade/downgrade/upgrade,
  `alembic check`, web lint/format/typecheck/test/build e smoke da API.

## Comandos reais de validação

```powershell
cd backend
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy app
$env:JOGA_TEST_DATABASE_URL = "postgresql+psycopg://joga:joga@127.0.0.1:5434/joga"
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m scripts.reconcile_financials

cd ..\web
pnpm lint; pnpm format:check; pnpm typecheck; pnpm test; pnpm build
```

## Critérios técnicos verificados

- [x] Reserva concluída gera registro de liberação `PENDING` (comportamento técnico).
- [x] Liberação respeita o default configurado e contestação aberta (comportamento técnico).
- [x] Reexecutar worker/liberação não duplica ledger nem valor.
- [x] Contestação é única por reserva quando aberta, exige motivo e é auditada.
- [x] Decisão exige operador autorizado e fica registrada.
- [x] Resumo, recebíveis, extrato e contestações são isolados por organização.
- [x] `OPERATOR` lê, mas não contesta; negativa testada.
- [x] Conciliação detecta divergência sem corrigir saldo.
- [x] Migração reversível e `alembic check` limpo.
- [x] Painel mostra os dados e abre contestação apenas para `OWNER`/`ADMIN`.

## Decisões de produto/financeiro pendentes (não aceitas)

- [ ] Aprovar `N` de liberação e a política de repasse.
- [ ] Aprovar a janela de contestação e o efeito de contestação após liberação.
- [ ] Aprovar o procedimento oficial para divergência de ledger.
- [ ] Aprovar o modelo de moderação financeira (CLI é provisória).
- [ ] Aprovar PSP de produção e conciliação externa.
- [ ] Revisão jurídica dos termos e da política de cancelamento/ausência.
- [x] Política consolidada de cancelamento, substituição e ausência definida na ADR 0039,
  que supera a ADR 0038.
- [x] Reverter/ajustar o código da ADR 0038 para a lógica de desfecho da ADR 0039.
- [x] Implementar fila de substitutos, cancelamento individual e T4/T5 no backend.
- [x] Implementar atribuição e pagamento do substituto com reembolso do substituído.
- [x] Implementar vaga paga em no-show, sem nova cobrança.
- [x] Implementar T6–T9 (pré-check-in, presença, geofence e fechamento).
- [x] Implementar chamada automática da fila, coordenadas obrigatórias e recomendação de formação.
- [x] Registrar ADR 0040: repasse 2 h após o início da partida.
- [x] Implementar Trust Factor interno e restrição ranqueada (ADR 0041).
- [ ] Implementar UI de presença/fila e UI de suporte para restrições.
- [ ] Definir o repasse/liberação à quadra do valor não reembolsado em desistência
  pós-confirmação.

## Evidências (2026-11-09)

- Backend: **376 passed** com `JOGA_TEST_DATABASE_URL`; `ruff`, formatação e `mypy` verdes.
- Migração `c15a1b2c3d4e`: upgrade, downgrade, novo upgrade e `alembic check` limpos.
- `scripts.release_payments` executado sem erros; `scripts.reconcile_financials` retornou
  “Conciliação sem divergências” no banco local.
- Painel: **19 testes**, `lint`, `format:check`, `typecheck` e `build` verdes; CSP validada.
- Testes cobrem liberação antes/depois do prazo configurado, idempotência, contestação
  bloqueando liberação, decisão autorizada/negada, isolamento entre organizações,
  `OPERATOR` sem contestação e divergência de conciliação.
- Nenhum dinheiro real, PSP de produção, split ou transferência foi acionado.
- **As evidências acima são de implementação técnica, não de aprovação de política.**

## Aprovação e condição de parada

A implementação técnica de referência foi autorizada em 2026-11-09. As decisões de prazo,
repasse, moderação e divergência listadas acima **não foram aprovadas**. Não iniciar 14B,
16, integração real de PSP nem transformar os defaults em regra sem aprovação explícita.
