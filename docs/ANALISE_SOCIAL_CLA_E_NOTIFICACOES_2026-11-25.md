# 1A0 — Diagnóstico do sistema de amizade, clã e notificações (app mobile)

**Base analisada:** `dda0a09` (main)
**Modo:** somente leitura — nenhum código de `mobile/` ou `backend/` foi alterado.
**Data:** 2026-11-25

> **Uso:** este é o diagnóstico 1A.0 pedido pelo dono antes da implementação.
> Ele fixa o mapa tela → endpoint → causa, a tabela `kind → tela` das
> notificações e a divisão backend (1A) × mobile (1B). A implementação pode
> divergir em detalhe visual, mas não em contrato sem nova decisão.

---

## 0. Resumo executivo

O **backend já implementa quase todo o fluxo** (busca por nome/tag, ciclo completo de pedido de amizade, pedido de entrada em clã com decisão, convites de clã, notificações persistidas). O problema é de **consumo no app**: metade das telas sociais é mock ou estado local, e os endpoints prontos não são chamados.

Cinco causas raiz explicam praticamente todas as reclamações:

1. `AddFriend` é **100% mock** — não há chamada de busca nem de envio de pedido (`mobile/src/screens/social.tsx:334-371`). O cliente nem tem `users.search` (`mobile/src/api/client.ts:1093-1145`).
2. `Friends` carrega **apenas** `/friends` + `/lobby-invites` (`mobile/src/state/app.tsx:674-684`); pedidos recebidos/enviados nunca são buscados. As abas "Solicitações" e "Bloqueados" são textos fixos (`mobile/src/screens/social.tsx:315-319`).
3. Pedido de clã tem estado **local** (`mobile/src/screens/social.tsx:1063,1141,1268-1288`), ignorando o `my_request` que o servidor já devolve (`backend/app/api/v1/clans.py:71-91,272`). Ao remontar a tela, o estado "Enviado" desaparece.
4. Dono/admin **não tem tela de pedidos**: `ClanProfile` só linka membros e configurações (`mobile/src/screens/social.tsx:520-546`), e `api.clans.requests`/`decideRequest` existem no cliente mas **nunca são chamados** (`mobile/src/api/client.ts:1245-1255`).
5. `Notifications.open()` só mapeia booking, moderação, resultado, clã (genérico), convite de lobby e partida (`mobile/src/screens/social.tsx:3580-3621`): `friend_*` não faz nada e convite de clã **retorna sem navegar** (`social.tsx:3601-3603`); o payload não carrega deep link (`backend/app/api/v1/notifications.py:24-31`).

Além disso: o perfil monta uma **tag falsa** a partir do UUID (`mobile/src/screens/core.tsx:1358`) porque o tipo `Profile` não declara `tag`, embora `/me/profile` a devolva (`backend/app/api/v1/profile.py:94-97`, `mobile/src/api/types.ts:69-76`); e o clã do perfil só aparece após abrir a aba de clã, porque `refreshCore` não carrega clã (`mobile/src/state/app.tsx:929-942`).

**Conclusão de esforço:** ~80% do trabalho é mobile consumindo contratos existentes; ~20% é backend adicionando campos pequenos (`tag` em 4 views, ids/nomes no `data` de notificações, opcionalmente um `GET /users/{id}`) e documentando o mapa de deep link.

---

## 1. Mapa tela → endpoint → estado

Legenda: **MOCK** = dado inventado na tela; **LOCAL** = estado React que morre ao remontar; **ÓRFÃO** = endpoint/cliente pronto e não usado; **FALTA** = nem endpoint consumido nem UI.

