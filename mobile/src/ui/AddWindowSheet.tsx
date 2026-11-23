import { useRef, useState } from 'react';
import { View, type TextInputInstance } from 'react-native';

import { useTheme } from '../state/context';
import { BottomSheetFrame, useSheetClose } from './BottomSheetFrame';
import { Btn, BtnRow, Chip, ChipRow, Txt } from './kit';
import { WEEKDAY_NAMES } from './datetime';
import { Text } from './text';
import { TimeField, formatTimeRange, normalizeTime } from './TimeField';

const TIME_ZONE = 'America/Sao_Paulo';

type Window = {
  weekday: number;
  start_time: string;
  end_time: string;
  timezone: string;
};

function toApiTime(value: string): string | null {
  const normalized = normalizeTime(value);
  return normalized ? `${normalized}:00` : null;
}

export function AddWindowSheet({
  visible,
  initialWeekday,
  onClose,
  onAdd,
}: {
  visible: boolean;
  initialWeekday: number;
  onClose: () => void;
  onAdd: (window: Window) => void;
}) {
  return (
    <AddWindowForm
      visible={visible}
      initialWeekday={initialWeekday}
      onClose={onClose}
      onAdd={onAdd}
    />
  );
}

/** Botões ficam no footer do frame: sempre acima do teclado e da barra do sistema. */
function AddWindowFooter({ error, onSubmit }: { error: string | null; onSubmit: () => boolean }) {
  const { palette, dark } = useTheme();
  const close = useSheetClose();
  return (
    <View style={{ gap: 10 }}>
      {error ? (
        <Text
          accessibilityLiveRegion="polite"
          style={{ fontSize: 13, lineHeight: 18, color: dark ? palette.danger : palette.lime }}
        >
          {error}
        </Text>
      ) : null}
      <BtnRow>
        <Btn tone="ghost" onPress={() => close()}>
          Cancelar
        </Btn>
        <Btn
          tone="primary"
          onPress={() => {
            if (onSubmit()) {
              close();
            }
          }}
        >
          Adicionar
        </Btn>
      </BtnRow>
    </View>
  );
}

function AddWindowForm({
  visible,
  initialWeekday,
  onClose,
  onAdd,
}: {
  visible: boolean;
  initialWeekday: number;
  onClose: () => void;
  onAdd: (window: Window) => void;
}) {
  const { palette } = useTheme();
  const endRef = useRef<TextInputInstance>(null);
  const [weekday, setWeekday] = useState(initialWeekday);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [touched, setTouched] = useState(false);

  const startApi = toApiTime(start);
  const endApi = toApiTime(end);
  const orderInvalid = !!startApi && !!endApi && endApi <= startApi;
  const valid = !!startApi && !!endApi && !orderInvalid;
  const preview = formatTimeRange(start, end);

  const submit = () => {
    setTouched(true);
    if (!startApi || !endApi || orderInvalid) {
      return false;
    }
    onAdd({ weekday, start_time: startApi, end_time: endApi, timezone: TIME_ZONE });
    return true;
  };

  const errorText =
    touched && !valid
      ? !startApi || !endApi
        ? 'Informe os horários no formato HH:MM. Ex.: 1900 vira 19:00.'
        : 'O fim precisa ser depois do início.'
      : null;

  return (
    <BottomSheetFrame
      visible={visible}
      onClose={onClose}
      title="Adicionar horário"
      subtitle="Escolha o dia e a janela de horário que você quer adicionar."
      accessibilityLabel="Adicionar horário de disponibilidade"
      footer={<AddWindowFooter error={errorText} onSubmit={submit} />}
    >
      <View style={{ gap: 14 }}>
        <ChipRow>
          {WEEKDAY_NAMES.map((day, index) => (
            <Chip key={day} on={weekday === index + 1} onPress={() => setWeekday(index + 1)}>
              {day}
            </Chip>
          ))}
        </ChipRow>
        <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
          <View style={{ flexGrow: 1, flexBasis: 130, minWidth: 0 }}>
            <TimeField
              label="Início"
              value={start}
              onChange={setStart}
              autoFocus
              returnKeyType="next"
              onSubmitEditing={() => endRef.current?.focus()}
              accessibilityLabel="Horário de início"
            />
          </View>
          <View style={{ flexGrow: 1, flexBasis: 130, minWidth: 0 }}>
            <TimeField
              label="Fim"
              value={end}
              onChange={setEnd}
              inputRef={endRef}
              returnKeyType="done"
              accessibilityLabel="Horário de fim"
            />
          </View>
        </View>
        {preview ? (
          <Text
            accessibilityLiveRegion="polite"
            style={{ fontSize: 13, lineHeight: 18, fontWeight: '700', color: palette.ink }}
          >
            Janela: {preview}
          </Text>
        ) : null}
        <Txt variant="tiny">
          Fuso {TIME_ZONE}. O horário vale só na sua disponibilidade; a partida ainda depende de
          lobby compatível.
        </Txt>
      </View>
    </BottomSheetFrame>
  );
}
