# Fase 14D.7 — Temporada, XP, nível e streak

**Status:** núcleo implementado localmente em 2026-11-12. Recompensas, trilha e catálogo
ficam para a fatia seguinte, porque dependem de decisão de produto.
**Branch:** `main`

## Fontes e contexto

- ADR 0043 §3 (trilha e XP) e §4 (missões e streak)
- `docs/ESPECIFICACAO_TEMPORADA_E_CATALOGO.md` §3 e §5
- Fase 14D.5 (quitação por ingressos)

## Objetivo

Dar progressão sem vantagem competitiva: XP igual para todos, nível derivado do XP, tier de
temporada que reseta e streak de vitórias com validade semanal.

## Implementação

- `seasons` — temporada trimestral com `code`, janela e `track_version`.
- `xp_events` — ledger append-only com `idempotency_key` única.
- `season_progress` — projeção `xp_total` e `level`, reconstruível.
- `win_streaks` — `current_wins`, `best_wins` e `last_match_week`.
- `app/modules/season/service.py` — `level_for`, `tier_for`, `award_xp`, `record_match_result`,
  `effective_streak`, `seed_current_season`.
- `GET /api/v1/me/progress` — temporada, XP, nível, tier, próximo nível e streak.

## Regras

| Item | Regra |
|---|---|
| XP por nível | 150 |
| Nível máximo | 30 |
| Tier | bronze 0–9 · prata 10–19 · ouro 20–30 |
| Reset | nível e XP resetam na virada da temporada |
| XP | idêntico para todos, nunca comprado |
| Streak | vitória soma; empate ou derrota zera; semana inteira sem jogar zera na leitura |
| Semana corrente | a semana ainda aberta não zera |

## Testes

`tests/test_season.py`:

- fronteiras de nível e tier;
- XP idempotente e conflito ao reutilizar chave com outro valor;
- nível acompanha o XP acumulado;
- streak soma em vitória, zera em derrota e preserva o recorde;
- streak expira depois de uma semana inteira sem jogar;
- `GET /me/progress` devolve temporada, XP, nível, próximo nível e streak.

Suíte completa, `ruff`, `mypy --strict` e `alembic check` verdes; migração `b7c8394d5162`
testada em upgrade, downgrade e novo upgrade.

## O que não está aqui

1. **Recompensas e trilha.** Não há tabela de níveis com prêmio: depende de decidir quais itens
   entram em cada faixa e quantos por temporada — decisão de produto.
2. **Missões.** O modelo e a regra existem na especificação, mas não há tabela nem progresso.
3. **Ganho de XP real.** Nada chama `award_xp` ainda: a ligação com partida concluída, vitória
   e primeira visita à quadra é a próxima fatia.
4. **Ingressos grátis por nível.** Dependem da trilha.
5. **Fechamento de temporada.** Não há job de `season_snapshot` nem emissão de badge.

## Próxima fatia

**14D.8 — Gancho de XP e missões:** ligar partida concluída, vitória e quadra nova ao ledger, e
criar o progresso semanal de missões.
