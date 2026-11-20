import {
  Children,
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import {
  Animated,
  Easing,
  Keyboard,
  KeyboardAvoidingView,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  useWindowDimensions,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useTheme } from '../state/context';
import { Text } from './text';

type CloseFn = (after?: () => void) => void;

const CloseContext = createContext<CloseFn>(() => undefined);

/**
 * Fecha o sheet com a animação de saída e só então avisa o dono do estado.
 * Use dentro de `children`/`footer` de `BottomSheetFrame`.
 */
export function useSheetClose(): CloseFn {
  return useContext(CloseContext);
}

const ENTER_MS = 220;
const EXIT_MS = 160;
/** Altura usada só antes do primeiro `onLayout`; depois vale a altura real. */
const FALLBACK_SHEET_HEIGHT = 420;

/**
 * Frame único de bottom sheet do app.
 *
 * Centraliza o que antes estava repetido em `Sheet` (App), `AddWindowSheet` e
 * `Select`: `Modal` transparente, backdrop, `KeyboardAvoidingView`, scroll
 * interno, altura máxima responsiva, inset inferior do sistema, gesto de
 * voltar do Android e fechamento por toque no backdrop.
 *
 * Regras de layout:
 * - o CTA fica no `footer`, fora do scroll, e reserva `insets.bottom` + respiro;
 * - o corpo rola (`keyboardShouldPersistTaps="handled"`) e encolhe com o teclado;
 * - nada usa `position: 'absolute'` funcional — só o backdrop decorativo.
 */
export function BottomSheetFrame({
  visible,
  onClose,
  title,
  subtitle,
  children,
  footer,
  maxHeightRatio = 0.92,
  accessibilityLabel,
}: {
  visible: boolean;
  onClose: () => void;
  title?: string;
  subtitle?: string;
  children?: ReactNode;
  footer?: ReactNode;
  /** Fração máxima da altura da janela ocupada pelo sheet. */
  maxHeightRatio?: number;
  accessibilityLabel?: string;
}) {
  const { palette } = useTheme();
  const insets = useSafeAreaInsets();
  const { height: windowHeight } = useWindowDimensions();
  const [progress] = useState(() => new Animated.Value(0));
  const [sheetHeight, setSheetHeight] = useState(0);
  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const closing = useRef(false);
  const closeRef = useRef(onClose);

  useEffect(() => {
    closeRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!visible) {
      progress.setValue(0);
      closing.current = false;
      return;
    }
    closing.current = false;
    Animated.timing(progress, {
      toValue: 1,
      duration: ENTER_MS,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [progress, visible]);

  // Com o teclado aberto a barra de navegação do Android é substituída pelo IME:
  // reservar `insets.bottom` ali só criaria um vão morto acima do teclado.
  useEffect(() => {
    if (!visible) {
      return;
    }
    const show = Keyboard.addListener('keyboardDidShow', () => setKeyboardVisible(true));
    const hide = Keyboard.addListener('keyboardDidHide', () => setKeyboardVisible(false));
    return () => {
      show.remove();
      hide.remove();
    };
  }, [visible]);

  const bottomGap = keyboardVisible ? 12 : Math.max(insets.bottom, 10) + 10;

  const close: CloseFn = (after) => {
    if (closing.current) {
      return;
    }
    closing.current = true;
    Animated.timing(progress, {
      toValue: 0,
      duration: EXIT_MS,
      easing: Easing.in(Easing.cubic),
      useNativeDriver: true,
    }).start(() => {
      closeRef.current();
      after?.();
    });
  };

  const maxHeight = Math.max(240, Math.round(windowHeight * maxHeightRatio));
  const from = sheetHeight > 0 ? sheetHeight : FALLBACK_SHEET_HEIGHT;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="none"
      statusBarTranslucent
      onRequestClose={() => close()}
    >
      <View style={{ flex: 1, justifyContent: 'flex-end' }}>
        <Animated.View
          pointerEvents="none"
          style={[
            StyleSheet.absoluteFill,
            { backgroundColor: 'rgba(23,25,27,.5)', opacity: progress },
          ]}
        />
        <KeyboardAvoidingView behavior="padding" style={{ flex: 1, justifyContent: 'flex-end' }}>
          <Pressable
            style={{ flex: 1 }}
            onPress={() => close()}
            accessible={false}
            importantForAccessibility="no"
          />
          <Animated.View
            accessibilityLabel={accessibilityLabel}
            onLayout={(event) => {
              const next = Math.round(event.nativeEvent.layout.height);
              if (next > 0 && next !== sheetHeight) {
                setSheetHeight(next);
              }
            }}
            style={{
              flexShrink: 1,
              maxHeight,
              backgroundColor: palette.surface,
              borderTopLeftRadius: 22,
              borderTopRightRadius: 22,
              borderTopWidth: 1.5,
              borderColor: palette.lineStrong,
              transform: [
                {
                  translateY: progress.interpolate({
                    inputRange: [0, 1],
                    outputRange: [from, 0],
                  }),
                },
              ],
            }}
          >
            <CloseContext.Provider value={close}>
              <View
                style={{
                  width: 44,
                  height: 5,
                  borderRadius: 999,
                  backgroundColor: palette.lineStrong,
                  alignSelf: 'center',
                  marginTop: 10,
                  marginBottom: 10,
                }}
              />
              {title ? (
                <View style={{ paddingHorizontal: 16, gap: 6, paddingBottom: 4 }}>
                  <Text
                    accessibilityRole="header"
                    numberOfLines={2}
                    style={{
                      fontSize: 20,
                      lineHeight: 22,
                      fontWeight: '900',
                      letterSpacing: -0.2,
                      textTransform: 'uppercase',
                      color: palette.ink,
                    }}
                  >
                    {title}
                  </Text>
                  {subtitle ? (
                    <Text style={{ fontSize: 13, lineHeight: 19, color: palette.muted }}>
                      {subtitle}
                    </Text>
                  ) : null}
                </View>
              ) : null}
              {Children.toArray(children).length > 0 ? (
                <ScrollView
                  bounces={false}
                  keyboardShouldPersistTaps="handled"
                  showsVerticalScrollIndicator={false}
                  style={{ flexShrink: 1 }}
                  contentContainerStyle={{
                    paddingHorizontal: 16,
                    paddingTop: 10,
                    // Sem footer, o último item do scroll é o que encosta na barra
                    // do sistema e precisa reservar o inset.
                    paddingBottom: footer ? 8 : bottomGap,
                  }}
                >
                  {children}
                </ScrollView>
              ) : null}
              {footer ? (
                <View
                  style={{
                    paddingHorizontal: 16,
                    paddingTop: 8,
                    paddingBottom: bottomGap,
                  }}
                >
                  {footer}
                </View>
              ) : null}
            </CloseContext.Provider>
          </Animated.View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}
