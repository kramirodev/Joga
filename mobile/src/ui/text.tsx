import { StyleSheet, Text as NativeText, type TextProps, type TextStyle } from 'react-native';

import { useTheme } from '../state/context';

/**
 * Texto do app com a escala de acessibilidade aplicada.
 *
 * Todo texto com `fontSize` explícito é multiplicado pela preferência
 * A/AA/AAA. Estilos sem tamanho explícito continuam herdando do pai.
 */
export function Text({ style, ...props }: TextProps) {
  const { fontScale } = useTheme();
  const flat = StyleSheet.flatten(style) as TextStyle | undefined;
  if (fontScale === 1 || !flat || typeof flat.fontSize !== 'number') {
    return <NativeText {...props} style={style} />;
  }
  const scaled: TextStyle = {
    ...flat,
    fontSize: Math.round(flat.fontSize * fontScale * 10) / 10,
    ...(typeof flat.lineHeight === 'number'
      ? { lineHeight: Math.round(flat.lineHeight * fontScale * 10) / 10 }
      : null),
  };
  return <NativeText {...props} style={scaled} />;
}
