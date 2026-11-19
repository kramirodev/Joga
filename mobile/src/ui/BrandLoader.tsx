import { useEffect, useState } from 'react';
import { AccessibilityInfo, Animated, Easing, Image, StyleSheet, View } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';

const BRAND_BG = '#0F1214';
const BRAND_GLOW = '#2A1214';
const CYCLE_MS = 10_000;

/**
 * Loader de abertura. Fica sobre o mesmo `#0F1214` do splash nativo e usa o
 * wordmark no mesmo tamanho aproximado, evitando salto entre splash e app.
 *
 * O gradiente é um cross-fade lento entre duas camadas de `LinearGradient`.
 * Apenas opacidade é animada; com redução de movimento o fundo fica estático.
 */
export function BrandLoader() {
  const [reduceMotion, setReduceMotion] = useState<boolean | null>(null);
  const [fade] = useState(() => new Animated.Value(0));

  useEffect(() => {
    let active = true;
    AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (active) {
        setReduceMotion(enabled);
      }
    });
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);
    return () => {
      active = false;
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    if (reduceMotion !== false) {
      fade.stopAnimation();
      fade.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(fade, {
          toValue: 1,
          duration: CYCLE_MS / 2,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(fade, {
          toValue: 0,
          duration: CYCLE_MS / 2,
          easing: Easing.inOut(Easing.sin),
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
            <Stop offset="0.58" stopColor="#171216" />
            <Stop offset="1" stopColor={BRAND_GLOW} />
          </LinearGradient>
        </Defs>
        <Rect width="100%" height="100%" fill="url(#brand-base)" />
      </Svg>
      <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, { opacity: fade }]}>
        <Svg width="100%" height="100%" preserveAspectRatio="none">
          <Defs>
            <LinearGradient id="brand-glow" x1="1" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={BRAND_GLOW} />
              <Stop offset="0.48" stopColor="#1F1216" />
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
