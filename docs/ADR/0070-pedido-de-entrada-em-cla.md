# ADR 0070 — Pedido de entrada em clã: idempotência, rastreio e decisão

- **Status:** Aprovado em 2026-11-23 (decisão do dono).
- **Data:** 2026-11-23
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0061 (edição de clã e convites); `backend/app/modules/clans/`;
  `docs/JOGA_DOCUMENTACAO_TECNICA.md` §20.3.

## Contexto

O índice único parcial já impedia duas linhas `pending` para o mesmo par
(clã, jogador), mas a API não expunha o estado do pedido. A tela voltava ao
formulário após refresh, o jogador reenviava, o dono não via o pedido no app e
ninguém era notificado. Dois `POST /join` concorrentes podiam retornar 500 por
`IntegrityError`. A nota do admin era gravada no campo `message` do solicitante.

## Decisões

1. **Pedido idempotente:** repetir `POST /clans/{id}/join` com pedido `pending`
   devolve o **mesmo** pedido (mesmo `id`), sem criar linha, sem duplicar
   notificação e sem 500. Corrida de `INSERT` é relida e devolvida.
2. **Estado visível:** `ClanSummaryView` ganha `my_request`
   (`id`, `status`, `created_at`, `decision_note`) no detalhe e na lista; a lista
   usa uma consulta em lote, sem N+1.
3. **Rastreio do jogador:** `GET /me/clan-requests?status=pending|history`
   devolve clã, status, mensagem, nota da decisão, criação e decisão.
4. **Rastreio do dono/admin:** `GET /clans/{id}/requests?status=pending|history`
   mantém a autorização de admin e passa a devolver `decided_at`, `decided_by` e
   `decision_note`.
5. **Nota separada:** `decision_note` é coluna própria (até 200 caracteres);
   nunca sobrescreve a mensagem escrita pelo jogador.
6. **Decisão única:** decidir um pedido que não está `pending` devolve 409
   `request_not_pending`; não há 200 silencioso.
7. **Cancelamento:** `DELETE /clans/{id}/requests/{request_id}` permite ao autor
   cancelar o próprio pedido `pending`. Terceiros recebem 404; o instante e o
   autor ficam em `decided_at`/`decided_by` para auditoria.
8. **Notificações:** novo pedido avisa owner/admin ativos (exceto o solicitante);
   a decisão avisa o solicitante; aceite/recusa de convite avisa o convidante.
   A chave de idempotência inclui o destinatário.
9. **Sem autoaceite:** clã com aprovação continua exigindo decisão humana; clã
   aberto continua entrando direto, como antes.
10. **Histórico:** o índice único parcial só cobre `pending`; pedidos
    `cancelled`/`rejected`/`approved` permanecem como histórico auditável.

## Consequências

- Migração `9d3e4f5a6b7c`: `decision_note` e índice
  `(user_id, status, created_at)`.
- O app mobile precisa consumir `my_request`, `GET /me/clan-requests`, a lista
  de pedidos do dono e o cancelamento; o painel web pode usar a mesma lista.
- O pedido de entrada e o convite de clã continuam fluxos distintos: convite é
  iniciado pelo clã; pedido é iniciado pelo jogador.
