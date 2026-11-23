import { type Ref } from 'react';
import { View, type StyleProp, type TextInputInstance, type ViewStyle } from 'react-native';

import { useTheme } from '../state/context';
import { Field, Input } from './kit';
import { Text } from './text';

/** Mantém só dígitos e insere `:` depois das duas primeiras posições. */
export function maskTimeInput(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 4);
  if (digits.length <= 2) {
    return digits;
  }
  return `${digits.slice(0, 2)}:${digits.slice(2)}`;
}

/**
 * Normaliza o que está visível no campo para `HH:MM`.
 *
 * Regras (o texto exibido é a fonte da verdade):
 * - `9` → `09:00`; `19` → `19:00` (sem minutos digitados, assume `:00`);
 * - `9:5` → `09:05`; `9:05` → `09:05`; `19:0` → `19:00`;
 * - hora 00–23 e minuto 00–59; qualquer outra coisa é inválida.
 */
export function normalizeTime(text: string): string | null {
  const cleaned = text.trim();
  if (!cleaned) {
    return null;
  }
  const [hourPart = '', minutePart = ''] = cleaned.split(':');
  if (!/^\d{1,2}$/.test(hourPart) || (minutePart !== '' && !/^\d{1,2}$/.test(minutePart))) {
    return null;
  }
  const hours = Number(hourPart);
  const minutes = minutePart === '' ? 0 : Number(minutePart);
  if (hours > 23 || minutes > 59) {
    return null;
  }
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}

export function timeToMinutes(value: string): number | null {
  const normalized = normalizeTime(value);
  if (!normalized) {
    return null;
  }
  const [hours, minutes] = normalized.split(':').map(Number);
  return hours * 60 + minutes;
}

/** Prévia legível do intervalo; `null` enquanto os dois lados não forem válidos. */
export function formatTimeRange(start: string, end: string): string | null {
  const from = normalizeTime(start);
  const to = normalizeTime(end);
  if (!from || !to) {
    return null;
  }
  return `${from} – ${to}`;
}

/**
 * Campo de horário único do app: máscara `HH:MM`, teclado numérico, foco
 * encadeado e erro inline. Substitui os `Input` soltos com `maxLength={5}`.
 */
export function TimeField({
  label,
  value,
  onChange,
  onBlur,
  onFocus,
  error,
  autoFocus,
  inputRef,
  returnKeyType = 'next',
  onSubmitEditing,
  accessibilityLabel,
  style,
}: {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  onFocus?: () => void;
  /** Mensagem exibida abaixo do campo; o campo também ganha borda de erro. */
  error?: string | null;
  autoFocus?: boolean;
  inputRef?: Ref<TextInputInstance>;
  returnKeyType?: 'next' | 'done' | 'go' | 'send';
  onSubmitEditing?: () => void;
  accessibilityLabel?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const { palette, dark } = useTheme();

  const field = (
    <View style={[{ gap: 7 }, style]}>
      <Input
        inputRef={inputRef}
        value={value}
        onChangeText={(next) => onChange(maskTimeInput(next))}
        onFocus={() => {
          onFocus?.();
        }}
        onBlur={() => {
          const normalized = normalizeTime(value);
          if (normalized && normalized !== value) {
            onChange(normalized);
          }
          onBlur?.();
        }}
        placeholder="HH:MM"
        keyboardType="number-pad"
        inputMode="numeric"
        maxLength={5}
        autoFocus={autoFocus}
        returnKeyType={returnKeyType}
        onSubmitEditing={onSubmitEditing}
        submitBehavior={returnKeyType === 'next' ? 'submit' : 'blurAndSubmit'}
        accessibilityLabel={accessibilityLabel ?? label}
        accessibilityHint="Digite a hora com dois dígitos e os minutos com dois dígitos."
        style={error ? { borderColor: dark ? palette.danger : palette.lime } : undefined}
      />
      {error ? (
        <Text
          accessibilityLiveRegion="polite"
          style={{ fontSize: 12.5, lineHeight: 17, color: dark ? palette.danger : palette.lime }}
        >
          {error}
        </Text>
      ) : null}
    </View>
  );

  if (!label) {
    return field;
  }
  return <Field label={label}>{field}</Field>;
}
