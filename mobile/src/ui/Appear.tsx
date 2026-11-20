import { useEffect, useState, type PropsWithChildren } from 'react';
import { Animated, type StyleProp, type ViewStyle } from 'react-native';

import { distance, duration, easing, motionDuration, useReducedMotion } from './motion';

/**
 * Entrada padrão de conteúdo: fade + 8 dp para cima em 180 ms. Com redução de
 * movimento, vira um crossfade de 100 ms e o deslocamento é removido.
 *
 * Use em blocos que aparecem/desaparecem por completo (estado vazio, estado de
 * erro, primeira lista confirmada). Não use em itens de lista grandes.
 */
export function Appear({
  children,
  style,
  travel = distance.enter,
  trigger,
}: PropsWithChildren<{
  style?: StyleProp<ViewStyle>;
  /** Deslocamento em dp; 0 deixa só o fade. */
  travel?: number;
  /** Muda o valor para replay da entrada quando o conteúdo confirmado troca. */
  trigger?: string | number | null;
}>) {
  const reduceMotion = useReducedMotion();
  const [progress] = useState(() => new Animated.Value(0));

  useEffect(() => {
    progress.setValue(0);
    const animation = Animated.timing(progress, {
      toValue: 1,
      duration: motionDuration(duration.base, reduceMotion),
      easing: easing.enter,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [progress, reduceMotion, trigger]);

  const transform =
    reduceMotion || travel === 0
      ? undefined
      : [
          {
            translateY: progress.interpolate({
              inputRange: [0, 1],
              outputRange: [travel, 0],
            }),
          },
        ];

  return (
    <Animated.View style={[{ opacity: progress, transform }, style]}>{children}</Animated.View>
  );
}
