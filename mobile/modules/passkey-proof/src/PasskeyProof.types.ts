/**
 * Resultado público de uma criação de passkey.
 *
 * Contém apenas dados públicos da cerimônia (ID da credencial e clientData).
 * Nenhuma chave privada, assinatura ou material secreto é exposto ao JavaScript.
 */
export type CreatePasskeyResult = {
  credentialId: string;
  rawId: string;
  clientDataType: string;
  clientDataOrigin: string;
  clientDataChallenge: string;
  registrationResponseJson: string;
};

/**
 * Resultado público de uma autenticação com passkey.
 *
 * `rpIdHashMatches` confirma que a asserção foi emitida para o RP ID solicitado,
 * comparando o SHA-256 do RP ID com os primeiros 32 bytes do authenticatorData.
 */
export type GetPasskeyResult = {
  credentialId: string;
  rawId: string;
  clientDataType: string;
  clientDataOrigin: string;
  rpIdHashMatches: boolean;
  userPresent: boolean;
  userVerified: boolean;
  authenticationResponseJson: string;
};
