import { useEffect, useRef } from 'react';
import { AppState } from 'react-native';

/**
 * Intervalo pausado automaticamente quando o app vai para segundo plano.
 *
 * O callback roda **imediatamente** ao habilitar e ao voltar do background:
 * o cronômetro não pode esperar o primeiro `setInterval` para sair de 00:00.
 */
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
    const tick = () => latest.current();
    const start = () => {
      // Tick imediato: cobre o mount, a habilitação e o retorno do background.
      tick();
      if (timer) {
        return;
      }
      timer = setInterval(tick, milliseconds);
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
