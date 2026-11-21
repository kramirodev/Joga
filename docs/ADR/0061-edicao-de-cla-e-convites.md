# ADR 0061 — Edição de clã e convites diretos para amigos

- **Status:** Aprovado em 2026-11-21.
- **Data:** 2026-11-21
- **Relaciona:** ADR 0060, `backend/app/api/v1/clans.py`,
  `backend/app/modules/clans/models.py`, `backend/app/modules/clans/service.py`,
  `backend/migrations/versions/4c5d6e7f8a9b_add_clan_invites.py` e
  `backend/app/modules/social/service.py`.

## Contexto

O clã já permitia criar, descobrir, pedir entrada, aprovar, promover, remover,
transferir posse, conversar e denunciar. Faltavam duas operações básicas: o dono
ou admin não conseguia corrigir nome, descrição e política de entrada; e não
havia convite direto para um amigo, só o pedido público de entrada.

A tag canônica (`#MIOLO`) foi definida na ADR 0060. O dono decidiu que a tag é
imutável para sempre: ela identifica o clã e não deve ser reciclada nem trocada
por edição.

## Decisão

### 1. Edição de clã

`PATCH /api/v1/clans/{clan_id}` aceita somente `name`, `description` e
`join_policy` (`approval|open|closed`). Qualquer outro campo no corpo, em
especial `tag`, responde **422** com `extra="forbid"`; não existe caminho de
serviço para alterar a tag. A autorização é de **owner ou admin** do clã
(`admin_required` para os demais), e cada campo efetivamente alterado gera um
evento `clan.updated` em `audit_log` com `details.changes` no formato
`{campo: {from, to}}`. Enviar o mesmo valor não gera auditoria.

Nome segue a regra do create: `strip`, 3 a 40 caracteres, único
(`name_taken`/`name_invalid`). Descrição tem no máximo 280 caracteres e pode
ser limpa com `null`. `closed` é permitido como qualquer outra política e fica
registrado na auditoria; não há justificativa obrigatória porque nenhuma regra
de produto a exige. A resposta é `ClanSummaryView`.

### 2. Convites de clã

Novo modelo `clan_invites`:

| Campo | Regra |
|---|---|
| `id` | UUID |
| `clan_id`, `inviter_id`, `invitee_id` | FKs com `ON DELETE CASCADE` |
| `status` | `pending|accepted|declined|expired` |
| `created_at` | criação |
| `expires_at` | criação + 7 dias |
| `answered_at` | resposta ou expiração/cancelamento |

O índice único parcial `uq_clan_invites_pending (clan_id, invitee_id) WHERE
status = 'pending'` impede dois convites pendentes do mesmo clã para a mesma
pessoa sem apagar o histórico. Há índices por `invitee_id/status` e
`clan_id/status`.

Endpoints e erros estáveis em `{detail: {code}}`:

- `POST /clans/{clan_id}/invites` `{user_id}` — owner/admin; convidado precisa
  ser amigo aceito (`not_friends`, 403), não bloqueado em nenhuma direção
  (`blocked`, 403), não membro do clã (`already_member`, 409), clã com vaga
  (`clan_full`, 409) e sem pendente duplicado (`already_invited`, 409).
  Responde 201 com `ClanInviteView`.
- `GET /me/clan-invites` — somente os convites `pending` e não expirados do
  jogador autenticado, com nome/tag do clã e quem convidou.
- `POST /clans/invites/{invite_id}/accept` — somente o convidado
  (`not_found`, 404 para terceiros); convite pendente e não expirado
  (`invite_expired`/`invite_not_pending`, 409); sem clã ativo
  (`already_in_clan`, 409); com vaga (`clan_full`, 409); respeita a carência de
  7 dias (`clan_cooldown`, 409). Torna o jogador `member` ativo, audita
  `clan.invite_accepted` e responde `ClanSummaryView`.
- `POST /clans/invites/{invite_id}/decline` — somente o convidado; marca
  `declined` e `answered_at`.
- `DELETE /clans/{clan_id}/invites/{invite_id}` — owner/admin cancela pendente.
  O status fechado não tem `cancelled`; o cancelamento usa `expired` com
  `answered_at` e auditoria `clan.invite_cancelled` com
  `reason=cancelled_by_admin`. Escolha: preserva histórico e libera o índice
  único parcial, sem ampliar o conjunto de status.

Convite pendente do jogador para outro clã não impede novo convite; a
exclusividade de clã ativo é verificada somente no aceite. A expiração é
materializada de forma preguiçosa na listagem e antes de novo convite; não há
worker dedicado.

### 3. Notificação

O convite cria uma notificação pela central existente (`NotificationService`),
com `kind=clan_invite`, chave idempotente `clan_invite:{invite_id}` e dados do
clã/convite. Isso reutiliza a Outbox e o dispatcher de push já existentes, sem
inventar um evento novo. Não há notificação de aceite/recusa nesta entrega.

## Consequências

- O app deve tratar a tag como somente leitura depois da criação; enviar `tag`
  no PATCH é erro de contrato (422).
- A tela de convite usa `GET /me/clan-invites`, não uma varredura de clãs.
- Administradores não têm listagem de convites enviados/pendentes nesta
  entrega; o cancelamento é feito pelo `invite_id` recebido na criação.
- Convites expirados permanecem no banco com status `expired`; uma limpeza
  periódica pode ser adicionada depois, sem mudança de contrato.
