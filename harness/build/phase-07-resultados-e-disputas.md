# Fase 07 — Resultados e disputas

**Status:** Implementada no backend e validada com PostgreSQL 16/PostGIS local em 2026-11-06; pendente de revisão/commit
**Branch prevista:** `feat/07-resultados-e-disputas` (a criar a partir de `main` após o merge do PR documental; a implementação local atual está sem commit)
**Data de início:** 2026-11-06 (planejamento e implementação local)
**Decisão de sequenciamento:** `docs/ADR/0023-fase-7-resultados-e-disputas.md`

## Fontes e contexto

- `AGENTS.md`, `GOALS.md`, `PLANS.md` (Fase 7)
- `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §9
- `docs/JOGA_DOCUMENTACAO_TECNICA.md` §10
- `docs/ADR/0008-desempate-resultados-confiabilidade.md`
- `docs/ADR/0023-fase-7-resultados-e-disputas.md`
- Fase 6: `matches`, `match_participants`, `match_state_transitions`, worker `advance_matches`
- `harness/build-log.md`

## Objetivo

Fechar o ciclo da partida após `IN_PROGRESS`: abrir a janela de relato, validar o resultado com três opções, tratar divergências, abrir segunda rodada e disputa, registrar decisão auditável e deixar o resultado `FINALIZED` pronto para consumo pela Fase 8 — sem implementar MMR.

## Escopo

- Backend-only, com API e testes. Sem telas mobile.
- Relato individual com três resultados: `TEAM_1`, `TEAM_2` ou `DRAW` quando o formato permitir.
- Prazo de relato de 10 minutos, controlado pelo backend.
- Quórum mínimo `ceil(elegíveis / 2)`.
- Resultado avaliado por maioria simples (plurality).
- Divergência de 50% sobre votos válidos.
- Segunda rodada de 5 minutos.
- Capitão provisório.
- Evidência textual privada de até 2.000 caracteres.
- Revisão humana por CLI auditável.
- Nenhum MMR, Trust Factor ou rating.
- Migração Alembic, testes e atualização de documentação.

## Fora do escopo

- Telas mobile de resultado, disputa ou revisão.
- MMR, rating, ranking e Trust Factor (Fase 8).
- Upload de imagens, áudios, vídeos ou arquivos.
- Painel administrativo completo, papéis de staff e fila de moderação (Fase 17).
- Notificações push, WebSocket e chat.
- Reservas, pagamentos e quadras (Fases 11–15).
- Alteração retroativa de capitães, votos ou resultados.

## Decisões fechadas

### Resultado e prazos

1. **Prazo de relato:** 10 minutos após `scheduled_end_at`, controlado pelo backend. Configurável por formato no futuro; o lobby não altera.
2. **Três resultados:** `TEAM_1`, `TEAM_2`, `DRAW`. `DRAW` só é aceito quando o formato permitir.
3. **Empate por formato:** futebol 5x5 permite `DRAW`; vôlei não permite.
4. **Votos ausentes/anulados:** fora do denominador; não contam como concordância nem discordância.
5. **Elegíveis:** congelados na abertura da primeira rodada; o mesmo conjunto vale para a segunda.
   - Elegível = participante com `status = checked_in` no momento da abertura.
   - `no_show`, `declined` e participantes não ativos não entram.
6. **Quórum:** `ceil(elegíveis / 2)` votos válidos. Abaixo disso, revisão humana; não finaliza.
7. **Resultado avaliado:** outcome com mais votos válidos (maioria simples/plurality), não maioria absoluta.
8. **Divergência:** `(votos_válidos − votos_no_resultado_avaliado) / votos_válidos`, comparada em inteiros:
   - `divergentes * 2 < válidos`: finaliza;
   - `divergentes * 2 == válidos`: segunda rodada;
   - `divergentes * 2 > válidos`: disputa.
9. **Sem tolerância separada de 1–2 votos.**
10. **Segunda rodada:** 5 minutos, sem renovação automática.
11. **Alternativas da segunda rodada:** todas as opções permitidas pelo formato, independentemente da distribuição da primeira rodada.
12. **Sem terceira rodada.**

### Segunda rodada — regra por cenário

| Cenário na primeira rodada | Segunda rodada | Alternativas |
|---|---|---|
| Resultado único e divergência exatamente 50% | Abre | Todas as permitidas pelo formato |
| Empate na primeira posição entre 2 resultados | Abre | Todas as permitidas pelo formato |
| Empate na primeira posição entre 3 resultados | Abre | Todas as permitidas pelo formato |
| Resultado único e divergência abaixo de 50% | Não abre | Finaliza |
| Resultado único e divergência acima de 50% | Não abre | Disputa + revisão humana |
| Quórum insuficiente | Não abre | Revisão humana |

**Segunda rodada — desfechos:**

| Cenário na segunda rodada | Desfecho |
|---|---|
| Quórum insuficiente | Revisão humana |
| Empate na primeira posição / sem resultado único | Revisão humana |
| Resultado único e divergência abaixo de 50% | Finaliza |
| Resultado único e divergência exatamente 50% | Análise interna; se inconclusiva, revisão humana |
| Resultado único e divergência acima de 50% | Disputa + revisão humana |

### Capitão

13. **Seleção:** maior número de partidas `FINALIZED`, do mesmo formato, concluídas antes da partida atual, nas quais o jogador tenha participado efetivamente. Empate por UUID.
14. **Momento:** na formação da partida, versão `provisional_v1`; não recalcular.
15. **Sem nível.** Trust Factor, MMR e idade ficam para a Fase 8, em partidas futuras.
16. **Confirmação do capitão:** registro separado, sem peso de voto. O capitão vota como qualquer participante.

### Evidência, visibilidade e revisão

17. **Evidência textual:** até 2.000 caracteres, uma por participante por disputa. Privada, restrita e auditável. Sem arquivos.
18. **Visibilidade:** relatos e votos individuais visíveis aos participantes; agregado e resultado parcial somente após o fechamento da rodada. Justificativas privadas não entram nessa visibilidade.
19. **Revisão humana:** CLI/script, `--operator` validado contra lista autorizada, `--reason` obrigatório. Sem painel ou endpoint público de moderação.
20. **Backend-only** e **sem MMR**.

## Estados e transições

```text
IN_PROGRESS -> RESULT_PENDING      (fim do horário; abre rodada 1)
RESULT_PENDING -> FINALIZED        (resultado validado)
RESULT_PENDING -> DISPUTED         (divergência > 50%)
RESULT_PENDING -> VOIDED           (decisão humana em revisão de quórum)
RESULT_PENDING -> FINALIZED        (decisão humana em revisão de quórum)
DISPUTED -> FINALIZED              (decisão humana)
DISPUTED -> VOIDED                 (decisão humana)
DISPUTED -> DISPUTED               (pedido de mais informações; registra evento)
```

`RESULT_PENDING` cobre rodada aberta e revisão de quórum. `DISPUTED` cobre divergência >50%, empate/sem resultado único na segunda rodada e análise interna inconclusiva.

## Modelo de dados previsto

- `matches`: `final_result` (`TEAM_1`, `TEAM_2`, `DRAW`, nulo), `finalized_at`, `voided_reason`, `result_version`.
- `match_participants`: `is_captain`, `captain_selection_version`, `captain_selected_at`.
- `match_result_eligible_participants`: `match_id`, `user_id`, `frozen_at`; único por partida/usuário.
- `match_result_rounds`: `match_id`, `round_number` (1/2), `status` (`OPEN`/`CLOSED`), `opens_at`, `deadline`, `closed_at`, `eligible_count`, `quorum`, `valid_votes`, `evaluated_outcome`, `divergent_votes`, `outcome` (`FINALIZED`/`SECOND_ROUND`/`DISPUTED`/`REVIEW`).
- `match_result_reports`: `round_id`, `participant_id`, `outcome`, `submitted_at`, `idempotency_key`, `request_hash`; append-only.
- `match_result_captain_confirmations`: `round_id`, `participant_id`, `outcome`, `submitted_at`, `idempotency_key`; append-only; sem contagem de voto.
- `match_disputes`: `match_id`, `round_id`, `reason`, `status`, `opened_at`, `closed_at`. Criado para todo caso enviado à revisão humana, com `reason` (`QUORUM`, `DIVERGENCE`, `TIE`, `SECOND_ROUND_50`, `NO_UNIQUE_RESULT`).
- `match_dispute_evidence`: `dispute_id`, `participant_id`, `text`, `char_count`, `created_at`; único por disputa/participante.
- `match_result_analyses`: `match_id`, `round_id`, `signals` (JSONB), `conclusion` (`INCONCLUSIVE` na Fase 7), `created_at`.
- `match_result_reviews`: `match_id`, `round_id`, `reason` (`QUORUM`, `DIVERGENCE`, `TIE`, `SECOND_ROUND_50`, `NO_UNIQUE_RESULT`), `status` (`PENDING`/`RESOLVED`/`CANCELLED`), `created_at`, `resolved_at`.
- `match_result_decisions`: `match_id`, `review_id`, `decision` (`FINALIZE`/`VOID`/`REQUEST_MORE_INFO`), `outcome`, `reason`, `operator_id`, `origin` (`SYSTEM`/`HUMAN`), `created_at`; append-only.
- `idempotency_records`: `scope`, `key`, `request_hash`, `response_status`, `response_body`, `created_at`; único por `scope`/`key`.

## Cálculo da rodada

```text
elegiveis = conjunto congelado
validos = último voto válido por participante elegível na rodada
quorum = ceil(len(elegiveis) / 2)

