# ADR 0057 — Fila com múltiplas entradas, substituição atômica e sorteio

- **Status:** Aprovado em 2026-11-20.
- **Data:** 2026-11-20
- **Numeração:** esta ADR ocupa o número **0057**. A numeração está congelada:
  **0053** = modo demo sem PSP, **0054** = cache e rate limit do catálogo
  público, **0055** = quadra pública gratuita, **0056** = enquete de escolha de
  quadra, **0057** = fila multi-entrada.
- **Relaciona:** `docs/CONTRATO_RESERVAS_APP.md` §23,
  `docs/JOGA_DOCUMENTACAO_TECNICA.md` §8,
  `backend/app/api/v1/matchmaking.py`,
  `backend/app/modules/matchmaking/service.py`,
  `backend/app/modules/matchmaking/policy.py` e
  `backend/app/modules/matchmaking/models.py`.

## Contexto

O banco já permitia várias entradas simultâneas do mesmo usuário: o índice
único parcial `uq_queue_entries_active` cobre `(user_id, format_id, mode)` com
`status = 'waiting'`. A API, porém, era single-entry: `POST /queue` criava uma
entrada, `GET /queue` devolvia apenas a mais recente e `DELETE /queue` cancelava
uma. O app mobile tem multiseleção de esportes e enviava só o primeiro item,
tratando a seleção do jogador como uma única modalidade.

Também não havia proteção contra um usuário ser escalado em duas partidas
sobrepostas quando possuía entradas em formatos diferentes (grupos distintos do
matcher) ou quando já tinha lobby agendado de ciclo anterior. O critério de
disponibilidade olhava apenas as janelas do perfil.

## Decisão

1. **Seleção explícita da fila.** `PUT /api/v1/matchmaking/queue` recebe
   `formats[]` e `modes[]` e materializa o produto cartesiano
   `formats × modes` como entradas `waiting`. A lista é deduplicada no servidor.
2. **Substituição atômica.** O `PUT` valida tudo (formato ativo, perfil
   esportivo, região, restrição ranqueada) **antes** de escrever; em seguida
   cancela todas as entradas `waiting` do usuário e insere as novas na mesma
   transação. Falha no meio não deixa estado parcial. Lista vazia apenas
   cancela a seleção.
3. **Leitura completa e compatibilidade.** `GET /queue` devolve `entries[]` com
   todas as `waiting` e mantém o campo legado `entry` (última `waiting` ou
   `matched`) para o app atual. `DELETE /queue` cancela todas as `waiting`.
   `POST /queue` continua com o comportamento single-entry, sem divergência.
4. **O matcher considera todas as `waiting`.** O pool nunca foi por
   `latest_entry`; a decisão registra que ele deve continuar olhando o conjunto
   inteiro de entradas.
5. **Sorteio no empate.** Quando o mesmo usuário tem entradas elegíveis em mais
   de um grupo `(format_id, mode)` no mesmo ciclo, apenas uma vira lobby. A
   ordem dos grupos é embaralhada com `secrets.SystemRandom` (não determinística,
   uniforme entre os grupos), então a entrada vencedora é sorteada. As demais
   permanecem `waiting` e **não** são canceladas. Um mesmo usuário não entra em
   dois lobbies no mesmo ciclo.
6. **Tempo consumido, não a entrada.** A disponibilidade continua vindo das
   janelas do perfil; o que muda é que horários já comprometidos pelo usuário
   são excluídos da busca de slot. O intervalo ocupado é derivado do **lobby**,
   não da reserva:
   - `lobbies` com `origin IN ('matchmaking', 'manual')`;
   - usuário como participante (`lobby_participants`);
   - `status != 'cancelled'` e `scheduled_end_at > now` (critério temporal:
     `completed` no futuro ainda ocupa; `completed` no passado não afeta);
   - intervalo `scheduled_start_at .. scheduled_end_at`.
   As demais entradas do usuário continuam ativas e podem formar outra partida
   em horário não sobreposto. O mesmo conjunto de ocupados vale para todas as
   entradas do usuário (casual e ranqueada).
7. **Sem migração.** O índice parcial existente já suporta a decisão.

