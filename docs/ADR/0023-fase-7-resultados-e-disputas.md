# ADR 0023 — Fase 7: resultados, disputas, capitão provisório e evidências

- **Status:** Aprovado em 2026-11-06, implementado no backend e validado com PostgreSQL 16/PostGIS local na mesma data; retenção provisória no ADR 0024; pendente de revisão e commit.
- **Data:** 2026-11-06
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `PLANS.md` Fase 7; `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §9; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §10; ADR 0008; `harness/build/phase-07-resultados-e-disputas.md`.

## Contexto

A Fase 6 encerrou o ciclo da partida em `IN_PROGRESS`, mas não implementou relatos, validação, disputa nem decisão. O schema já prevê `RESULT_PENDING`, `DISPUTED`, `FINALIZED` e `VOIDED`, porém a matriz de transições ainda não permite alcançá-los.

A Fase 7 precisa fechar o ciclo de resultado sem antecipar MMR/Trust Factor (Fase 8), sem criar telas mobile e sem introduzir armazenamento de arquivos.

## Decisões aprovadas

### Prazo e resultados

1. **Prazo de relato:** 10 minutos após o encerramento da partida. O backend controla o prazo; o aplicativo não é autoridade. O valor é configurável por formato no futuro, mas cada lobby não pode alterá-lo livremente.
2. **Três resultados possíveis:** `TEAM_1`, `TEAM_2` ou `DRAW`, quando o formato permitir. A votação não é binária.
3. **Empate esportivo por formato:** futebol 5x5 permite `DRAW`; vôlei não permite. A opção inválida é rejeitada.
4. **Votos ausentes ou anulados:** não entram no denominador e não significam concordância nem discordância.
5. **Resultado avaliado:** o resultado com mais votos válidos (maioria simples/plurality). Não confundir com maioria absoluta.
6. **Divergência:** calculada em relação ao resultado avaliado, usando apenas votos válidos como denominador:
   - menos de 50%: resultado pode ser confirmado;
   - exatamente 50%: segunda rodada;
   - mais de 50%: disputa e revisão humana.
7. **Sem tolerância separada de 1–2 votos.** A regra é o limite de 50%.
8. **Quórum mínimo:** `ceil(participantes_elegíveis / 2)` votos válidos.
   - O conjunto de elegíveis é congelado na abertura da primeira rodada e reutilizado na segunda.
   - Abaixo do quórum: revisão humana, sem finalização automática.
9. **Segunda rodada:** 5 minutos, controlada pelo backend, sem renovação automática. Ocorre quando há empate na primeira posição ou divergência exatamente igual a 50% na primeira rodada.
10. **Alternativas da segunda rodada:** todas as opções permitidas pelo formato (`TEAM_1`, `TEAM_2` e, se permitido, `DRAW`), independentemente da distribuição da primeira rodada.
11. **Resultado da segunda rodada:**
    - resultado único e divergência abaixo de 50%: finaliza;
    - exatamente 50%: análise interna; se inconclusiva, revisão humana;
    - acima de 50%: disputa e revisão humana;
    - empate na primeira posição, ausência de resultado único ou falta de quórum: revisão humana.
12. **Sem terceira rodada.** A segunda rodada é a última etapa automática de votação.

### Capitão

13. **Seleção provisória:** maior número de partidas `FINALIZED`, do mesmo formato, concluídas antes da partida atual, nas quais o jogador tenha efetivamente participado. Empate resolvido por UUID.
14. **Momento:** na formação da partida, com versão `provisional_v1`. A seleção é registrada e não recalculada retroativamente.
15. **Sem critério de nível.** Trust Factor, MMR e idade só podem ser incorporados na Fase 8, para partidas futuras.
16. **Confirmação do capitão não é voto adicional.** O capitão tem o mesmo voto individual dos demais; a confirmação de equipe é um registro separado, usado como sinal interno, sem peso automático.

### Evidência, revisão e escopo

17. **Evidência textual:** no máximo 2.000 caracteres, uma justificativa por participante por disputa. Privada, com acesso restrito e auditável. Sem anexos, imagens ou upload.
18. **Visibilidade:** relatos e votos individuais visíveis aos participantes; contagem agregada e resultado parcial somente após o fechamento da rodada. Justificativas privadas não entram nessa visibilidade.
19. **Revisão humana:** CLI/script auditável. `--operator` validado contra lista de operadores autorizados, `--reason` obrigatório. Sem painel administrativo nem endpoint público de moderação.
20. **Backend-only:** sem telas mobile nesta fase.
21. **Sem MMR:** nenhum rating é implementado ou atualizado. O resultado `FINALIZED` será consumido pela Fase 8.
22. **Histórico preservado:** votos, alterações, confirmações, decisões e revisões são append-only; nada é sobrescrito ou alterado retroativamente.

## Consequências

- A matriz de transições passa a incluir `IN_PROGRESS → RESULT_PENDING`, `RESULT_PENDING → FINALIZED | DISPUTED | VOIDED` e `DISPUTED → FINALIZED | VOIDED`.
- O worker de partidas precisa encerrar a partida pelo horário, abrir a primeira rodada, fechar rodadas e abrir a segunda.
- O modelo de dados precisa de rodadas, elegíveis congelados, relatos, confirmações de capitão, disputa, evidência textual, análise, revisão e decisão.
- `match_participants` precisa registrar capitão e versão da seleção.
- A Fase 7 continua sem storage de arquivos, o que reduz escopo e risco.
- A Fase 8 será a primeira consumidora de `FINALIZED`; nenhum rating será aplicado antes dela.
- O contrato HTTP completo está em `harness/build/phase-07-resultados-e-disputas.md`.

## Implementação realizada (2026-11-06)

- **Módulos:** `backend/app/modules/results/` (modelos, política pura e serviço) e `backend/app/modules/idempotency/` (registro de replay).
- **Migração:** `backend/migrations/versions/e1a4c7d9b230_add_match_results.py`; `signals` e `response_body` usam JSONB no PostgreSQL e JSON no SQLite de testes. Aplicada, revertida e reaplicada com sucesso em PostgreSQL 16/PostGIS local.
- **API:** `GET /matches/{id}/result`, `GET/POST /matches/{id}/result-reports`, `POST /matches/{id}/result-confirmations`, `POST /matches/{id}/disputes/{dispute_id}/evidence` e `GET /matches/{id}/disputes/{dispute_id}/evidence/me`.
- **Worker:** `scripts/advance_matches.py` passou a abrir/fechar rodadas e apurar resultados após o ciclo de partidas.
- **Revisão humana:** `scripts/review_match_result.py`, com operador validado por `JOGA_REVIEW_OPERATORS`, motivo obrigatório, `--dry-run` e exit codes 0–5.
- **Capitão:** seleção `provisional_v1` na formação, por partidas `FINALIZED` do mesmo formato e UUID como desempate; somente lobbies de matchmaking.
- **Rate limiting:** `backend/app/modules/ratelimit/`, tabela `rate_limit_counters` e migração `f2b5d8e1a7c3_add_rate_limit_counters.py`; POSTs de relato, confirmação e evidência limitados por usuário em janela fixa de 60 segundos, com `429 rate_limited` e `Retry-After`.
- **Testes:** `test_results_policy.py`, `test_results_service.py`, `test_results_api.py`, `test_review_cli.py`, `test_results_postgres.py`, `test_ratelimit.py` e `test_results_cleanup.py`, apoiados por `helpers_results.py`. Sem PostgreSQL: **224 passed, 21 skipped**. Com `JOGA_TEST_DATABASE_URL`: **245 passed, 0 skips**, incluindo concorrência de votos, confirmações, fechamento de rodada, segunda rodada, decisão humana, rate limit e retenção.
- **Retenção:** política provisória no `docs/ADR/0024-retencao-provisoria-resultados.md`; limpeza manual por `scripts/cleanup_results.py`, com `--dry-run` e prazos configuráveis.
- **Desvios documentados:** `Idempotency-Key` ausente retorna 422 `missing_idempotency_key` e chave acima de 120 caracteres retorna 422 `invalid_idempotency_key`; `result_version` começa em 0 e vira 1 na primeira finalização; a retenção definitiva depende da revisão LGPD das Fases 10/19.
- **Fora do escopo:** MMR/rating, telas mobile, painel administrativo, upload de arquivos e notificações.

## Pontos de implementação confirmados na execução

1. **Análise interna na Fase 7.** Confirmado e implementado: a análise interna produz parecer auditável com os sinais disponíveis (consistência entre rodadas, mudanças de voto e confirmações de capitão) e **sempre encaminha para revisão humana**, sem decisão automática.
2. **Confirmação do capitão como registro separado.** Confirmado e implementado: existe um registro próprio de confirmação por capitão, sem contar como voto.

## O que este ADR não decide

- Não define detalhes de implementação além dos registrados acima; a decisão em si não cria código, migração, endpoint ou tela.
- Não define MMR, Trust Factor ou algoritmo de rating.
- Não aprova upload de arquivos.
- Não define a política completa de revisão humana.
- Não substitui `PLANS.md` nem o arquivo da Fase 7.
