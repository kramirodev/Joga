# Fase 05 — Filas e matchmaking

**Status:** Complete (backend)
**Branch:** `feat/05-filas-e-matchmaking` (a partir de `main` em `bda06b0`)
**Decisão de sequenciamento:** `docs/ADR/0020-fase-5-fila-casual-e-formacao.md`
**Data de início:** 2026-11-03

## Fontes e contexto

- `AGENTS.md`, `GOALS.md`, `PLANS.md` (Fase 5)
- `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §7 (matchmaking) e §8 (lobbies)
- `docs/JOGA_DOCUMENTACAO_TECNICA.md` §8 (matchmaking e agendamento), §18 (modelo) e §19 (API)
- Fase 4 integrada em `main` (`bda06b0`): perfil, agenda semanal, região e descoberta
- `harness/build-log.md`

## Objetivo

Permitir que jogadores entrem numa fila persistida e que um worker forme partidas compatíveis de forma transacional, idempotente e auditável, sem depender de Redis como fonte da verdade.

## Escopo

- Entrada, saída e estado da fila em PostgreSQL.
- Compatibilidade por formato, modo, preferência de quadra, região e agenda.
- Seleção de horário concreto a partir da agenda semanal.
- Balanceamento de equipes por nível autodeclarado (`level_v1`).
- Formação transacional de lobby + participantes, com locks e constraints.
- Worker separado, recuperável e idempotente, com registro de execução e versão.
- Expiração de entradas e reconciliação de estado.

## Fora do escopo

- Ranqueada e MMR (Fase 8).
- Máquina de estados de partida, confirmação, presença e cancelamento (Fase 6).
- Resultados e disputas (Fase 7).
- Escolha/votação de quadra e reservas (Fases 9 e 14).
- Chat do lobby, notificações push e WebSocket.
- Matchmaking entre formatos diferentes ou grupos pré-formados.

## Decisões registradas

1. Fila **somente casual** nesta fase; `ranked` é rejeitado com `400 ranked_not_available`.
2. Janela de horário vem da **agenda do perfil**; busca de 7 dias, slots de 30 min, antecedência mínima de 2 h.
3. Balanceamento **`level_v1`** (iniciante 1, intermediário 2, avançado 3), minimizando a diferença entre equipes; versão gravada.
4. **MMR** fica para a Fase 8 como política `mmr_v1`, com nota base e separação de quem não jogou ranqueada; o schema não muda.
5. Centro do lobby = média geográfica dos centros aproximados; raio = menor raio informado, limitado a 30 km.
6. Preferência efetiva de quadra = interseção (`PUBLIC_ONLY` + `PRIVATE_ONLY` incompatível).
7. `venue_id` nulo nesta fase; quadra é Fase 9/14.
8. Worker em processo separado, `FOR UPDATE SKIP LOCKED`, revalidação dentro da transação.
9. Entrada expira em 24 h ou ao sair/entrar em partida.

## Componentes previstos

- `backend/app/modules/matchmaking/{models,service,policy,worker}.py`
- migração Alembic com `queue_entries`, `lobbies`, `lobby_participants` e `matchmaking_runs`
- `backend/app/api/v1/matchmaking.py`
- `backend/scripts/run_matchmaking.py`
- testes de unidade, API e concorrência em PostgreSQL
- `mobile/` fora do escopo desta iteração

## Implementação entregue

- `backend/app/modules/matchmaking/models.py`: `QueueEntry`, `Lobby`, `LobbyParticipant`, `MatchmakingRun`.
- `backend/app/modules/matchmaking/policy.py`: interseção de quadra, região de encontro, balanceamento `level_v1` e escolha de horário.
- `backend/app/modules/matchmaking/service.py`: entrada/saída da fila, expiração, seleção com `FOR UPDATE SKIP LOCKED` e formação transacional.
- `backend/app/api/v1/matchmaking.py`: `POST|GET|DELETE /matchmaking/queue`.
- `backend/scripts/run_matchmaking.py`: rodada única ou loop.
- `backend/migrations/versions/c5e1a7d3f208_add_matchmaking_queue_and_lobbies.py`: tabelas, índices e unique parcial da entrada ativa.

## Evidências executadas

| Verificação | Resultado |
|---|---|
| Migração `c5e1a7d3f208` | aplicada, revertida para `b8d2f4a6c910` e reaplicada |
| Index único parcial | `uq_queue_entries_active` em (`user_id`, `format_id`, `mode`) com `status = 'waiting'` |
| Ruff / formatação | sem achados |
| Mypy | sem erros em 41 arquivos |
| Pytest sem PostgreSQL | 145 passed, 13 skipped |
| Pytest com `JOGA_TEST_DATABASE_URL` | 158 passed |
| Concorrência | 20 entradas + 2 workers simultâneos → 2 lobbies, 20 participantes, 20 usuários distintos, 20 entradas `matched` |
| Idempotência | segunda rodada forma 0 lobbies e não duplica participantes |
| Incompatibilidades | quadra pública × particular, regiões distantes e ausência de agenda não formam lobby |
| Expiração | 10 entradas vencidas marcadas como `expired`, nenhum lobby criado |
| Smoke HTTP real | cadastro, perfil, agenda, região e `POST /matchmaking/queue` 201; duplicado 409; ranqueada 400; estado `waiting` |
| Smoke do worker | `python -m scripts.run_matchmaking` gravou rodada `completed`, versão `level_v1`, 0 lobbies com 1 jogador |

## Critérios de aceite

- [x] Entrada e saída de fila autenticadas, com estado consultável e sem duplicidade ativa por usuário/formato/modo.
- [x] Compatibilidade de quadra, formato e região validada no servidor.
- [x] Horário concreto escolhido a partir da agenda e gravado no lobby com duração do formato.
- [x] Equipes balanceadas por `level_v1`, com versão registrada.
- [x] Formação transacional sem duplicidade sob concorrência.
- [x] Worker recuperável: reexecução após falha não duplica nem perde lobbies.
- [x] Entradas inconsistentes/expiradas reconciliadas.
- [x] Testes concorrentes em PostgreSQL demonstram ausência de duplicidade.
- [x] Documentação, migração e build log atualizados.

## Riscos e limites

- Catálogo de locais vazio: lobby nasce sem quadra.
- Agenda é semanal e sem feriados/exceções; o slot escolhido pode não ser conveniente.
- Sem MMR, o equilíbrio é aproximado pelo nível autodeclarado.
- Sem notificações: o participante descobre a partida ao consultar o estado.
- Fuso tratado como `America/Sao_Paulo` nesta fase.

## Condição de parada

Encerrar ao cumprir os critérios acima. Não iniciar a Fase 6 nem implementar MMR sem autorização.
