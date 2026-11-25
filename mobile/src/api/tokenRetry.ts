/**
 * Token a usar na repetição de uma chamada que recebeu 401.
 *
 * O backend rotaciona a sessão a cada refresh. Se outra chamada já renovou
 * enquanto esta aguardava, o token da sessão é mais novo que o token enviado
 * e deve vencer — repetir com ele evita uma segunda rotação que revogaria o
 * token recém-recebido.
 */
export function retryTokenAfterRefresh(
  sentToken: string,
  currentToken: string | null | undefined,
  refreshedToken: string,
): string {
  if (currentToken && currentToken !== sentToken) {
    return currentToken;
  }
  return refreshedToken;
}
