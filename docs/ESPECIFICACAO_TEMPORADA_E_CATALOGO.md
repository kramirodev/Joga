# Especificação técnica — Temporada, trilha, XP, passe e catálogo cosmético

- **Versão:** 1.0
- **Data:** 2026-11-11
- **Status:** especificação para implementação futura. **Nada implementado.**
- **Base:** ADR 0043 (temporada, passe e customização), ADR 0042 (ingresso e passe), ADR 0025 (MMR, rankings e cosméticos), ADR 0029 (sem fotos de pessoas), ADR 0044 (clãs no MVP), ADR 0045 (estatísticas e inteligência de rede).

> Este documento define modelos, regras e contratos. Não define arte, copy, preço final nem calendário de lançamento. Onde a decisão ainda depende de dados, está marcado como **calibração pendente**.

---

## 1. Escopo

No escopo: temporada trimestral, trilha de níveis, XP, missões, streak, passe trimestral com franquia mensal, catálogo cosmético em três estados, atribuição e equipamento de itens.

Fora do escopo: troféus de clã (ADR 0044), MMR e ranking (ADR 0025), estatísticas pessoais e de rede (ADR 0045), publicidade (Fase 18), moderação.

---

## 2. Conceitos

| Conceito | Definição |
|---|---|
| **Temporada** | Período de 3 meses, alinhado ao trimestre civil. Há 4 por ano |
| **Ciclo de passe** | O mesmo trimestre. Um passe cobre exatamente uma temporada |
| **Trilha** | 30 níveis por temporada. Cada nível exige 150 XP |
| **XP** | Progresso. Único e igual para todos. Nunca comprado, nunca multiplicado por assinatura |
| **Missão** | Tarefa semanal com recompensa de XP. Três por semana |
| **Streak** | Vitórias consecutivas **com validade semanal**: derrota, empate ou semana sem jogar zeram. `best_wins` é recorde permanente |
| **Item cosmético** | Elemento visual. Existe em exatamente um dos três estados: livre, XP ou passe |
| **Atribuição** | Registro que diz que o jogador pode usar um item, e por quê |

---

## 3. Modelo de dados

### 3.1 Temporada e trilha

```text
seasons
  id                uuid pk
  code              text unique          -- "2027-Q1"
  starts_at         timestamptz          -- 00:00 America/Sao_Paulo
  ends_at           timestamptz          -- exclusivo
  status            enum(draft, active, closing, closed)
  track_version     int                  -- incrementa a cada rebalanceamento
  badge_item_id     uuid fk cosmetic_items
```

```text
season_track_levels
  season_id         uuid fk seasons
  level             smallint             -- 1..30
  xp_required       int                  -- acumulado para alcançar o nível
  free_reward_id    uuid fk cosmetic_items null
  pass_reward_id    uuid fk cosmetic_items null
  primary key (season_id, level)
```

Regra: `xp_required(level) = level * 150`. O nível 1 é alcançado com 150 XP; o 30 com 4.500.

### 3.2 XP — ledger append-only

```text
xp_events
  id                uuid pk
  user_id           uuid fk
  season_id         uuid fk seasons
  source            enum(match, win, mission, new_venue, admin_adjust)
  amount            int                  -- sempre positivo; ajuste é evento novo
  ref_type          text                 -- "match", "mission", "venue"
  ref_id            uuid
  idempotency_key   text
  created_at        timestamptz
  unique (source, ref_type, ref_id)
  unique (idempotency_key)
```

O ledger é a **fonte da verdade**. `season_progress` é projeção reconstruível:

```text
season_progress
  user_id, season_id    pk composta
  xp_total              int
  level                 smallint
  updated_at            timestamptz
```

Nenhum XP é atribuído diretamente em `season_progress`. Toda concessão passa por `xp_events`. Correção é novo evento com `source=admin_adjust`, nunca `update` ou `delete`.

### 3.3 Missões

```text
mission_definitions
  code              text pk              -- "play_one", "new_venue", "on_time_checkin"
  season_id         uuid fk seasons null -- null = vale em qualquer temporada
  target            int
  xp_reward         int
  active            bool
```

```text
mission_progress
  user_id, season_id, week_start   pk composta
  mission_code                     pk
  progress                         int
  completed_at                     timestamptz null
  unique (user_id, season_id, week_start, mission_code)
```

