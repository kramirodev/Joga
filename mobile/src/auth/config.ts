/**
 * Configuração de credencial por build. O backend não expõe flags públicas;
 * o app não infere a fase a partir de dados do usuário.
 *
 * Beta (padrão): e-mail primário, telefone dormente.
 * Lançamento: ligue `EXPO_PUBLIC_AUTH_PHONE_ENABLED=true` e
 * `EXPO_PUBLIC_AUTH_PHONE_REQUIRED=true` no build.
 */
function flag(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined || value.trim() === '') {
    return fallback;
  }
  const normalized = value.trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes';
}

const emailEnabled = flag(process.env.EXPO_PUBLIC_AUTH_EMAIL_ENABLED, true);
const phoneEnabled = flag(process.env.EXPO_PUBLIC_AUTH_PHONE_ENABLED, false);
const phoneRequired = flag(process.env.EXPO_PUBLIC_AUTH_PHONE_REQUIRED, false);

export const authConfig = {
  emailEnabled,
  phoneEnabled,
  phoneRequired,
  /** Cadastro usa telefone primeiro somente quando ele é obrigatório no lançamento. */
  signupMethod:
    !emailEnabled || (phoneEnabled && phoneRequired) ? ('phone' as const) : ('email' as const),
} as const;

export type AuthMethod = 'email' | 'phone';

export function otherMethod(method: AuthMethod): AuthMethod {
  return method === 'email' ? 'phone' : 'email';
}
