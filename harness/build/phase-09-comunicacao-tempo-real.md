# Fase 09 — Comunicação em tempo real

**Status:** Fase 9 encerrada em 2026-11-06 (9A backend, 9B mobile e 9C retenção/WebSocket mobile)
**Branch:** `feat/09-comunicacao-tempo-real`
**Decisão:** `docs/ADR/0026-comunicacao-tempo-real-e-amigos.md`

## Objetivo

Adicionar comunicação autorizada e resiliente ao núcleo esportivo: chat por lobby, lista de amigos, convites, bloqueios, Outbox transacional e entrega em tempo real por WebSocket, com push por adaptador e sem tornar conexão ou notificação fonte de verdade.

## Escopo

- WebSocket autenticado no handshake e autorizado por sala.
- Chat textual por lobby, persistido no PostgreSQL antes da entrega.
- Outbox transacional para eventos de chat, convites e mudanças relevantes.
- Lista de amigos: solicitar, aceitar, remover e bloquear.
- Convites de lobby sujeitos a amizade, bloqueio e limite de frequência.
- Tokens de push por dispositivo, com adaptador substituível e adaptador de teste.
- Reconciliação: reconexão recupera estado/histórico via API.
- Limites de tamanho, taxa e autorização.

## Não fazer

- Chat global universal, upload de mídia ou anexos.
- Conexão em memória como fonte de estado ou coordenação entre processos.
- Confiar em evento WebSocket/push como prova de estado.
- Push real sem provedor e credenciais autorizados.
- Redis obrigatório nesta fase; ele pode entrar depois para distribuição/presença.
- Telas mobile de chat/amigos antes de atualizar `mobile/AGENTS.md`.

## Blocos de entrega

### 9A — Backend

- Migração: `outbox_events`, `friendships`, `user_blocks`, `lobby_messages`, `lobby_invites`, `device_push_tokens`.
- Serviços de amigos, bloqueios, chat, convites e Outbox.
- Endpoint WebSocket `/api/v1/ws` com autenticação por header e assinatura de salas.
- APIs HTTP de chat, amigos, convites e tokens de push.
- Dispatcher de Outbox no processo da API e worker de push separado.
- Testes unitários, HTTP, WebSocket e PostgreSQL.

### 9B — Mobile (pendente de autorização)

- Tela de chat do lobby, lista de amigos e convites.
- Atualização de `mobile/AGENTS.md` e do escopo da fase antes do código.
- Sem exposição de dados de outros usuários fora das relações autorizadas.

## Modelo de dados

### `outbox_events`

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `event_type` | varchar(60) | ex.: `lobby.message.created` |
| `aggregate_type` / `aggregate_id` | varchar/varchar | referência lógica |
| `payload` | JSONB | dados mínimos do evento |
| `status` | varchar(20) | `PENDING`, `DISPATCHED`, `FAILED` |
| `attempts` | integer | default 0 |
| `available_at` | timestamptz | retry/agendamento |
| `created_at` / `dispatched_at` | timestamptz | auditoria |

Índice por `status`/`available_at`; eventos são append-only, exceto o estado de dispatch.

### `friendships`

Par único ordenado (`user_low_id`, `user_high_id`), status `PENDING`/`ACCEPTED`/`REMOVED`, solicitante (`requested_by`), timestamps. Unique por par.

### `user_blocks`

`blocker_id`, `blocked_id`, `created_at`; unique por par. Bloqueio impede convites e amizade.

### `lobby_messages`

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `lobby_id` | UUID | FK `lobbies.id` |
| `sender_id` | UUID | FK `users.id` |
| `body` | varchar(2000) | texto, sem mídia |
| `created_at` | timestamptz | default `now()` |

Índice por `lobby_id`/`created_at`; append-only.

### `lobby_invites`

`lobby_id`, `inviter_id`, `invitee_id`, status `PENDING`/`ACCEPTED`/`DECLINED`/`EXPIRED`/`CANCELLED`, `created_at`, `expires_at`, `responded_at`; unique por lobby/convite pendente.

### `device_push_tokens`

`user_id`, `token` (único), `platform`, `created_at`, `last_seen_at`, `revoked_at`. O token nunca é exposto a outros usuários.

## Contratos

### WebSocket

`GET /api/v1/ws` com `Authorization: Bearer <access_token>`.

- Handshake valida sessão ativa.
- Cliente envia `{"type":"subscribe","lobby_id":"..."}` e `{"type":"unsubscribe",...}`.
- Servidor valida vínculo real com o lobby em cada assinatura.
- Envia `{"type":"lobby.message.created","data":{...}}`.
- Heartbeat/ping; conexão encerrada se a sessão expirar/for revogada.
- Reconexão não recupera estado via socket; o cliente busca histórico HTTP.

### HTTP

