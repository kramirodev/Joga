# Especificação as-built — Temporada, trilha, XP, passe e catálogo cosmético

**Versão:** 1.1<br>
**Data:** 16 de novembro de 2026<br>
**Status:** implementado no backend pelas fatias 14D.7–14D.16; a camada de conta/preço será realinhada pela Fase 14E (ADR 0049).<br>
**Base:** ADR 0043, ADR 0045, ADR 0046 e ADR 0049.

> Este documento substitui a especificação de implementação futura. Ele descreve o **as-built** e as pendências. A fonte do schema é `docs/DATA_MODEL.md`; a fonte da verdade é o código e as migrations.

---

## 1. Unidade e regras de crédito

- A substância jurídica e contábil é **crédito de consumo expresso em reais**, 1:1.
- O **ticket** é a unidade de exibição do crédito; não é moeda, não é unidade de conta e não tem efeito jurídico/contábil/fiscal autônomo.
- O saldo em reais não é exibido como carteira. O valor do espaço, a taxa e a tabela de conversão tickets ↔ faixa/valor aparecem antes da confirmação; a NFS-e materializa o valor.
- Crédito comprado **não expira**.
- A franquia mensal do passe é uma cota de assinatura: **não se acumula**, não se converte em saldo e tem período mensal.
- Tickets gratuitos de nível são promoção e **expiram com a temporada**.
- Não há transferência, revenda, saque ou troca de crédito.

## 2. Tabelas implementadas

| Tabela | Papel |
|---|---|
| `ticket_packs` | Escada de pacotes e preço de exibição |
| `ticket_purchases` | Compra de pacote, valor, status e referência |
| `ticket_lots` | Lote de origem, saldo projetado, preço unitário, período |
| `ticket_lot_consumptions` | Consumo por lote e referência |
| `ticket_balances` | Projeção de saldo |
| `pass_subscriptions` | Assinatura trimestral, status e período |
| `pass_deliveries` | Entrega mensal idempotente |
| `seasons` | Temporada trimestral |
| `season_progress` | Nível, XP e progresso |
| `xp_events` | Ledger append-only de XP |
| `win_streaks` | Sequência de vitórias por semana |
| `season_items` | Itens de trilha e catálogo |
| `season_track_levels` | Níveis e item associado |
| `season_claims` | Resgates |
| `badges` / `player_badges` | Insígnias |
| `player_items` | Itens possuídos/equipados |
| `mission_progress` | Missões semanais |
| `season_placements` | Divisão/posição no fechamento |

**Não existem** com os nomes da especificação antiga: `pass_plans`, `pass_cycles`, `pass_allowances`, `cosmetic_items`, `player_cosmetics`, `player_loadout`, `mission_definitions`. O as-built usa `season_items`, `season_claims`, `player_items`, `player_badges`, `pass_deliveries`.

## 3. Endpoints reais

- `GET /api/v1/me/progress`
- `GET /api/v1/me/progress/track`
- `POST /api/v1/me/progress/track/{level}/claim`
- `GET /api/v1/me/progress/badges`
- `PUT /api/v1/me/progress/badges/equip`
- `GET /api/v1/me/progress/missions`
- `GET /api/v1/me/pass`
- `GET /api/v1/me/pass/plans`
- `POST /api/v1/me/pass/subscriptions`
- `GET /api/v1/me/pass/subscriptions/{id}`
- `POST /api/v1/me/pass/subscriptions/{id}/sync`
- `DELETE /api/v1/me/pass/subscriptions/{id}`
- `GET /api/v1/me/tickets`
- `GET /api/v1/me/tickets/packs`
- `POST /api/v1/me/tickets/purchases`
- `GET /api/v1/me/tickets/purchases/{id}`
- `POST /api/v1/me/tickets/purchases/{id}/sync`

**Não existem:** `/seasons/current`, `/me/track`, `/me/missions`, `/me/streak`, `/me/cosmetics`, `/me/loadout`, `/me/pass/checkout`.

## 4. Temporada e progressão

- Temporada trimestral; fechamento cria a próxima, semeia a trilha e registra `season_placements`.
- Divisão competitiva tem reset suave; o rating interno persiste. Nível de temporada (bronze/prata/ouro) reseta.
- Trilha de 30 níveis; itens em três estados (livre, XP, passe).
- XP de partida e de vitória; streak semanal; missões semanais.
- XP é append-only e idempotente por `ref_id`.
- Item de passe deve ser revogado ao fim do ciclo; hoje a revogação não existe.
- Itens de temporada são globais por `code`, não por temporada; isso impede recompensa por temporada e precisa ser corrigido.
- Fronteira de temporada/semana usa UTC; no Brasil vira às 21h. Corrigir para o fuso local é pendência.

## 5. Passe

- Assinatura trimestral com cobrança única e entrega mensal de 10/20/30/50 tickets de exibição.
- A franquia não acumula e não se converte em saldo.
- Passe fica fora do escrow (ADR 0049 §2.6).
- Venda no meio da temporada: três meses a partir do pagamento; restrição de janela/pro-rata ainda não decidida.
- Reembolso de passe/pacote não implementado; política pendente.
- Itens de passe e badges: atribuição implementada; revogação/equipamento completo pendente.

## 6. Estatísticas e rede (ADR 0045)

- Estatísticas essenciais: divisão/progresso, partidas, V/E/D, presença, streak e sequência de temporadas.
- Estatísticas do passe: evolução, histórico por quadra, passaporte, horários, retrospectiva.
- Inteligência de rede: quadras mais usadas, horários e densidade competitiva, em faixas, com amostra mínima de 20 partidas/30 dias e atualização diária.
- MMR bruto nunca é exposto; a leitura pública é divisão/progresso.
- Camada visual móvel parcial; evolução, retrospectiva e horários ainda não têm tela completa.

## 7. Pendências da 14E/14D

1. Integrar o ledger em reais; `ticket_lots` passa a ser registro de origem, não saldo.
2. Persistir preço do espaço, taxa, percentual e total na reserva.
3. Converter lotes existentes pelo preço unitário pago, 1:1, com idempotência.
4. Remover expiração de crédito comprado; manter período do passe e expiração de tickets gratuitos.
5. Corrigir unicidade de item por temporada e revogação ao fim do ciclo.
6. Implementar reembolso de pacote/passe.
7. Completar UI de inventário, loadout, retrospectiva e horários.
8. Corrigir fronteira de temporada para fuso local.
