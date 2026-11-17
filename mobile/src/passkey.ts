import PasskeyProof from '../modules/passkey-proof/src/PasskeyProofModule';

export class PasskeyUnavailableError extends Error {
  constructor() {
    super('passkey_unavailable');
    this.name = 'PasskeyUnavailableError';
  }
}

export type PasskeyCredential = Record<string, unknown>;

export function passkeyAvailable(): boolean {
  return PasskeyProof !== null;
}

async function createFromOptions(publicKey: Record<string, unknown>): Promise<PasskeyCredential> {
  if (!PasskeyProof) {
    throw new PasskeyUnavailableError();
  }
  const result = await PasskeyProof.createPasskeyFromRequestAsync(JSON.stringify(publicKey));
  return JSON.parse(result.registrationResponseJson) as PasskeyCredential;
}

async function getFromOptions(publicKey: Record<string, unknown>): Promise<PasskeyCredential> {
  if (!PasskeyProof) {
    throw new PasskeyUnavailableError();
  }
  const result = await PasskeyProof.getPasskeyFromRequestAsync(JSON.stringify(publicKey));
  return JSON.parse(result.authenticationResponseJson) as PasskeyCredential;
}

export function createPasskey(publicKey: Record<string, unknown>): Promise<PasskeyCredential> {
  return createFromOptions(publicKey);
}

export function getPasskey(publicKey: Record<string, unknown>): Promise<PasskeyCredential> {
  return getFromOptions(publicKey);
}