- `GET /api/v1/lobbies/{lobby_id}/messages?before=...&limit=...`
- `POST /api/v1/lobbies/{lobby_id}/messages` (Idempotency-Key; corpo 1–2000)
- `GET /api/v1/friends`
- `POST /api/v1/friends/requests` (`user_id`)
- `POST /api/v1/friends/requests/{id}/accept`
- `DELETE /api/v1/friends/{user_id}`
- `POST /api/v1/blocks` (`user_id`)
- `DELETE /api/v1/blocks/{user_id}`
- `POST /api/v1/lobbies/{lobby_id}/invites` (`user_id`)
- `POST /api/v1/lobby-invites/{id}/accept|decline`
- `PUT /api/v1/push-tokens` (`token`, `platform`)
- `DELETE /api/v1/push-tokens/{token}`

## Regras

- Só participantes do lobby leem/escrevem chat.
- Convite só para amigo aceito, sem bloqueio, com limite por hora e sem duplicidade.
- Chat: 1–2000 caracteres, sem mídia; rate limit por usuário/lobby.
- Evento de chat é gravado na mesma transação da mensagem; a entrega é best-effort.
- Falha de WebSocket/push não altera mensagem, convite, partida ou resultado.
- Push só para usuários desconectados; sem provider real nesta fase.
- Sessão revogada perde WebSocket na próxima verificação/heartbeat.
- Dados de amigos/bloqueios não são visíveis para terceiros.

## Critérios de aceite

- [x] WebSocket autenticado, autorizado por lobby e encerrado em sessão inválida.
- [x] Chat persistido antes da entrega; reconnect recupera via API.
- [x] Evento duplicado não duplica mensagem/efeito.
- [x] Amizade e convite respeitam bloqueio, privacidade e limite.
- [x] Falha de push/socket não corrompe estado oficial.
- [x] Outbox transacional e dispatcher idempotente.
- [x] Testes negativos de autorização e concorrência.
- [x] Documentação, migração e build-log atualizados.
- [x] Mobile (9B) com chat, amigos, convites e estados de erro/carregamento.

## Condição de parada

Encerrar 9A com backend estável; não iniciar 9B sem autorização específica. Não iniciar Fase 10 automaticamente.

## Implementação 9A

- **Migração:** `b4e8d1f6c752_add_social_chat_outbox.py`, com `outbox_events`, `friendships`, `user_blocks`, `lobby_messages`, `lobby_invites` e `device_push_tokens`.
- **Chat:** `app/modules/chat/`, endpoints `GET/POST /api/v1/lobbies/{id}/messages`, persistência antes da entrega, histórico paginado e idempotência.
- **Amigos/bloqueios/convites:** `app/modules/social/`, endpoints de solicitação, aceite, remoção, bloqueio, convite de lobby e resposta.
- **Outbox:** `app/modules/outbox/`, gravação transacional e dispatcher interno; entrega WebSocket é best-effort e o histórico permanece na API.
- **WebSocket:** `GET /api/v1/ws`, autenticação por `Authorization`, assinatura de lobby autorizada e heartbeat.
- **Push:** `app/modules/push/` com tokens por dispositivo, adaptador de teste e interface de envio; nenhum provedor real configurado.
- **Testes:** 25 novos testes de chat, social, push, Outbox e WebSocket. Sem PostgreSQL: **281 passed, 23 skipped**; com `JOGA_TEST_DATABASE_URL`: **304 passed**. `ruff`, `ruff format`, `mypy` e `alembic check` passam.
- **Limite:** WebSocket entrega apenas conexões do processo atual; Redis e fan-out multi-processo ficam para a fase de hardening/escala. Push real depende de provedor e credenciais.

## Implementação 9B

- **Mobile:** `mobile/src/CommunicationPanel.tsx`, integrado ao `App.tsx`.
- **Chat:** seleção de partida/lobby, histórico, envio idempotente e atualização manual.
- **Amigos:** lista, solicitação a partir dos participantes da partida e convite para o lobby selecionado.
- **Convites:** lista de pendentes e ações de aceitar/recusar.
- **Governança:** `mobile/AGENTS.md` atualizado para autorizar as telas da Fase 9B.
- **Validação:** `pnpm run typecheck`, `pnpm run lint`, `pnpm run format:check` e `expo install --check` passam. O backend ganhou `lobby_id` no resumo de partida para permitir o chat.
- **Limite:** o app usa atualização manual/HTTP; a conexão WebSocket nativa no mobile ainda não foi integrada e não há teste automatizado de UI.

## Implementação 9C

- **WebSocket mobile:** `CommunicationPanel` abre `ws://.../api/v1/ws` com `Authorization`, assina o lobby selecionado, faz merge idempotente das mensagens recebidas e tenta reconectar após queda.
- **Retenção:** ADR 0027 e `scripts/cleanup_communication.py`; mensagens 730 dias, convites 90 dias, Outbox 30 dias e tokens de push revogados 90 dias, com `--dry-run`.
- **Testes:** limpeza de comunicação coberta em `test_communication_cleanup.py`; WebSocket mobile validado por `typecheck`/`lint` e smoke HTTP no aparelho.
- **Limite:** o teste visual do WebSocket no aparelho depende de sessão válida e backend ativo; não há teste automatizado de UI.
