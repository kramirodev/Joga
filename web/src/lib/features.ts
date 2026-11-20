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

/**
 * Capability que libera a administração da plataforma.
 *
 * A navegação e as rotas `/admin/*` só existem com esta capability na sessão.
 */
export const PLATFORM_ADMIN_CAPABILITY = "platform.admin";

/**
 * Compra de tickets desligada enquanto o backend responde
 * `503 ticket_purchase_disabled`. Nenhuma ação de compra é renderizada no
 * painel; a constante documenta o portão e evita que uma tela futura apareça
 * por engano.
 */
export const TICKET_PURCHASE_ENABLED = false;