| Tela (`mobile/src/screens/social.tsx`) | Fonte de dados hoje | Endpoint existente e não consumido | Diagnóstico |
|---|---|---|---|
| `Friends` (`:187-332`) | `loadSocial()` → `/friends` e `/lobby-invites` (`mobile/src/state/app.tsx:674-684`); lista sem tag (`social.tsx:218-223`) | `GET /friends/requests?direction=incoming\|outgoing&status=pending` (`backend/app/api/v1/social.py:206-218`); `GET /blocks` (`social.py:302-310`) | **LOCAL/FALTA**: abas "Solicitações" e "Bloqueados" são `Notice` fixo (`social.tsx:315-319`); `invites` do contexto nem é lido (`social.tsx:190`) |
| `AddFriend` (`:334-371`) | `useState` apenas; "buscar" só liga `searched` (`:337-344`) e a tela sempre responde "Nenhum jogador encontrado" (`:360-363`) | `GET /users/search?q=` com `tag` e `relation` (`backend/app/api/v1/users.py:42-81`); `POST /friends/requests` (`social.py:221-239`) | **MOCK**. Não há `api.users.search` nem `requestFriend` chamado (`mobile/src/api/client.ts:1093-1145`; grep sem uso de `requestFriend`) |
| `ClanDiscovery` (`:570-877`) | `GET /clans` real (`:606-629`) | `my_request` já vem em cada card (`backend/app/api/v1/clans.py:91,272,479-491`) | **PARCIAL**: card ignora `my_request` e mostra "Solicitar" de novo (`social.tsx:783-808`); tipo `Clan` não declara `my_request` (`mobile/src/api/types.ts:698-709`) |
| `ClanJoin` (`:1050-1394`) | `GET /clans/{id}` real (`:1083-1110`), mas estado "pendente" local (`:1063,1141`) | `my_request` no detalhe (`backend/app/api/v1/clans.py:562-568`); `GET /me/clan-requests` (`clans.py:538-548`) | **LOCAL**: refresh/remontagem perde "Solicitação enviada" (`social.tsx:1268-1288`) e permite reenviar |
| `ClanProfile` (`:373-552`) | `loadClan()` (`mobile/src/state/app.tsx:686-703`) | `GET /clans/{id}/requests` (admin) (`backend/app/api/v1/clans.py:594-610`) | **FALTA** link/contador de pedidos para dono/admin (`social.tsx:520-546`) |
| `ClanMembers` (`:1414-1738`) | `loadClan()` (`:1444-1474`), papéis reais | `requests`/`decide` no cliente (`mobile/src/api/client.ts:1245-1255`) | **ÓRFÃO**: só convida (`social.tsx:1725-1729`), não decide pedidos |
| `ClanSettings` (`:1818-2296`) | `PATCH /clans/{id}` real | — | OK para edição; sem pedidos |
| `ClanInvite` (convites enviados, `:4524-4914`) | `friends` + `POST /clans/{id}/invites`; lista `pending` **local** (`:4535,4609-4617`) | Nenhum `GET` de convites enviados (não existe no backend) | **LOCAL**: após refresh, "Convidar" volta e o 2º envio bate em `already_invited` (`backend/app/modules/clans/service.py:729-732`) |
| `Notifications` (`:3349-3836`) | `GET /me/notifications` + `GET /me/clan-invites` (`social.tsx:3382-3420`) | `friend_*` e `clan_join_*` no feed (`backend/app/modules/social/service.py:826-867`, `clans/service.py:351-398`); `GET /friends/requests` e `GET /clans/{id}/requests` | **PARCIAL**: convites de clã funcionam (`social.tsx:3692-3753`), mas notificações de amizade/pedido não têm ação; sem pull-to-refresh (só `ClanChat` usa `RefreshControl`, `social.tsx:2950`) |
| `ProfileMe` (`mobile/src/screens/core.tsx:1303-1650`) | `profile`, `clan` do contexto (`:1306-1319`) | `GET /me/profile` devolve `tag` (`backend/app/api/v1/profile.py:94-97,349`) | **MOCK parcial**: tag = 4 primeiros hex do UUID (`core.tsx:1358`); não chama `loadClan` → "Sem clã" até abrir a aba (`core.tsx:1336`) |
| `ProfileOther` (`core.tsx:1653-1759`) | Só `nav.params.name/userId` (`:1657-1659`) | Não existe `GET /users/{id}` (só `/users/search`, `backend/app/api/v1/users.py:42`) | **MOCK**: tag falsa (`core.tsx:1659`), divisão/nível/partidas fixos (`:1684-1718`) |
| `LobbyInvite` (`core.tsx:921-1028`) | `friends` real, mas `tag: ''` (`:938`) | `Friend.tag` não existe (`backend/app/api/v1/social.py:42-48`) | **PARCIAL**: funciona, sem tag |
| `BlockUser` (`social.tsx:4488-4515`) | Mock "Marcus_rise" (`:4494-4497`) | `POST/DELETE /blocks` (`backend/app/api/v1/social.py:313-335`); `GET /blocks` (`:302-310`) | **MOCK** |

Observações transversais:

- O app monta `stack` por aba e **mantém as telas anteriores montadas** (`mobile/App.tsx:1136-1151`); voltar de `add-friend` **não** reexecuta o `useEffect` de `Friends` (`social.tsx:194-210`). Só tocar de novo na aba recria a raiz (`mobile/App.tsx:994-999` + `mobile/src/state/navigationStack.ts:14-17`), que é o "atualizar a página" relatado.
- `refreshCore` (boot/foreground) **não** inclui `loadSocial` nem `loadClan` (`mobile/src/state/app.tsx:929-942`).
- `notification.created` é publicado no WebSocket (`backend/app/modules/notifications/dispatch.py:107-124`), mas o app só reage a `lobby.invite.created` (`mobile/src/state/app.tsx:1098-1101`).
- Não há registro de push token no app (grep sem `push-tokens`/`expo-notifications` em `mobile/`), embora a rota exista (`backend/app/api/v1/social.py:419-435`).

---

## 2. Causa raiz de cada defeito relatado

### 2.1 Pedido de clã "duplicado" e estado "Enviado" que não persiste

- **Não há duplicata no banco.** `ClanJoinRequest` tem índice único parcial para `status='pending'` (`backend/app/modules/clans/models.py:124-131`) e `request_join` devolve a linha existente (`backend/app/modules/clans/service.py:424-427,439-446`); há teste de concorrência (`backend/tests/test_clans.py:1015-1078`).
- O defeito é de **UI**: o "pendente" é `useState` (`mobile/src/screens/social.tsx:1063`), setado só na resposta (`:1141`) e exibido apenas enquanto a tela está montada (`:1268-1288`). O servidor já devolve `my_request` no `GET /clans/{id}` (`backend/app/api/v1/clans.py:562-568`), mas a tela não lê (`social.tsx:1112-1116`), e o tipo `Clan` nem declara o campo (`mobile/src/api/types.ts:698-709`).
- Em `ClanDiscovery`, o botão também ignora `my_request` e volta a "Solicitar" (`social.tsx:783-808`). Resultado: refresh → botão ativo → usuário reenvia (o servidor deduplica, mas a percepção é de duplicidade).

### 2.2 Solicitante não vê pedidos de amizade enviados nem pedidos de clã enviados

