import { NativeModule, requireOptionalNativeModule } from 'expo';

import type { CreatePasskeyResult, GetPasskeyResult } from './PasskeyProof.types';

/**
 * Módulo local de prova da Fase 1.
 *
 * Expo `~58.0.22`, React Native `0.88.1`. Android-only: usa o Credential Manager
 * (`androidx.credentials`) com o Google Password Manager. Não existe implementação
 * iOS neste protótipo; a associação/build iOS permanece pendente.
 *
 * `requireOptionalNativeModule` evita que o app quebre em Expo Go ou em builds sem
 * o módulo nativo; nesses casos o valor é `null` e a tela de prova informa que a
 * cerimônia exige o development build Android.
 */
export declare class PasskeyProofModule extends NativeModule {
  /** Versão do Android em execução, apenas para exibir na tela de prova. */
  getPlatformSummary(): string;

  /**
   * Cria uma passkey para o RP ID informado. O desafio é gerado no dispositivo
   * com `SecureRandom`; não há backend nem verificação remota nesta prova.
   */
  createPasskeyAsync(rpId: string, rpName: string, userName: string): Promise<CreatePasskeyResult>;

  /**
   * Autentica com uma passkey do RP ID informado. Com `credentialId` vazio, o
   * seletor de contas do sistema é aberto.
   */
  getPasskeyAsync(rpId: string, credentialId: string): Promise<GetPasskeyResult>;
}

export default requireOptionalNativeModule<PasskeyProofModule>('PasskeyProof');