## Por que o lobby, e não a reserva

`bookings.lobby_id` tem constraint única (`uq_bookings_lobby`) e o contrato
exige lobby existente: a reserva é 1:1 com o lobby e não existe reserva sem
lobby. O horário é fixado na criação do lobby, antes de pagamento ou divisão de
ingresso. Logo, contar `bookings` duplicaria a ocupação e dependeria de um
estado financeiro que não define o compromisso de tempo.

## Achado de verificação (não corrigido nesta ADR)

Consulta somente leitura no banco local (`127.0.0.1:5434/joga`, 2026-11-20):
4 reservas, todas com `lobby_id`; **1 divergente** entre `bookings.starts_at` e
`lobbies.scheduled_start_at` (reserva `a5698838-…`: `13:00:00Z` contra
`11:49:33.304515Z`). `POST /api/v1/bookings` recebe `starts_at` do cliente e
valida agenda, conflito e participação no lobby, mas **não exige igualdade** com
o horário do lobby. Isso é um achado separado; a fila usa o lobby como
autoridade e não foi alterada por causa dele.

## Alternativas consideradas

- **Manter uma entrada por vez e sobrescrever no `POST`:** rejeitado. Perde a
  multiseleção do app e mistura criação com substituição.
- **Cancelar e recriar em transações separadas:** rejeitado. Abre janela sem
  fila e estado parcial em caso de falha.
- **Escolher a entrada vencedora pela ordem de criação:** rejeitado. Prejudica
  sempre a mesma modalidade e não atende ao sorteio aprovado.
- **Marcar as entradas perdedoras como canceladas:** rejeitado. O produto manda
  mantê-las `waiting` para o próximo ciclo.
- **Bloquear por reserva (`bookings`):** rejeitado. Duplicaria a contagem e
  dependeria de pagamento; o lobby já fixa o horário.

## Consequências

- O app deve trocar a seleção por `PUT /queue` com todas as modalidades/modos
  escolhidos; `GET` passa a listar `entries[]`.
- O worker pode manter entradas `waiting` de um usuário por vários ciclos, sem
  risco de sobreposição.
- A busca de slot fica um pouco mais restritiva: um slot só é escolhido se não
  cruzar nenhum lobby ativo de qualquer participante.
- O sorteio é não determinístico; testes comprovam que os dois grupos podem
  vencer em execuções repetidas.
- O recorde de tempo ocupado usa apenas lobbies; reservas continuam sendo
  validadas no seu próprio fluxo para o espaço físico.

## Emenda 2026-11-20 — seleção explícita por par

A decisão 1 (produto cartesiano `formats × modes`) permanece válida como
contrato legado, mas era insuficiente: pedir futebol ranqueado e vôlei casual
obrigava o app a criar também futebol casual e vôlei ranqueada.

O `PUT /api/v1/matchmaking/queue` passa a aceitar `selections`, lista explícita
de `{ format_id, mode, level? }`:

- cada par vira exatamente uma entrada `waiting`, sem produto cartesiano;
- `selections` é mutuamente exclusiva com `formats`, `modes` e `levels`
  (`422 ambiguous_queue_selection`), para não haver duas fontes de seleção nem
  de nível;
- par `(format_id, mode)` repetido responde `422 duplicate_queue_selection`;
- `level` do par, quando presente, substitui o nível do perfil apenas naquele
  par; ausente, vale o perfil;
- `level` só se aplica a **casual**. Ranqueada pareia por MMR e divide times por
  rating, então `level` em par `ranked` responde `422
  level_not_applicable_for_ranked` (mesma regra para `levels` no contrato
  legado). Sem nível, a entrada ranqueada continua guardando o nível do perfil,
  que permanece sem efeito no pareamento;
- `selections: []` cancela todas as entradas `waiting`.

A substituição continua atômica e por diferença, preservando `created_at` dos
pares que permanecem, cancelando só os removidos e sem tocar em `matched`.
Não há migração: o índice único parcial `(user_id, format_id, mode)` para
`status = 'waiting'` já garante a unicidade. A implementação é
`MatchmakingService.replace_targets`, com `replace` mantido como adaptador do
contrato cartesiano.