- Amizade: `loadSocial` só busca `/friends` e `/lobby-invites` (`mobile/src/state/app.tsx:678-683`); `loadSocial` nem é chamado no boot (`:929-942`). As abas são estáticas (`social.tsx:315-319`). O endpoint pronto (`backend/app/api/v1/social.py:206-218`) e o cliente não tem `friendRequests`; tem apenas `requestFriend`/`acceptFriend` (`mobile/src/api/client.ts:1097-1111`), ambos sem uso.
- Clã: `GET /me/clan-requests?status=pending` existe (`backend/app/api/v1/clans.py:538-548`, serviço em `backend/app/modules/clans/service.py:590-612`) e **não há método no cliente** (`mobile/src/api/client.ts:1147-1284`).

### 2.3 Dono do clã não vê pedidos recebidos nem aceita/recusa

- Não existe tela nem link. `ClanProfile` lista apenas "Membros e cargos" e "Configurações" (`social.tsx:520-546`); `ClanMembers` só oferece "Convidar membros" (`:1725-1729`); `ClanSettings` não tem seção de pedidos (`:2113-2293`).
- `api.clans.requests` e `api.clans.decideRequest` existem (`mobile/src/api/client.ts:1245-1255`), mas não há nenhuma chamada (grep sem uso em `mobile/src`). O backend está completo: listar/decidir/cancelar (`backend/app/api/v1/clans.py:594-653`) com autorização de admin (`backend/app/modules/clans/service.py:566-587`).
- O dono recebe **notificação** `clan_join_request` (`backend/app/modules/clans/service.py:351-369`), mas tocá-la leva a `clan` genérico (`social.tsx:3600-3605`), onde não há fila de pedidos.

### 2.4 Notificações "quase inúteis"

- Mapeamento incompleto em `open()` (`social.tsx:3580-3621`):
  - `friend_request_received`/`friend_accepted`/`friend_declined`/`friend_cancelled` → **nenhum ramo**, toque só marca como lida (`:3581-3583`).
  - `clan_invite` → `return` sem navegar (`:3600-3603`).
  - `clan_join_request` → `clan` genérico (`:3604-3605`).
  - `match_created` → `lobby-detail` com `matchId` (`:3617-3619`), mas o payload não tem `lobby_id` (`backend/app/modules/matches/service.py:117-127`), então a tela `lobby-found` (mock, `mobile/src/screens/core.tsx:446-471`) nunca é alvo.
- O `data` de amizade traz só `friendship_id`/`counterpart_id` (`backend/app/modules/social/service.py:862-865`); o `title/body` é genérico ("Você recebeu um pedido de amizade", `:833-841`), então a lista não mostra **quem**.
- O `data` de pedido de clã traz `clan_id`/`request_id` (`backend/app/modules/clans/service.py:366-367`), sem nome/tag do solicitante.
- `NotificationView` não tem campo de destino/deep link (`backend/app/api/v1/notifications.py:24-31`).
- O feed só recarrega no mount (`social.tsx:3399-3420`); não há pull-to-refresh (o único `RefreshControl` está no chat, `social.tsx:2950`) nem reação ao evento `notification.created` (`mobile/src/state/app.tsx:1098-1101`).

### 2.5 Amizade enviar/receber não funciona

- Enviar: `AddFriend` não chama a API (`social.tsx:334-371`). Não há busca de jogador (`/users/search`, `backend/app/api/v1/users.py:42`).
- Receber: `Friends` não busca `/friends/requests` (`mobile/src/state/app.tsx:678-683`); "Solicitações" é texto fixo (`social.tsx:315-319`).
- Mesmo que houvesse lista, faltam no cliente: listar, recusar (`POST /friends/requests/{id}/decline`, `backend/app/api/v1/social.py:257-269`) e cancelar (`DELETE /friends/requests/{id}`, `social.py:272-285`). `removeFriend` existe e não é usado (`mobile/src/api/client.ts:1110-1112`).

### 2.6 Nome/tag canônicos, busca `nome#tag`, botões de nome e tag

- O servidor já canonicaliza nome em MAIÚSCULAS (`backend/app/core/text.py:93-108`, aplicado em `backend/app/modules/profile/service.py:194` e `backend/app/modules/identity/email_accounts.py:522`) e a tag é `#` + 8 hex maiúsculos (`backend/app/modules/identity/tags.py:31-36,53-71`).
- A busca `/users/search` já é case-insensitive, aceita `nome#TAG` e `#TAG`, escapa curingas e devolve `relation` (`backend/app/modules/social/service.py:193-267`; testes em `backend/tests/test_user_search.py:60-243`). **Nada disso é consumido.**
- O app exibe tag falsa (`core.tsx:1358`, `:1659`, `:1801`) porque `Profile` não declara `tag` (`mobile/src/api/types.ts:69-76`) e `Friend` também não (`:645`).
- Fallbacks locais como `onboarding.displayName` (`core.tsx:153,1335`) podem renderizar nome não canônico antes do perfil chegar; o servidor é a fonte da verdade (`core.tsx` deve priorizar `profile.display_name`).
- `AddFriend` tem um campo único `nome#tag` (`social.tsx:350-356`); não há dois campos lado a lado.
- Decisão pendente: nome de **clã** não é canonicalizado (`backend/app/modules/clans/service.py:235-240`, unicidade case-sensitive).

### 2.7 "Sem clã" no perfil até atualizar

- `ProfileMe` lê `clan` do contexto (`core.tsx:1311,1336`) mas não chama `loadClan` (`:1323-1333`).
- `refreshCore` não carrega clã (`mobile/src/state/app.tsx:929-942`); `loadClan` só roda em telas de clã (`social.tsx:382,642,932,1132,1447,1460`).
- Como o perfil fica montado (`mobile/App.tsx:1136-1151`), mesmo voltar de outra aba não recarrega.

