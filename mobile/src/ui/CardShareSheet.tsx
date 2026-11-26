import { useEffect, useRef, useState, type ComponentRef, type RefObject } from 'react';
import { PixelRatio, Platform, View, useWindowDimensions } from 'react-native';
import { Asset, requestPermissionsAsync } from 'expo-media-library';
import * as Sharing from 'expo-sharing';
import { captureRef } from 'react-native-view-shot';

import { useTheme } from '../state/context';
import { BottomSheetFrame } from './BottomSheetFrame';
import { Btn, BtnRow, TextBtn } from './kit';
import { ProfileCard, type ProfileCardData } from './ProfileCard';
import { Text } from './text';

/** Saída fixa do compartilhamento: 1080×1440 (3:4). */
export const SHARE_IMAGE_WIDTH = 1080;
export const SHARE_IMAGE_HEIGHT = 1440;

type Status = { text: string; error?: boolean };

/**
 * Prévia do cartão e ações de compartilhar/salvar. A captura usa uma instância
 * fora da tela do MESMO `ProfileCard`, para a imagem sair em 1080×1440 sem
 * depender do espaço disponível no sheet.
 */
export function CardShareSheet({
  visible,
  data,
  captureTarget,
  onClose,
}: {
  visible: boolean;
  data: ProfileCardData;
  captureTarget: RefObject<ComponentRef<typeof View> | null>;
  onClose: () => void;
}) {
  const { palette } = useTheme();
  const { width } = useWindowDimensions();
  const [busy, setBusy] = useState<'share' | 'save' | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const visibleRef = useRef(visible);
  useEffect(() => {
    visibleRef.current = visible;
  }, [visible]);
  const previewWidth = Math.max(180, width - 32);

  const close = () => {
    setBusy(null);
    setStatus(null);
    onClose();
  };

  const captureCard = async () => {
    if (!captureTarget.current) {
      setStatus({ text: 'A prévia ainda não está pronta. Tente de novo.', error: true });
      return null;
    }
    try {
      // Garante que o cartão oculto já passou pelo layout antes de capturar.
      await new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      });
      // No iOS `width`/`height` são pontos e o renderer multiplica pela escala
      // da tela; no Android a opção já é o tamanho final em pixels físicos.
      // Assim o PNG sai sempre em 1080×1440.
      const ratio = PixelRatio.get();
      const width =
        Platform.OS === 'ios' ? Math.round(SHARE_IMAGE_WIDTH / ratio) : SHARE_IMAGE_WIDTH;
      const height =
        Platform.OS === 'ios' ? Math.round(SHARE_IMAGE_HEIGHT / ratio) : SHARE_IMAGE_HEIGHT;
      const uri = await captureRef(captureTarget, {
        format: 'png',
        quality: 1,
        result: 'tmpfile',
        width,
        height,
      });
      return uri.startsWith('file://') ? uri : `file://${uri}`;
    } catch {
      setStatus({ text: 'Não foi possível gerar a imagem. Tente de novo.', error: true });
      return null;
    }
  };

  const share = async () => {
    if (busy) {
      return;
    }
    setBusy('share');
    setStatus({ text: 'Gerando imagem…' });
    const uri = await captureCard();
    if (!uri) {
      setBusy(null);
      return;
    }
    if (!visibleRef.current) {
      setBusy(null);
      return;
    }
    try {
      if (!(await Sharing.isAvailableAsync())) {
        setStatus({ text: 'Compartilhar não está disponível neste aparelho.', error: true });
        setBusy(null);
        return;
      }
      await Sharing.shareAsync(uri, { mimeType: 'image/png', dialogTitle: 'Compartilhar cartão' });
      setStatus(null);
    } catch {
      setStatus({ text: 'Não foi possível abrir o compartilhamento.', error: true });
    }
    setBusy(null);
  };

  const save = async () => {
    if (busy) {
      return;
    }
    setBusy('save');
    setStatus({ text: 'Gerando imagem…' });
    const uri = await captureCard();
    if (!uri) {
      setBusy(null);
      return;
    }
    if (!visibleRef.current) {
      setBusy(null);
      return;
    }
    try {
      const permission = await requestPermissionsAsync(true, ['photo']);
      if (!permission.granted) {
        setStatus({ text: 'Permita salvar fotos para guardar o cartão.', error: true });
        setBusy(null);
        return;
      }
      await Asset.create(uri);
      setStatus({ text: 'Cartão salvo na galeria.' });
    } catch {
      setStatus({ text: 'Não foi possível salvar a imagem.', error: true });
    }
    setBusy(null);
  };

  return (
    <BottomSheetFrame
      visible={visible}
      onClose={close}
      title="Compartilhar cartão"
      subtitle="Prévia do cartão que aparece no seu perfil."
      accessibilityLabel="Compartilhar cartão"
      footer={
        <View style={{ gap: 6 }}>
          {status ? (
            <Text
              accessibilityLiveRegion="polite"
              style={{
                fontSize: 12.5,
                lineHeight: 17,
                fontWeight: '700',
                textAlign: 'center',
                color: status.error ? palette.danger : palette.muted,
              }}
            >
              {status.text}
            </Text>
          ) : null}
          <BtnRow>
            <Btn tone="ghost" icon="download" disabled={busy !== null} onPress={() => void save()}>
              Salvar imagem
            </Btn>
            <Btn tone="primary" icon="share" disabled={busy !== null} onPress={() => void share()}>
              Compartilhar
            </Btn>
          </BtnRow>
          <TextBtn onPress={close}>Fechar</TextBtn>
        </View>
      }
    >
      <View style={{ alignItems: 'center' }}>
        <ProfileCard data={data} imageMode width={previewWidth} />
      </View>
    </BottomSheetFrame>
  );
}
