import { SvgXml } from 'react-native-svg';

import { themeArtXml, type ThemeArtKey } from './themeArt';

/**
 * Arte do tema como fundo decorativo. O XML já vem preparado pelo gerador
 * (`scripts/generate-theme-art.mjs`): classes embutidas e ids prefixados.
 * `slice` cobre o cartão sem distorcer a proporção original.
 */
export function ThemeArt({ art }: { art: ThemeArtKey }) {
  return (
    <SvgXml
      xml={themeArtXml[art]}
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMid slice"
    />
  );
}
