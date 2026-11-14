# Fase 16 — Clãs, troféus e moderação mínima

**Status:** implementado no backend em 2026-11-13.
**Depende de:** Fase 8 (competitivo), 14D.14 (temporada), 14D.12 (passe).
**Não inclui:** UI mobile, moderação completa da Fase 17 e painel administrativo.

## Decisões aprovadas

1. Até **30 membros** por clã.
2. Entrada por **aprovação** (padrão), com `open` e `closed` disponíveis.
3. **Um clã ativo por jogador**; troca livre com **carência de 7 dias**.
4. Troféus na **mesma temporada trimestral**, por formato.
5. **50/30/20** = vitória/empate/derrota, com **10 melhores membros** e
   **7 dias de permanência**.
6. Denúncia **oculta imediatamente**; admin mantém oculta ou restaura.

## Modelo

- `clans`: nome, tag, descrição, política de entrada e status.
- `clan_members`: papel (`owner`, `admin`, `member`), status e datas; índice
  único parcial garante um clã ativo por jogador.
- `clan_join_requests`: pedido pendente único por clã e jogador.
- `clan_trophy_events`: evento append-only por partida e jogador, com
  `unique(match_id, user_id)`.
- `clan_trophy_snapshots`: fechamento por clã, temporada e formato.
- `clan_messages` e `clan_reports`: chat com ocultação e revisão auditável.

Migração `b7d4f1a9c620`, aplicada em upgrade → downgrade → upgrade;
`alembic check` limpo.

## Superfície

| Método | Rota | Efeito |
|---|---|---|
| POST | `/clans` | Cria clã e torna o autor dono |
| GET | `/clans` | Descoberta com busca por nome/tag |
| GET | `/clans/ranking` | Ranking por temporada e formato |
| GET | `/me/clan` | Clã do jogador |
| GET | `/clans/{id}` | Perfil do clã e troféus |
| POST | `/clans/{id}/join` | Pedido de entrada ou entrada direta |
| GET | `/clans/{id}/requests` | Fila de pedidos (admin) |
| POST | `/clans/{id}/requests/{rid}/decide` | Aprova ou rejeita |
| GET | `/clans/{id}/members` | Membros ativos |
| DELETE | `/clans/{id}/members/{uid}` | Remove membro (admin) |
| POST | `/clans/{id}/members/{uid}/role` | Promove/rebaixa (dono) |
| POST | `/clans/{id}/transfer` | Transfere a posse |
| POST | `/clans/{id}/leave` | Sai (dono precisa transferir) |
| GET/POST | `/clans/{id}/messages` | Chat só para membros |
| POST | `/clans/{id}/messages/{mid}/report` | Denúncia + ocultação imediata |
| GET | `/clans/{id}/reports` | Fila de revisão (admin) |
| POST | `/clans/{id}/reports/{rid}/decide` | Mantém oculta ou restaura |

## Troféus

- Ponto por partida finalizada: vitória 50, empate 30, derrota 20.
- Só quem está no clã há pelo menos 7 dias na data da partida.
- A soma do clã usa os 10 melhores membros da temporada/formato.
- O fechamento grava `clan_trophy_snapshots` (idempotente) via
  `scripts.close_seasons`.
- Troca de clã não leva troféus; nada é comprado ou transferido.

## Testes

`tests/test_clans.py`: criação e dono único, aprovação, carência de 7 dias,
dono precisa transferir, chat só para membros, denúncia oculta e restauração,
revisão restrita a admin, troféus idempotentes, top-10, snapshot e permanência
mínima.

## Pendente

1. Consequência para denúncia falsa e limite por jogador (Fase 17).
2. UI mobile de clã, chat, troféus e moderação.
3. Escudo/cores do clã e catálogo cosmético.
4. Destino do clã quando o dono exclui a conta.
5. Calibrar a fórmula e a permanência mínima com dados do piloto.
