# ADR 0069 — Ciclo completo de pedidos de amizade

- **Status:** Aprovado em 2026-11-23 (decisão do dono).
- **Data:** 2026-11-23
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0026 (comunicação em tempo real, amigos e convites);
  `backend/app/modules/social/`; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §12/§20.3.

## Contexto

O modelo de amizade existia apenas como par único com `PENDING`, `ACCEPTED` e
`REMOVED`. Faltava o ciclo de vida do pedido: o destinatário não tinha como
listar pedidos recebidos, descobrir o `request_id` para aceitar, recusar ou
cancelar; o remetente não via os enviados; dois envios concorrentes podiam
retornar 500; e nenhum dos eventos gerava notificação. Na prática, o sistema
era inutilizável de ponta a ponta.

## Decisões

1. **Estados:** `PENDING`, `ACCEPTED`, `DECLINED`, `CANCELLED`, `REMOVED`.
   `REMOVED` continua sendo o desfazer de amizade; `DECLINED` e `CANCELLED`
   distinguem recusa de cancelamento. O status é sempre validado no servidor.
2. **Um par, um registro:** o par ordenado continua único
   (`uq_friendship_pair`). Reabrir um pedido recusado/cancelado reutiliza a
   mesma linha, com `requested_by` atual, `responded_at = NULL` e
   `created_at` renovado para refletir o novo pedido.
3. **Solicitante é participante:** `requested_by` precisa ser `user_low_id` ou
   `user_high_id` (check no banco).
4. **Resposta:** `responded_at` registra o instante de aceite, recusa ou
   cancelamento.
5. **Listagem:** `GET /api/v1/friends/requests` aceita
   `direction=incoming|outgoing|all` e `status=pending|history`, sempre
   restrita ao usuário autenticado.
6. **Recusa e cancelamento:** `POST /friends/requests/{id}/decline` é exclusivo
   do destinatário; `DELETE /friends/requests/{id}` é exclusivo do autor.
   Ambos exigem `PENDING` e devolvem 404 para não participante ou estado
   inválido, sem revelar a existência do recurso.
7. **Envio idempotente:** reenviar o mesmo pedido pendente devolve 201 com o
   mesmo `id` e não cria notificação nova. Pedido pendente na direção oposta
   devolve 409 `incoming_friend_request` com `request_id` para o app oferecer
   o aceite.
8. **Concorrência:** o `INSERT` roda em savepoint; violação de unicidade é
   relida com `FOR UPDATE` e convertida em resposta idempotente, nunca em 500.
9. **Anti-spam:** criação e reabertura consomem um limite de 20 pedidos por
   hora por autor. Reenvio idempotente não consome.
10. **Notificações:** `friend_request_received`, `friend_accepted`,
    `friend_declined` e `friend_cancelled`, com `friendship_id` e
    `counterpart_id` em `data`. A chave de idempotência inclui o destinatário,
    porque a central procura a chave globalmente.
11. **Bloqueios:** `GET /friends/blocks` lista apenas os bloqueios feitos pelo
    próprio usuário.

## Consequências

- Migração `8b2c3d4e5f60` amplia o check de status, adiciona `responded_at`,
  o check de participante e índices para listagens.
- O ADR 0026 item 11 passa a apontar para este ADR.
- A busca de jogador por `nome#tag` continua fora deste escopo; sem ela, o app
  só consegue enviar pedido a partir de um `user_id` já conhecido (membro de
  clã, participante de partida/lobby). O contrato de busca é a próxima etapa.
- O histórico é por par: ao reabrir, o estado anterior deixa de existir na
  linha; o rastro fica na central de notificações/outbox.
