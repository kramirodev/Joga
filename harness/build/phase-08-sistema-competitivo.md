# Fase 08 — Sistema competitivo

**Status:** Implementada no backend e no mobile; 8C concluído em 2026-11-06
**Branch:** `feat/08-sistema-competitivo`
**Decisão:** `docs/ADR/0025-sistema-competitivo-mmr-e-rankings.md`

## Objetivo

Fechar o ciclo competitivo após `FINALIZED`: aplicar MMR uma única vez por partida ranqueada, manter histórico append-only, derivar divisão visível, oferecer ranking por formato e registrar sinais de Trust Factor sem punição automática.

## Escopo

- MMR oculto por usuário e formato/modalidade, calculado exclusivamente no backend.
- Glicko-2 adaptado para equipes, com incerteza individual e inflação de `RD` por inatividade.
- `rating_events` append-only e `rating_accounts` como estado atual.
- Trust Factor oculto, score neutro e `trust_events` auditáveis; sem penalidade automática na Fase 8.
- Fila ranqueada habilitada com política de matchmaking `mmr_v1`.
- Ranking top 100 por formato e posição individual.
- Telas mobile de divisão, progresso e ranking; sem exibir MMR bruto nem Trust Factor.
- Simulações sintéticas para validar convergência antes de liberar ranking público.

## Não fazer

- Rating editável pelo cliente ou painel.
- Apagar histórico de rating ou Trust Factor.
- Usar desempenho individual para alterar MMR.
- Aplicar rating em partida casual, `DISPUTED`, `RESULT_PENDING`, `VOIDED` ou `CANCELLED`.
- Denúncia isolada gerar punição automática.
- Conquistas e troféus (ficam para a Fase 16).
- Expor MMR bruto, RD, volatilidade ou Trust Factor no app.

## Blocos de entrega

### 8A — Motor de rating

- Migração `rating_accounts`, `rating_events`, `trust_accounts` e `trust_events`.
- Motor Glicko-2 puro, testável e versionado como `glicko2_team_v1`.
- Serviço de aplicação idempotente por partida/usuário/versão.
- Worker `scripts/apply_ratings.py`.
- Simulações determinísticas de convergência.
- Testes unitários, de serviço e PostgreSQL.

### 8B — Ranqueado, ranking e leitura

- Remover o bloqueio de `ranked` na fila.
- Política `mmr_v1`: média de MMR por equipe e limite de dispersão interna.
- Endpoints de ranking e cartão individual.
- Testes de concorrência e de balanceamento.

### 8C — Mobile

- Tela competitiva com seletor de formato, divisão, progresso, posição e top 100.
- Estados de carregamento/erro/vazio e acessibilidade.
- Nenhuma exposição de MMR bruto ou Trust Factor.

## Modelo de dados

### `rating_accounts`

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK `users.id`, cascade |
| `format_id` | UUID | FK `sport_formats.id`, cascade |
| `rating` | float | MMR atual, default 1500 |
| `rating_deviation` | float | RD atual, default 350 |
| `volatility` | float | default 0.06 |
| `matches_played` | integer | partidas ranqueadas processadas |
| `last_rated_at` | timestamptz | última aplicação |
| `algorithm_version` | varchar(40) | `glicko2_team_v1` |
| `created_at` / `updated_at` | timestamptz | default `now()` |

Único por `(user_id, format_id)`.

### `rating_events`

Histórico imutável por partida/usuário/versão.

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `match_id` | UUID | FK `matches.id` |
| `user_id` | UUID | FK `users.id` |
| `format_id` | UUID | FK `sport_formats.id` |
| `algorithm_version` | varchar(40) | versão aplicada |
| `result` | varchar(10) | `WIN`, `LOSS`, `DRAW` |
| `expected_score` | float | expectativa antes da partida |
| `rating_before` / `rating_after` | float | MMR |
| `rd_before` / `rd_after` | float | incerteza |
| `volatility_before` / `volatility_after` | float | volatilidade |
| `delta` | float | `rating_after - rating_before` |
| `created_at` | timestamptz | default `now()` |

Único por `(match_id, user_id, algorithm_version)`; índice por `(user_id, format_id, created_at)`.
`delta` é limitado a `±100` na v1.

### `trust_accounts`

| Coluna | Tipo | Regra |
|---|---|---|
| `user_id` | UUID | PK/FK `users.id` |
| `score` | integer | default 100, oculto |
| `updated_at` | timestamptz | default `now()` |

### `trust_events`

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK `users.id` |
| `match_id` | UUID | FK `matches.id`, nullable |
| `event_type` | varchar(40) | sinal auditável |
| `severity` | smallint | 0–5 |
| `metadata` | JSONB | contexto mínimo, sem PII desnecessária |
| `created_at` | timestamptz | default `now()` |

Append-only. Na Fase 8, `trust_accounts.score` permanece 100; eventos não aplicam delta automático.

## Algoritmo `glicko2_team_v1`

Parâmetros aprovados:

| Parâmetro | Valor |
|---|---:|
| Rating inicial | 1500 |
| RD inicial | 350 |
| RD máximo | 350 |
| Volatilidade inicial | 0.06 |
| Período de inatividade | 7 dias |
| Períodos para RD voltar ao máximo | 50 |
| Delta máximo por partida | ±100 |
| Colocação | 5 partidas |
| Bronze | < 1200 |
| Prata | 1200–1399 |
| Ouro | 1400–1599 |
| Platina | 1600–1799 |
| Diamante | 1800+ |

