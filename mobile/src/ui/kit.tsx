import type { PropsWithChildren, ReactNode, Ref } from 'react';
import {
  Children,
  createContext,
  isValidElement,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import {
  Animated,
  KeyboardAvoidingView,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
  type StyleProp,
  type TextInputInstance,
  type TextInputProps,
  type TextStyle,
  type ViewStyle,
  type ScrollViewInstance,
} from 'react-native';
import Svg, {
  Circle as SvgCircle,
  Path as SvgPath,
  Polyline as SvgPolyline,
  Rect as SvgRect,
  Text as SvgText,
} from 'react-native-svg';

import type { VisualIdentity } from '../api/types';
import { useNav, useTheme } from '../state/context';
import { Appear } from './Appear';
import { BottomSheetFrame as SheetFrame, useSheetClose } from './BottomSheetFrame';
import { IdentityBadge } from './IdentityBadge';
import { Icon, type IconName } from './icons';
import {
  duration,
  dwell,
  easing,
  loops,
  motionDuration,
  reduced,
  scale,
  useReducedMotion,
  useSelectionScale,
} from './motion';
import { Text } from './text';
import { space, type, type TextVariant } from './theme';

type ColorToken = 'ink' | 'soft' | 'onInk' | 'softOnInk' | 'lime' | 'limeDeep' | 'white' | 'red';

export function Txt({
  children,
  variant = 'sub',
  color,
  weight,
  align,
  numberOfLines,
  adjustsFontSizeToFit,
  minimumFontScale,
  style,
}: PropsWithChildren<{
  variant?: TextVariant;
  color?: ColorToken;
  weight?: TextStyle['fontWeight'];
  align?: TextStyle['textAlign'];
  numberOfLines?: number;
  adjustsFontSizeToFit?: boolean;
  minimumFontScale?: number;
  style?: StyleProp<TextStyle>;
}>) {
  const { palette } = useTheme();
  const tokens: Record<ColorToken, string> = {
    ink: palette.ink,
    soft: palette.muted,
    onInk: palette.onInk,
    softOnInk: palette.softOnInk,
    lime: palette.lime,
    limeDeep: palette.limeDeep,
    white: '#F1F3F0',
    red: palette.red,
  };
  const softByDefault: TextVariant[] = ['lead', 'sub', 'tiny', 'topbarSub'];
  const spec = type[variant];
  const flat = StyleSheet.flatten(style) as TextStyle | undefined;
  const size = flat?.fontSize ?? spec.fontSize;
  const line = flat?.lineHeight ?? (flat?.fontSize ? Math.round(size * 1.02) : spec.lineHeight);
  return (
    <Text
      numberOfLines={numberOfLines}
      adjustsFontSizeToFit={adjustsFontSizeToFit}
      minimumFontScale={minimumFontScale}
      maxFontSizeMultiplier={1.3}
      style={[
        {
          fontSize: size,
          lineHeight: line,
          letterSpacing: spec.letterSpacing,
          fontWeight: weight ?? spec.fontWeight,
          textTransform: spec.uppercase ? 'uppercase' : 'none',
          color: tokens[color ?? (softByDefault.includes(variant) ? 'soft' : 'ink')],
          includeFontPadding: false,
        },
        variant === 'num' ? { fontVariant: ['tabular-nums'] } : null,
        align ? { textAlign: align } : null,
        style,
      ]}
    >
      {children}
    </Text>
  );
}

export function B({ children }: PropsWithChildren) {
  const { palette } = useTheme();
  return <Text style={{ fontWeight: '800', color: palette.ink }}>{children}</Text>;
}

export function Row({
  children,
  between,
  wrap,
  top,
  gap,
  style,
}: PropsWithChildren<{
  between?: boolean;
  wrap?: boolean;
  top?: boolean;
  gap?: number;
  style?: StyleProp<ViewStyle>;
}>) {
  return (
    <View
      style={[
        { flexDirection: 'row', alignItems: 'center', gap: 10 },
        between ? { justifyContent: 'space-between' } : null,
        wrap ? { flexWrap: 'wrap' } : null,
        top ? { alignItems: 'flex-start' } : null,
        gap !== undefined ? { gap } : null,
        style,
      ]}
    >
      {children}
    </View>
  );
}

export function Col({
  children,
  gap,
  style,
}: PropsWithChildren<{ gap?: number; style?: StyleProp<ViewStyle> }>) {
  return <View style={[{ flexDirection: 'column', gap: gap ?? 10 }, style]}>{children}</View>;
}

type CardTone = 'surface' | 'flat' | 'ink' | 'lime' | 'blue' | 'green' | 'orange' | 'red';

export function Card({
  children,
  tone = 'surface',
  padding = space.card,
  onPress,
  style,
  accessibilityLabel,
}: PropsWithChildren<{
  tone?: CardTone;
  padding?: number;
  onPress?: () => void;
  style?: StyleProp<ViewStyle>;
  accessibilityLabel?: string;
}>) {
  const { palette, dark } = useTheme();
  // Contêiner estático usa `lineSubtle` (visível sem competir com interativo);
  // card clicável usa `lineStrong`. No claro os três tokens têm o mesmo pixel.
  const outline = onPress ? palette.lineStrong : palette.lineSubtle;
  const toneStyle: Record<CardTone, ViewStyle> = {
    surface: { backgroundColor: palette.surface, borderColor: outline },
    flat: {
      backgroundColor: palette.surface2,
      borderColor: dark ? palette.lineSubtle : palette.surface2,
    },
    ink: { backgroundColor: dark ? palette.surface2 : palette.ink, borderColor: outline },
    lime: { backgroundColor: palette.limeSoft, borderColor: outline },
    blue: { backgroundColor: palette.blueSoft, borderColor: outline },
    green: { backgroundColor: palette.greenSoft, borderColor: outline },
    orange: { backgroundColor: palette.orangeSoft, borderColor: outline },
    red: { backgroundColor: palette.redSoft, borderColor: outline },
  };
  const cardStyle = [
    {
      borderRadius: space.radius,
      borderWidth: 1.5,
      padding,
      shadowColor: '#17191B',
      // No escuro a separação é o contorno, não sombra/brilho.
      shadowOpacity: dark ? 0 : 0.04,
      shadowRadius: 12,
      shadowOffset: { width: 0, height: 8 },
      elevation: dark ? 0 : 1,
    },
    toneStyle[tone],
    tone === 'flat' ? { shadowOpacity: 0, elevation: 0 } : null,
    style,
  ];

  return (
    <CardToneContext.Provider value={tone}>
      {onPress ? (
        <Pressable
          onPress={onPress}
          accessibilityRole="button"
          accessibilityLabel={accessibilityLabel}
          style={({ pressed }) => [
            cardStyle,
            pressed ? { opacity: 0.9, transform: [{ scale: scale.card }] } : null,
          ]}
        >
          {children}
        </Pressable>
      ) : (
        <View style={cardStyle}>{children}</View>
      )}
    </CardToneContext.Provider>
  );
}

type BadgeTone = 'default' | 'lime' | 'blue' | 'green' | 'orange' | 'red' | 'ink';

export function Badge({ children, tone = 'default' }: PropsWithChildren<{ tone?: BadgeTone }>) {
  const { palette, dark } = useTheme();
  let bg = palette.surface2;
  let border = dark ? palette.lineSubtle : palette.line;
  let color = palette.ink;
  if (tone === 'lime') {
    bg = dark ? palette.surface2 : palette.ink;
    border = dark ? palette.lineSubtle : palette.ink;
    // Marca como texto pequeno sobre superfície escura exige `brandStrong`.
    color = dark ? palette.brandStrong : palette.lime;
  } else if (tone === 'ink') {
    bg = dark ? palette.surface2 : palette.ink;
    border = dark ? palette.lineSubtle : palette.ink;
    color = dark ? palette.brandStrong : palette.onInk;
  } else if (tone !== 'default') {
    bg = palette.surface2;
    border = palette.lineSubtle;
    // Semânticos têm papel próprio: não viram vermelho de marca.
    color = dark
      ? tone === 'blue'
        ? palette.info
        : tone === 'green'
          ? palette.success
          : tone === 'orange'
            ? palette.warning
            : palette.danger
      : palette.ink;
  }
  return (
    <View
      style={{
        alignSelf: 'flex-start',
        backgroundColor: bg,
        borderColor: border,
        borderWidth: 1,
        borderRadius: 5,
        paddingHorizontal: 7,
        paddingVertical: 4,
      }}
    >
      <Text
        style={{
          fontSize: 10.5,
          lineHeight: 11,
          fontWeight: '800',
          letterSpacing: 0.6,
          textTransform: 'uppercase',
          color,
        }}
      >
        {children}
      </Text>
    </View>
  );
}

export function CardHeader({
  title,
  badge,
  variant = 'h3',
  icon,
}: {
  title: string;
  badge?: ReactNode;
  variant?: 'h3' | 'label' | 'tiny';
  icon?: ReactNode;
}) {
  return (
    <View
      style={{
        flexDirection: 'row',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <View
        style={{
          flexGrow: 1,
          flexShrink: 1,
          flexBasis: '55%',
          minWidth: 0,
          flexDirection: 'row',
          alignItems: 'center',
          gap: 6,
        }}
      >
        {icon}
        <Txt
          variant={variant}
          numberOfLines={2}
          adjustsFontSizeToFit
          minimumFontScale={0.8}
          style={{ flexShrink: 1, minWidth: 0 }}
        >
          {title}
        </Txt>
      </View>
      {badge ? <View style={{ flexShrink: 0, marginLeft: 'auto' }}>{badge}</View> : null}
    </View>
  );
}

export function SystemNotice({ children }: PropsWithChildren) {
  const { palette } = useTheme();
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: 8,
        borderWidth: 1.5,
        borderColor: palette.lineSubtle,
        borderRadius: 14,
        backgroundColor: palette.surface2,
        paddingHorizontal: 13,
        paddingVertical: 12,
      }}
    >
      <Badge>SISTEMA</Badge>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 13, lineHeight: 19, color: palette.inkSoft }}>{children}</Text>
      </View>
    </View>
  );
}

