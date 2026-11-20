export type RefreshFailure = 'suspended' | 'expired' | 'unavailable';

/**
 * Classificação explícita da falha do refresh de sessão.
 *
 * - `account_suspended`: só o corpo do servidor liga a tela de suspensão;
 * - `expired`: token inválido, refresh rejeitado/rotacionado/revogado — logout;
 * - `unavailable`: rede, timeout, 5xx ou 429 — mantém a sessão e mostra erro.
 */
export function classifyRefreshFailure(
  status: number,
  code: string | null | undefined,
): RefreshFailure {
  if (code === 'account_suspended') {
    return 'suspended';
  }
  if (status === 0 || status === 429 || status >= 500) {
    return 'unavailable';
  }
  if (status === 401 || status === 403) {
    return 'expired';
  }
  if (status >= 400) {
    return 'expired';
  }
  return 'unavailable';
}
