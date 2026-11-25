import { Image, type ImageSourcePropType } from 'react-native';

import type { ThemeArtKey } from './themes';

/**
 * Arte do tema rasterizada (PNG 1200×900). O SVG com gradientes/máscaras não
 * renderizava de forma confiável no Android dentro do `SvgXml`; o PNG usa o
 * pipeline de imagem normal e cobre o cartão com `resizeMode="cover"`.
 */
const THEME_IMAGES: Record<ThemeArtKey, ImageSourcePropType> = {
  'noite-quadra': require('../../assets/themes/noite-quadra.png'),
  'golden-hour': require('../../assets/themes/golden-hour.png'),
  'dia-de-jogo': require('../../assets/themes/dia-de-jogo.png'),
  'ceu-vermelho': require('../../assets/themes/ceu-vermelho.png'),
  'ceu-claro': require('../../assets/themes/ceu-claro.png'),
};

export function ThemeArt({ art }: { art: ThemeArtKey }) {
  return (
    <Image
      source={THEME_IMAGES[art]}
      resizeMode="cover"
      accessible={false}
      style={{ width: '100%', height: '100%' }}
    />
  );
}