se len(validos) < quorum:
    revisao(QUORUM)

líderes = outcomes com contagem máxima
se len(líderes) != 1:
    se rodada == 1: abrir_rodada_2()
    senão: revisao(NO_UNIQUE_RESULT)

avaliado = líderes[0]
divergentes = len(validos) - contagem[avaliado]

se divergentes * 2 < len(validos):
    finalizar(avaliado)
se divergentes * 2 == len(validos):
    se rodada == 1: abrir_rodada_2()
    senão: analise_interna(); revisao(SECOND_ROUND_50)
senão:
    disputa(DIVERGENCE)
```

Comparações em inteiros, nunca em ponto flutuante.

## Análise interna da Fase 7

Como Trust Factor e MMR ainda não existem, a análise interna **não decide automaticamente**. Ela registra um parecer auditável com:

- contagens e resultado avaliado da primeira e da segunda rodada;
- participantes que mudaram de voto entre as rodadas;
- confirmações dos capitães e se coincidem com o resultado avaliado;
- sinalização de mudanças coordenadas ou inconsistentes;
- conclusão `INCONCLUSIVE` na Fase 7.

O caso segue para revisão humana com motivo `SECOND_ROUND_50`. A decisão automática só poderá existir na Fase 8, quando houver Trust Factor/MMR.

## Contrato HTTP

Base: `/api/v1`. Autenticação: `Authorization: Bearer <access_token>`.
Erros: `{"detail": {"code": "<business_code>"}}`.
`Idempotency-Key` obrigatório nos `POST`; escopo = endpoint + ator + partida + rodada + hash do corpo.

### 1. `GET /matches/{match_id}/result`

**Autorização:** participante da partida. Não participante recebe 404.

**Resposta 200:**

```json
{
  "match_id": "uuid",
  "state": "RESULT_PENDING",
  "round": 1,
  "round_status": "OPEN",
  "opens_at": "2026-11-06T21:00:00Z",
  "deadline": "2026-11-06T21:10:00Z",
  "eligible_count": 10,
  "quorum": 5,
  "valid_votes": 3,
  "can_vote": true,
  "my_vote": {
    "outcome": "TEAM_1",
    "submitted_at": "2026-11-06T21:02:00Z"
  },
  "aggregate_visible": false,
  "aggregate": null,
  "captain_confirmations_visible": false,
  "captain_confirmations": null,
  "final_result": null,
  "dispute_id": null,
  "review": null
}
```

Após o fechamento, `round_status` = `CLOSED`, `aggregate_visible` = true e:

```json
{
  "aggregate": {
    "valid_votes": 10,
    "counts": {"TEAM_1": 5, "TEAM_2": 3, "DRAW": 2},
    "leaders": ["TEAM_1"],
    "evaluated": "TEAM_1",
    "divergent": 5,
    "divergence_ratio": 0.5
  },
  "captain_confirmations_visible": true,
  "captain_confirmations": [
    {
      "participant_id": "uuid",
      "team": 1,
      "outcome": "TEAM_1",
      "submitted_at": "2026-11-06T21:03:00Z"
    }
  ],
  "dispute_id": "uuid",
  "review": {"pending": true, "reason": "SECOND_ROUND_50"}
}
```

`review` nunca expõe operador, justificativa interna ou evidência.

**Erros:** 401 `unauthorized`; 404 `match_not_found`.

### 2. `GET /matches/{match_id}/result-reports?round=1`

**Autorização:** participante.

**Resposta 200:**

```json
{
  "round": 1,
  "status": "OPEN",
  "reports": [
    {
      "participant_id": "uuid",
      "display_name": "Nome",
      "outcome": "TEAM_1",
      "is_captain": false,
      "submitted_at": "2026-11-06T21:02:00Z"
    }
  ]
}
```

Retorna o voto efetivo por participante. Histórico de correções não é exposto aos participantes.

**Erros:** 401; 404 `match_not_found`; 422 `invalid_round`.

### 3. `POST /matches/{match_id}/result-reports`

**Autorização:** participante elegível.

**Body:**

```json
{"round": 1, "outcome": "TEAM_1"}
```

**Resposta 201:**

```json
{
  "report_id": "uuid",
  "round": 1,
  "outcome": "TEAM_1",
  "submitted_at": "2026-11-06T21:02:00Z",
  "effective": true
}
```

**Regras:**

- Rodada 1: um voto efetivo por participante; nova chave após voto → 409.
- Rodada 2: múltiplos envios permitidos; voto efetivo = último envio válido; histórico append-only.
- `DRAW` rejeitado quando o formato não permite.
- `outcome` fora de `TEAM_1|TEAM_2|DRAW` → 422.
- Voto após `deadline` → 409, mesmo que o worker ainda não tenha fechado.

**Erros:**

| HTTP | Código | Situação |
|---:|---|---|
| 401 | `unauthorized` | sem sessão |
| 404 | `match_not_found` | partida inexistente ou usuário não participa |
| 409 | `result_window_not_open` | janela ainda não abriu |
| 409 | `result_window_closed` | prazo vencido |
| 409 | `round_not_open` | rodada não é a atual |
| 409 | `ineligible_participant` | fora do conjunto congelado |
| 409 | `result_report_already_submitted` | rodada 1 já votada |
| 422 | `invalid_outcome` | outcome inválido |
| 422 | `draw_not_allowed` | empate não permitido no formato |
| 409 | `idempotency_conflict` | mesma chave, corpo diferente |
| 429 | `rate_limited` | excesso de tentativas |

### 4. `POST /matches/{match_id}/result-confirmations`

**Autorização:** capitão da partida (registro separado, não voto).

**Body:**

```json
{"round": 1, "outcome": "TEAM_1"}
```

**Resposta 201:**

```json
{
  "confirmation_id": "uuid",
  "round": 1,
  "outcome": "TEAM_1",
  "submitted_at": "2026-11-06T21:03:00Z"
}
```

**Erros:** 401; 404 `match_not_found`; 403 `not_captain`; 409 `result_window_closed`; 409 `round_not_open`; 409 `captain_confirmation_already_submitted`; 422 `invalid_outcome`; 422 `draw_not_allowed`; 409 `idempotency_conflict`.

### 5. `POST /matches/{match_id}/disputes/{dispute_id}/evidence`

**Autorização:** participante da partida e da disputa.

**Body:**

```json
{"text": "Justificativa privada com até 2000 caracteres."}
```

**Resposta 201:**

```json
{
  "evidence_id": "uuid",
  "char_count": 42,
  "created_at": "2026-11-06T21:20:00Z"
}
```

**Regras:** uma evidência por participante por disputa; texto privado; sem arquivos; sem exposição no lobby. A janela de evidência fica aberta enquanto a revisão estiver `PENDING` e fecha quando a revisão for `RESOLVED` ou `CANCELLED`.

**Erros:** 401; 404 `match_not_found`/`dispute_not_found`; 409 `evidence_window_closed`; 409 `evidence_already_submitted`; 422 `evidence_empty`; 422 `evidence_too_long`; 409 `idempotency_conflict`.

### 6. `GET /matches/{match_id}/disputes/{dispute_id}/evidence/me`

**Autorização:** autor da evidência.

**Resposta 200:**

```json
{
  "evidence_id": "uuid",
  "text": "Justificativa privada...",
  "char_count": 42,
  "created_at": "2026-11-06T21:20:00Z"
}
```

**Erros:** 401; 404 `evidence_not_found`.

### 7. CLI interna de revisão

Não há endpoint HTTP de moderação na Fase 7.

```bash
python -m scripts.review_match_result \
  --match-id <uuid> \
  --operator <operator_id> \
  --reason "Justificativa auditável" \
  --decision FINALIZE \
  --outcome TEAM_1