---

## 3. Contratos: o que falta / está incompleto no backend

### 3.1 Campos `tag` ausentes (pequeno, alto impacto)

| View | Arquivo:linha | Falta |
|---|---|---|
| `FriendView` | `backend/app/api/v1/social.py:42-48` | `tag: str` (usado por Amigos, convite de lobby, bloqueados) |
| `FriendRequestView` | `backend/app/api/v1/social.py:65-72` | `counterpart_tag: str` (pedidos recebidos/enviados sem `#tag`) |
| `MemberView` (clã) | `backend/app/api/v1/clans.py:129-133` | `tag: str` (membros com nome#tag) |
| `RequestView` (pedido de clã) | `backend/app/api/v1/clans.py:140-149` | `tag: str` (fila do dono com nome#tag) |
| `ClanInviteView` | `backend/app/api/v1/clans.py:98-108` | opcional `inviter_tag: str` |

Preenchimento já tem fonte: `User.tag` (`backend/app/modules/identity/models.py`, usado em `backend/app/modules/social/service.py:255-257`). O `_display_name` de clã (`backend/app/api/v1/clans.py:215-218`) vira um `_identity(session, user_id) -> (name, tag)`.

### 3.2 `my_request` não é contrato de app

- Backend: `MyRequestSummaryView` (`backend/app/api/v1/clans.py:71-78`), embutido em `ClanSummaryView.my_request` (`:91`) e populado em lista/detalhe/meu clã (`:272,479-491,530-535,562-568`).
- Mobile: `Clan` não tem `my_request` (`mobile/src/api/types.ts:698-709`) → descartado no runtime.
- Falta também `message` no resumo (existe em `MyRequestView`, `backend/app/api/v1/clans.py:156-167`) se a UI quiser exibir o texto enviado.

### 3.3 Pedidos de clã do próprio jogador

- `GET /me/clan-requests` (`backend/app/api/v1/clans.py:538-548`) pronto e testado (`backend/tests/test_clans.py:1104-1155`); **sem método no cliente**.
- `DELETE /clans/{clan_id}/requests/{request_id}` (cancelar) pronto (`backend/app/api/v1/clans.py:640-653`); **sem método no cliente**.
- `GET /clans/{id}/requests` e `POST .../decide` prontos (`clans.py:594-637`), cliente existe e está órfão (`mobile/src/api/client.ts:1245-1255`).

### 3.4 Convites de clã enviados

- Não existe endpoint para o admin listar convites pendentes do clã; por isso `ClanInvite` mantém `pending` em memória (`mobile/src/screens/social.tsx:4535,4609-4617`). Sugestão mínima: `GET /clans/{id}/invites?status=pending` (espelho de `list_pending_invites`, `backend/app/modules/clans/service.py:752-782`, que hoje é só do convidado).
- `ClanInviteView` já tem `status`/`expires_at` (`backend/app/api/v1/clans.py:98-108`), então é só listagem.

### 3.5 Notificações: `data` e deep link

- `NotificationView` não carrega destino (`backend/app/api/v1/notifications.py:24-31`).
- `friend_*`: `data` = `friendship_id`, `counterpart_id`; `body` genérico (`backend/app/modules/social/service.py:826-867`). **Falta** `counterpart_name`/`counterpart_tag` e corpo com o nome.
- `clan_join_request`: `data` = `clan_id`, `request_id`; **falta** `requester_name`/`requester_tag` (origem em `backend/app/modules/clans/service.py:351-369`).
- `clan_join_approved|rejected`: `data` = `clan_id`, `request_id`, opcional `decision_note` (`clans/service.py:386-398`) — suficiente.
- `clan_invite`: `data` tem `invite_id`, `clan_id`, `clan_name`, `clan_tag`, `inviter_id` (`clans/service.py:740-746`) — falta `screen`, mas `kind` basta.
- `match_created`: `data` = `match_id` (`backend/app/modules/matches/service.py:125`); **falta `lobby_id`** (disponível em `match.lobby_id`, `matches/service.py:91`) para abrir `lobby-found`/`lobby-detail` com o id certo.
- **Recomendação de contrato (menor):** manter `kind` como discriminador estável e apenas completar `data` com os ids/nomes acima; documentar a tabela `kind → tela/params` em `docs/JOGA_DOCUMENTACAO_TECNICA.md` (seção 12 / nota 9D). **Alternativa (maior):** `data.destination = {screen, params}` — acopla backend a rotas do app; não recomendado agora.
- Consistência: status de amizade é MAIÚSCULO (`PENDING/ACCEPTED/...`, `backend/app/modules/social/models.py:35-37,72`) e de clã é minúsculo (`pending/approved/...`, `backend/app/modules/clans/models.py:113-116,141-143`). O app precisa de mapas distintos; vale documentar (não mudar agora).

### 3.6 Perfil público (opcional, mas necessário para `ProfileOther`)

- Não existe `GET /users/{id}` (rotas de perfil são só `/me/*`, `backend/app/api/v1/profile.py:241-475`; `users.py` só tem busca, `:42`).
- Mínimo sugerido: `GET /users/{user_id}` → `{ user_id, display_name, tag, relation, clan: {id,name,tag}|null }`, sem PII, reusando `_relations_for` (`backend/app/modules/social/service.py:706-747`) e `active_clan_for` (`backend/app/modules/clans/service.py:107-112`).

---

## 4. Fluxo desejado (passo a passo)

### 4.1 Buscar e adicionar amigo

1. Tela `AddFriend`: dois campos lado a lado — **Nome** (texto, `maxLength=60`) e **Tag** (`InputPrefix` com `#`, `autoCapitalize="characters"`, `maxLength=12`), preenchíveis de forma independente. Botão primário "Buscar".
2. Consulta = `nome` + (`#` + tag) quando a tag existir; senão só nome. Chamada `GET /users/search?q=...` (`backend/app/api/v1/users.py:42-81`). Case-insensitive já resolvido no servidor (`backend/app/modules/social/service.py:242-253`).
3. Resultado por linha: identidade + `display_name` + `tag` (já vem do endpoint, `users.py:31-35`) + ação derivada de `relation`:
   - `none` → botão **Adicionar**;
   - `outgoing_request` → **Enviado** (desabilitado);
   - `incoming_request` → **Aceitar** + **Recusar** (mesma linha, sem sair da tela);
   - `friend` → **Amigo** (desabilitado).
4. **Adicionar** → `POST /friends/requests {user_id}` (`backend/app/api/v1/social.py:221-239`). Tratar:
   - `201` → estado local vira `outgoing_request` **e** recarregar `/friends/requests?direction=outgoing&status=pending` (persistência real);
   - `409 incoming_friend_request` + `request_id` (`social.py:121-130`) → oferecer "Aceitar pedido existente" chamando `POST /friends/requests/{request_id}/accept` (`social.py:242-254`);
   - `409 already_friends`, `409 friend_request_exists`, `409 blocked_relationship`, `429 rate_limited` (`social.py:131-155`).
5. Reenviar o mesmo pedido é idempotente no servidor (`backend/app/modules/social/service.py:334-336,795-802`), mas a UI deve manter **Enviado** e nunca habilitar de novo.

### 4.2 Receber, aceitar, recusar, cancelar

1. `Friends` aba **Solicitações** com duas seções (ou `Seg` interno): **Recebidos** e **Enviados**.
2. Recebidos: `GET /friends/requests?direction=incoming&status=pending` (`social.py:206-218`). Linha com nome#tag + **Aceitar** / **Recusar**.
   - Aceitar → `POST /friends/requests/{id}/accept` (`social.py:242`) → remover da lista, inserir em Amigos, toast.
   - Recusar → `POST /friends/requests/{id}/decline` (`social.py:257`) → remover da lista.
3. Enviados: `GET /friends/requests?direction=outgoing&status=pending` → **Cancelar** (`DELETE /friends/requests/{id}`, `social.py:272`).
4. Amigos: `GET /friends` (`social.py:195-203`) com nome#tag; ação **Remover** (`DELETE /friends/{user_id}`, `social.py:288-299`) e **Bloquear** (`POST /blocks`, `social.py:313-325`).
5. Bloqueados: `GET /blocks` (`social.py:302-310`) + **Desbloquear** (`DELETE /blocks/{user_id}`, `social.py:328-335`).
6. Estados obrigatórios: vazio ("Nenhum pedido"), erro com retry, "tudo em dia".

### 4.3 Pedido de entrada em clã: enviar uma vez e persistir

1. `ClanDiscovery`: para cada clã, derivar ação de `my_request?.status` (`backend/app/api/v1/clans.py:71-78,91`):
   - `pending` → **Pendente** (desabilitado, sem reenvio);
   - `rejected`/`cancelled` → **Solicitar de novo**;
   - `approved` ou `is_member` → **Abrir**.
2. `ClanJoin`: ao carregar o detalhe, se `detail.my_request.status === 'pending'`, renderizar direto o estado **"Solicitação enviada"** (mesmo componente de `social.tsx:1268-1288`), sem botão de enviar.
3. Enviar → `POST /clans/{id}/join` (`backend/app/api/v1/clans.py:571-591`). Resposta `{status:'pending', request}` (`clans.py:174-176`): persistir o estado a partir de `request.status`, não de `useState` solto. `{status:'joined'}` → recarregar clã e abrir `clan`.
4. Estados de erro já mapeados: `already_member`, `already_in_clan`, `clan_full`, `clan_cooldown`, `clan_closed`, `not_found` (`mobile/src/screens/social.tsx:1146-1168`; backend `backend/app/api/v1/clans.py:319-339`).
5. "Meus pedidos" (perfil do clã ou Friends): `GET /me/clan-requests?status=pending` → nome#tag do clã, data, status, **Cancelar** (`DELETE /clans/{clan_id}/requests/{request_id}`, `clans.py:640-653`).

### 4.4 Dono/admin: ver e decidir

1. `ClanProfile` (se `my_role` ∈ `owner|admin`, `isAdminRole` em `mobile/src/state/clanSocial.ts:132-134`): novo `ListRow` **"Pedidos de entrada"** com contador.
2. Tela nova (ou sheet) `clan-requests`: `GET /clans/{id}/requests?status=pending` (`backend/app/api/v1/clans.py:594-610`).
3. Linha: nome#tag, mensagem (200 chars), data, **Aprovar** / **Recusar** (+ nota opcional).
   - `POST /clans/{id}/requests/{rid}/decide {approve, note}` (`clans.py:613-637`).
   - `409 request_not_pending` = outra pessoa decidiu → recarregar e informar (`backend/app/modules/clans/service.py:510-513`).
   - `403` (`owner_required`/`admin_required`) → esconder ações.
4. Aprovar deve atualizar membros/contagem (recarregar `loadClan()`); recusar só remove da fila.
5. Histórico: `?status=history` (`clans.py:599`).

### 4.5 Convites de clã enviados

1. `ClanInvite`: carregar pendentes do servidor (novo `GET /clans/{id}/invites?status=pending` ou reuso de `ClanInviteView`) em vez de `useState` (`mobile/src/screens/social.tsx:4535`).
2. Enviar → `POST /clans/{id}/invites` (`backend/app/api/v1/clans.py:883-900`); 409 `already_invited` → marcar "Convite pendente" (não erro) (`backend/app/modules/clans/service.py:729-732`).
3. Cancelar → `DELETE /clans/{id}/invites/{invite_id}` (`clans.py:944-957`).

### 4.6 Notificação → ação → tela

Tabela de destino (proposta de contrato estável por `kind`):

| `kind` | Origem | Destino/ação | Pré-requisito de `data` |
|---|---|---|---|
| `friend_request_received` | `social/service.py:835` | `friends` aba **Recebidos** (ou aceitar/recusar inline) | `counterpart_name`, `counterpart_tag`, `friendship_id` |
| `friend_accepted` | `social/service.py:380` | `friends` aba **Amigos** | `counterpart_id`, nome |
| `friend_declined` | `social/service.py:411` | `friends` aba **Enviados** (histórico) | idem |
| `friend_cancelled` | `social/service.py:444` | `friends` aba **Recebidos** | idem |
| `clan_join_request` | `clans/service.py:363` | `clan-requests` (dono/admin) | `clan_id`, `request_id`, `requester_name`, `requester_tag` |
| `clan_join_approved` / `clan_join_rejected` | `clans/service.py:379` | `clan` (aprovado) / "Meus pedidos" (recusado, com `decision_note`) | `clan_id`, `request_id` |
| `clan_invite` | `clans/service.py:736` | `notifications` seção "Convites de clã" com **Aceitar/Recusar** (já implementada, `social.tsx:3692-3753`) | `invite_id`, `clan_name`, `clan_tag`, `inviter_id` |
| `clan_invite_accepted` / `_declined` | `clans/service.py:880,916` | `clan-members` / `clan-invite` | `invitee_id` |
| `match_created` ("lobby encontrado") | `matches/service.py:119` | `lobby-found`/`lobby-detail` | `match_id`, **`lobby_id`** |
| `booking_*`, `moderation_*`, `result*` | já mapeados | manter (`social.tsx:3586-3596`) | — |

Implementação no app: `open(item)` deve despachar por `kind` **prefixado** (`friend_`, `clan_join_`, `clan_invite`, `match_`, `lobby_`) e cair em fallback "Abrir notificações"/nenhuma navegação. Para `clan_invite`, remover o `return` de `social.tsx:3601-3603` e rolar até a seção de convites (ou marcar destaque).

### 4.7 Refresh por foco (sem redesign)

1. **Boot/foreground:** incluir `loadSocial()` e `loadClan()` em `refreshCore` (`mobile/src/state/app.tsx:929-942`), com tolerância a falha (`Promise.allSettled` já usado em `:933`).
2. **Foco de tela:** helper `useScreenFocus(ownId, cb)` baseado em `nav.id` (topo da pilha muda em push/pop/tab, `mobile/App.tsx:789-796,892-1012`), chamando `cb()` quando `nav.id === ownId`. Isso cobre voltar de `add-friend`/`clan-join` sem remontar (hoje as telas ficam montadas, `App.tsx:1136-1151`).
3. **Pull-to-refresh** em `Friends`, `ClanProfile`, `ClanMembers`, `Notifications`, `ClanInvite` (padrão de `social.tsx:2950`).
4. **Pós-mutação:** cada ação (aceitar, decidir, enviar) invalida/recarrega a lista afetada e o contador, sem depender de remontagem.
5. **Contador de notificações:** reagir a `notification.created` no subscriber global (`mobile/src/state/app.tsx:1098-1101`) chamando `loadNotifications()` (o evento já é publicado, `backend/app/modules/notifications/dispatch.py:107-124`).

---

## 5. Testes e critérios de aceite

### 5.1 Backend (pytest; CI roda `python -m pytest`)

Já cobertos e servem de rede de segurança (não reescrever):

- Amizade: fluxo, listagem/recusa, cancelamento só pelo autor, idempotência e conflito de direção, rate limit 429 — `backend/tests/test_social_api.py:46-275`.
- Busca: case-insensitive, acento, curingas, tag com/sem `#`, relação, suspensos, PII, rate limit — `backend/tests/test_user_search.py:60-243`.
- Clã: pedido repetido sem duplicata, corrida, `my_request` no detalhe/lista, meus pedidos pending/history, decisão com nota, segunda decisão 409, cancelamento só pelo autor, notificações — `backend/tests/test_clans.py:1015-1355`.

Novos testes necessários (contratos deste relatório):

1. `test_friend_view_includes_tag` — `GET /friends` e `GET /friends/requests` retornam `tag` canônica (`#` + hex maiúsculo) igual a `users.tag`.
2. `test_clan_member_and_request_views_include_tag` — `GET /clans/{id}/members` e `/requests`.
3. `test_friend_notification_carries_counterpart_name_and_tag` — após `POST /friends/requests`, a notificação do destinatário tem `data.counterpart_name/tag` e `body` com o nome.
4. `test_clan_join_request_notification_carries_requester_identity` — dono/admin recebe `requester_name/tag`.
5. `test_match_created_notification_carries_lobby_id` — `data.lobby_id` presente e igual a `matches.lobby_id`.
6. `test_clan_pending_invites_list_for_admin_only` — novo `GET /clans/{id}/invites?status=pending` (403 para membro comum, 200 para dono, só do próprio clã).
7. `test_users_public_profile_minimal` (se aprovado) — `GET /users/{id}` sem PII, com `relation` e clã; 404 para inexistente; 403/404 para bloqueado.
8. `test_my_request_summary_includes_message` (se a UI for exibir a mensagem no card) — contrato de `MyRequestSummaryView`.

### 5.2 Mobile (node --test, arquivos puros)

Padrão atual: helpers puros em `mobile/src/state/*.ts` testados por `*.test.mjs`; a lista de arquivos é fixa em `mobile/package.json` (`"test"`), então **incluir o novo arquivo no script**.

Extrair para `mobile/src/state/socialState.ts` (ou `notificationTarget.ts`) e testar:

1. `composePlayerQuery(name, tag)` → `"NOME#TAG"`, `"#TAG"`, `"NOME"` (trim/uppercase, tag sem `#`).
2. `friendActionFor(relation)` → `add|sent|accept|friend`.
3. `clanCardAction({is_member, my_request, policy, full})` → `open|pending|resend|join|request|closed|full`.
4. `clanJoinState(my_request, response)` → `pending|rejected|joined`.
5. `notificationTarget(kind, data)` → `{screen, params}` para todos os `kind` da tabela 4.6, incluindo fallback para `data` inválido/ausente (deep link inválido).
6. `clanRequestDecisionError(code)` → mensagem + `reload` para `request_not_pending`/`already_in_clan`/`clan_full`.

Também: `npm run typecheck`, `npm run lint`, `npm run format:check` (scripts reais em `mobile/package.json`).

### 5.3 Critérios de aceite verificáveis (produto)

1. Buscar `nome` + tag em `AddFriend` encontra o jogador (case-insensitive); adicionar uma vez → linha vira **Enviado**; matar/reabrir o app → continua **Enviado** (lista Enviados).
2. Dois toques rápidos em **Adicionar**/`Solicitar` geram **uma** requisição e um estado final (sem erro visível de duplicata).
3. Destinatário vê o pedido em **Recebidos**; aceitar move para Amigos em ambas as contas após refresh; recusar remove.
4. `Solicitar entrada` em clã por aprovação → **Pendente** no card e no detalhe; refresh/reabrir app mantém **Pendente**; segundo toque não reenvia.
5. Dono/admin vê "Pedidos de entrada" com contador; aprovar torna o solicitante membro (contagem sobe); recusar remove; segunda decisão concorrente mostra "já decidido" e recarrega.
6. "Meus pedidos" lista pedidos pendentes com clã e permite cancelar; após cancelar, o card volta a **Solicitar**.
7. Notificação de pedido de amizade mostra o nome#tag do remetente e abre a lista correta; convite de clã mostra clã e permite aceitar/recusar; partida formada abre o lobby correspondente; nenhum toque fica "morto".
8. Perfil mostra `nome#tag` reais do servidor e o clã correto no primeiro frame (sem "Sem clã" intermitente).
9. Convites de clã pendentes continuam visíveis após refresh e não podem ser reenviados.

---

## 6. Riscos e edge cases

| Caso | Comportamento atual / risco | Tratamento recomendado |
|---|---|---|
| Duplo toque | Botões usam refs locais em várias telas (`social.tsx:587,890,1066,4538`), mas `AddFriend`/decisão de pedido ainda não têm lock | Lock por id + desabilitar durante a chamada; backend já é idempotente (`clans/service.py:424-427`, `social/service.py:334-336`) |
| Refresh/remontagem | Estado local some (`social.tsx:1063,4535`) | Fonte da verdade = resposta do servidor (`my_request`, listas) |
| Offline | `JoinFailure`/`StateScreen` já existem (`social.tsx:554-566,1246-1265`) | Manter fila otimista só após confirmação; nunca mostrar "Enviado" sem 2xx |
| 409/duplicata | Códigos distintos por feature (`social.py:131-155`, `clans.py:319-339`) | Mapear `friend_request_exists`/`already_invited`/`request_not_pending` para estado, não erro |
| Rate limit | 20 pedidos de amizade/h (`social/service.py:27,816-824`), 60 buscas/h (`:30,217-224`), 20 convites/h (`:26`) | Respeitar `Retry-After` (`social.py:146-151`); UI desabilita e explica |
| Bloqueio | Busca exclui bloqueados nos dois sentidos (`social/service.py:226-231`); pedido bloqueado dá 409 (`:329-330`) | Não oferecer "Adicionar"; em erro, mensagem neutra |
| Clã cheio | 30 membros (`backend/app/modules/clans/service.py:38,457,697`); `clan_full` 409 (`backend/app/api/v1/clans.py:330-332`) | Card "Cheio", botão desabilitado; decisão de aprovar com clã cheio deve recarregar |
| Convite/pedido expirado | Convite de clã expira em 7 dias e é marcado `expired` na leitura (`clans/service.py:40,760-768`); pedido não expira | Mostrar "Expirou" e permitir novo pedido; pedido antigo requer cancelar antes (índice único `models.py:124-131`) |
| Usuário suspenso | Busca exclui `User.status != 'active'` (`social/service.py:235-240`); convite/pedido para suspenso deve falhar | Tratar `user_not_found`/`blocked_relationship` como "indisponível" |
| 130% / fonte grande | `ThemeValue.largeTargets/fontScale` (`mobile/src/state/context.tsx:33-63`); linhas com `BtnRow` podem quebrar | Usar `BtnRow`/`flexWrap` e testar com `fontScale` máximo; evitar larguras fixas em linhas com 2 botões |
| Deep link inválido | `open()` navega com params possivelmente `undefined` (`social.tsx:3614,3618`) | Resolver destino puro (testável) e cair em `notifications`/`friends` quando faltar id |
| Convite de clã × convite de lobby | Ambos contêm `invite`; a ordem atual evita colisão (`social.tsx:3598-3615`) | Manter prefixo explícito: `clan_invite` antes de `invite` |
| Bloqueio de tela mock | `BlockUser` mostra "Marcus_rise" (`social.tsx:4494-4497`) | Trocar por params reais ou esconder até existir fluxo |
| Nome de clã | Case-sensitive e sem canonicalização (`clans/service.py:235-240`) | Decidir: manter como está (documentar) ou canonicalizar com migração |

---

## 7. Divisão proposta (ordem de execução, sem redesign visual)

### Etapa B1 — Backend: contrato pequeno (1 PR)

1. `tag` em `FriendView`, `FriendRequestView` (`backend/app/api/v1/social.py:42-72`) e em `MemberView`, `RequestView` (`backend/app/api/v1/clans.py:129-149`), com helper único de identidade (nome+tag) no lugar de `_display_name` (`clans.py:215-218`).
2. `data` das notificações: `counterpart_name/tag` (`backend/app/modules/social/service.py:826-867`), `requester_name/tag` (`backend/app/modules/clans/service.py:351-369`), `lobby_id` (`backend/app/modules/matches/service.py:117-127`). Sem mudar `kind`.
3. `my_request.message` no resumo (`backend/app/api/v1/clans.py:71-78`) — opcional, se o card for exibir.
4. Documentar a tabela `kind → destino` e a distinção de casing de status em `docs/JOGA_DOCUMENTACAO_TECNICA.md` (seção 12 e nota 9D).
5. Testes 5.1 itens 1-5.

### Etapa B2 — Backend: lacunas funcionais (1 PR, se aprovado)

1. `GET /clans/{id}/invites?status=pending` (admin) reusando `ClanInviteView` e `list_pending_invites` (`backend/app/modules/clans/service.py:752-782`).
2. `GET /users/{user_id}` mínimo para `ProfileOther` (nome, tag, relação, clã), sem PII.
3. Testes 5.1 itens 6-7.

### Etapa M1 — Mobile: contratos e estado (sem UI nova)

1. `mobile/src/api/types.ts`: `Friend.tag`, `ClanMember.tag`, `Clan.my_request`, `FriendRequest`, `MyClanRequest`, `ClanJoinResult` tipado.
2. `mobile/src/api/client.ts`: `users.search`; `social.friendRequests/decline/cancel/remove/blocks`; `clans.myRequests/cancelRequest/invites`; remover `unknown` de `requests/decideRequest/join` (`client.ts:1186-1195,1245-1255`).
3. `mobile/src/state/app.tsx`: `loadSocial` busca `/friends` + `friendRequests incoming/outgoing` + `blocks`; `refreshCore` inclui `loadSocial`/`loadClan` (`:929-942`); subscriber de `notification.created` (`:1098-1101`).
4. Helper `useScreenFocus` (nav por topo, `mobile/App.tsx:789-796`).

### Etapa M2 — Mobile: amizade

1. `AddFriend` real: dois campos + busca + ações por `relation` (`social.tsx:334-371`).
2. `Friends`: Solicitações (recebidos/enviados) e Bloqueados reais (`social.tsx:315-319`); nome#tag; remover/bloquear/desbloquear.
3. `ProfileOther` com `GET /users/{id}` e tag real (`core.tsx:1653-1759`).

### Etapa M3 — Mobile: clã

1. `ClanDiscovery`/`ClanJoin` lendo `my_request` (`social.tsx:783-808,1112-1116,1268-1288`).
2. `ClanProfile`: link "Pedidos de entrada" com contador para owner/admin (`social.tsx:520-546`).
3. Tela `clan-requests` com aprovar/recusar/histórico.
4. "Meus pedidos" + cancelar (Friends ou perfil do clã).
5. `ClanInvite` com pendentes do servidor (`social.tsx:4535,4609-4617`).

### Etapa M4 — Mobile: notificações e perfil

1. `notificationsTarget(kind, data)` puro (tabela 4.6) e `open()` usando-o (`social.tsx:3580-3621`), incluindo remover o `return` de convite de clã (`:3601-3603`).
2. Ações inline de amizade/pedido na lista, quando aplicável.
3. Pull-to-refresh em `Friends`, `ClanProfile`, `ClanMembers`, `Notifications`, `ClanInvite`.
4. `ProfileMe`: `tag` de `profile.tag` (`core.tsx:1358`) e `loadClan` no foco (`:1323-1333`).

Cada etapa deve parar para revisão; nada aqui autoriza commit, push ou deploy.

---

## 8. Confirmações

- **Nenhum código foi alterado** em `mobile/`, `backend/` ou em qualquer outro diretório. O único arquivo criado é este relatório.
- **Nenhum comando de git** foi executado (nem em `C:\prog\joga`, nem no worktree).
- **Nenhuma fase seguinte foi iniciada**; nenhuma ação externa, migração ou deploy.
- Trabalho realizado apenas por leitura em `C:\Users\crn26\.local\share\opencode\worktree\133308\social-analysis` (branch `feat/social-analysis-1a0`, base `dda0a09`).
