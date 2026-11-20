import type { QueueCourtPreference, QueueMode } from '../api/types';

export type { QueueCourtPreference, QueueMode };

export type QueueIntent = {
  mode: QueueMode;
  formatId?: string;
  courtPreference: QueueCourtPreference;
};

let pending: QueueIntent | null = null;

/** Guarda a intenção de entrar na fila enquanto o perfil é completado. */
export function setPendingQueueIntent(intent: QueueIntent): void {
  pending = intent;
}

export function peekPendingQueueIntent(): QueueIntent | null {
  return pending;
}

/** Consome a intenção uma única vez, evitando enqueue duplicado. */
export function consumePendingQueueIntent(): QueueIntent | null {
  const current = pending;
  pending = null;
  return current;
}