export function Pill({ children, icon }: PropsWithChildren<{ icon?: IconName }>) {
  const { palette } = useTheme();
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
        borderWidth: 1.5,
        borderColor: palette.lineSubtle,
        backgroundColor: palette.surface,
        borderRadius: 999,
        paddingHorizontal: 11,
        paddingVertical: 7,
      }}
    >
      {icon ? <Icon name={icon} size={16} color={palette.ink} /> : null}
      <Text style={{ fontSize: 12.5, lineHeight: 13, fontWeight: '700', color: palette.ink }}>
        {children}
      </Text>
    </View>
  );
}

export function Progress({ value, tone }: { value: number; tone?: string }) {
  const { palette } = useTheme();
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <View
      style={{
        height: 14,
        borderWidth: 1.5,
        borderColor: palette.lineSubtle,
        borderRadius: 999,
        backgroundColor: palette.progressTrack,
        overflow: 'hidden',
      }}
    >
      <View
        style={{
          height: '100%',
          width: `${clamped}%`,
          backgroundColor: palette.lime,
          borderRightWidth: clamped > 0 ? 1.5 : 0,
          borderRightColor: palette.line,
        }}
      />
    </View>
  );
}

export function Meter({ value, total = 5 }: { value: number; total?: number }) {
  const { palette } = useTheme();
  return (
    <View style={{ flexDirection: 'row', gap: 4 }}>
      {Array.from({ length: total }, (_, index) => (
        <View
          key={index}
          style={{
            flex: 1,
            height: 9,
            borderRadius: 2,
            borderWidth: 1,
            backgroundColor: index < value ? palette.lime : palette.progressTrack,
            borderColor: index < value ? palette.lime : palette.line,
          }}
        />
      ))}
    </View>
  );
}

type ActionProps = {
  go?: string;
  back?: boolean;
  modal?: string;
  toast?: string;
  disabled?: boolean;
};

function useAction() {
  const nav = useNav();
  return (action: ActionProps, onPress?: () => void) => {
    if (action.disabled) {
      return;
    }
    if (action.go) {
      nav.go(action.go);
      return;
    }
    if (action.back) {
      nav.back();
      return;
    }
    if (action.modal) {
      nav.openModal(action.modal);
      return;
    }
    if (action.toast) {
      nav.toast(action.toast);
      return;
    }
    onPress?.();
  };
}

const BtnRowContext = createContext(false);
const CardToneContext = createContext<CardTone>('surface');

export function Btn({
  children,
  tone = 'default',
  icon,
  small,
  block,
  onPress,
  ...action
}: PropsWithChildren<
  ActionProps & {
    tone?: 'default' | 'primary' | 'ghost' | 'soft' | 'danger';
    icon?: IconName;
    small?: boolean;
    block?: boolean;
    onPress?: () => void;
  }
>) {
  const { palette, dark, largeTargets } = useTheme();
  const run = useAction();
  const inRow = useContext(BtnRowContext);
  const cardTone = useContext(CardToneContext);
  const ghostOutline =
    tone === 'ghost' &&
    ((dark && cardTone === 'ink') ||
      cardTone === 'lime' ||
      cardTone === 'blue' ||
      cardTone === 'green' ||
      cardTone === 'orange' ||
      cardTone === 'red');
  const textColor =
    action.disabled && dark
      ? palette.muted
      : tone === 'primary' || tone === 'danger'
        ? dark
          ? palette.brandInk
          : '#F1F3F0'
        : tone === 'ghost' || tone === 'soft'
          ? palette.ink
          : dark
            ? palette.bg
            : palette.onInk;
  let backgroundColor = palette.ink;
  let borderColor: string = palette.lineStrong;
  if (tone === 'primary') {
    backgroundColor = palette.lime;
    borderColor = dark ? palette.lime : palette.lineStrong;
  } else if (tone === 'ghost') {
    backgroundColor = palette.surface2;
    borderColor = dark ? palette.lineStrong : ghostOutline ? palette.lime : 'transparent';
  } else if (tone === 'soft') {
    backgroundColor = dark ? palette.surface3 : palette.surface2;
    borderColor = dark ? palette.lineStrong : palette.surface3;
  } else if (tone === 'danger') {
    backgroundColor = palette.red;
    borderColor = palette.red;
  }
  // Desabilitado no escuro não usa opacidade (que apaga o texto): vira uma
  // placa neutra com contorno, mantendo o texto legível e a geometria.
  const disabledNeutral = !!action.disabled && dark;
  return (
    <Pressable
      disabled={action.disabled}
      onPress={() => run(action, onPress)}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!action.disabled }}
      style={({ pressed }) => ({
        width: inRow ? undefined : block ? '100%' : small ? undefined : '100%',
        flex: inRow ? 1 : undefined,
        // Fora de `BtnRow` o botão mantém a largura do rótulo: sem isto, um
        // nome em duas linhas espreme o texto e corta "Adicionar" na linha.
        flexShrink: inRow ? 1 : 0,
        minHeight: largeTargets ? (small ? 54 : 60) : small ? 46 : 52,
        borderRadius: small ? 11 : 14,
        borderWidth: 1.5,
        borderColor: disabledNeutral ? palette.lineStrong : borderColor,
        backgroundColor: disabledNeutral ? palette.surface3 : backgroundColor,
        opacity: action.disabled ? (dark ? 1 : 0.38) : pressed ? 0.92 : 1,
        transform: pressed && !action.disabled ? [{ scale: scale.button }] : [],
        paddingHorizontal: small ? 14 : 16,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 9,
      })}
    >
      {icon ? <Icon name={icon} size={18} color={textColor} /> : null}
      <Text
        numberOfLines={2}
        adjustsFontSizeToFit
        minimumFontScale={0.8}
        maxFontSizeMultiplier={1.2}
        style={{
          flexShrink: 1,
          fontSize: small ? 14 : 15,
          lineHeight: small ? 18 : 20,
          fontWeight: '800',
          letterSpacing: 0.1,
          color: textColor,
          textAlign: 'center',
        }}
      >
        {children}
      </Text>
    </Pressable>
  );
}

export function BtnRow({ children }: PropsWithChildren) {
  return (
    <BtnRowContext.Provider value>
      <View style={{ flexDirection: 'row', gap: 10 }}>{children}</View>
    </BtnRowContext.Provider>
  );
}

