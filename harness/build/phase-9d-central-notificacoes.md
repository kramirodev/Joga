# Fase 9D — Central de notificações e prazos

**Status:** implementado no backend em 2026-11-14.
**Depende de:** Fase 9 (Outbox/push), 13C/14D.16 (reservas e ingressos).
**Não inclui:** provedor real de push, tela mobile ou painel de notificações, lembretes agendados de todos os timers.

## Problema

Push e WebSocket eram transporte, mas não existia histórico consultável nem
estado de leitura. O app tinha uma tela de notificações sem endpoint, e o
estabelecimento não recebia evento persistido de nova reserva.

## Decisões

1. Notificação é um registro persistido, separado de push e WebSocket.
2. Cada notificação tem chave de idempotência; repetir o evento não duplica.
3. A criação grava também um evento `notification.created` na Outbox, na mesma
   transação.
4. `GET /me/notifications` devolve histórico, contador de não lidas e paginação.
5. Marcar lida e marcar todas como lidas são escopados ao usuário.
6. O jogador só lê e altera as próprias notificações.
7. Reservas geram notificação para organização e participantes nos marcos:
   solicitação, aceite, recusa, confirmação, cancelamento e conclusão.
8. Partida formada gera notificação de confirmação com prazo.
9. Retenção inicial: 180 dias, com rotina manual `cleanup_notifications`.
10. Push real continua pendente de provedor; a Outbox já carrega o evento.

## Superfície

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/v1/me/notifications` | Histórico, `unread_count`, `unread_only`, paginação |
| GET | `/api/v1/me/notifications/unread-count` | Contador de não lidas |
| POST | `/api/v1/me/notifications/{id}/read` | Marca uma notificação como lida |
| POST | `/api/v1/me/notifications/read-all` | Marca todas como lidas |

## Modelo

Migração `d0e1f2a3b4c5`:

- `notifications` (`user_id`, `kind`, `title`, `body`, `data`, `idempotency_key`,
  `created_at`, `read_at`);
- índices por usuário/data e usuário/não lida.

## Testes

- `tests/test_notifications.py`: idempotência, Outbox, listagem, contador,
  marcação de leitura, isolamento entre usuários e gatilhos de reserva.
- `tests/test_communication_cleanup.py` ajustado para contar apenas eventos de
  teste, já que partidas agora geram notificações legítimas.

## Pendente

1. Provedor real de push e dispatcher de `notification.created`.
2. Lembretes automáticos de T1/T2/T3/T4 e check-in.
3. Consumo da central pelo app e pelo painel.
4. Preferências de notificação por tipo/canal.
5. Revisão de retenção/LGPD na Fase 19.
