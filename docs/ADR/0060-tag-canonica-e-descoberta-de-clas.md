# ADR 0060 — Tag canônica de clã e filtros de descoberta

- **Status:** Aprovado em 2026-11-20.
- **Data:** 2026-11-20
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_TECNICA.md` §12.6,
  `backend/app/api/v1/clans.py`, `backend/app/modules/clans/service.py`,
  `backend/app/modules/clans/models.py` e
  `backend/migrations/versions/3b25be23dfba_canonical_clan_tags.py`.

## Contexto

O dono criou um clã com a tag `6666`, sem `#`. A API apenas aplicava
`strip().upper()` e aceitava de 2 a 8 caracteres, então a tag era gravada sem o
`#` que o produto usa para identificar clãs. A mesma tela de descoberta oferecia
"Entrar/Solicitar" no próprio clã do jogador, embora a API já rejeitasse o
pedido; a listagem não dizia à UI qual é o papel do jogador nem aceitava os
filtros "Aberto" e "Com vaga". A transferência de posse rebaixava o antigo dono
para `admin`, não para `member`, e não registrava auditoria.

## Decisão

1. **Tag canônica.** A tag do clã é sempre `#` + miolo, com miolo em
   `[A-Z0-9]{2,7}` (total de 3 a 8 caracteres). A API aceita `6666`, `#6666` e
   espaços nas bordas; normaliza para `#6666`. Miolo inválido responde
   `tag_invalid`; colisão após normalização responde `tag_taken` (ou
   `name_or_tag_taken` na corrida de unicidade).
2. **Banco.** `clans.tag` continua em `String(8)` e a constraint
   `tag_length_valid` passa a exigir prefixo `#` e comprimento de 3 a 8. O
   miolo é validado no serviço, porque a regra `[A-Z0-9]` não é portável entre
   PostgreSQL e SQLite.
3. **Migração.** A revisão `3b25be23dfba` reescreve as tags existentes de forma
   determinística e idempotente: limpa caracteres fora de `[A-Z0-9]`, corta o
   miolo em 7, prefixa `#` e, em caso de colisão, acrescenta sufixo numérico
   registrado no log. As trocas usam valores temporários para não violar a
   constraint única no meio do processo. O downgrade remove o `#` e restaura a
   constraint antiga, também resolvendo colisões.
4. **Descoberta.** `GET /api/v1/clans` aceita `open=true|false` (política
   `open`), `has_slots=true|false` (membros ativos abaixo de `MAX_MEMBERS`) e
   mantém `q` (nome ou tag, aceitando a busca com ou sem `#`). A resposta
   `ClanSummaryView` expõe `my_role` (`owner|admin|member|null`) e
   `is_member`, além dos campos existentes.
5. **Clã próprio.** `POST /clans/{id}/join` responde `already_member` quando o
   jogador já é membro ativo daquele clã, inclusive em clã fechado.
6. **Transferência.** Somente o `owner` atual transfere. O alvo precisa ser
   membro ativo; o autor vira `member`, o alvo vira `owner`, ambos travados com
   `FOR UPDATE` na mesma transação, e a ação é registrada em `audit_log` como
   `clan.ownership_transferred`. Transferir para si responde `already_owner`.
7. **Contagem.** `members` em `ClanSummaryView` conta apenas
   `clan_members.status = 'active'`; pedidos pendentes e membros que saíram não
   entram.

## Pendência deliberada: filtro por esporte

O modelo `Clan` não tem vínculo com esporte ou formato: a modalidade aparece só
nos eventos de troféu (`ClanTrophyEvent.format_id`). Criar um filtro de esporte
exigiria decidir e migrar um campo de esporte do clã, o que não foi feito nesta
entrega. O app não deve enviar esse parâmetro até a decisão de produto/modelo.

## Consequências

- O app pode exibir a tag já com `#` e enviar o que o jogador digitar; o backend
  devolve a forma canônica.
- A tela Descobrir deve usar `my_role`/`is_member` para esconder "Entrar" no
  próprio clã e usar `open`/`has_slots` como filtros reais.
- Bancos existentes têm as tags normalizadas no deploy da migração; eventuais
  colisões são resolvidas por sufixo e ficam no log do Alembic.
