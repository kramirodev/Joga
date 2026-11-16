# Fase 14D.10 + 14D.11 — XP de vitória, streak e missão de check-in

**Status:** implementado no backend em 2026-11-13.
**Depende de:** 14D.7 (XP/streak), 14D.9 (missões), Fase 7 (resultados).

## Problema

`record_match_result` existia e nunca era chamado, então vitória não somava
streak nem pagava os +40 XP da ADR 0043 §3. A missão `on_time_checkin` estava
em `MISSION_CODES` e não era gravada em lugar nenhum.

## Decisão

1. **Resultado confirmado é o gatilho.** O gancho roda em `_finalize` (apuração
   automática) e na decisão humana `FINALIZE`. Partida em disputa ou anulada não
   paga nada.
2. **Só quem esteve presente conta.** Participantes com `status = checked_in`.
3. **Vitória:** +40 XP com chave `win:{match_id}:{user_id}` e streak +1.
   Empate e derrota não pagam XP de vitória e zeram a streak.
4. **Idempotência em duas camadas:** o evento de XP tem chave única por partida
   e jogador; `record_match_result` ignora a mesma partida repetida. A máquina
   de estados garante uma única finalização.
5. **Sem temporada ativa, o gancho é silencioso** e não quebra a finalização.
6. **Check-in no prazo:** ao confirmar presença antes de `scheduled_start_at`,
   grava a missão semanal `on_time_checkin`. A missão completa uma vez por
   semana e paga 40 XP.

## Arquivos

- `backend/app/modules/results/service.py` — `_award_season_result` e chamadas.
- `backend/app/modules/matches/service.py` — `_record_on_time_checkin`.
- `backend/app/modules/season/service.py` — guarda de idempotência na streak.

## Testes

`tests/test_season_result_hooks.py` cobre vitória (XP e streak por time),
empate (zera sem XP), disputa (não paga), reexecução do gancho e missão de
check-in. `tests/test_season.py` passou a usar partidas distintas e verifica que
a mesma partida não infla a sequência.

## Pendente

- XP de vitória em partida casual e ranqueada ao mesmo tempo? Hoje vale para as
  duas, como a ADR 0043 descreve.
- Correção de resultado revertido não compensa XP/streak (não há fluxo de
  reversão depois de `FINALIZED`).
