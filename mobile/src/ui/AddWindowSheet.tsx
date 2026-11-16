import { useState } from 'react';
import { Modal, Pressable, Text, View } from 'react-native';

import { useTheme } from '../state/context';
import { Btn, BtnRow, Chip, ChipRow, Field, Input, Txt } from './kit';
import { WEEKDAY_NAMES } from './datetime';

const TIME_ZONE = 'America/Sao_Paulo';

function normalize(value: string): string | null {
  const match = value.trim().match(/^(\d{1,2}):(\d{2})$/);
  if (!match) {
    return null;
  }
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 23 || minutes > 59) {
    return null;
  }
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:00`;
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
  onAdd: (window: {
    weekday: number;
    start_time: string;
    end_time: string;
    timezone: string;
  }) => void;
}) {
  const { palette } = useTheme();
  const [weekday, setWeekday] = useState(initialWeekday);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [touched, setTouched] = useState(false);

  const normalizedStart = normalize(start);
  const normalizedEnd = normalize(end);
  const valid = !!normalizedStart && !!normalizedEnd && normalizedEnd > normalizedStart;

  const submit = () => {
    setTouched(true);
    if (!normalizedStart || !normalizedEnd || !valid) {
      return;
    }
    onAdd({
      weekday,
      start_time: normalizedStart,
      end_time: normalizedEnd,
      timezone: TIME_ZONE,
    });
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable
        onPress={onClose}
        style={{ flex: 1, backgroundColor: 'rgba(23,25,27,.5)', justifyContent: 'flex-end' }}
      >
        <Pressable
          onPress={() => undefined}
          style={{
            backgroundColor: palette.surface,
            borderTopLeftRadius: 22,
            borderTopRightRadius: 22,
            borderTopWidth: 1.5,
            borderColor: palette.lineStrong,
            paddingHorizontal: 16,
            paddingTop: 16,
            paddingBottom: 26,
            maxHeight: '86%',
          }}
        >
          <View
            style={{
              width: 44,
              height: 5,
              borderRadius: 999,
              backgroundColor: palette.lineStrong,
              alignSelf: 'center',
              marginBottom: 14,
            }}
          />
          <Txt variant="h2" style={{ fontSize: 20, marginBottom: 6 }}>
            Adicionar horário
          </Txt>
          <Txt variant="sub" style={{ fontSize: 13, marginBottom: 12 }}>
            Escolha o dia e a janela de horário que você quer adicionar.
          </Txt>
          <Txt variant="label" style={{ marginBottom: 8 }}>
            Dia
          </Txt>
          <ChipRow style={{ marginBottom: 14 }}>
            {WEEKDAY_NAMES.map((day, index) => (
              <Chip key={day} on={weekday === index + 1} onPress={() => setWeekday(index + 1)}>
                {day}
              </Chip>
            ))}
          </ChipRow>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <View style={{ flex: 1 }}>
              <Field label="Início">
                <Input
                  value={start}
                  onChangeText={setStart}
                  maxLength={5}
                  placeholder="HH:MM"
                  keyboardType="default"
                />
              </Field>
            </View>
            <View style={{ flex: 1 }}>
              <Field label="Fim">
                <Input
                  value={end}
                  onChangeText={setEnd}
                  maxLength={5}
                  placeholder="HH:MM"
                  keyboardType="default"
                />
              </Field>
            </View>
          </View>
          {touched && !valid ? (
            <Text style={{ fontSize: 13, lineHeight: 18, color: palette.lime, marginTop: 8 }}>
              Informe horários válidos no formato HH:MM, com o fim depois do início.
            </Text>
          ) : null}
          <View style={{ marginTop: 16 }}>
            <BtnRow>
              <Btn tone="ghost" onPress={onClose}>
                Cancelar
              </Btn>
              <Btn tone="primary" onPress={submit}>
                Adicionar
              </Btn>
            </BtnRow>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