`week_start` é a segunda-feira 00:00 em `America/Sao_Paulo`. O reset semanal é **derivado**, não uma rotina destrutiva: uma nova semana é uma nova linha.

### 3.4 Streak de vitórias

```text
win_streaks
  user_id           uuid pk
  current_wins      int
  best_wins         int
  last_match_week   date          -- segunda-feira da semana da última partida contada
  last_match_id     uuid
  updated_at        timestamptz
```

Regras:

1. Vitória incrementa `current_wins`; empate ou derrota zeram.
2. **Semana sem partida concluída zera a sequência** no fechamento da semana. Quem não jogou, perdeu.
3. Exibição: `current_wins` vale enquanto `last_match_week >= semana_atual − 1`; caso contrário, 0. A semana corrente ainda aberta não zera — o jogador ainda pode jogar.
4. `best_wins` é recorde histórico e nunca diminui, inclusive entre temporadas.
5. Só conta resultado **confirmado**; partida em disputa não altera o streak.
6. Não concede XP nem qualquer vantagem. É exibição de perfil.
7. Recalculado a partir dos resultados gravados, nunca do cliente. O job semanal `weekly_streak_close` materializa o reset e alimenta a notificação de perda.

### 3.5 Passe

```text
pass_plans
  id                uuid pk
  code              text unique          -- "jogador", "craque", "time", "elenco"
  monthly_tickets   smallint             -- 10, 20, 30, 50
  quarterly_price   numeric(10,2)        -- 97,50 / 195,00 / 292,50 / 487,50
  unit_price        numeric(10,4)        -- 3,25
  active            bool
```

Preço unitário do passe: **R$ 3,25**, acima do pacote grande (R$ 3,10). O passe não dá desconto por ingresso; compensa em franquia mensal, ingressos grátis por nível e Temporada.

```text
pass_subscriptions
  id                uuid pk
  user_id           uuid fk
  plan_id           uuid fk pass_plans
  status            enum(pending, active, past_due, cancelled, ended)
  current_cycle_id  uuid fk pass_cycles null
  created_at, updated_at
```

```text
pass_cycles
  id                uuid pk
  subscription_id   uuid fk
  season_id         uuid fk seasons     -- ciclo = temporada
  month_index       smallint            -- 1..3
  starts_at, ends_at timestamptz
  paid_at           timestamptz null
  payment_id        uuid null           -- referência ao PSP
  status            enum(pending, paid, failed, refunded)
```

```text
pass_allowances
  id                uuid pk
  user_id           uuid fk
  cycle_id          uuid fk pass_cycles
  tickets_granted   smallint
  granted_at        timestamptz
  expires_at        timestamptz         -- fim do mês correspondente
  unique (cycle_id, user_id, month_index)
```

Regras:

1. O ciclo do passe é o **trimestre civil**, igual à temporada. Não existe passe mensal.
2. Cobrança única por trimestre; a franquia é concedida **mês a mês**, no primeiro dia de cada mês do ciclo.
3. A franquia **expira no fim do mês**. Não acumula e não converte em ingresso comprado (ADR 0042 §4).
4. Assinatura contratada no meio do trimestre ativa no primeiro dia do mês seguinte, com cobrança proporcional aos meses inteiros restantes.
5. Inadimplência: a franquia do mês não é concedida, o passe permanece `past_due` por 15 dias e depois `cancelled`. Os itens emprestados são revogados no cancelamento.
6. Cancelamento vale para o próximo ciclo; o ciclo pago é entregue até o fim.

### 3.6 Catálogo cosmético

```text
cosmetic_items
  id                uuid pk
  code              text unique          -- "frame_ouro_2027q1"
  category          enum(theme, palette, avatar_base, avatar_hair, avatar_accessory,
                         avatar_kit, frame, celebration, profile_effect, home_block,
                         clan_crest, badge)
  state             enum(free, xp, pass)
  rarity            enum(common, rare, epic, season)
  layer             smallint             -- ordem de composição quando aplicável
  artwork_ref       text                 -- chave no storage/CDN
  introduced_season uuid fk seasons null
  retired_at        timestamptz null     -- item que não retorna
```

```text
player_cosmetics
  user_id, item_id  pk composta
  source            enum(free, xp, pass, admin)
  unlocked_at       timestamptz
  revoked_at        timestamptz null     -- apenas source=pass
  revoked_reason    text null
```

