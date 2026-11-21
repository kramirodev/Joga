export type RefreshFailure = 'suspended' | 'retry' | 'expired' | 'unavailable';

/**
 * Códigos que provam que o refresh não vale mais. Só estes deslogam.
 *
 * - `invalid_refresh_token`: token desconhecido/expirado;
 * - `refresh_reuse_detected`: reutilização fora da janela de tolerância (ADR 0058);
 * - `invalid_token`: access token rejeitado de forma definitiva.
 */
const EXPLICIT_REVOCATION_CODES = new Set([
  'invalid_refresh_token',
  'refresh_reuse_detected',
  'invalid_token',
]);

/** Corrida legítima de rotação (ADR 0058): repetir com o par mais novo. */
const RETRY_REQUIRED_CODES = new Set(['refresh_retry_required']);

export function isExplicitSessionRevocation(code: string | null | undefined): boolean {
  return !!code && EXPLICIT_REVOCATION_CODES.has(code);
}

/**
 * Classificação explícita da falha do refresh de sessão.
 *
 * - `account_suspended`: só o corpo do servidor liga a tela de suspensão;
 * - `retry`: `refresh_retry_required` — corrida transitória, repetir uma vez
 *   com o par mais novo; se persistir, mantém a sessão;
 * - `expired`: o servidor disse explicitamente que o refresh foi
 *   invalidado/revogado (`invalid_refresh_token`, `refresh_reuse_detected`) —
 *   único caso de logout;
 * - `unavailable`: rede, timeout, 5xx, 429 ou 4xx sem revogação explícita —
 *   mantém a sessão e mostra erro.
 */
export function classifyRefreshFailure(
  status: number,
  code: string | null | undefined,
): RefreshFailure {
  if (code === 'account_suspended') {
    return 'suspended';
  }
  if (code && RETRY_REQUIRED_CODES.has(code)) {
    return 'retry';
  }
  if (status === 0 || status === 429 || status >= 500) {
    return 'unavailable';
  }
  if (status === 401 || status === 403) {
    return isExplicitSessionRevocation(code) ? 'expired' : 'unavailable';
  }
  // 4xx sem código de revogação não prova que a sessão morreu.
  return 'unavailable';
}

/** Só uma revogação explícita pode apagar os tokens locais. */
export function sessionRecoveryDecision(
  status: number,
  code: string | null | undefined,
): 'clear' | 'keep' {
  return classifyRefreshFailure(status, code) === 'expired' ? 'clear' : 'keep';
}

/** Corrida transitória da ADR 0058: repetir **uma vez** com o par mais novo. */
export function shouldRetryRefresh(status: number, code: string | null | undefined): boolean {
  return classifyRefreshFailure(status, code) === 'retry';
}
