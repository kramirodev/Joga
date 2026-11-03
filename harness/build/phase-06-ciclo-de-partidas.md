# Fase 06 — Ciclo de partidas

**Status:** Complete (backend)
**Branch:** `feat/06-ciclo-de-partidas` (a partir de `main` em `9846d74`)
**Data de início:** 2026-11-03

## Fontes e contexto

- `AGENTS.md`, `GOALS.md`, `PLANS.md` (Fase 6)
- `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §9 (partidas, capitães, confirmação)
- `docs/JOGA_DOCUMENTACAO_TECNICA.md` §10 (ciclo de vida), §18 (modelo) e §19 (API)
- Fase 5 (`lobbies`, `lobby_participants`, `queue_entries`, worker)
- `harness/build-log.md`

## Objetivo

Dar à partida um ciclo de vida controlado no servidor: confirmação, recusa, prazo, expiração, presença e cancelamento, com matriz de transições testada, idempotência e autorização por participante.

## Escopo

- Máquina de estados central (serviço de domínio), sem transição livre por endpoint.
- `matches`, `match_participants` e trilha `match_state_transitions` (append-only).
- Confirmação/recusa por participante, com prazo e limiar configuráveis.
- Check-in de presença (sem usar GPS como prova).
- Expiração e cancelamento com motivo.
- Worker/rotina que avança estados por tempo, de forma idempotente.
- Endpoints de consulta e ação restritos a participantes.

## Fora do escopo

- Relato, validação, disputa e resultado (Fase 7).
- MMR/Trust Factor (Fases 8 e 17).
- Capitães funcionais (dependem de Trust Factor, MMR e histórico; ver pendência).
- Chat, notificações push e WebSocket.
- Escolha/votação de quadra e reservas.

## Estados da fase

Implementar até `IN_PROGRESS`:

`PENDING_CONFIRMATION → READY → IN_PROGRESS`, com saídas `CANCELLED` e `EXPIRED` a partir de `PENDING_CONFIRMATION`/`READY`.

Estados de resultado (`RESULT_PENDING`, `FINALIZED`, `DISPUTED`, `VOIDED`) entram na Fase 7; a constraint nasce com eles para evitar migração, mas nenhum endpoint os alcança agora.

## Decisões registradas

1. **Confirmação de 100%.** Todos os participantes precisam confirmar; prazo em `min(formado + 24 h, início − 45 min)`.
2. **Sem tolerância após o início.** Não há atraso: o check-in fecha 30 min antes e a partida não pode começar atrasada.
3. **Dissolução com prioridade.** Recusa ou confirmação incompleta no prazo dissolve a partida; quem confirmou volta para `waiting` mantendo o `created_at` original (prioridade na fila) e quem não confirmou tem a entrada expirada.
4. **Suplente automático.** No fechamento do check-in, cada ausente é marcado `no_show` e o worker convida o primeiro jogador compatível da fila, com 15 min para confirmar e fazer check-in. Sem suplente até `início − 15 min`, a partida é cancelada.
5. **Cancelamento.** Recusa individual é permitida até o prazo e dissolve a partida; ninguém cancela o grupo unilateralmente.
6. **Capitães adiados** para a Fase 7/8; os critérios dependem de Trust Factor/MMR e "maior idade" exigiria data de nascimento.
7. **Penalidades por no-show** (banimento temporário, reputação) ficam para as Fases 8/17; a Fase 6 registra `no_show` como fonte de verdade.
8. **Início automático.** A partida vai a `IN_PROGRESS` no horário quando todos os ativos fizeram check-in.

## Implementação entregue

- `backend/app/modules/matches/models.py`: `Match`, `MatchParticipant`, `MatchStateTransition`.
- `backend/app/modules/matches/service.py`: matriz de transições, confirmação, recusa, check-in, suplente automático, dissolução com prioridade e avanço por tempo.
- `backend/app/api/v1/matches.py`: `GET /matches`, `GET /matches/{id}`, `POST /matches/{id}/confirm|decline|check-in`.
- `backend/scripts/advance_matches.py`: rodada única ou loop.
- Migração `d7f2b9c4e615`; a formação da Fase 5 agora cria a partida em `PENDING_CONFIRMATION`.

## Evidências executadas

| Verificação | Resultado |
|---|---|
| Migração `d7f2b9c4e615` | aplicada, revertida para `c5e1a7d3f208` e reaplicada |
| Ruff / formatação | sem achados |
| Mypy | sem erros em 45 arquivos |
| Pytest sem PostgreSQL | 161 passed, 14 skipped |
| Pytest com `JOGA_TEST_DATABASE_URL` | 175 passed |
| Concorrência | 10 confirmações simultâneas → estado `READY`, 10 confirmados, **1** transição `READY` |
| Dissolução | recusa e prazo vencido cancelam; confirmados voltam a `waiting` mantendo `created_at` |
| Suplente | ausente vira `no_show`, suplente é convidado, confirma, faz check-in e a partida inicia |
| Sem suplente | no prazo de substituição, partida vai a `CANCELLED`/`no_substitute` |
| Autorização | não participante recebe 404 em consulta e ações |
| Idempotência | confirmação e check-in repetidos não duplicam estado nem transições |

## Critérios de aceite

- [x] Matriz de transições válidas e inválidas testada.
- [x] Requisições repetidas não duplicam ações nem transições.
- [x] Somente participantes atuam e consultam a própria partida.
- [x] Prazo, expiração e check-in avançam por rotina idempotente.
- [x] Estado e histórico auditáveis; motivo registrado em cancelamento.
- [x] Testes de autorização negativa e de concorrência.
- [x] Documentação, migração e build log atualizados.

## Condição de parada

Encerrar ao cumprir os critérios. Não iniciar a Fase 7.