```text
player_loadout
  user_id, slot     pk composta          -- slot = category
  item_id           uuid fk cosmetic_items
  updated_at
```

Regras:

1. **Um item, um estado.** Não existe item ao mesmo tempo `xp` e `pass`.
2. `state=free` → atribuição automática no cadastro, permanente.
3. `state=xp` → atribuição ao alcançar o nível que o contém, permanente.
4. `state=pass` → atribuição enquanto houver ciclo `paid` cobrindo a data; **empréstimo**, revogável.
5. Item emprestado revogado **não apaga o histórico**: `revoked_at` é preenchido e o registro permanece para readquirir ao reassinar.
6. Item com `retired_at` não entra em novas temporadas, mas quem já tem mantém.
7. **Nenhum item concede vantagem competitiva.** Não existe campo de efeito em `cosmetic_items` que alcance MMR, Trust Factor, matchmaking ou troféu.

### 3.7 Acessibilidade fora do catálogo

Tamanho de fonte, alto contraste, redução de movimento e alvos de toque ampliados **não são itens cosméticos**. São preferências de conta, sempre disponíveis, em tabela própria:

```text
accessibility_preferences
  user_id pk
  font_scale, contrast_mode, reduced_motion, large_targets
```

Isso impede que uma regressão de catálogo bloqueie acessibilidade.

---

## 4. Regras de XP

| Fonte | XP | Condição |
|---|---:|---|
| Partida concluída | 100 | Partida `COMPLETED` com presença confirmada |
| Vitória | +40 | Resultado confirmado; não vale em empate nem em partida sem resultado |
| Missão concluída | 40 | Uma vez por semana por missão |
| Primeira visita à quadra | 50 | Uma vez por quadra por jogador, em qualquer temporada |
| Ajuste administrativo | variável | Com justificativa e auditoria |

Proibições explícitas:

- XP por compra, por assinatura, por indicação ou por anúncio.
- Multiplicador de XP para assinante.
- XP por partida cancelada, expirada ou sem presença.
- XP duplicado para o mesmo `ref_id`, inclusive em caso de substituição.
- Qualquer XP atribuído a partir de payload do cliente.

Limites de segurança (calibração pendente): teto diário de 400 XP e teto semanal de 1.200 XP por jogador, para conter abuso sem bloquear uso legítimo.

---

## 5. Trilha e recompensas

1. 30 níveis por temporada, 150 XP por nível.
2. Cada nível tem uma recompensa **free** e, quando aplicável, uma **pass**.
3. A recompensa é **reivindicada** pelo jogador (ação explícita), não creditada em silêncio. Isso cria o momento de retorno ao app.
4. Recompensa não reivindicada até o fechamento da temporada é perdida — exceto itens `free`, que são creditados automaticamente.
5. O fechamento da temporada gera `season_snapshot` com nível final, XP e recompensas, para auditoria e para o badge.
6. **Nível da temporada** — bronze (1–9), prata (10–19), ouro (20–30) — é derivado do nível alcançado e **reseta na virada**. Não acumula entre temporadas. O streak de vitórias não reseta.
7. **Jogador que entra no meio da temporada começa no nível 1**, sem crédito proporcional. Não se recompensa quem não jogou. A contrapartida é de desenho, não de crédito: a curva precisa ser barata nos primeiros níveis para que o ingressante tardio alcance progresso visível nas primeiras partidas.
8. **Ingressos grátis por nível:** free recebe 1 a cada 5 níveis (máx. 6 por temporada); passe recebe 2 (máx. 12). São franquia: expiram no fim da temporada e não acumulam. Custo de 3,3% e 6,7% da receita respectivamente.

Distribuição sugerida (calibração pendente):

| Faixa de nível | Recompensa típica |
|---|---|
| 1–10 | Molduras, paletas, acessórios comuns |
| 11–20 | Acessórios raros, efeitos de perfil |
| 21–29 | Celebrações, kits |
| 30 | Item de temporada exclusivo + badge |

---

## 6. Missões

| Código | Alvo | Como é medido |
|---|---|---|
| `play_one` | 1 | Partida concluída na semana |
| `new_venue` | 1 | Primeira partida na quadra |
| `on_time_checkin` | 1 | Check-in até `starts_at` |

Regras:

