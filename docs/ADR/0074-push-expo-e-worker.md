# ADR 0074 — Push via Expo Push Service e worker de notificações

- **Status:** Aprovado em 2026-11-23 (decisão do dono).
- **Data:** 2026-11-23
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `backend/app/modules/push/`; `backend/workers/notification_dispatch.py`;
  `backend/app/modules/notifications/dispatch.py`; ADR 0026.

## Contexto

As notificações do JOGA existiam na Outbox e na central, mas não chegavam ao
celular: não havia provedor real, nenhum worker drenava `notification.created`,
o app não registrava token e o Expo Go não recebe push remoto no Android desde o
SDK 53.

## Decisões

1. **Provedor:** Expo Push Service (`https://exp.host/--/api/v2/push/send`),
   escolhido pelo dono. O app usará Expo Push Token; o projeto EAS/FCM fica no
   app, não no backend.
2. **Sender:** `ExpoPushSender` com lote de até 100 mensagens, timeout
   configurável, `trust_env=False`, access token opcional (`JOGA_EXPO_ACCESS_TOKEN`,
   nunca logado) e códigos de erro internos. Tickets com
   `DeviceNotRegistered`/`InvalidPushToken` revogam o token.
3. **Worker separado:** `python -m workers.notification_dispatch` drena a Outbox
   em ciclo curto (`JOGA_NOTIFICATION_DISPATCH_INTERVAL_SECONDS`, default 5 s),
   com shutdown gracioso e sem entrega fingida quando o sender não existe.
4. **Outbox:** o dispatcher marca `dispatched`, `failed` ou `no_active_tokens`,
   respeita `retry_in_seconds` e não converte notificação interna de moderação
   em push do jogador.
5. **Tempo real:** o dispatcher publica `notification.created` via publisher
   injetado. Como o worker é outro processo, o `ConnectionManager` local da API
   não é alcançado; o app deve reconciliar por `GET /me/notifications` (foco,
   abertura e polling). Fan-out por Redis fica para hardening.
6. **Receipts:** o envio confirma o ticket; a consulta de receipts da Expo fica
   como próximo passo (revogação tardia e métrica de entrega).
7. **Credenciais:** `JOGA_EXPO_ACCESS_TOKEN` é opcional; projectId/FCM/EAS são
   do app. O Expo Go não serve para push remoto; é preciso development build.

## Consequências

- O backend entrega push sem depender de FCM direto.
- `deploy/start.sh` passa a subir o worker em background.
- O app (Onda 3.10) precisa registrar o token, tratar permissão, canal Android,
  foreground/background, tap com deep link e revogar no logout.
- Sem receipts e sem fan-out, a entrega é “melhor esforço”; a central do app não
  deve depender de WS para atualizar.
