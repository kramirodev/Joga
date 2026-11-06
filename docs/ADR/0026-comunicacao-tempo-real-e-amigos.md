# ADR 0026 — Comunicação em tempo real, Outbox, amigos e convites

- **Status:** Aprovado em 2026-11-06; 9A e 9B implementados.
- **Data:** 2026-11-06
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `PLANS.md` Fase 9; `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §8.2 e §20.1; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §12 e §20.3/§21; ADR 0023; `harness/build/phase-09-comunicacao-tempo-real.md`.

## Contexto

A Fase 8 concluiu o competitivo. A Fase 9 adiciona comunicação por lobby, amigos, convites e notificações. O estado oficial continua no PostgreSQL; WebSocket e push são canais de entrega, não fontes de verdade.

O projeto ainda não tem Redis configurado. O MVP roda um processo de API, mas a arquitetura não pode depender de memória para coordenar estado entre processos.

## Decisões

### Outbox e entrega

1. Toda mensagem, convite ou evento que exija entrega grava `outbox_events` na mesma transação da entidade.
2. O dispatcher pode entregar mais de uma vez; consumidores e cliente devem ser idempotentes.
3. WebSocket é best-effort e nunca prova de estado. O cliente reconcilia via API.
4. Nesta fase, o registro de conexões WebSocket é local ao processo da API. Ele serve apenas para entrega; não é fonte de verdade nem coordenação entre processos.
5. Redis fica opcional nesta fase e pode ser adicionado depois para distribuição/presença, sem alterar o contrato.
6. Push usa interface de adaptador. A Fase 9 entrega adaptador de teste/registro; provedor real exige credenciais e autorização.

### Chat

7. Chat é por lobby, texto apenas, 1–2000 caracteres, sem mídia.
8. Somente participantes autorizados leem e escrevem; autorização é revalidada no backend.
9. Mensagem é persistida no PostgreSQL antes de ser entregue.
10. Rate limit por usuário e lobby; sem chat global.

### Amigos, bloqueios e convites

11. Amizade usa par único ordenado, status `PENDING`/`ACCEPTED`/`REMOVED` e solicitante registrado.
12. Bloqueio é único por par e impede amizade, convite e entrega de eventos sociais.
13. Convite de lobby só pode ser enviado para amigo aceito, sem bloqueio, com limite por hora e sem duplicidade pendente.
14. Convite não garante vaga; aceite também respeita estado e capacidade do lobby.
15. Dados de amigos e bloqueios não são expostos a terceiros.

### WebSocket

16. Handshake exige access token válido.
17. Cada assinatura de sala valida o vínculo real do usuário com o lobby.
18. Sessão revogada/expirada encerra a conexão na revalidação/heartbeat.
19. Heartbeat e limite de conexões/mensagens protegem contra abuso.
20. Reconexão recupera o estado via API; o socket não é fonte de histórico.

### Push

21. Tokens de push são por dispositivo, únicos e revogáveis.
22. Push é usado apenas para usuários desconectados ou eventos relevantes; falha não altera estado oficial.
23. Nenhum token é exposto a outros usuários ou em logs.

### Mobile

24. A tela mobile de chat/amigos/convites não integra a 9A.
25. Para 9B, `mobile/AGENTS.md` e o escopo da fase devem ser atualizados formalmente antes do código.

## Consequências

- Novas tabelas: `outbox_events`, `friendships`, `user_blocks`, `lobby_messages`, `lobby_invites`, `device_push_tokens`.
- A API ganha WebSocket e endpoints sociais/chat.
- O sistema permanece correto se WebSocket, push ou dispatcher falharem.
- Multi-processo exigirá Redis ou outro broker na fase de hardening/escala.
- Push real fica condicionado a provedor e credenciais.

## O que este ADR não decide

- Provedor de push (FCM/APNs) e credenciais.
- Implantação de Redis e topologia de múltiplos processos.
- Chat de clã, mídia, moderação de conteúdo e retenção definitiva.
- Interface mobile de chat/amigos.