export function TextBtn({
  children,
  muted,
  onPress,
  ...action
}: PropsWithChildren<ActionProps & { muted?: boolean; onPress?: () => void }>) {
  const { palette, largeTargets } = useTheme();
  const run = useAction();
  return (
    <Pressable
      disabled={action.disabled}
      onPress={() => run(action, onPress)}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!action.disabled }}
      hitSlop={{ top: 4, bottom: 4, left: 8, right: 8 }}
      style={({ pressed }) => ({
        minHeight: largeTargets ? 56 : 48,
        justifyContent: 'center',
        paddingHorizontal: 2,
        opacity: action.disabled ? 0.38 : pressed ? 0.62 : 1,
        transform: pressed && !action.disabled ? [{ scale: scale.press }] : [],
      })}
    >
      <Text
        style={{
          flexShrink: 1,
          fontSize: 14,
          lineHeight: 18,
          fontWeight: muted ? '700' : '800',
          color: muted ? palette.muted : palette.ink,
          textDecorationLine: 'underline',
        }}
      >
        {children}
      </Text>
    </Pressable>
  );
}

export function IconBtn({
  icon,
  label,
  plain,
  ink,
  onPress,
  expanded,
  ...action
}: ActionProps & {
  icon: IconName;
  label: string;
  plain?: boolean;
  ink?: boolean;
  onPress?: () => void;
  /** Estado de painel expansível (ex.: seletor de emotes). Aditivo. */
  expanded?: boolean;
}) {
  const { palette, dark, largeTargets } = useTheme();
  const run = useAction();
  let bg = palette.surface;
  let border = palette.lineStrong;
  let color = palette.ink;
  if (plain) {
    bg = 'transparent';
    border = 'transparent';
  }
  if (ink) {
    bg = dark ? palette.lime : palette.ink;
    border = bg;
    color = dark ? palette.brandInk : palette.onInk;
  }
  return (
    <Pressable
      onPress={() => run(action, onPress)}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!action.disabled, expanded: !!expanded }}
      style={({ pressed }) => ({
        width: largeTargets ? 54 : 48,
        height: largeTargets ? 54 : 48,
        flexShrink: 0,
        borderRadius: largeTargets ? 27 : 24,
        borderWidth: 1.5,
        borderColor: border,
        backgroundColor: bg,
        alignItems: 'center',
        justifyContent: 'center',
        opacity: action.disabled ? 0.38 : pressed ? 0.85 : 1,
        transform: pressed && !action.disabled ? [{ scale: scale.iconButton }] : [],
      })}
    >
      <Icon name={icon} size={20} color={color} />
    </Pressable>
  );
}

export function Chip({
  children,
  on,
  tone,
  icon,
  lock,
  go,
  onPress,
  toast,
  accessibilityLabel,
  disabled,
}: PropsWithChildren<{
  on?: boolean;
  tone?: 'lime';
  icon?: IconName;
  lock?: boolean;
  go?: string;
  toast?: string;
  onPress?: () => void;
  accessibilityLabel?: string;
  /** Filtro/bloqueio honesto: continua visível, mas não finge funcionar. */
  disabled?: boolean;
}>) {
  const { palette, dark, largeTargets } = useTheme();
  const nav = useNav();
  const selectionScale = useSelectionScale(!!on);
  let bg = palette.surface;
  let border = palette.lineStrong;
  let color = palette.ink;
  if (on && tone === 'lime') {
    bg = palette.lime;
    border = dark ? palette.lime : palette.ink;
    color = dark ? palette.brandInk : palette.ink;
  } else if (on) {
    bg = dark ? palette.surface3 : palette.ink;
    border = dark ? palette.lime : palette.ink;
    color = dark ? palette.ink : palette.onInk;
  }
  const press = () => {
    if (onPress) {
      onPress();
      return;
    }
    if (go) {
      nav.go(go);
      return;
    }
    if (toast) {
      nav.toast(toast);
    }
  };
  return (
    <Animated.View style={{ transform: [{ scale: selectionScale }] }}>
      <Pressable
        onPress={press}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel}
        accessibilityState={{ selected: !!on, disabled: !!disabled }}
        style={({ pressed }) => ({
          minHeight: largeTargets ? 54 : 48,
          borderRadius: 999,
          borderWidth: 1.5,
          borderColor: border,
          backgroundColor: bg,
          paddingHorizontal: 12,
          paddingVertical: 9,
          flexDirection: 'row',
          alignItems: 'center',
          gap: 6,
          opacity: disabled ? 0.55 : pressed ? 0.9 : 1,
          transform: pressed && !disabled ? [{ scale: scale.chip }] : [],
        })}
      >
        {icon ? <Icon name={icon} size={14} color={color} /> : null}
        <Text style={{ flexShrink: 1, fontSize: 13, lineHeight: 14, fontWeight: '700', color }}>
          {children}
        </Text>
        {lock ? <Icon name="lock" size={14} color={color} /> : null}
      </Pressable>
    </Animated.View>
  );
}