Regras:

1. Para cada equipe, usar média de `rating` e média de `rating_deviation`.
2. Calcular expectativa de vitória pela diferença de rating e incerteza do adversário (Glicko-2).
3. Aplicar atualização Glicko-2 a cada jogador usando sua própria incerteza, com resultado coletivo (`WIN`, `LOSS` ou `DRAW`).
4. Jogador com `RD` alto se move mais; jogador estável se move menos.
5. Inatividade aumenta `RD`, nunca reduz o rating.
6. Aplicar o cap de `±100` ao delta final.
7. Divisão é derivada do rating; com menos de 5 partidas, o app mostra “Provisório”.
8. Partidas casuais não geram rating.

## Implementação 8A

- **Motor:** `backend/app/modules/ratings/engine.py`, versão `glicko2_team_v1`, validado contra o exemplo canônico do Glicko-2.
- **Simulação:** `backend/app/modules/ratings/simulation.py` e `scripts/simulate_ratings.py`; com 60 jogadores e 3.000 partidas, quartil inferior ≈1279 e superior ≈1666.
- **Persistência:** `rating_accounts`, `rating_events`, `trust_accounts` e `trust_events`; migração `a3f7c9e2d641_add_ratings_and_trust_events.py`.
- **Serviço/worker:** `RatingService` idempotente e `scripts/apply_ratings.py`.
- **Testes:** `test_ratings_engine.py` (11), `test_ratings_service.py` (10) e `test_ratings_postgres.py` (1). Sem PostgreSQL: **245 passed, 22 skipped**; com `JOGA_TEST_DATABASE_URL`: **267 passed**. `ruff`, `ruff format`, `mypy` e `alembic check` passam.
- **Pendente em 8A:** nenhum item funcional conhecido.
- **8B:** `mmr_v1` com média e dispersão máxima de 800; fila ranqueada habilitada; `GET /api/v1/ratings/me` e `GET /api/v1/rankings`; top 100 por formato e jogadores em colocação fora do ranking público.
- **8C:** bloqueado por conflito de governança: `mobile/AGENTS.md` proíbe telas de produto enquanto o app é protótipo da Fase 1. É necessário atualizar esse arquivo/ADR antes de implementar a tela competitiva.

## Implementação 8B

- **API:** `backend/app/api/v1/ratings.py`, com leitura de divisão/progresso/posição e ranking paginado; nenhum campo de MMR bruto, RD ou Trust Factor.
- **Matchmaking:** `ranked` habilitado; política `mmr_v1` ordena candidatos por proximidade de MMR e limita a dispersão interna a 800 pontos por equipe.
- **Testes:** `test_ratings_api.py` (6), casos de `mmr_v1` em `test_matchmaking_policy.py` (4) e `test_matchmaking_postgres.py` (1 ranked). Sem PostgreSQL: **256 passed, 23 skipped**; com `JOGA_TEST_DATABASE_URL`: **279 passed**. `ruff`, `ruff format`, `mypy` e `alembic check` passam.

## Implementação 8C

- **Mobile:** `mobile/src/CompetitivePanel.tsx` exibe seletor de formato, divisão, progresso, posição e top 50; não recebe nem mostra MMR bruto, RD, volatilidade ou Trust Factor.
- **API client:** tipos `MyRating`/`RankingPage` e `ratingsApi` em `mobile/src/api.ts`.
- **Governança:** `mobile/AGENTS.md` atualizado para autorizar exclusivamente a tela competitiva da Fase 8C.
- **Validação:** `pnpm run typecheck`, `pnpm run lint`, `pnpm run format:check` e `pnpm exec expo install --check` passam.
- **Limite:** não há teste automatizado de UI em aparelho; a validação visual depende de development build/Expo com backend local.

## Contratos previstos (8B)

- `GET /api/v1/ratings/me?format_id=...` — divisão, progresso, posição, partidas e provisório.
- `GET /api/v1/rankings?format_id=...&limit=...&offset=...` — top 100 e posição individual.
- Nenhum endpoint expõe MMR bruto, RD, volatilidade ou Trust Factor.

## Testes e critérios de aceite

- [x] Glicko-2 puro: favorito, zebra, empate, novo jogador, inatividade, cap e divisão.
- [x] Simulação: jogadores convergem para faixas distintas; zebra move mais que favorito.
- [x] Aplicação única por partida/usuário/versão.
- [x] Casual, `DISPUTED`, `VOIDED` e `CANCELLED` não alteram rating.
- [x] Worker processa partida finalizada e é seguro ao reexecutar.
- [x] Concorrência PostgreSQL não duplica evento nem perde atualização.
- [x] Ranking ordena por MMR e desempata de forma determinística.
- [x] Fila ranqueada respeita média e dispersão de MMR.
- [x] Mobile exibe divisão, progresso e ranking sem MMR bruto.
- [x] Documentação, migração, runbook e build-log atualizados.

## Condição de parada

Encerrar a Fase 8 ao cumprir 8A, 8B e 8C. Não iniciar Fase 9 automaticamente. Não implementar conquistas, troféus ou clãs nesta fase.
