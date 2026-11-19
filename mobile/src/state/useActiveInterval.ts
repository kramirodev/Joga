import { useEffect, useRef } from 'react';
import { AppState } from 'react-native';

/** Intervalo pausado automaticamente quando o app vai para segundo plano. */
export function useActiveInterval(
  callback: () => void,
  milliseconds: number,
  enabled = true,
): void {
  const latest = useRef(callback);

  useEffect(() => {
    latest.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    let timer: ReturnType<typeof setInterval> | null = null;
    const start = () => {
      if (timer) {
        return;
      }
      timer = setInterval(() => latest.current(), milliseconds);
    };
    const stop = () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    };
    if (AppState.currentState !== 'background') {
      start();
    }
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        start();
      } else {
        stop();
      }
    });
    return () => {
      stop();
      subscription.remove();
    };
  }, [enabled, milliseconds]);
}