1. Reset semanal na segunda-feira 00:00 (`America/Sao_Paulo`).
2. Progresso derivado de eventos de partida, nunca do cliente.
3. Conclusão credita XP automaticamente por `xp_events` (idempotente).
4. Missão não concluída não penaliza, não expira saldo e não gera dívida.

---

## 7. Atribuição: como um item fica disponível

Resolução de disponibilidade, em ordem:

```text
disponível(item, jogador, agora) =
     item.state = free
  ou (item.state = xp   e existe player_cosmetics(source=xp) não revogado)
  ou (item.state = pass e existe ciclo pass_cycles.status=paid cobrindo agora)
```

Regras de precedência:

1. `free` e `xp` são **permanentes**: não dependem de assinatura e não são revogados.
2. `pass` é **empréstimo**: revogado no fim do ciclo pago ou no cancelamento.
3. Revogação de item equipado desequipa e devolve ao default do slot, sem quebrar o perfil.
4. Reassinar restaura automaticamente os itens `pass` do catálogo vigente, sem perder escolhas anteriores.

---

## 8. Contratos de API

Públicos (autenticados, escopo do próprio jogador):

| Método | Rota | Função |
|---|---|---|
| GET | `/api/v1/seasons/current` | Temporada ativa, datas e `track_version` |
| GET | `/api/v1/me/progress` | XP, nível, próxima recompensa |
| GET | `/api/v1/me/track` | Trilha com estado por nível (bloqueado, disponível, reivindicado) |
| POST | `/api/v1/me/track/{level}/claim` | Reivindica recompensa de nível |
| GET | `/api/v1/me/missions` | Missões da semana e progresso |
| GET | `/api/v1/me/streak` | Streak atual e recorde |
| GET | `/api/v1/me/cosmetics` | Catálogo com estado de atribuição |
| PUT | `/api/v1/me/loadout` | Equipa itens por slot |
| GET | `/api/v1/me/pass` | Assinatura, ciclo, franquia do mês |
| POST | `/api/v1/me/pass/checkout` | Abre cobrança do ciclo |

Internos (worker, sem exposição pública):

| Evento | Efeito |
|---|---|
| `match.completed` | XP de partida, vitória, missões, streak |
| `booking.presence.confirmed` | Elegibilidade de XP e check-in |
| `venue.first_visit` | XP de quadra nova |
| `pass.cycle.paid` | Ativa ciclo e agenda franquias mensais |
| `pass.cycle.failed` | Marca `past_due`, suspende franquia |
| `season.closed` | Snapshot, badge, encerramento da trilha |

Regras de contrato:

1. Todos os endpoints são idempotentes quando criam efeito financeiro ou de progresso.
2. Nenhum endpoint aceita `xp`, `level` ou `item` vindos do cliente.
3. `GET /me/pass` nunca expõe dados de pagamento; apenas estado e franquia.
4. Erros de autorização usam 404 para não revelar existência de recurso de outro jogador.

---

## 9. Invariantes

1. XP é igual para todos; assinatura não acelera progressão.
2. Item de conquista nunca é perk direto.
3. Identidade e acessibilidade nunca são pagas.
4. Nenhum item altera competitividade.
5. Ledger de XP e de franquia é append-only.
6. Franquia do passe não acumula e não vira ingresso comprado.
7. Um item pertence a exatamente um estado.
8. O cliente nunca é fonte de verdade de progresso.

---

## 10. Observabilidade

Métricas: XP concedido por fonte, missões concluídas por semana, taxa de conclusão da trilha, ciclos de passe pagos e falhos, franquias concedidas e expiradas, itens desbloqueados por estado, itens revogados.

Alertas: XP negativo, XP duplicado por `ref_id`, nível inconsistente entre ledger e projeção, franquia concedida sem ciclo pago, item equipado sem atribuição válida.

---

## 11. Pendências

1. **Balanceamento de XP** — confirmar 150 XP/nível, 30 níveis e os tetos diário/semanal com dados de frequência.
2. Catálogo de arte por categoria e por temporada; definir o que é free na primeira temporada.
3. Definir se o nível 30 exige 4.500 XP linear ou uma curva não linear.
4. Definir período de reivindicação de recompensa e o que acontece com não reivindicada.
5. Definir preço final do trimestre e se haverá pagamento parcelado.
6. Definir integração dos escudos de clã (ADR 0044) ao catálogo.
7. Definir a comunicação do reset de temporada e do reset de nível.