```

- `--operator` validado contra `JOGA_REVIEW_OPERATORS` (lista separada por vírgula). Fora da lista → erro 3.
- `--reason` obrigatório, 1–500 caracteres.
- `--decision`: `FINALIZE`, `VOID` ou `REQUEST_MORE_INFO`.
- `--outcome` obrigatório para `FINALIZE`; precisa ser permitido pelo formato.
- `--dry-run` opcional para validar sem gravar.
- Só age em revisão `PENDING`; caso contrário, erro 4.
- Grava `match_result_decisions` com `origin = HUMAN`, atualiza estado e resultado.
- Exit codes: 0 sucesso; 2 argumento inválido; 3 operador não autorizado; 4 revisão não encontrada/não pendente; 5 transição inválida.

## Controle de prazo e fechamento

- Worker `advance_matches.py`:
  1. Em `scheduled_end_at`, move `IN_PROGRESS → RESULT_PENDING`.
  2. Congela elegíveis e cria rodada 1 com `deadline = opens_at + 10 min`.
  3. No deadline, fecha a rodada e aplica a regra.
  4. Se segunda rodada: cria rodada 2 com `deadline = opens_at + 5 min`, mesmo conjunto de elegíveis.
  5. No deadline da rodada 2, fecha e aplica o desfecho.
- Fechamento é idempotente e usa lock por partida.
- Não há renovação automática.
- A API rejeita voto após o deadline mesmo que o worker esteja atrasado.
- Worker atrasado não altera o prazo; reconcile relata rodadas vencidas.

## Testes previstos

### Unitários

- Plurality com três resultados.
- Quórum `ceil(elegíveis/2)` e congelamento de elegíveis.
- Votos ausentes/anulados fora do denominador.
- Divergência abaixo, exatamente e acima de 50%, com comparação inteira.
- Empate na primeira posição (2 e 3 resultados) → segunda rodada.
- Segunda rodada com todas as alternativas permitidas.
- Segunda rodada: quórum, empate, 50%, >50%, finalização.
- `DRAW` aceito no futebol e rejeitado no vôlei.
- Capitão por `FINALIZED` do mesmo formato, UUID e versão.
- Evidência: 2.000 caracteres, uma por participante, acesso privado.
- Análise interna sempre `INCONCLUSIVE` na Fase 7.

### API

- Participante vota; não participante recebe 404.
- Voto duplicado: idempotência e 409 conforme a rodada.
- Voto após prazo → 409.
- `DRAW` indevido → 422.
- Relatos individuais visíveis; agregado oculto enquanto a rodada está aberta.
- Agregado visível após fechamento.
- Capitão confirma; não capitão recebe 403.
- Evidência privada, limite e autoria.
- Erros de negócio com os códigos definidos.

### Concorrência e integração

- Dois votos simultâneos do mesmo participante não duplicam.
- Worker fecha a rodada uma única vez.
- Duas execuções do worker não abrem duas segundas rodadas.
- Decisão humana concorrente não duplica evento.
- Migração aplica, reverte e reaplica.
- Testes com `JOGA_TEST_DATABASE_URL`.

## Critérios de aceite

- [x] Relato de 10 minutos controlado pelo backend.
- [x] Três resultados e `DRAW` apenas quando permitido.
- [x] Elegíveis congelados e quórum `ceil(n/2)`.
- [x] Votos ausentes/anulados fora do denominador.
- [x] Plurality e divergência em relação ao resultado avaliado.
- [x] Abaixo de 50% finaliza; exatamente 50% abre segunda rodada; acima de 50% abre disputa.
- [x] Segunda rodada de 5 minutos com todas as alternativas permitidas.
- [x] Segunda rodada sem resultado único/quórum → revisão humana.
- [x] Análise interna da Fase 7 não decide automaticamente.
- [x] Capitão provisório determinístico, registrado e não retroativo.
- [x] Evidência textual de até 2.000 caracteres, privada e auditável.
- [x] CLI exige operador autorizado e motivo.
- [x] Nenhum MMR/rating aplicado.
- [x] Contrato HTTP e códigos de erro implementados como acima. `429 rate_limited` é aplicado aos POSTs de resultado, confirmação e evidência, com `Retry-After`. `Idempotency-Key` ausente/chave longa usam códigos adicionais (`missing_idempotency_key`, `invalid_idempotency_key`).
- [x] Testes de autorização negativa, concorrência e idempotência passam — cobertos em SQLite e em PostgreSQL real com `tests/test_results_postgres.py`; migração aplicada e revertida no banco local descartável.
- [x] Retenção provisória documentada no ADR 0024 e aplicável por CLI com `--dry-run`.
- [x] Documentação, migração e build-log atualizados.

## Implementação realizada

- **Arquivos principais:** `backend/app/modules/results/{models,policy,service,cleanup}.py`, `backend/app/modules/idempotency/{models,service}.py`, `backend/app/modules/ratelimit/{models,service}.py`, `backend/app/api/v1/results.py`, `backend/scripts/review_match_result.py`, `backend/scripts/cleanup_results.py`, `backend/migrations/versions/e1a4c7d9b230_add_match_results.py` e `backend/migrations/versions/f2b5d8e1a7c3_add_rate_limit_counters.py`.
- **Integrações:** `matches.service` recebeu a matriz de transições e a seleção de capitão; `advance_matches.py` apura rodadas; `router.py` registra os endpoints; `config.py` lê `JOGA_REVIEW_OPERATORS` e `JOGA_RESULTS_RATE_LIMIT_PER_MINUTE`; `.env.example` traz os placeholders.
- **Testes:** `backend/tests/test_results_policy.py` (10), `test_results_service.py` (23), `test_results_api.py` (13), `test_review_cli.py` (4), `test_results_postgres.py` (7), `test_ratelimit.py` (6) e `test_results_cleanup.py` (7), apoiados por `helpers_results.py`. Sem PostgreSQL: **224 passed, 21 skipped**. Com `JOGA_TEST_DATABASE_URL` local: **245 passed, 0 skips**. `ruff check`, `ruff format --check`, `mypy app` e `alembic check` passam.
- **Migração:** `e1a4c7d9b230` e `f2b5d8e1a7c3` aplicadas, revertidas e reaplicadas com sucesso no PostgreSQL 16/PostGIS local; nomes de constraints dentro do limite de 63 caracteres; `signals`/`response_body` em JSONB. `alembic check` retorna “No new upgrade operations detected” após correção de divergências pré-existentes de sessões, perfil, locais e `spatial_ref_sys`.
- **Rate limiting:** módulo `backend/app/modules/ratelimit/`, tabela `rate_limit_counters` e migração `f2b5d8e1a7c3_add_rate_limit_counters.py`; POSTs de relato, confirmação e evidência limitados por usuário em janela fixa de 60 segundos (`JOGA_RESULTS_RATE_LIMIT_PER_MINUTE`, padrão 30), com `429 rate_limited` e `Retry-After`.
- **Retenção:** política provisória no `docs/ADR/0024-retencao-provisoria-resultados.md`, aplicada manualmente por `scripts/cleanup_results.py` com `--dry-run`; a política definitiva fica para a revisão LGPD das Fases 10/19.
- **Desvios:** `missing_idempotency_key` e `invalid_idempotency_key` são extensões ao contrato original; a retenção definitiva ainda depende de revisão LGPD.
- **Fora do escopo mantido:** sem MMR, sem tela mobile, sem painel administrativo, sem upload e sem notificações.

## Riscos e limites

- A Fase 7 não tem Trust Factor/MMR; a análise interna é um parecer e sempre vai para revisão humana.
- Sem notificações, o jogador descobre a janela ao consultar a API.
- Sem tela mobile, a fase é operável por API/CLI.
- Evidência textual limita a qualidade probatória; arquivos ficam para fase posterior.
- A revisão humana por CLI é provisória e não substitui a Fase 17.
- Worker precisa estar rodando; API não fecha rodadas sozinha.

## Pontos confirmados na execução

1. **Análise interna:** confirmada e implementada como parecer `INCONCLUSIVE` com encaminhamento para revisão humana, sem decisão automática.
2. **Confirmação do capitão:** confirmada e implementada como registro separado, sem contar como voto adicional.
3. **Retenção:** segue pendente; não bloqueia a implementação, mas precisa ser definida na revisão de LGPD.

## Condição de parada

A implementação foi iniciada por pedido explícito do responsável, antes do merge do PR documental e da criação da branch `feat/07-resultados-e-disputas`. O trabalho permanece sem commit/push até autorização. Encerrar a fase ao cumprir os critérios restantes. Não iniciar a Fase 8.
