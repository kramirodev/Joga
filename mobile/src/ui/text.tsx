import { StyleSheet, Text as NativeText, type TextProps, type TextStyle } from 'react-native';

import { useTheme } from '../state/context';
import { fontFamilyForWeight } from './theme';

/**
 * Texto do app com a escala de acessibilidade aplicada.
 *
 * Todo texto com `fontSize` explícito é multiplicado pela preferência
 * A/AA/AAA. Estilos sem tamanho explícito continuam herdando do pai.
 */
export function Text({ style, ...props }: TextProps) {
  const { fontScale } = useTheme();
  const flat = StyleSheet.flatten(style) as TextStyle | undefined;
  // O peso já é escolhido pelo arquivo Selawik correto; mantemos `normal`
  // para o Android não sintetizar um segundo negrito.
  const font: TextStyle = {
    fontFamily: flat?.fontFamily ?? fontFamilyForWeight(flat?.fontWeight),
    fontWeight: 'normal',
  };
  if (fontScale === 1 || !flat || typeof flat.fontSize !== 'number') {
    return <NativeText {...props} style={[style, font]} />;
  }
  const scaled: TextStyle = {
    fontSize: Math.round(flat.fontSize * fontScale * 10) / 10,
    ...(typeof flat.lineHeight === 'number'
      ? { lineHeight: Math.round(flat.lineHeight * fontScale * 10) / 10 }
      : null),
  };
  return <NativeText {...props} style={[style, font, scaled]} />;
}
