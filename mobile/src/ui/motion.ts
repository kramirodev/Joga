import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, Easing } from 'react-native';

import { useTheme } from '../state/context';

/**
 * Fonte única do movimento do JOGA.
 *
 * Regras:
 * - só `transform` e `opacity`, sempre com `useNativeDriver: true`;
 * - nada acima de 320 ms, exceto loops de espera;
 * - com redução de movimento, nenhuma transição passa de 100 ms e nenhum loop
 *   roda (`motionDuration` + checagem de `reduceMotion`).
 */
export const duration = {
  instant: 0,
  fast: 120,
  base: 180,
  medium: 240,
  slow: 320,
} as const;

export const easing = {
  /** Curva padrão do produto. */
  standard: Easing.bezier(0.2, 0, 0, 1),
  enter: Easing.out(Easing.cubic),
  exit: Easing.in(Easing.cubic),
  loop: Easing.inOut(Easing.quad),
} as const;

/** Deslocamentos em dp para entradas; a tela cheia continua usando a largura. */
export const distance = {
  nudge: 4,
  enter: 8,
  toast: 12,
} as const;

export const scale = {
  /** Feedback de toque. */
  press: 0.97,
  button: 0.985,
  card: 0.994,
  chip: 0.98,
  iconButton: 0.94,
  /** Pico ao selecionar um chip/segmento. */
  selected: 0.98,
  /** Aba ativa: nunca acima de 1.06. */
  tabIcon: 1.06,
} as const;

/** Spring da tab bar: baixa velocidade e sem oscilação. */
export const spring = {
  speed: 18,
  bounciness: 0,
} as const;

/** Loops de espera (os únicos permitidos acima de 320 ms). */
export const loops = {
  pulse: 620,
  brand: 10_000,
} as const;

/** Dwells que não são animação, mas precisam do mesmo dono. */
export const dwell = {
  skeleton: 120,
  toast: 2_000,
} as const;

export const reduced = {
  /** Único movimento permitido com redução: crossfade curto de opacidade. */
  crossfade: 100,
  /** Opacidade estática de skeletons/pulsos com redução ligada. */
  pulseOpacity: 0.6,
} as const;

/**
 * Duração efetiva de uma transição. Com redução, translações são removidas no
 * chamador e o que resta é um crossfade de no máximo 100 ms.
 */
export function motionDuration(ms: number, reduceMotion: boolean): number {
  if (!reduceMotion) {
    return ms;
  }
  return ms <= 0 ? 0 : Math.min(ms, reduced.crossfade);
}

/** Preferência do sistema, com listener. Desconhecido conta como reduzido. */
export function useSystemReducedMotion(): boolean {
  const [systemReduced, setSystemReduced] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((value) => {
        if (active) {
          setSystemReduced(value);
        }
      })
      .catch(() => {
        if (active) {
          // Sem resposta, assume que pode animar: não deixa o app sem feedback.
          setSystemReduced(false);
        }
      });
    const subscription = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      setSystemReduced,
    );
    return () => {
      active = false;
      subscription.remove();
    };
  }, []);

  // Enquanto o sistema não respondeu, trata como reduzido para não iniciar loop.
  return systemReduced !== false;
}

/** Combinação explícita das duas preferências: interna ou sistema. */
export function combineReducedMotion(internal: boolean, system: boolean): boolean {
  return internal || system;
}

/**
 * Preferência efetiva dentro do app. O `Shell` combina a preferência interna
 * com `AccessibilityInfo` e publica no `ThemeContext`; componentes leem daqui
 * para não registrar um listener por botão.
 */
export function useReducedMotion(): boolean {
  return useTheme().reducedMotion;
}

/**
 * Pulso de seleção: o chip/segmento que passa a selecionado cresce de 0.98
 * para 1 em 120 ms. Com redução, o valor fica em 1 (sem animação).
 */
export function useSelectionScale(selected: boolean): Animated.Value {
  const reduceMotion = useReducedMotion();
  const [value] = useState(() => new Animated.Value(1));
  const wasSelected = useRef(selected);

  useLayoutEffect(() => {
    if (wasSelected.current === selected) {
      return;
    }
    wasSelected.current = selected;
    if (!selected) {
      value.setValue(1);
      return;
    }
    if (reduceMotion) {
      value.setValue(1);
      return;
    }
    value.setValue(scale.selected);
    const animation = Animated.timing(value, {
      toValue: 1,
      duration: duration.fast,
      easing: easing.enter,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [reduceMotion, selected, value]);

  return value;
}
