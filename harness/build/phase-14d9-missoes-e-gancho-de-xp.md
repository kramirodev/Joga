# Fase 14D.9 — Missões semanais e gancho de XP

**Status:** implementado localmente em 2026-11-12.
**Branch:** `main`

## Fontes e contexto

- ADR 0043 §3 (trilha e XP) e §4 (missões e streak)
- Fase 14D.7 (temporada) e 14D.8 (trilha)
- `docs/ESPECIFICACAO_TEMPORADA_E_CATALOGO.md` §4 e §6

## Objetivo

Fazer o XP acontecer por jogar, e não só existir como tabela.

## Regras aplicadas

| Fonte | XP | Gatilho |
|---|---:|---|
| Partida concluída | 100 | Reserva `COMPLETED` com presença `PRESENT` |
| Primeira visita à quadra | 50 | Primeira reserva `COMPLETED` do jogador naquele espaço |
| Missão concluída | 40 | `play_one` e `new_venue`, uma vez por semana |

- **Idempotência:** partida usa `match:{booking_id}:{user}`; quadra usa `venue:{space_id}:{user}`; missão usa `mission:{season_id}:{week}:{code}:{user}`.
- **Missões semanais:** `play_one`, `new_venue`, `on_time_checkin`. O reset é uma linha nova por `week_start`, sem rotina destrutiva.
- **Sem temporada ativa:** o gancho é silencioso, não quebra a conclusão da partida.

## Implementação

- `mission_progress` com PK `(user_id, season_id, week_start, mission_code)`.
- `MISSION_DEFINITIONS`, `record_mission`, `award_match_xp`, `award_new_venue_xp`, `missions_for`.
- `BookingService.complete` chama `_award_season_progress` para os presentes e `_is_first_visit` para decidir a quadra nova.
- `GET /api/v1/me/progress/missions`.

## Testes

`tests/test_season_hooks.py`:

- conclusão credita 230 XP (100 + 40 + 50 + 40) e completa as duas missões;
- concluir duas vezes não soma XP de novo;
- endpoint lista as três missões da semana com progresso zero.

Suíte completa, `ruff`, `mypy --strict` e `alembic check` verdes; migração `d9e95b6f7384`
testada em upgrade, downgrade e novo upgrade.

## Lacunas

1. **XP de vitória não existe.** Depende do resultado confirmado no domínio de resultados; o
   gancho ali não foi ligado.
2. **Missão `on_time_checkin` não avança.** O check-in vive no módulo de presença e ainda não
   chama `record_mission`.
3. **Streak não é atualizada na conclusão.** `record_match_result` existe, mas o resultado não
   chega ao módulo de temporada.
4. **Sem fechamento de temporada:** não há snapshot, encerramento nem emissão de insígnia em lote.
5. **Sem passe:** a trilha paga continua bloqueada.

## Próxima fatia

**14D.10 — Resultado no XP e fechamento de temporada:** ligar vitória/derrota ao XP e à streak,
fechar a temporada com snapshot e distribuir a insígnia.
