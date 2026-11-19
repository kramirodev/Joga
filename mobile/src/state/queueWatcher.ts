import { useEffect, useRef } from 'react';
import { AppState } from 'react-native';

const QUEUE_POLL_MS = 5000;

let owner: symbol | null = null;
let timer: ReturnType<typeof setInterval> | null = null;
let appSub: { remove(): void } | null = null;
let pollRef: (() => void) | null = null;

function stopTimer() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

function startTimer() {
  if (timer || !pollRef) {
    return;
  }
  timer = setInterval(() => pollRef?.(), QUEUE_POLL_MS);
}

/**
 * Uma única inscrição de polling de fila para o app inteiro. Fica pausada
 * quando o app não está em primeiro plano e é removida no unmount ou quando
 * o modo da fila muda.
 */
export function useQueueWatcher(poll: () => void, enabled: boolean, scope = 'default'): void {
  const latest = useRef(poll);

  useEffect(() => {
    latest.current = poll;
  }, [poll]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    if (owner) {
      if (__DEV__) {
        console.warn('useQueueWatcher: já existe um poller ativo; inscrição ignorada.');
      }
      return;
    }
    const id = Symbol(`queue-watcher:${scope}`);
    owner = id;
    pollRef = () => latest.current();
    appSub = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        startTimer();
      } else {
        stopTimer();
      }
    });
    if (AppState.currentState !== 'background') {
      startTimer();
    }
    return () => {
      if (owner !== id) {
        return;
      }
      owner = null;
      pollRef = null;
      stopTimer();
      appSub?.remove();
      appSub = null;
    };
  }, [enabled, scope]);
}
