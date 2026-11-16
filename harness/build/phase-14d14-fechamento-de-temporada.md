# Fase 14D.14 — Fechamento de temporada e reset suave da divisão

**Status:** implementado no backend em 2026-11-13.
**Depende de:** 14D.7 (temporada), Fase 8 (rating).

## Problema

A temporada nascia ativa e nunca fechava. Como a divisão era derivada de
`matches_played` acumulado, ela também nunca voltava a "Provisório" na virada,
contrariando a ADR 0045 §1.6.

## Decisão

1. **`close_expired_season`** fecha a temporada vencida (`status = closed`),
   cria a do trimestre corrente e semeia a trilha de 30 níveis.
2. **Reset suave:** o `RatingAccount` (rating, RD e volatilidade) permanece
   intacto. A contagem de colocação passa a ser por temporada em
   `season_placements`.
3. **Provisório por temporada:** `GET /ratings/me`, posição e top 100 usam a
   contagem da temporada ativa. Com menos de 5 ranqueadas, o jogador aparece
   como `PROVISIONAL` e fora do ranking; depois, a divisão sai do rating
   persistente.
4. **Fora de temporada**, a leitura cai para a contagem histórica, para não
   apagar a divisão de quem está sem temporada ativa.
5. **Rotina:** `python -m scripts.close_seasons` fecha temporadas vencidas e
   aceita `--loop --interval`.

## Modelo

`season_placements` com PK `(user_id, season_id)` e `matches_played`. Migração
`f5b2d8e4c310`, aplicada em upgrade → downgrade → upgrade; `alembic check` limpo.

## Testes

`tests/test_season_close.py`: fecha 2026-Q4, abre 2027-Q1 com trilha, preserva
rating e zera a colocação; fechar sem temporada vencida é no-op.
`tests/test_ratings_api.py` passou a criar a colocação da temporada nos
cenários de ranking.

## Pendente

- Fechamento não gera extrato/retrospectiva automática; a retrospectiva da
  ADR 0043 §7 é leitura derivada.
- Definição de o que acontece com partidas ranqueadas em andamento na virada.
- Notificação de fim de temporada.