export function ChipRow({ children, style }: PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) {
  return (
    <View style={[{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, style]}>{children}</View>
  );
}

/** Medidas do trilho; o indicador usa as mesmas bordas/padding/gap do container. */
const SEG_BORDER = 1.5;
const SEG_PADDING = 4;
const SEG_GAP = 4;

function segSelectedIndex(children: ReactNode): number {
  const items = Children.toArray(children).filter(isValidElement);
  return Math.max(
    0,
    items.findIndex((child) => !!(child.props as { on?: boolean }).on),
  );
}

/**
 * Seleção única com pílula deslizante. O item selecionado não pinta o próprio
 * fundo: uma única pílula medida por `onLayout` percorre o trilho com
 * `duration.base` (120–240 ms), sempre com `useNativeDriver`.
 *
 * Os `SegBtn` são `flex: 1`, então todos os espaços têm a mesma largura; o
 * indicador acompanha a largura medida do container. Com redução de movimento
 * a pílula salta direto para o destino (troca instantânea permitida).
 */
export function Seg({ children, style }: PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) {
  const { palette, dark } = useTheme();
  const reduceMotion = useReducedMotion();
  const selectedIndex = segSelectedIndex(children);
  const count = Children.toArray(children).filter(isValidElement).length;
  const [containerWidth, setContainerWidth] = useState(0);
  const [slot] = useState(() => new Animated.Value(selectedIndex));

  useLayoutEffect(() => {
    if (reduceMotion) {
      slot.stopAnimation();
      slot.setValue(selectedIndex);
      return;
    }
    const animation = Animated.timing(slot, {
      toValue: selectedIndex,
      duration: duration.base,
      easing: easing.standard,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [reduceMotion, selectedIndex, slot]);

  const innerWidth = Math.max(0, containerWidth - SEG_BORDER * 2 - SEG_PADDING * 2);
  const itemWidth = count > 0 ? Math.max(0, (innerWidth - SEG_GAP * (count - 1)) / count) : 0;
  const step = itemWidth + SEG_GAP;
  const travel = slot.interpolate({
    inputRange: [0, Math.max(1, count - 1)],
    outputRange: [0, step * Math.max(0, count - 1)],
  });

  return (
    <View
      onLayout={(event) => {
        const next = event.nativeEvent.layout.width;
        if (Math.abs(next - containerWidth) > 0.5) {
          setContainerWidth(next);
        }
      }}
      style={[
        {
          flexDirection: 'row',
          backgroundColor: palette.surface2,
          borderWidth: SEG_BORDER,
          borderColor: palette.lineStrong,
          borderRadius: 12,
          padding: SEG_PADDING,
          gap: SEG_GAP,
          position: 'relative',
        },
        style,
      ]}
    >
      {itemWidth > 0.5 ? (
        <Animated.View
          pointerEvents="none"
          style={{
            position: 'absolute',
            top: SEG_BORDER + SEG_PADDING,
            bottom: SEG_BORDER + SEG_PADDING,
            left: SEG_BORDER + SEG_PADDING,
            width: itemWidth,
            borderRadius: 8,
            backgroundColor: dark ? palette.lime : palette.ink,
            // Mesma largura nos dois temas: transparente no claro não pinta.
            borderWidth: 1,
            borderColor: dark ? palette.lime : 'transparent',
            transform: [{ translateX: travel }],
          }}
        />
      ) : null}
      {children}
    </View>
  );
}

export function SegBtn({
  children,
  on,
  go,
  onPress,
}: PropsWithChildren<{ on?: boolean; go?: string; onPress?: () => void }>) {
  const { palette, dark, largeTargets } = useTheme();
  const nav = useNav();
  const selectionScale = useSelectionScale(!!on);
  return (
    <Animated.View style={{ flex: 1, minWidth: 0, transform: [{ scale: selectionScale }] }}>
      <Pressable
        onPress={() => (go ? nav.go(go) : onPress?.())}
        accessibilityRole="button"
        accessibilityState={{ selected: !!on }}
        style={({ pressed }) => ({
          flex: 1,
          minWidth: 0,
          minHeight: largeTargets ? 54 : 48,
          borderRadius: 8,
          paddingHorizontal: 4,
          paddingVertical: 6,
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'transparent',
          opacity: pressed ? 0.88 : 1,
        })}
      >
        <Text
          numberOfLines={1}
          adjustsFontSizeToFit
          minimumFontScale={0.78}
          maxFontSizeMultiplier={1.2}
          style={{
            fontSize: 13,
            lineHeight: 17,
            fontWeight: '800',
            color: on ? (dark ? palette.brandInk : palette.onInk) : palette.muted,
            textAlign: 'center',
          }}
        >
          {children}
        </Text>
      </Pressable>
    </Animated.View>
  );
}

/**
 * Conteúdo que troca junto com um `Seg` sem remontar a tela nem o scroll:
 * o container é o mesmo, os filhos novos entram com fade de `duration.base`.
 * Com redução de movimento a troca é instantânea. Nada de rota, `key` por
 * segmento ou nova árvore.
 */
export function SegContent({
  value,
  children,
  style,
}: PropsWithChildren<{ value: string; style?: StyleProp<ViewStyle> }>) {
  const reduceMotion = useReducedMotion();
  const [opacity] = useState(() => new Animated.Value(1));
  const previous = useRef(value);

  useLayoutEffect(() => {
    const changed = previous.current !== value;
    previous.current = value;
    if (reduceMotion) {
      opacity.stopAnimation();
      opacity.setValue(1);
      return;
    }
    if (!changed) {
      return;
    }
    opacity.stopAnimation();
    opacity.setValue(0.55);
    const animation = Animated.timing(opacity, {
      toValue: 1,
      duration: duration.base,
      easing: easing.enter,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [opacity, reduceMotion, value]);

  return <Animated.View style={[{ gap: space.gap, opacity }, style]}>{children}</Animated.View>;
}

export function Field({ label, children }: PropsWithChildren<{ label: string }>) {
  const { palette } = useTheme();
  return (
    <View style={{ gap: 7 }}>
      <Text
        style={{
          fontSize: 12,
          lineHeight: 16,
          fontWeight: '800',
          letterSpacing: 0.8,
          textTransform: 'uppercase',
          color: palette.muted,
        }}
      >
        {label}
      </Text>
      {children}
    </View>
  );
}

export function Input({
  inputRef,
  ...props
}: TextInputProps & { inputRef?: Ref<TextInputInstance> }) {
  const { palette, dark, largeTargets, fontScale } = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <TextInput
      ref={inputRef}
      {...props}
      maxFontSizeMultiplier={1.3}
      placeholderTextColor={palette.muted}
      onFocus={(event) => {
        setFocused(true);
        props.onFocus?.(event);
      }}
      onBlur={(event) => {
        setFocused(false);
        props.onBlur?.(event);
      }}
      style={[
        {
          width: '100%',
          minHeight: largeTargets ? 58 : 52,
          borderWidth: focused ? 2 : 1.5,
          borderColor: focused ? (dark ? palette.focus : palette.ink) : palette.lineStrong,
          borderRadius: 12,
          backgroundColor: palette.surface,
          paddingHorizontal: focused ? 13.5 : 14,
          paddingVertical: largeTargets ? 16 : 13,
          fontSize: Math.round(14 * fontScale * 10) / 10,
          color: palette.ink,
        },
        props.style,
      ]}
    />
  );
}

export function InputPrefix({ children, input }: PropsWithChildren<{ input: ReactNode }>) {
  const { palette } = useTheme();
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        borderWidth: 1.5,
        borderColor: palette.lineStrong,
        borderRadius: 12,
        backgroundColor: palette.surface,
        overflow: 'hidden',
      }}
    >
      <Text
        style={{
          paddingHorizontal: 12,
          paddingVertical: 14,
          fontWeight: '800',
          color: palette.muted,
          borderRightWidth: 1.5,
          borderRightColor: palette.line,
        }}
      >
        {children}
      </Text>
      <View style={{ flex: 1 }}>{input}</View>
    </View>
  );
}

export function Textarea(props: TextInputProps) {
  return (
    <Input
      {...props}
      multiline
      maxLength={props.maxLength ?? 2000}
      textAlignVertical="top"
      style={{ minHeight: 110 }}
    />
  );
}

export function Select({
  options,
  value,
  onChange,
}: {
  options: string[];
  value?: string;
  onChange?: (value: string) => void;
}) {
  const { palette, largeTargets } = useTheme();
  const [open, setOpen] = useState(false);
  const [internal, setInternal] = useState(value ?? options[0] ?? '');
  const current = value ?? internal;
  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        accessibilityRole="button"
        accessibilityLabel={current}
        style={({ pressed }) => ({
          width: '100%',
          minHeight: largeTargets ? 58 : 52,
          borderWidth: 1.5,
          borderColor: palette.lineStrong,
          borderRadius: 12,
          backgroundColor: palette.surface,
          paddingHorizontal: 14,
          paddingVertical: 13,
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 10,
          opacity: pressed ? 0.9 : 1,
          transform: pressed ? [{ scale: scale.card }] : [],
        })}
      >
        <Text style={{ flexShrink: 1, fontSize: 14, color: palette.ink }}>{current}</Text>
        <Icon name="next" size={16} color={palette.muted} />
      </Pressable>
      <SheetFrame visible={open} onClose={() => setOpen(false)} accessibilityLabel="Escolher opção">
        <SelectOptions
          options={options}
          current={current}
          onSelect={(option) => {
            setInternal(option);
            onChange?.(option);
          }}
        />
      </SheetFrame>
    </>
  );
}

function SelectOptions({
  options,
  current,
  onSelect,
}: {
  options: string[];
  current: string;
  onSelect: (option: string) => void;
}) {
  const { palette, dark } = useTheme();
  const close = useSheetClose();
  return (
    <View>
      {options.map((option) => (
        <Pressable
          key={option}
          accessibilityRole="button"
          accessibilityState={{ selected: option === current }}
          onPress={() => {
            onSelect(option);
            close();
          }}
          style={({ pressed }) => ({
            minHeight: 50,
            justifyContent: 'center',
            paddingVertical: 8,
            borderBottomWidth: 1,
            borderBottomColor: palette.line,
            opacity: pressed ? 0.6 : 1,
          })}
        >
          <Text
            style={{
              fontSize: 15,
              fontWeight: option === current ? '800' : '500',
              color: option === current ? (dark ? palette.brandStrong : palette.lime) : palette.ink,
            }}
          >
            {option}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

export function Check({
  children,
  checked,
  onChange,
  disabled,
}: PropsWithChildren<{
  checked?: boolean;
  onChange?: (value: boolean) => void;
  disabled?: boolean;
}>) {
  const { palette, dark } = useTheme();
  const [internal, setInternal] = useState(!!checked);
  const value = checked === undefined ? internal : checked;
  return (
    <Pressable
      disabled={disabled}
      accessibilityRole="checkbox"
      accessibilityState={{ checked: value, disabled: !!disabled }}
      onPress={() => {
        if (disabled) {
          return;
        }
        if (checked === undefined) {
          setInternal(!internal);
        }
        onChange?.(!value);
      }}
      style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, minHeight: 48 }}
    >
      <View
        style={{
          width: 22,
          height: 22,
          flexShrink: 0,
          marginTop: 1,
          borderRadius: 3,
          borderWidth: 2,
          borderColor: value ? (dark ? palette.brand : palette.ink) : palette.lineStrong,
          backgroundColor: value ? (dark ? palette.brand : palette.ink) : palette.surface,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {value ? (
          <Icon
            name="check"
            size={14}
            color={dark ? palette.brandInk : palette.onInk}
            strokeWidth={2.8}
          />
        ) : null}
      </View>
      <Text style={{ flex: 1, fontSize: 13.5, lineHeight: 20, color: palette.ink }}>
        {children}
      </Text>
    </Pressable>
  );
}

export function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  const { palette, dark } = useTheme();
  return (
    <Pressable
      onPress={() => onChange(!checked)}
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      hitSlop={11}
      style={({ pressed }) => ({
        width: 44,
        height: 44,
        marginVertical: -11,
        marginHorizontal: -11,
        alignItems: 'center',
        justifyContent: 'center',
        opacity: pressed ? 0.8 : 1,
      })}
    >
      <View
        style={{
          width: 22,
          height: 22,
          borderRadius: 3,
          borderWidth: 2,
          borderColor: checked ? (dark ? palette.brand : palette.ink) : palette.lineStrong,
          backgroundColor: checked ? (dark ? palette.brand : palette.ink) : palette.surface,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {checked ? (
          <Icon
            name="check"
            size={14}
            color={dark ? palette.brandInk : palette.onInk}
            strokeWidth={2.8}
          />
        ) : null}
      </View>
    </Pressable>
  );
}

export function Divider({ style }: { style?: StyleProp<ViewStyle> }) {
  const { palette } = useTheme();
  return <View style={[{ height: 1.5, backgroundColor: palette.line }, style]} />;
}

export function Kv({ label, value }: { label: ReactNode; value: ReactNode }) {
  const { palette } = useTheme();
  return (
    <View
      style={{
        flexDirection: 'row',
        justifyContent: 'space-between',
        gap: 12,
        paddingVertical: 9,
        borderBottomWidth: 1,
        borderBottomColor: palette.line,
      }}
    >
      <Text style={{ fontSize: 14, lineHeight: 20, color: palette.ink, flexShrink: 1 }}>
        {label}
      </Text>
      <Text
        style={{
          fontSize: 14,
          lineHeight: 20,
          fontWeight: '800',
          color: palette.ink,
          textAlign: 'right',
          flexShrink: 1,
          fontVariant: ['tabular-nums'],
        }}
      >
        {value}
      </Text>
    </View>
  );
}

export function Notice({
  children,
  tone,
  icon = 'info',
}: PropsWithChildren<{ tone?: 'lime' | 'blue' | 'green' | 'orange' | 'red'; icon?: IconName }>) {
  const { palette, dark } = useTheme();
  let bg = palette.surface2;
  let color = palette.inkSoft;
  let borderColor = dark ? palette.lineSubtle : palette.line;
  if (dark) {
    // No escuro o `tone` deixa de ser decorativo: erro/alerta/sucesso/informação
    // ganham cor + contorno + ícone, sem depender só de cor.
    if (tone === 'lime') {
      bg = palette.limeSoft;
      borderColor = palette.brand;
      color = palette.ink;
    } else if (tone) {
      bg = palette.surface2;
      borderColor =
        tone === 'blue'
          ? palette.info
          : tone === 'green'
            ? palette.success
            : tone === 'orange'
              ? palette.warning
              : palette.danger;
      color = borderColor;
    }
  } else if (tone === 'lime') {
    bg = palette.limeSoft;
    color = palette.ink;
  } else if (tone) {
    bg = palette.surface2;
    color = palette.ink;
  }
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: 10,
        borderWidth: 1.5,
        borderColor,
        borderRadius: 14,
        backgroundColor: bg,
        paddingHorizontal: 13,
        paddingVertical: 12,
      }}
    >
      <View style={{ marginTop: 1 }}>
        <Icon name={icon} size={16} color={color} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 13, lineHeight: 19, color }}>{children}</Text>
      </View>
    </View>
  );
}

export function TimerCard({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: string;
  note: string;
  tone?: 'on' | 'done' | 'late';
}) {
  const { palette } = useTheme();
  let bg = palette.surface;
  let border = palette.lineSubtle;
  if (tone === 'on') {
    bg = palette.limeSoft;
    border = palette.lineStrong;
  } else if (tone === 'done') {
    bg = palette.surface2;
  } else if (tone === 'late') {
    bg = palette.redSoft;
    border = palette.red;
  }
  return (
    <View
      style={{
        flex: 1,
        borderWidth: 1.5,
        borderColor: border,
        borderRadius: 14,
        backgroundColor: bg,
        paddingHorizontal: 12,
        paddingVertical: 11,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 10,
      }}
    >
      <View style={{ flex: 1 }}>
        <Text
          style={{
            fontSize: 10.5,
            lineHeight: 13,
            fontWeight: '800',
            letterSpacing: 1,
            textTransform: 'uppercase',
            color: palette.muted,
          }}
        >
          {label}
        </Text>
        <Text
          style={{
            fontSize: 18,
            lineHeight: 20,
            fontWeight: '900',
            fontVariant: ['tabular-nums'],
            color: palette.ink,
          }}
        >
          {value}
        </Text>
        <Text style={{ fontSize: 11, lineHeight: 15, color: palette.muted, marginTop: 2 }}>
          {note}
        </Text>
      </View>
      <Icon name="clock" size={16} color={palette.muted} />
    </View>
  );
}

export function StateScreen({
  icon,
  title,
  text,
  actions,
}: {
  icon: IconName;
  title: string;
  text: string;
  actions?: ReactNode;
}) {
  const { palette } = useTheme();
  const reduceMotion = useReducedMotion();
  const [iconScale] = useState(() => new Animated.Value(0.92));

  useEffect(() => {
    if (reduceMotion) {
      iconScale.setValue(1);
      return;
    }
    const animation = Animated.timing(iconScale, {
      toValue: 1,
      duration: duration.medium,
      easing: easing.enter,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [iconScale, reduceMotion]);

  return (
    <Appear>
      <View
        style={{
          alignItems: 'center',
          paddingTop: 28,
          paddingHorizontal: 8,
          paddingBottom: 8,
          gap: 12,
        }}
      >
        <Animated.View
          style={{
            width: 72,
            height: 72,
            borderRadius: 36,
            backgroundColor: palette.surface2,
            borderWidth: 1.5,
            borderColor: palette.lineSubtle,
            alignItems: 'center',
            justifyContent: 'center',
            transform: [{ scale: iconScale }],
          }}
        >
          <Icon name={icon} size={32} color={palette.ink} />
        </Animated.View>
        <Txt variant="h1" align="center" style={{ fontSize: 28, lineHeight: 28, maxWidth: 300 }}>
          {title}
        </Txt>
        <Txt variant="tiny" align="center" style={{ maxWidth: 300 }}>
          {text}
        </Txt>
        {actions ? <View style={{ width: '100%', gap: 8, marginTop: 8 }}>{actions}</View> : null}
      </View>
    </Appear>
  );
}

export function EmptyState({
  title,
  text,
  actions,
}: {
  title: string;
  text: string;
  actions?: ReactNode;
}) {
  const { palette } = useTheme();
  return (
    <Appear>
      <View style={{ alignItems: 'center', paddingVertical: 26, paddingHorizontal: 10, gap: 8 }}>
        <View
          style={{
            width: 56,
            height: 56,
            borderRadius: 28,
            backgroundColor: palette.surface2,
            borderWidth: 1.5,
            borderColor: palette.lineSubtle,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Icon name="search" size={24} color={palette.muted} />
        </View>
        <Txt variant="h3" align="center">
          {title}
        </Txt>
        <Txt variant="sub" align="center" style={{ maxWidth: 280 }}>
          {text}
        </Txt>
        {actions ? <View style={{ width: '100%', gap: 8, marginTop: 6 }}>{actions}</View> : null}
      </View>
    </Appear>
  );
}

export type LoadingVariant =
  | 'generic'
  | 'home'
  | 'social'
  | 'clan'
  | 'list'
  | 'cards'
  | 'venue'
  | 'wallet'
  | 'season'
  | 'heroList'
  | 'track'
  | 'timers'
  | 'grid';

export function LoadingState({
  label = 'Carregando.',
  variant = 'generic',
}: {
  label?: string;
  variant?: LoadingVariant;
}) {
  const { palette, dark } = useTheme();
  const reduceMotion = useReducedMotion();
  const [pulse] = useState(() => new Animated.Value(0));
  const [fade] = useState(() => new Animated.Value(0));
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), dwell.skeleton);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!visible) {
      return;
    }
    const animation = Animated.timing(fade, {
      toValue: 1,
      duration: motionDuration(duration.base, reduceMotion),
      easing: easing.enter,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [fade, reduceMotion, visible]);

  useEffect(() => {
    if (!visible || reduceMotion) {
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
  }, [pulse, reduceMotion, visible]);

  const opacity = reduceMotion
    ? reduced.pulseOpacity
    : pulse.interpolate({ inputRange: [0, 1], outputRange: [reduced.pulseOpacity, 1] });

  const block = (height: number, width: ViewStyle['width'] = '100%', radius = 10) => (
    <View style={{ height, width, borderRadius: radius, backgroundColor: palette.surface2 }} />
  );

  const line = (width: ViewStyle['width'] = '100%') => block(14, width, 7);

  const heroBlock = (height: number, width: ViewStyle['width'] = '100%', radius = 7) => (
    <View
      style={{
        height,
        width,
        borderRadius: radius,
        backgroundColor: dark ? palette.surface3 : palette.lineOnInk,
      }}
    />
  );

  const circle = (size = 34) => (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: palette.surface2,
      }}
    />
  );

  const surfaceCard = (children: ReactNode, minHeight?: number) => (
    <View
      style={{
        borderRadius: 18,
        borderWidth: 1.5,
        borderColor: palette.lineSubtle,
        backgroundColor: palette.surface,
        padding: 16,
        minHeight,
        gap: 10,
      }}
    >
      {children}
    </View>
  );

  const hero = (height = 190) => (
    <View
      style={{
        height,
        borderRadius: 18,
        borderWidth: 1.5,
        borderColor: palette.lineSubtle,
        backgroundColor: dark ? palette.surface2 : palette.ink,
        padding: 16,
        justifyContent: 'space-between',
      }}
    >
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        {heroBlock(20, 104, 5)}
        {heroBlock(18, 78, 5)}
      </View>
      <View style={{ gap: 10 }}>
        {heroBlock(30, '76%', 6)}
        {heroBlock(14, '56%', 6)}
      </View>
      {heroBlock(14, '40%', 6)}
    </View>
  );

  const listCard = (count: number) => (
    <View
      style={{
        borderRadius: 18,
        borderWidth: 1.5,
        borderColor: palette.lineSubtle,
        backgroundColor: palette.surface,
        overflow: 'hidden',
      }}
    >
      {Array.from({ length: count }, (_, index) => (
        <View
          key={index}
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            gap: 12,
            paddingHorizontal: 18,
            paddingVertical: 15,
            borderBottomWidth: index === count - 1 ? 0 : 1,
            borderBottomColor: palette.line,
          }}
        >
          {circle(34)}
          <View style={{ flex: 1, gap: 7 }}>
            {line('55%')}
            {line('82%')}
          </View>
          {block(10, 10, 5)}
        </View>
      ))}
    </View>
  );

  const grid = (count: number, height = 150) => (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
      {Array.from({ length: count }, (_, index) => (
        <View
          key={index}
          style={{
            width: '47%',
            height,
            borderRadius: 18,
            borderWidth: 1.5,
            borderColor: palette.lineSubtle,
            backgroundColor: palette.surface,
            padding: 16,
            gap: 10,
          }}
        >
          {line('52%')}
          {block(32, '42%', 6)}
          {line('68%')}
        </View>
      ))}
    </View>
  );

  const trackGrid = () => (
    <>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        {line('34%')}
        {block(22, 58, 999)}
      </View>
      {block(14)}
      <View
        style={{
          flexDirection: 'row',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          rowGap: 7,
        }}
      >
        {Array.from({ length: 30 }, (_, index) => (
          <View
            key={index}
            style={{
              width: '18%',
              height: 54,
              borderRadius: 10,
              borderWidth: 1.5,
              borderColor: palette.lineSubtle,
              backgroundColor: palette.surface,
            }}
          />
        ))}
      </View>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        {line('30%')}
        {line('18%')}
      </View>
      {listCard(3)}
    </>
  );

  let content: ReactNode;

  switch (variant) {
    case 'social':
      content = (
        <>
          {block(54, '100%', 12)}
          {listCard(4)}
        </>
      );
      break;
    case 'clan':
      content = (
        <>
          {hero(190)}
          {surfaceCard(
            <>
              {line('28%')}
              {line('82%')}
              {line('58%')}
            </>,
            104,
          )}
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <View style={{ flex: 1 }}>
              {surfaceCard(
                <>
                  {line('48%')}
                  {line('70%')}
                </>,
                92,
              )}
            </View>
            <View style={{ flex: 1 }}>
              {surfaceCard(
                <>
                  {line('48%')}
                  {line('70%')}
                </>,
                92,
              )}
            </View>
          </View>
          {listCard(4)}
        </>
      );
      break;
    case 'list':
      content = listCard(4);
      break;
    case 'cards':
      content = (
        <>
          {surfaceCard(
            <>
              {line('45%')}
              {line('78%')}
              {line('36%')}
            </>,
            120,
          )}
          {surfaceCard(
            <>
              {line('52%')}
              {line('82%')}
            </>,
            120,
          )}
        </>
      );
      break;
    case 'venue':
      content = (
        <>
          {surfaceCard(
            <>
              {block(146, '100%', 14)}
              {line('62%')}
              {line('82%')}
            </>,
            238,
          )}
          {surfaceCard(
            <>
              {block(146, '100%', 14)}
              {line('55%')}
            </>,
            220,
          )}
        </>
      );
      break;
    case 'wallet':
      content = (
        <>
          {hero(200)}
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <View style={{ flex: 1 }}>{block(52, '100%', 14)}</View>
            <View style={{ flex: 1 }}>{block(52, '100%', 14)}</View>
          </View>
          {listCard(3)}
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            {line('24%')}
            {line('26%')}
          </View>
          {listCard(2)}
        </>
      );
      break;
    case 'season':
      content = (
        <>
          {hero(190)}
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <View style={{ flex: 1 }}>
              {surfaceCard(
                <>
                  {line('42%')}
                  {block(28, '50%', 6)}
                  {line('62%')}
                </>,
                112,
              )}
            </View>
            <View style={{ flex: 1 }}>
              {surfaceCard(
                <>
                  {line('42%')}
                  {block(28, '50%', 6)}
                  {line('62%')}
                </>,
                112,
              )}
            </View>
          </View>
          {surfaceCard(
            <>
              {line('30%')}
              <View style={{ flexDirection: 'row', gap: 7 }}>
                {Array.from({ length: 7 }, (_, index) => (
                  <View
                    key={index}
                    style={{
                      flex: 1,
                      height: 54,
                      borderRadius: 10,
                      borderWidth: 1.5,
                      borderColor: palette.lineSubtle,
                      backgroundColor: palette.surface2,
                    }}
                  />
                ))}
              </View>
              {line('66%')}
            </>,
            160,
          )}
          {surfaceCard(
            <>
              {line('28%')}
              <View style={{ flexDirection: 'row', gap: 6 }}>
                {block(22, 64, 5)}
                {block(22, 74, 5)}
                {block(22, 58, 5)}
              </View>
            </>,
            84,
          )}
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <View style={{ flex: 1 }}>{block(52, '100%', 14)}</View>
            <View style={{ flex: 1 }}>{block(52, '100%', 14)}</View>
          </View>
        </>
      );
      break;
    case 'heroList':
      content = (
        <>
          {hero(190)}
          {listCard(4)}
          {surfaceCard(
            <>
              {line('32%')}
              {line('82%')}
              {line('65%')}
              {line('48%')}
            </>,
            130,
          )}
          {block(52, '100%', 14)}
        </>
      );
      break;
    case 'track':
      content = trackGrid();
      break;
    case 'timers':
      content = (
        <>
          <View style={{ flexDirection: 'row', gap: 7 }}>
            <View style={{ flex: 1 }}>{block(74, '100%', 14)}</View>
            <View style={{ flex: 1 }}>{block(74, '100%', 14)}</View>
          </View>
          {surfaceCard(
            <>
              {line('45%')}
              {line('72%')}
            </>,
            92,
          )}
          {surfaceCard(
            <>
              {line('60%')}
              {line('40%')}
            </>,
            72,
          )}
          {block(52, '100%', 14)}
        </>
      );
      break;
    case 'grid':
      content = (
        <>
          {line('92%')}
          {line('70%')}
          {grid(4)}
          {block(52, '100%', 14)}
        </>
      );
      break;
    case 'home':
      content = (
        <>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            {line('38%')}
            {line('24%')}
          </View>
          {hero(190)}
          {surfaceCard(
            <>
              {line('30%')}
              {block(34, '45%', 6)}
              {line('52%')}
            </>,
            104,
          )}
          {surfaceCard(
            <>
              {line('34%')}
              {line('72%')}
              {block(14, '100%', 999)}
            </>,
            112,
          )}
          {surfaceCard(
            <>
              {line('30%')}
              {block(22, '52%', 6)}
              {block(14, '100%', 999)}
              {line('62%')}
            </>,
            104,
          )}
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            {line('28%')}
            {line('18%')}
          </View>
          {listCard(3)}
          {block(52, '100%', 14)}
        </>
      );
      break;
    default:
      content = (
        <>
          {line('60%')}
          {line('86%')}
          {line('42%')}
          {surfaceCard(
            <>
              {line('50%')}
              {line('80%')}
              {line('62%')}
            </>,
            120,
          )}
        </>
      );
  }

  if (!visible) {
    return null;
  }

  return (
    <Animated.View
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      style={{ paddingTop: 4, opacity: fade }}
    >
      <Animated.View style={{ gap: 14, opacity }}>{content}</Animated.View>
    </Animated.View>
  );
}

export function CardList({ children }: PropsWithChildren) {
  const { palette } = useTheme();
  return (
    <View
      style={{
        backgroundColor: palette.surface,
        borderWidth: 1.5,
        borderColor: palette.lineSubtle,
        borderRadius: space.radius,
        overflow: 'hidden',
      }}
    >
      {children}
    </View>
  );
}

export function ListRow({
  children,
  onPress,
  last,
  style,
}: PropsWithChildren<{ onPress?: () => void; last?: boolean; style?: StyleProp<ViewStyle> }>) {
  const { palette, largeTargets } = useTheme();
  const content = (
    <View
      style={[
        {
          flexDirection: 'row',
          alignItems: 'center',
          gap: 12,
          paddingHorizontal: 18,
          paddingVertical: largeTargets ? 18 : 15,
          borderBottomWidth: last ? 0 : 1,
          borderBottomColor: palette.line,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
  if (!onPress) {
    return content;
  }
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => ({
        backgroundColor: pressed ? palette.surface2 : 'transparent',
      })}
    >
      {content}
    </Pressable>
  );
}

export function PlayerRow({
  name,
  role,
  identity,
  cap,
  badge,
}: {
  name: string;
  role: string;
  identity?: Partial<VisualIdentity> | null;
  cap?: boolean;
  badge?: ReactNode;
}) {
  const { palette } = useTheme();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 }}>
      <IdentityBadge identity={identity} size={30} palette={palette} />
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={{ fontSize: 12.5, lineHeight: 14, fontWeight: '700', color: palette.ink }}>
          {name}
        </Text>
        <Text style={{ fontSize: 10.5, lineHeight: 14, color: palette.muted }}>{role}</Text>
      </View>
      {cap ? <Icon name="shield" size={16} color={palette.limeDeep} /> : null}
      {badge}
    </View>
  );
}

export function TeamCard({
  name,
  players,
  badge,
}: {
  name: string;
  players: { name: string; role: string; identity?: Partial<VisualIdentity> | null }[];
  badge?: ReactNode;
}) {
  const { palette } = useTheme();
  return (
    <View
      style={{
        borderWidth: 1.5,
        borderColor: palette.lineSubtle,
        borderRadius: 14,
        padding: 11,
        backgroundColor: palette.surface,
      }}
    >
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <Text
          style={{
            fontSize: 12,
            fontWeight: '900',
            letterSpacing: 1,
            textTransform: 'uppercase',
            color: palette.ink,
          }}
        >
          {name}
        </Text>
        {badge}
      </View>
      {players.map((player) => (
        <PlayerRow
          key={player.name}
          name={player.name}
          role={player.role}
          identity={player.identity}
        />
      ))}
    </View>
  );
}

const pageScrollOffsets = new Map<string, number>();

export function Page({
  title,
  sub,
  right,
  rightGo,
  back = true,
  children,
  center,
  flush,
  rightNode,
  hideHeader,
  scroll = true,
  onBack,
}: PropsWithChildren<{
  title?: string;
  sub?: string;
  right?: IconName;
  rightGo?: string;
  back?: boolean;
  center?: boolean;
  flush?: boolean;
  rightNode?: ReactNode;
  hideHeader?: boolean;
  /** Desliga o ScrollView para telas que hospedam uma FlatList própria. */
  scroll?: boolean;
  /**
   * Intercepta o botão de voltar do cabeçalho (ex.: confirmar descarte de um
   * formulário sujo). Sem a prop, o comportamento continua sendo `nav.back()`.
   */
  onBack?: () => void;
}>) {
  const { palette, contentBottomInset } = useTheme();
  const nav = useNav();
  const scrollRef = useRef<ScrollViewInstance>(null);
  const scrollKey = `${nav.id}:${JSON.stringify(nav.params ?? {})}`;
  const savedOffset = useRef(pageScrollOffsets.get(scrollKey) ?? 0);
  const restored = useRef(false);
  const restoreOffset = () => {
    if (restored.current) {
      return;
    }
    restored.current = true;
    if (savedOffset.current > 0) {
      requestAnimationFrame(() => {
        scrollRef.current?.scrollTo({ y: savedOffset.current, animated: false });
      });
    }
  };

  const header = hideHeader ? null : (
    <View
      style={{
        minHeight: 54,
        paddingTop: 8,
        paddingBottom: 2,
        marginHorizontal: flush ? 16 : 0,
        flexDirection: 'row',
        alignItems: 'center',
        gap: 10,
        backgroundColor: palette.bg,
        zIndex: 5,
      }}
    >
      {back && nav.canGoBack ? (
        onBack ? (
          <IconBtn icon="back" label="Voltar" plain onPress={onBack} />
        ) : (
          <IconBtn icon="back" label="Voltar" plain back />
        )
      ) : null}
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text
          accessibilityRole="header"
          numberOfLines={2}
          adjustsFontSizeToFit
          minimumFontScale={0.82}
          maxFontSizeMultiplier={1.2}
          style={{
            fontSize: 16,
            lineHeight: 18,
            fontWeight: '900',
            letterSpacing: 0.4,
            textTransform: 'uppercase',
            color: palette.ink,
          }}
        >
          {title}
        </Text>
        {sub ? (
          <Text
            numberOfLines={2}
            maxFontSizeMultiplier={1.3}
            style={{ fontSize: 13, lineHeight: 18, color: palette.muted, marginTop: 2 }}
          >
            {sub}
          </Text>
        ) : null}
      </View>
      {rightNode ?? (right ? <IconBtn icon={right} label={title ?? 'Ação'} go={rightGo} /> : null)}
    </View>
  );

  if (!scroll) {
    return (
      <KeyboardAvoidingView style={{ flex: 1, backgroundColor: palette.bg }} behavior="padding">
        <View
          style={{
            flex: 1,
            paddingHorizontal: flush ? 0 : 16,
            paddingBottom: contentBottomInset,
            alignItems: center ? 'center' : 'stretch',
          }}
        >
          {header}
          <View style={{ flex: 1, gap: 14 }}>{children}</View>
        </View>
      </KeyboardAvoidingView>
    );
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: palette.bg }} behavior="padding">
      <ScrollView
        ref={scrollRef}
        style={{ flex: 1 }}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        onScroll={(event) => {
          pageScrollOffsets.set(scrollKey, event.nativeEvent.contentOffset.y);
        }}
        scrollEventThrottle={32}
        onLayout={restoreOffset}
        onContentSizeChange={restoreOffset}
        contentContainerStyle={{
          paddingHorizontal: flush ? 0 : 16,
          paddingBottom: 26 + contentBottomInset,
          gap: 14,
          alignItems: center ? 'center' : 'stretch',
        }}
        showsVerticalScrollIndicator={false}
      >
        {header}
        {children}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export function Range({
  min,
  max,
  value,
  onChange,
}: {
  min: number;
  max: number;
  value: number;
  onChange: (value: number) => void;
}) {
  const { palette } = useTheme();
  const [width, setWidth] = useState(0);
  const ratio = (value - min) / (max - min);
  return (
    <Pressable
      onLayout={(event) => setWidth(event.nativeEvent.layout.width)}
      onPress={(event) => {
        if (!width) {
          return;
        }
        const next = Math.max(0, Math.min(1, event.nativeEvent.locationX / width));
        onChange(Math.round(min + next * (max - min)));
      }}
      style={({ pressed }) => ({
        height: 40,
        justifyContent: 'center',
        opacity: pressed ? 0.85 : 1,
      })}
    >
      <View style={{ height: 4, borderRadius: 2, backgroundColor: palette.progressTrack }}>
        <View
          style={{
            height: 4,
            width: `${ratio * 100}%`,
            backgroundColor: palette.lime,
            borderRadius: 2,
          }}
        />
      </View>
      <View
        style={{
          position: 'absolute',
          left: `${ratio * 100}%`,
          marginLeft: -10,
          width: 20,
          height: 20,
          borderRadius: 10,
          backgroundColor: palette.ink,
          borderWidth: 2,
          borderColor: palette.surface,
        }}
      />
    </Pressable>
  );
}

export function WelcomeCourt() {
  return (
    <Svg viewBox="0 0 340 150" width="100%" height={150}>
      <SvgRect width="340" height="150" fill="#15171A" />
      <SvgRect
        x="24"
        y="14"
        width="292"
        height="100"
        rx="5"
        fill="#1E2125"
        stroke="#383D43"
        strokeWidth={2}
      />
      <SvgPath d="M170 14v100M24 64h292" stroke="#383D43" strokeWidth={2} />
      <SvgCircle cx="170" cy="64" r="22" fill="none" stroke="#383D43" strokeWidth={2} />
      <SvgRect x="24" y="38" width="38" height="52" fill="none" stroke="#383D43" strokeWidth={2} />
      <SvgRect x="278" y="38" width="38" height="52" fill="none" stroke="#383D43" strokeWidth={2} />
      <SvgCircle cx="296" cy="32" r="10" fill="#E53935" />
      <SvgText x="24" y="136" fontSize="9" fontFamily="Arial" fill="#A6ABB1">
        QUADRA · ILUSTRAÇÃO
      </SvgText>
      <SvgText x="250" y="136" fontSize="9" fontFamily="Arial" fill="#A6ABB1">
        JOGA
      </SvgText>
    </Svg>
  );
}

export function PhotoCourt({ tone = 'green' }: { tone?: 'green' | 'blue' | 'orange' }) {
  const tones: Record<'green' | 'blue' | 'orange', [string, string, string]> = {
    green: ['#E7EAE7', '#D5D9D6', '#62686E'],
    blue: ['#E7EAE7', '#D5D9D6', '#62686E'],
    orange: ['#E7EAE7', '#D5D9D6', '#E53935'],
  };
  const [bg, surface, stroke] = tones[tone];
  return (
    <Svg viewBox="0 0 320 146" width="100%" height={146}>
      <SvgRect width="320" height="146" fill={bg} />
      <SvgRect
        x="22"
        y="18"
        width="276"
        height="110"
        rx="4"
        fill={surface}
        stroke={stroke}
        strokeWidth={2}
      />
      <SvgPath d="M160 18v110M22 73h276" stroke={stroke} strokeWidth={2} opacity={0.7} />
      <SvgCircle
        cx="160"
        cy="73"
        r="22"
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        opacity={0.7}
      />
      <SvgRect
        x="22"
        y="47"
        width="34"
        height="52"
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        opacity={0.7}
      />
      <SvgRect
        x="264"
        y="47"
        width="34"
        height="52"
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        opacity={0.7}
      />
      <SvgPath d="M38 18v110M282 18v110" stroke={stroke} strokeWidth={2} opacity={0.5} />
      <SvgText x="16" y="138" fontSize="9" fontFamily="Arial" fill={stroke}>
        QUADRA · ILUSTRAÇÃO
      </SvgText>
    </Svg>
  );
}

export function Photo({
  tone,
  children,
}: PropsWithChildren<{ tone?: 'green' | 'blue' | 'orange' }>) {
  const { palette } = useTheme();
  return (
    <View
      style={{
        borderRadius: 16,
        overflow: 'hidden',
        borderWidth: 1.5,
        borderColor: palette.lineSubtle,
        backgroundColor: palette.surface2,
      }}
    >
      <PhotoCourt tone={tone} />
      {children}
    </View>
  );
}

export function PhotoCap({ children, badge }: PropsWithChildren<{ badge?: ReactNode }>) {
  const { palette } = useTheme();
  return (
    <View
      style={{
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 8,
        paddingHorizontal: 10,
        paddingVertical: 8,
        backgroundColor: palette.surface,
      }}
    >
      <Text style={{ fontSize: 11, lineHeight: 15, color: palette.muted, flex: 1 }}>
        {children}
      </Text>
      {badge}
    </View>
  );
}

export function QrSvg({ seed = 7, size = 168 }: { seed?: number; size?: number }) {
  let state = seed;
  const cells: { x: number; y: number }[] = [];
  const n = 21;
  const cellSize = 4;
  for (let y = 0; y < n; y += 1) {
    for (let x = 0; x < n; x += 1) {
      state = (state * 73 + 41) % 997;
      const finder = (x < 7 && y < 7) || (x > 13 && y < 7) || (x < 7 && y > 13);
      const on = finder
        ? x === 0 ||
          x === 6 ||
          y === 0 ||
          y === 6 ||
          (x >= 2 && x <= 4 && y >= 2 && y <= 4) ||
          (y >= 2 && y <= 4 && x >= 4 && x <= 6)
        : state % 3 === 0;
      if (on) {
        cells.push({ x: x * cellSize, y: y * cellSize });
      }
    }
  }
  return (
    <Svg width={size} height={size} viewBox="0 0 84 84">
      <SvgRect width="84" height="84" fill="#F1F3F0" />
      {cells.map((cell, index) => (
        <SvgRect
          key={index}
          x={cell.x}
          y={cell.y}
          width={cellSize}
          height={cellSize}
          fill="#17191B"
        />
      ))}
    </Svg>
  );
}

export function ChartSvg() {
  const { palette } = useTheme();
  return (
    <Svg viewBox="0 0 320 120" width="100%" height={120}>
      <SvgPath d="M8 102h304M8 76h304M8 50h304M8 24h304" stroke={palette.line} strokeWidth={1} />
      <SvgPolyline
        points="10,98 52,92 94,94 136,76 178,70 220,58 262,54 304,36"
        fill="none"
        stroke={palette.ink}
        strokeWidth={3}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {[
        [10, 98],
        [94, 94],
        [178, 70],
        [262, 54],
      ].map(([cx, cy], index) => (
        <SvgCircle
          key={index}
          cx={cx}
          cy={cy}
          r={4}
          fill={palette.lime}
          stroke={palette.ink}
          strokeWidth={2}
        />
      ))}
      <SvgCircle cx="304" cy="36" r="5" fill={palette.ink} />
      <SvgText x="10" y="116" fontSize="9" fill={palette.muted} fontFamily="Arial">
        INÍCIO
      </SvgText>
      <SvgText x="268" y="116" fontSize="9" fill={palette.muted} fontFamily="Arial">
        HOJE
      </SvgText>
    </Svg>
  );
}

const HEAT_ROWS: [string, string[]][] = [
  ['06', ['h1', 'h1', 'empty', 'empty', 'h1', 'h2', 'h1']],
  ['09', ['h1', 'h2', 'h2', 'h1', 'empty', 'h2', 'h2']],
  ['12', ['h2', 'h3', 'h3', 'h2', 'h1', 'h3', 'h3']],
  ['18', ['h3', 'h4', 'h4', 'h3', 'h2', 'h4', 'h4']],
  ['21', ['h4', 'h4', 'h3', 'h4', 'h3', 'h4', 'h3']],
];

export function HeatGrid() {
  const { palette } = useTheme();
  const color = (level: string) => {
    if (level === 'h1') return palette.heat1;
    if (level === 'h2') return palette.heat2;
    if (level === 'h3') return palette.heat3;
    if (level === 'h4') return palette.heat4;
    return palette.surface;
  };
  return (
    <View>
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
        <View style={{ width: 34 }} />
        {['S', 'T', 'Q', 'Q', 'S', 'S', 'D'].map((day, index) => (
          <Text
            key={`${day}-${index}`}
            style={{
              flex: 1,
              textAlign: 'center',
              fontSize: 10,
              fontWeight: '800',
              color: palette.muted,
            }}
          >
            {day}
          </Text>
        ))}
      </View>
      {HEAT_ROWS.map(([time, cells]) => (
        <View
          key={time}
          style={{ flexDirection: 'row', gap: 4, alignItems: 'center', marginBottom: 4 }}
        >
          <Text
            style={{
              width: 30,
              textAlign: 'right',
              fontSize: 10,
              fontWeight: '700',
              color: palette.muted,
              fontVariant: ['tabular-nums'],
            }}
          >
            {time}
          </Text>
          {cells.map((level, index) => (
            <View
              key={index}
              style={{
                flex: 1,
                height: 26,
                borderRadius: 4,
                backgroundColor: color(level),
                borderWidth: 1,
                borderColor: level === 'empty' ? palette.line : palette.line,
                borderStyle: level === 'empty' ? 'dashed' : 'solid',
              }}
            />
          ))}
        </View>
      ))}
    </View>
  );
}

export function Spacer({ height = 4 }: { height?: number }) {
  return <View style={{ height }} />;
}

export function styles() {
  return StyleSheet.create({});
}
