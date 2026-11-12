# Fase 14D.8 — Trilha, itens e insígnias

**Status:** implementado localmente em 2026-11-12, com arte em placeholder.
**Branch:** `main`

## Fontes e contexto

- ADR 0043 §5 (customização) e §11 (itens de temporada e insígnias)
- `docs/ESPECIFICACAO_TEMPORADA_E_CATALOGO.md` §5
- Fase 14D.7 (temporada, XP e streak)

## Decisões de produto aplicadas

| Tema | Decisão |
|---|---|
| Itens por temporada | **7**, incluindo emotes de chat |
| Categorias | Acessório de personagem, animação de lobby, emote de chat, ícone de entrada e insígnia |
| Nível 30 | Entrega a **insígnia da temporada** |
| Insígnia × medalha | Conceitos distintos; a insígnia é de temporada/fundador, a medalha é competitiva |
| Perfil | Até **3 insígnias equipadas** |
| Distribuição | Níveis 4, 8, 12, 17, 21, 26 e 30 |

## Itens da temporada 2026-Q4

| Nível | Item | Categoria | Trilha |
|---:|---|---|---|
| 4 | Emote Joinha | emote | free |
| 8 | Faixa de Cabeça | accessory | free |
| 12 | Ícone Relâmpago | entry_icon | **passe** |
| 17 | Emote Palmas | emote | free |
| 21 | Entrada Fumaça | lobby_animation | **passe** |
| 26 | Óculos Escuros | accessory | **passe** |
| 30 | Insígnia da Temporada | badge | free |

Ingressos grátis: níveis 5, 10, 15, 20, 25 e 30.

## Implementação

- `season_items`, `season_track_levels`, `season_claims`, `badges`, `player_badges`, `player_items`.
- `seed_season_track` cria itens, insígnia e os 30 degraus.
- `claim_level` valida XP, bloqueia trilha paga sem passe, entrega item e ingressos e é idempotente.
- `equip_badge` ocupa um dos três espaços e libera o anterior naquele slot.
- Endpoints: `GET /me/progress/track`, `POST /me/progress/track/{level}/claim`,
  `GET /me/progress/badges`, `PUT /me/progress/badges/equip`.
- Migração `c8d94a5e6273`, com a trilha da 2026-Q4 semeada.

## Testes

`tests/test_season_track.py`:

- trilha expõe 30 níveis e 7 itens;
- resgate sem XP retorna `409 level_locked`;
- resgate credita ingresso e não duplica;
- nível de trilha paga retorna `403 pass_required`;
- nível 30 entrega a insígnia e ela pode ser equipada;
- equipar insígnia de outro jogador retorna 404.

Suíte completa, `ruff`, `mypy --strict` e `alembic check` verdes; migração testada em
upgrade, downgrade e novo upgrade.

## Placeholders e lacunas

1. **Arte.** Todo item tem `artwork_ref = placeholder/<code>`; não há arquivo final.
2. **Passe não existe como assinatura.** A trilha paga é recusada com `pass_required`; quando o
   passe for implementado, o resgate passa a checar o ciclo ativo.
3. **Inventário mínimo.** `player_items` guarda o código do item; não há equipar item de avatar,
   catálogo por categoria nem revogação de item emprestado.
4. **Medalhas.** O tipo existe no catálogo, mas não há emissão.
5. **Fechamento de temporada.** Não há job que encerre a temporada, emita a insígnia de todos os
   elegíveis e feche a trilha.
6. **Missões e gancho de XP.** Nada chama `award_xp` em partida concluída ainda.

## Próxima fatia

**14D.9 — Missões semanais e gancho de XP:** ligar partida concluída, vitória, quadra nova e
check-in ao ledger, e criar o progresso semanal de missões.
