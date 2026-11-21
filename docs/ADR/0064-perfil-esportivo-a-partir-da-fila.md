# ADR 0064 — Perfil esportivo a partir da escolha da fila

- **Status:** Aprovado em 2026-11-21.
- **Data:** 2026-11-21
- **Numeração:** esta ADR ocupa o número **0064**. A numeração está congelada:
  **0063** = moderação de quadras, **0064** = perfil esportivo a partir da fila.
- **Relaciona:** `docs/ADR/0057-fila-multi-entrada.md`,
  `backend/app/api/v1/matchmaking.py`,
  `backend/app/modules/matchmaking/service.py`,
  `backend/app/modules/profile/models.py` e
  `backend/app/modules/profile/service.py`.

## Contexto

O jogador escolhe esporte, nível e preferência de quadra na própria tela de
fila. O `PUT /api/v1/matchmaking/queue` (e o `POST /queue` legado de entrada
única) validava `UserSportProfile` existente e respondia
`409 sport_profile_required` quando o perfil ainda não tinha aquele formato. O
app então mandava o jogador "completar este esporte" no perfil: a mesma escolha
era pedida duas vezes, em telas diferentes, e a fila não podia começar sem uma
ida prévia ao perfil.

O perfil esportivo já tem tudo o que a fila precisa: `user_id`, `format_id`,
`level` e `court_preference`, com unicidade por `(user_id, format_id)`.

## Decisão

1. **A fila alimenta o perfil.** `MatchmakingService` faz upsert de
   `UserSportProfile` para cada formato que entra na fila, tanto em
   `enqueue` (`POST`) quanto em `replace`/`replace_targets` (`PUT`). A escolha
   feita na fila vira a **última preferência** daquele formato.
2. **Nível casual vence.** Quando a seleção casual traz nível explícito
   (`selections[].level` ou `levels` do contrato legado), esse nível é gravado
   no perfil. Sem nível explícito, o perfil existente é preservado; se não
   existir perfil, continua valendo `409 sport_profile_required`, porque não há
   nível escolhido a persistir. O `POST` casual, que não recebe nível, mantém
   esse comportamento.
3. **Ranqueada não inventa preferência.** Ranqueada pareia por MMR e divide
   times por rating (ADR 0025); nível não participa do pareamento. Se o formato
   selecionado apenas em ranqueada ainda não tem perfil, ele é criado com
   `intermediate`; se já existe, o nível salvo é preservado. Nível explícito em
   par ranqueado continua respondendo `422 level_not_applicable_for_ranked`.
4. **Preferência de quadra global.** Se o payload trouxer
   `court_preference`, o valor é gravado no perfil de **todos os formatos
   selecionados**. Sem o campo, a preferência existente é preservada; na
   criação, o default é `ANY`.
5. **Só os formatos da fila são tocados.** Formatos não selecionados não
   recebem perfil nem têm o perfil alterado.
6. **Atomicidade.** O upsert usa a mesma `Session` e a mesma transação da fila.
   O `PUT`/`POST` só faz `commit` depois que toda a seleção foi validada,
   comparada e escrita; qualquer erro anterior ao `commit` é desfeito pelo
   `rollback` da rota. As validações de formato ativo, região, ranqueada
   restrita, duplicidade de par e níveis são executadas antes da criação/edição
   do perfil.
7. **Sem mudança no contrato de resposta.** O corpo de `GET`/`PUT`/`POST` da
   fila permanece o mesmo (`entry`, `entries[]`, `matched[]` e os campos de
   `QueueEntryResponse`).
8. **Sem migração.** O schema `user_sport_profiles` e a constraint
   `uq_user_sport_profiles_user_format` já sustentam o upsert.

## Consequências

- O app deixa de exigir uma passagem prévia pelo perfil: escolher esporte,
  nível e quadra na fila já cria/atualiza a preferência.
- `GET /api/v1/me/profile` passa a refletir a escolha da fila na requisição
  seguinte; não há cache de perfil, apenas leitura da sessão/banco.
- A emenda de 2026-11-20 da ADR 0057, que dizia que o nível do par substituía o
  perfil "apenas naquele par", fica superada nesta parte: o nível casual
  explícito agora também atualiza o perfil.
- Entradas já preservadas por `created_at` continuam usando o nível do perfil
  atualizado quando não enviam override; o cronômetro de espera não reinicia.
- Um formato selecionado em casual e ranqueada no mesmo pedido grava o nível
  casual no perfil; a entrada ranqueada apenas registra esse nível e continua
  pareando por MMR.
- Concorrência continua protegida pela constraint única: duas requisições
  simultâneas que tentem criar o mesmo perfil podem gerar `409 queue_conflict`,
  sem perfil ou fila parcial.

## Alternativas consideradas

- **Manter o `409 sport_profile_required` e pedir o perfil antes da fila:**
  rejeitado. É o trabalho duplicado que motivou a decisão e contraria o fluxo
  aprovado de escolher tudo na fila.
- **Ignorar a escolha de nível/quadra da fila e usar sempre o perfil:** rejeitado.
  A escolha da fila deixaria de ter efeito e o perfil ficaria desatualizado.
- **Sobrescrever o nível em ranqueada com `intermediate`:** rejeitado. Ranqueada
  não usa nível para parear e apagaria uma preferência legítima do casual.
- **Criar perfil para todos os formatos do catálogo:** rejeitado. Ampliaria
  dados pessoais sem escolha do jogador e tocaria formatos fora da seleção.
- **Gravar perfil em transação separada:** rejeitado. Uma falha na fila deixaria
  o perfil alterado, contra a atomicidade exigida.

## Verificação

Testes em `backend/tests/test_matchmaking_api.py` cobrem: criação de perfil na
primeira fila casual com o nível escolhido; `GET /me/profile` refletindo sem
cache; `court_preference` global atualizando todos os formatos selecionados e
nenhum fora deles; ranqueada sem perfil criando `intermediate`; ranqueada com
perfil preservando o nível; `replace` com nível alterado atualizando o perfil; e
falha depois do upsert desfazendo perfil e fila.
