import { useEffect, useState } from 'react';
import { Animated, Image, StyleSheet, View } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';

import { easing, loops, useReducedMotion } from './motion';

const BRAND_BG = '#0F1214';
const BRAND_DEEP = '#191A1E';

/**
 * Loader de abertura. Fica sobre o mesmo `#0F1214` do splash nativo e usa o
 * wordmark no mesmo tamanho aproximado, evitando salto entre splash e app.
 *
 * O gradiente é um cross-fade lento entre duas camadas de `LinearGradient`.
 * Apenas opacidade é animada; com redução de movimento (interna ou do sistema)
 * o fundo fica estático.
 *
 * A paleta do loader é neutra: sem vermelho vazado/glow de marca, separação
 * feita por superfície chapada.
 */
export function BrandLoader() {
  const reduceMotion = useReducedMotion();
  const [fade] = useState(() => new Animated.Value(0));

  useEffect(() => {
    if (reduceMotion) {
      fade.stopAnimation();
      fade.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(fade, {
          toValue: 1,
          duration: loops.brand / 2,
          easing: easing.loop,
          useNativeDriver: true,
        }),
        Animated.timing(fade, {
          toValue: 0,
          duration: loops.brand / 2,
          easing: easing.loop,
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [fade, reduceMotion]);

  return (
    <View style={styles.root}>
      <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" preserveAspectRatio="none">
        <Defs>
          <LinearGradient id="brand-base" x1="0" y1="0" x2="1" y2="1">
            <Stop offset="0" stopColor={BRAND_BG} />
            <Stop offset="0.58" stopColor="#141519" />
            <Stop offset="1" stopColor={BRAND_DEEP} />
          </LinearGradient>
        </Defs>
        <Rect width="100%" height="100%" fill="url(#brand-base)" />
      </Svg>
      <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, { opacity: fade }]}>
        <Svg width="100%" height="100%" preserveAspectRatio="none">
          <Defs>
            <LinearGradient id="brand-glow" x1="1" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={BRAND_DEEP} />
              <Stop offset="0.48" stopColor="#131418" />
              <Stop offset="1" stopColor={BRAND_BG} />
            </LinearGradient>
          </Defs>
          <Rect width="100%" height="100%" fill="url(#brand-glow)" />
        </Svg>
      </Animated.View>
      <Image
        source={require('../../assets/brand/JOGA-wordmark.png')}
        style={styles.wordmark}
        resizeMode="contain"
        accessibilityRole="image"
        accessibilityLabel="JOGA"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: BRAND_BG,
    alignItems: 'center',
    justifyContent: 'center',
  },
  wordmark: {
    width: 198,
    height: (198 * 183) / 687,
  },
});
