import { useEffect, useState } from 'react';
import { Animated, type StyleProp, type ViewStyle } from 'react-native';

import { easing, loops, reduced, useReducedMotion } from './motion';

/**
 * Ponto de "aguardando" da fila. Só opacidade, com `useNativeDriver`, e o loop
 * é parado no unmount ou quando a redução de movimento está ligada (aí fica
 * estático a 60%, que ainda comunica estado sem piscar).
 */
export function PulseDot({
  color,
  size = 8,
  active = true,
  style,
}: {
  color: string;
  size?: number;
  active?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const reduceMotion = useReducedMotion();
  const [pulse] = useState(() => new Animated.Value(0));

  useEffect(() => {
    if (!active || reduceMotion) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: loops.pulse,
          easing: easing.loop,
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: loops.pulse,
          easing: easing.loop,
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [active, pulse, reduceMotion]);

  return (
    <Animated.View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: color,
          opacity: reduceMotion
            ? reduced.pulseOpacity
            : pulse.interpolate({ inputRange: [0, 1], outputRange: [0.45, 1] }),
        },
        style,
      ]}
    />
  );
}
