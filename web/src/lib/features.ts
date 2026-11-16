/**
 * Central de notificações de moderação.
 *
 * O backend separa notificações em dois canais: `player` (app do jogador) e
 * `moderation` (triagem interna). O painel consome os endpoints dedicados
 * `/moderation/notifications`, que sempre operam o canal interno e exigem
 * `moderation.read` (`403 moderator_required` para conta comum).
 *
 * Desligue esta constante se a central precisar sair do ar sem remover código.
 */
export const MODERATION_NOTIFICATIONS_ENABLED = true;
