# Fase 13 — Reservas e temporizadores

**Status:** 13A (backend) e 13B (painel mobile de reservas e ajustes de painel) implementados e validados localmente em 2026-11-07; criação automática a partir do lobby, T2 em horário comercial e pagamentos reais pendentes.
**Branch:** `feat/13-reservas-temporizadores`

## Fontes e contexto

- `AGENTS.md`
- `GOALS.md`
- `PLANS.md` — Fase 13
- `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §10.3–10.8 e §11
- `docs/JOGA_DOCUMENTACAO_TECNICA.md` §13, §14, §18, §19 e §20
- Fases 5, 6, 11 e 12A: lobbies, partidas, organizações, quadras, agenda e bloqueios

## Objetivo

Permitir que um lobby solicite uma quadra, o estabelecimento aceite ou recuse e o bloqueio seja controlado por temporizadores independentes no backend, sem dupla reserva, com histórico auditável e sem confiar no relógio do cliente.

## Escopo 13A — backend

- `bookings` com snapshot de preço, espaço, organização, lobby, política e horário.
- `booking_participants` com vaga, contribuição, confirmação e estado de pagamento.
- `booking_holds` transacionais por espaço e intervalo, com expiração e liberação.
- `booking_timers` independentes para T1, T2 e T3.
- `booking_events` append-only com ator, estado anterior, novo estado, motivo e timestamp.
- Máquina de estados central: `PARTICIPANT_CONFIRMATION`, `REQUESTED`, `DECLINED`, `EXPIRED`, `HOLD_CONFIRMED`, `PAYMENT_PENDING`, `CONFIRMED`, `CANCELLED`, `CANCELLED_BY_VENUE`, `CANCELLED_BY_PLAYER`, `SUBSTITUTING`, `COMPLETED`.
- Confirmação/recusa de participação (T1), aceite/recusa do estabelecimento (T2), abertura de pagamentos e expiração do hold (T3).
- Simulação de pagamento somente em ambiente local/teste; provedor real fica para a Fase 14.
- Substituição de participante sem reiniciar T3 e sem duplicar vaga/cobrança.
- Worker `scripts/advance_bookings.py` idempotente para expirar prazos e liberar holds.
- Autorização: participante só vê/atua nas próprias reservas; organização só vê reservas dos próprios estabelecimentos.
- Prevenção de sobreposição com lock transacional e constraint de exclusão no PostgreSQL.

## Fora do escopo

- Cobrança Pix real, split, custódia, webhooks, reembolso e conciliação (Fase 14).
- KYC/recebedor (12B).
- Interface de painel e mobile da reserva (13B).
- Redirecionamento automático para outra quadra; decisão pendente.
- Regras completas de horário comercial para T2; a 13A usa prazo em tempo corrido e registra a pendência.
- Liberação financeira ao estabelecimento (Fase 15).

## Pré-requisitos e dependências

- Fase 12A integrada ou autorização para empilhar a 13A na branch atual.
- Lobby com participantes e formato definidos.
- Estabelecimento, espaço e agenda da Fase 12A.
- Definição de que a 13A não movimenta dinheiro real.

## Arquivos/componentes esperados

- `backend/app/modules/bookings/models.py`, `service.py` e `__init__.py`.
- `backend/app/api/v1/bookings.py`.
- Migração Alembic revisável.
- `backend/tests/test_bookings_api.py`, `test_bookings_service.py` e `test_bookings_postgres.py`.
- `backend/scripts/advance_bookings.py`.
- Ajustes de capacidade em `organizations/permissions.py` (`bookings:read`, `bookings:manage`).

## Riscos e decisões pendentes

- **Alto:** dupla reserva do mesmo espaço/intervalo. Lock transacional e constraint de exclusão são obrigatórios.
- **Alto:** timers reiniciados por substituição ou aceite repetido. Transições devem ser idempotentes e testadas.
- **Alto:** participante vendo ou alterando reserva alheia. Testar autorização negativa em todas as rotas.
- **Médio:** T2 em horário comercial ainda não implementado; usar tempo corrido na 13A e registrar a pendência.
- **Médio:** pagamento simulado não é prova de pagamento real; a Fase 14 deve substituir o simulador por PSP.
- **Médio:** regra de cancelamento/reembolso definitiva depende do contrato e da Fase 14.
- **Pendente:** duração configurável por estabelecimento para T2/T3, redirecionamento, política de reembolso e conclusão automática.

## Plano de verificação

- **Red:** testes falhando para dupla reserva concorrente, timer expirado, transição inválida, participante externo, substituição duplicada e pagamento sem PSP.
- **Green:** implementar o mínimo com locks, constraints e máquina de estados central.
- **Refactor:** extrair cálculo de prazos, autorização e transições; manter rotas finas.
- **Verify:** pytest sem e com PostgreSQL, ruff, mypy, alembic, smoke HTTP e revisão do diff.

## Comandos reais de validação

```bash
cd backend
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy app
.venv/bin/python -m pytest
JOGA_TEST_DATABASE_URL="postgresql+psycopg://joga:joga@127.0.0.1:5434/joga" \
  .venv/bin/python -m pytest tests/test_bookings_postgres.py -v
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic check
```

## Critérios de aceite

- [x] Dois pedidos concorrentes não criam holds sobrepostos no mesmo espaço.
- [x] T1, T2 e T3 são independentes, controlados pelo backend e idempotentes.
- [x] Transições inválidas são rejeitadas e cada transição registra ator, motivo e estado anterior.
- [x] Participante só atua em reservas das quais participa; organização só vê as próprias.
- [x] Substituição não duplica vaga, cobrança nem reinicia T3.
- [x] Reserva não confirma com pagamento incompleto.
- [x] Hold expirado é liberado e o histórico permanece.
- [x] Pagamento simulado fica restrito a ambiente local/teste.
- [x] Migração reversível e `alembic check` limpo.
- [x] Fase 14 não é iniciada e nenhum PSP real é acionado.

## Evidências exigidas

- Saída de pytest, Postgres, ruff, mypy e alembic.
- Revisão do diff e `git diff --check`.
- Atualização de `harness/build-log.md`.
- Relatório de limitações e pendências.

## 13B — painel mobile de reservas (implementado)

- `mobile/src/BookingPanel.tsx` lista as reservas do jogador, mostra T1/T2/T3, vaga, contribuição e estado de pagamento.
- Ações: confirmar/recusar participação e pagamento simulado local.
- `mobile/src/api.ts` ganhou tipos e `bookingsApi`.
- `App.tsx` inclui o painel após comunicação.
- `mobile/AGENTS.md` foi atualizado para refletir a autorização da 13B.
- Limitação: a criação da reserva ainda depende do lobby/quadra; não há seletor de quadra no mobile nesta rodada.

## Evidências da 13A/13B (2026-11-07)

- Backend: **352 passed** com `JOGA_TEST_DATABASE_URL`; sem PostgreSQL, os testes de concorrência são ignorados.
- `ruff check`, `ruff format --check` e `mypy app` passam.
- Migração `26b70fd0fbc7` aplicada; ciclo upgrade → downgrade → upgrade e `alembic check` validados em banco descartável com PostGIS.
- Testes HTTP: T1/T2/T3, pagamento parcial, expiração, recusa, substituição, isolamento por participante e idempotência por lobby.
- Teste PostgreSQL: dois aceites concorrentes para o mesmo espaço/intervalo geram **um hold** e um conflito.
- Painel web: aba de reservas com aceite/recusa/conclusão, coberta por teste de UI.
- Mobile: `tsc --noEmit`, `eslint` e `prettier --check` passam; painel de reservas integrado ao `App.tsx`.
- Nenhum PSP real foi acionado; pagamento é simulado apenas em ambiente local/teste.

## Aprovação e condição de parada

13A concluída e validada localmente em 2026-11-07. 13B (jornada mobile completa e ajustes de painel) só começa após autorização. Não iniciar a Fase 14 sem autorização explícita.
