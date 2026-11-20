import { useEffect, useRef } from 'react';
import { AppState } from 'react-native';

import { nextPollDelay } from './queueState';

const POLL_MS = 5_000;

/**
 * Único poller global da fila. Ativo enquanto houver entradas `waiting`,
 * pausado em segundo plano, com poll imediato no foreground e backoff
 * 5 → 10 → 20 → 30 s em falha. Um dono por app (montado no `AppProvider`).
 */
export function useQueueWatcher(poll: () => Promise<void>, enabled: boolean): void {
  const latest = useRef(poll);

  useEffect(() => {
    latest.current = poll;
  }, [poll]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    let timer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;
    let running = false;
    let failures = 0;

    const clear = () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const schedule = (delay: number) => {
      clear();
      if (cancelled || AppState.currentState === 'background') {
        return;
      }
      timer = setTimeout(run, delay);
    };

    const run = async () => {
      if (cancelled || running) {
        return;
      }
      running = true;
      try {
        await latest.current();
        failures = 0;
      } catch {
        failures += 1;
      } finally {
        running = false;
        schedule(failures === 0 ? POLL_MS : nextPollDelay(failures));
      }
    };

    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        failures = 0;
        void run();
      } else {
        clear();
      }
    });

    if (AppState.currentState !== 'background') {
      void run();
    }

    return () => {
      cancelled = true;
      clear();
      subscription.remove();
    };
  }, [enabled]);
}
