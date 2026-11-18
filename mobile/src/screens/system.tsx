import { useEffect, useState } from 'react';
import { Platform, View } from 'react-native';

import { api, ApiError } from '../api/client';
import type { CpfStatus, Device, Passkey } from '../api/types';
import { authConfig } from '../auth/config';
import { createPasskey, passkeyAvailable } from '../passkey';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import { Icon } from '../ui/icons';
import {
  Badge,
  Btn,
  Card,
  CardList,
  Chip,
  Field,
  IconBtn,
  Input,
  Kv,
  ListRow,
  LoadingState,
  Notice,
  Page,
  Row,
  Seg,
  SegBtn,
  StateScreen,
  Toggle,
  Txt,
} from '../ui/kit';
import { Text } from '../ui/text';
import type { ScreenDef } from './types';

function Settings() {
  const nav = useNav();
  const { palette } = useTheme();
  const items = [
    {
      icon: 'user' as const,
      title: 'Conta e perfil',
      sub: 'Nome, tag e e-mail',
      go: 'profile-edit',
    },
    {
      icon: 'chat' as const,
      title: 'Notificações',
      sub: 'Prazos, partidas, pagamentos e social',
      go: 'notifications',
    },
    {
      icon: 'eye' as const,
      title: 'Privacidade',
      sub: 'Convites, região e bloqueios',
      go: 'privacy',
    },
    {
      icon: 'eye' as const,
      title: 'Acessibilidade',
      sub: 'Fonte, movimento e alvos',
      go: 'accessibility',
    },
    {
      icon: 'bolt' as const,
      title: 'Personalização',
      sub: 'Temas, densidade, home, sons e háptica',
      go: 'customization',
    },
    {
      icon: 'shield' as const,
      title: 'Segurança',
      sub: 'Passkeys, dispositivos e sessões',
      go: 'security',
    },
    {
      icon: 'mail' as const,
      title: 'Credenciais de login',
      sub: 'E-mail que autentica a conta',
      go: 'credentials',
    },
    {
      icon: 'download' as const,
      title: 'LGPD',
      sub: 'Exportar dados e excluir conta',
      go: 'lgpd-export',
    },
    {
      icon: 'trash' as const,
      title: 'Excluir conta',
      sub: 'Consequências, prazo e confirmação',
      go: 'lgpd-delete',
    },
    {
      icon: 'info' as const,
      title: 'Termos e privacidade',
      sub: 'Termos, privacidade e cancelamento',
      go: 'terms-privacy',
    },
    {
      icon: 'chat' as const,
      title: 'Ajuda e suporte',
      sub: 'Contestação, moderação e pagamentos',
      go: 'support',
    },
    {
      icon: 'info' as const,
      title: 'Sobre o JOGA',
      sub: 'Versão, licenças e ambiente',
      go: 'about',
    },
  ];
  return (
    <Page title="Configurações">
      <CardList>
        {items.map((item, index) => (
          <ListRow
            key={item.title}
            last={index === items.length - 1}
            onPress={() => nav.go(item.go)}
          >
            <IconBtn icon={item.icon} label={item.title} plain go={item.go} />
            <View style={{ flex: 1 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                  {item.title}
                </Text>
              </View>
              <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
            </View>
            <Text style={{ color: palette.muted }}>›</Text>
          </ListRow>
        ))}
      </CardList>
      <Btn tone="ghost" icon="logout" modal="logout">
        Sair da conta
      </Btn>
    </Page>
  );
}

function Accessibility() {
  const nav = useNav();
  const { accessibility, setAccessibility } = useApp();
  const [size, setSize] = useState(accessibility.fontScale);
  const [motion, setMotion] = useState(accessibility.reducedMotion);
  const [targets, setTargets] = useState(accessibility.largeTargets);

  const save = async () => {
    try {
      await setAccessibility({ fontScale: size, reducedMotion: motion, largeTargets: targets });
      nav.toast('Preferências de acessibilidade salvas.');
    } catch {
      nav.toast('Não foi possível salvar as preferências.');
    }
  };

  return (
    <Page title="Acessibilidade">
      <Card>
        <Row between>
          <Txt variant="h3">Tamanho do texto</Txt>
          <Badge tone="green">LIVRE</Badge>
        </Row>
        <Seg style={{ marginTop: 8 }}>
          {['A', 'AA', 'AAA'].map((item) => (
            <SegBtn
              key={item}
              on={size === item}
              onPress={() => setSize(item as 'A' | 'AA' | 'AAA')}
            >
              {item}
            </SegBtn>
          ))}
        </Seg>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Reduzir movimento</Txt>
          <Toggle checked={motion} onChange={setMotion} />
        </Row>
        <Row between style={{ marginTop: 12 }}>
          <Txt variant="h3">Alvos de toque ampliados</Txt>
          <Toggle checked={targets} onChange={setTargets} />
        </Row>
      </Card>
      <Notice tone="green" icon="shield">
        Essas preferências não são itens de catálogo e não dependem do passe. Elas ficam salvas
        neste aparelho.
      </Notice>
      <Btn tone="primary" onPress={save}>
        Salvar preferências
      </Btn>
    </Page>
  );
}

function Customization() {
  const { dark, setDark } = useApp();
  const { palette } = useTheme();
  const [density, setDensity] = useState('Confortável');
  const [sounds, setSounds] = useState(true);
  const [animations, setAnimations] = useState(true);
  return (
    <Page title="Personalização">
      <Row between>
        <Badge tone="green">GRÁTIS</Badge>
        <Badge>APARÊNCIA</Badge>
      </Row>
      <Card>
        <Txt variant="h3">Tema</Txt>
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
          {['Claro', 'Escuro'].map((item) => (
            <Chip
              key={item}
              on={item === 'Escuro' ? dark : !dark}
              onPress={() => setDark(item === 'Escuro')}
            >
              {item}
            </Chip>
          ))}
        </View>
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          Claro e escuro são gratuitos e acompanham o sistema até você escolher manualmente.
        </Txt>
      </Card>
      <Card>
        <Txt variant="h3">Cor de destaque</Txt>
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
          {['#E53935', '#62686E', '#62686E', '#E53935', '#62686E'].map((color, index) => (
            <View
              key={index}
              style={{
                width: 46,
                height: 46,
                borderRadius: 23,
                backgroundColor: color,
                borderWidth: index === 0 ? 2 : 1.5,
                borderColor: index === 0 ? '#17191B' : palette.line,
              }}
            />
          ))}
        </View>
      </Card>
      <Card>
        <Txt variant="h3">Densidade dos cartões</Txt>
        <Seg style={{ marginTop: 8 }}>
          {['Confortável', 'Compacta'].map((item) => (
            <SegBtn key={item} on={density === item} onPress={() => setDensity(item)}>
              {item}
            </SegBtn>
          ))}
        </Seg>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Blocos da home</Txt>
          <Txt variant="tiny">ordem</Txt>
        </Row>
        <View style={{ marginTop: 6 }}>
          {['Próxima partida', 'Saldo', 'Missão', 'Temporada'].map((item, index) => (
            <View
              key={item}
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                paddingVertical: 11,
                borderBottomWidth: index === 3 ? 0 : 1,
                borderBottomColor: palette.line,
              }}
            >
              <Text style={{ width: 24, fontWeight: '900', color: palette.ink }}>{index + 1}</Text>
              <Text style={{ flex: 1, fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item}
              </Text>
              <Text style={{ color: palette.muted }}>⋯</Text>
            </View>
          ))}
        </View>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Sons e háptica</Txt>
          <Toggle checked={sounds} onChange={setSounds} />
        </Row>
        <Row between style={{ marginTop: 12 }}>
          <Txt variant="h3">Animações</Txt>
          <Toggle checked={animations} onChange={setAnimations} />
        </Row>
      </Card>
      <Btn tone="primary" disabled>
        Persistência da personalização em implantação
      </Btn>
    </Page>
  );
}

function passkeyError(error: unknown): string {
  if (error instanceof ApiError) {
    const map: Record<string, string> = {
      invalid_passkey: 'Não foi possível validar a passkey.',
      passkey_already_registered: 'Esta passkey já está cadastrada.',
      rate_limited: 'Muitas tentativas. Aguarde e tente novamente.',
      invalid_token: 'Sua sessão expirou. Entre novamente.',
    };
    return map[error.code] ?? 'Não foi possível concluir a passkey.';
  }
  return 'Não foi possível concluir a passkey.';
}

function Security() {
  const nav = useNav();
  const { palette } = useTheme();
  const { session } = useApp();
  const [keys, setKeys] = useState<Passkey[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (session) {
      api.auth
        .passkeys(session.accessToken)
        .then((result) => setKeys(result.credentials))
        .catch(() => undefined);
    }
  }, [session]);
  const list = keys.map((item) => ({
    id: item.credential_id,
    name: item.name ?? 'Passkey',
    sub: item.last_used_at
      ? `último uso em ${item.last_used_at.slice(0, 10)}`
      : `cadastrada em ${item.created_at.slice(0, 10)}`,
  }));
  const revoke = async (id: string) => {
    if (!session) {
      return;
    }
    try {
      await api.auth.revokePasskey(session.accessToken, id);
      setKeys((current) => current.filter((item) => item.credential_id !== id));
      nav.toast('Passkey revogada.');
    } catch (error) {
      nav.toast(passkeyError(error));
    }
  };
  const addPasskey = async () => {
    if (!session || busy) {
      return;
    }
    if (!passkeyAvailable()) {
      nav.toast('A passkey exige o development build Android; o módulo iOS ainda não existe.');
      return;
    }
    setBusy(true);
    try {
      const options = await api.auth.passkeyRegistrationOptions(session.accessToken);
      const credential = await createPasskey(options.public_key);
      await api.auth.passkeyRegistrationVerify(
        session.accessToken,
        options.challenge_id,
        credential,
        Platform.OS === 'ios' ? 'iPhone' : 'Android',
      );
      const refreshed = await api.auth.passkeys(session.accessToken);
      setKeys(refreshed.credentials);
      nav.toast('Passkey adicionada.');
    } catch (error) {
      nav.toast(passkeyError(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Page title="Segurança">
      <Card>
        <Row between>
          <Txt variant="h3">Passkeys</Txt>
          <Badge tone="green">{list.length} ativas</Badge>
        </Row>
        <View style={{ marginTop: 6 }}>
          {list.length === 0 ? (
            <Txt variant="tiny" style={{ paddingVertical: 10 }}>
              Nenhuma passkey cadastrada. Adicione uma para entrar sem código.
            </Txt>
          ) : null}
          {list.map((item, index) => (
            <View
              key={item.id}
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: 10,
                paddingVertical: 11,
                borderBottomWidth: index === list.length - 1 ? 0 : 1,
                borderBottomColor: palette.line,
              }}
            >
              <Text style={{ color: palette.ink }}>◈</Text>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                  {item.name}
                </Text>
                <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
              </View>
              <Btn tone="ghost" small block={false} onPress={() => revoke(item.id)}>
                Revogar
              </Btn>
            </View>
          ))}
        </View>
        <View style={{ marginTop: 10 }}>
          <Btn tone="primary" icon="plus" onPress={addPasskey} disabled={busy}>
            {busy ? 'Abrindo…' : 'Adicionar passkey'}
          </Btn>
        </View>
      </Card>
      <CardList>
        {[
          {
            icon: 'mail' as const,
            title: 'Credenciais de login',
            sub: 'E-mail ativo e troca de endereço',
            go: 'credentials',
          },
          {
            icon: 'lock' as const,
            title: 'Trocar senha',
            sub: 'Senha atual e nova senha',
            go: 'change-password',
          },
          ...(authConfig.phoneEnabled
            ? [
                {
                  icon: 'user' as const,
                  title: 'Trocar telefone',
                  sub: 'Confirme por código no telefone atual',
                  go: 'phone-change',
                },
              ]
            : []),
          {
            icon: 'eye' as const,
            title: 'Dispositivos e sessões',
            sub: 'Sessões ativas da conta',
            go: 'devices',
          },
          {
            icon: 'shield' as const,
            title: 'Recuperação de conta',
            sub: 'Passkey + análise de risco',
            go: 'recovery',
          },
        ].map((item, index, all) => (
          <ListRow key={item.title} last={index === all.length - 1} onPress={() => nav.go(item.go)}>
            <IconBtn icon={item.icon} label={item.title} plain go={item.go} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.title}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
            </View>
            <Text style={{ color: palette.muted }}>›</Text>
          </ListRow>
        ))}
      </CardList>
      <Notice tone="orange" icon="lock">
        {authConfig.phoneEnabled
          ? 'Trocar o telefone encerra todas as sessões.'
          : 'A troca de e-mail encerra as outras sessões e mantém esta ativa.'}
      </Notice>
    </Page>
  );
}

function Devices() {
  const nav = useNav();
  const { palette } = useTheme();
  const { session } = useApp();
  const [devices, setDevices] = useState<Device[]>([]);
  useEffect(() => {
    if (session) {
      api.auth
        .devices(session.accessToken)
        .then((result) => setDevices(result.devices))
        .catch(() => undefined);
    }
  }, [session]);
  const list = devices.map((item) => ({
    id: item.id,
    name: item.name ?? item.platform,
    sub: item.last_seen_at ? `último acesso ${item.last_seen_at.slice(0, 10)}` : 'sessão ativa',
  }));
  const revoke = async (id: string) => {
    if (!session) {
      return;
    }
    try {
      await api.auth.revokeDevice(session.accessToken, id);
      setDevices((current) => current.filter((item) => item.id !== id));
      nav.toast('Sessão revogada.');
    } catch {
      nav.toast('Não foi possível revogar esta sessão.');
    }
  };
  return (
    <Page title="Dispositivos">
      {list.length === 0 ? (
        <Card>
          <Txt variant="tiny">Nenhuma sessão ativa encontrada.</Txt>
        </Card>
      ) : (
        <CardList>
          {list.map((item, index) => (
            <ListRow key={item.id} last={index === list.length - 1}>
              <Text style={{ color: palette.ink }}>◉</Text>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                  {item.name}
                </Text>
                <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
              </View>
              <Btn tone="ghost" small block={false} onPress={() => revoke(item.id)}>
                Revogar
              </Btn>
            </ListRow>
          ))}
        </CardList>
      )}
    </Page>
  );
}

function Privacy() {
  const nav = useNav();
  const { palette } = useTheme();
  const [invites, setInvites] = useState('Amigos');
  const [showRegion, setShowRegion] = useState(true);
  return (
    <Page title="Privacidade">
      <Card>
        <Row between>
          <Txt variant="h3">Quem pode me convidar</Txt>
          <Badge>amigos</Badge>
        </Row>
        <Seg style={{ marginTop: 8 }}>
          {['Todos', 'Amigos', 'Ninguém'].map((item) => (
            <SegBtn key={item} on={invites === item} onPress={() => setInvites(item)}>
              {item}
            </SegBtn>
          ))}
        </Seg>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Mostrar região no perfil</Txt>
          <Toggle checked={showRegion} onChange={setShowRegion} />
        </Row>
        <Txt variant="tiny" style={{ marginTop: 6 }}>
          Apenas cidade e raio aproximado. Nunca endereço, bairro exato ou coordenada.
        </Txt>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Quem pode ver meu histórico</Txt>
          <Badge>público</Badge>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 6 }}>
          Divisão, nível, partidas e conquistas. Valores financeiros e telefone nunca.
        </Txt>
      </Card>
      <CardList>
        {[
          {
            icon: 'lock' as const,
            title: 'Bloqueios',
            sub: 'Gerencie a partir do perfil do jogador',
            go: 'friends',
          },
          {
            icon: 'chat' as const,
            title: 'Notificações',
            sub: 'Prazos, partidas e social',
            go: 'notifications',
          },
        ].map((item, index, all) => (
          <ListRow key={item.title} last={index === all.length - 1} onPress={() => nav.go(item.go)}>
            <IconBtn icon={item.icon} label={item.title} plain go={item.go} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.title}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
            </View>
            <Text style={{ color: palette.muted }}>›</Text>
          </ListRow>
        ))}
      </CardList>
    </Page>
  );
}

function Cpf() {
  const nav = useNav();
  const { session } = useApp();
  const [status, setStatus] = useState<CpfStatus | null>(null);
  const [value, setValue] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = () => {
    if (!session) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api.profile
      .cpf(session.accessToken)
      .then(setStatus)
      .catch(() => nav.toast('Não foi possível consultar o CPF.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  const save = async () => {
    if (!session || busy) {
      return;
    }
    const digits = value.replace(/\D/g, '');
    if (digits.length !== 11) {
      nav.toast('Informe um CPF com 11 dígitos.');
      return;
    }
    setBusy(true);
    try {
      setStatus(await api.profile.updateCpf(session.accessToken, digits));
      setValue('');
      nav.toast('CPF salvo para a nota fiscal.');
    } catch (error) {
      nav.toast(
        error instanceof ApiError && error.code === 'invalid_cpf'
          ? 'CPF inválido.'
          : 'Não foi possível salvar o CPF.',
      );
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!session || busy) {
      return;
    }
    setBusy(true);
    try {
      setStatus(await api.profile.clearCpf(session.accessToken));
      nav.toast('CPF removido do perfil.');
    } catch {
      nav.toast('Não foi possível remover o CPF.');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <Page title="CPF para nota fiscal">
        <LoadingState label="Consultando o CPF do perfil." variant="cards" />
      </Page>
    );
  }

  return (
    <Page title="CPF para nota fiscal">
      <Card>
        <Row between>
          <Txt variant="h3">CPF no perfil</Txt>
          <Badge tone={status?.cpf_present ? 'green' : 'orange'}>
            {status?.cpf_present ? 'INFORMADO' : 'NÃO INFORMADO'}
          </Badge>
        </Row>
        {status?.cpf_present ? (
          <Kv label="CPF" value={status.cpf_masked ?? '•••'} />
        ) : (
          <Txt variant="tiny" style={{ marginTop: 6 }}>
            O CPF é usado na NFS-e emitida pelo estabelecimento pelo uso da quadra. Ele não aparece
            no perfil público.
          </Txt>
        )}
      </Card>
      <Field label={status?.cpf_present ? 'Substituir CPF' : 'Informar CPF'}>
        <Input
          value={value}
          onChangeText={setValue}
          keyboardType="number-pad"
          maxLength={14}
          placeholder="000.000.000-00"
          autoCorrect={false}
        />
      </Field>
      <Btn tone="primary" onPress={save} disabled={busy || value.replace(/\D/g, '').length !== 11}>
        {busy ? 'Salvando…' : 'Salvar CPF'}
      </Btn>
      {status?.cpf_present ? (
        <Btn tone="ghost" onPress={remove} disabled={busy}>
          Remover CPF do perfil
        </Btn>
      ) : null}
      <Notice tone="blue" icon="shield">
        O CPF é armazenado de forma protegida. A NFS-e de intermediação é emitida pelo JOGA contra o
        mesmo titular; o app não inventa número de documento.
      </Notice>
    </Page>
  );
}

function LgpdExport() {
  const { palette } = useTheme();
  return (
    <Page title="Exportar dados">
      <Card>
        <Txt variant="h3">O que entra</Txt>
        <View style={{ marginTop: 6 }}>
          {[
            'Perfil, modalidades e disponibilidade',
            'Partidas, resultados e divisão',
            'Ingressos, reservas e recibos',
            'Mensagens e consentimentos',
          ].map((item, index) => (
            <View
              key={item}
              style={{
                flexDirection: 'row',
                gap: 8,
                paddingVertical: 11,
                borderBottomWidth: index === 3 ? 0 : 1,
                borderBottomColor: palette.line,
              }}
            >
              <Icon name="check" size={16} color={palette.ink} />
              <Text style={{ flex: 1, fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item}
              </Text>
            </View>
          ))}
        </View>
      </Card>
      <Notice tone="green" icon="shield">
        A exportação é gratuita e não exige passe. Dados de terceiros são omitidos. O pedido é
        atendido pelo suporte enquanto não há fluxo automático no app.
      </Notice>
      <Btn tone="primary" go="support" icon="chat">
        Solicitar pelo suporte
      </Btn>
      <Btn tone="ghost" go="lgpd-delete">
        Excluir minha conta
      </Btn>
    </Page>
  );
}

function LgpdDelete() {
  const [confirmation, setConfirmation] = useState('');
  const canDelete = confirmation.trim().toUpperCase() === 'EXCLUIR';
  return (
    <Page title="Excluir conta">
      <Card tone="red">
        <Txt variant="h3">O que acontece</Txt>
        <Txt variant="tiny" style={{ marginTop: 6 }}>
          Sua conta, perfil, avatar, mensagens e preferências são excluídos. Registros financeiros e
          fiscais podem ser retidos pelo prazo legal. O saldo de crédito comprado segue a política
          de encerramento; a franquia do passe já disponibilizada não é reembolsada.
        </Txt>
      </Card>
      <Field label="Digite EXCLUIR para confirmar">
        <Input
          value={confirmation}
          onChangeText={setConfirmation}
          placeholder="EXCLUIR"
          maxLength={7}
          autoCapitalize="characters"
          autoCorrect={false}
        />
      </Field>
      <Notice tone="blue" icon="chat">
        A exclusão automática ainda não está disponível no app. Envie o pedido pelo suporte para
        preservar o contraditório e os prazos legais.
      </Notice>
      <Btn tone="danger" go="support" disabled={!canDelete}>
        Solicitar exclusão pelo suporte
      </Btn>
      <Btn tone="ghost" back>
        Cancelar
      </Btn>
    </Page>
  );
}

function TermsPrivacy() {
  const nav = useNav();
  const { palette } = useTheme();
  const [terms, setTerms] = useState<{ id: string; version: string } | null>(null);
  const [termsReady, setTermsReady] = useState(false);
  useEffect(() => {
    let active = true;
    api.legal
      .currentTerms()
      .then((result) => {
        if (active) {
          setTerms(result.terms);
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) {
          setTermsReady(true);
        }
      });
    return () => {
      active = false;
    };
  }, []);
  const items = [
    {
      icon: 'info' as const,
      title: 'Termos de uso',
      sub: termsReady
        ? terms
          ? `Versão ${terms.version} aprovada`
          : 'Nenhuma versão aprovada publicada'
        : 'Consultando a versão vigente…',
      readOnly: true,
    },
    {
      icon: 'shield' as const,
      title: 'Política de privacidade',
      sub: 'LGPD, localização e retenção',
      readOnly: true,
    },
    {
      icon: 'clock' as const,
      title: 'Política de cancelamento',
      sub: 'Cutoff, T4, no-show e devolução',
      readOnly: false,
    },
    {
      icon: 'wallet' as const,
      title: 'Política de ingressos',
      sub: 'Validade, consumo e devolução',
      readOnly: false,
    },
  ];
  return (
    <Page title="Termos e privacidade">
      <CardList>
        {items.map((item, index) => (
          <ListRow
            key={item.title}
            last={index === items.length - 1}
            onPress={() => {
              if (item.readOnly) {
                nav.go('terms', { readOnly: 1 });
                return;
              }
              nav.toast('Conteúdo disponível pelo suporte.');
            }}
          >
            <IconBtn
              icon={item.icon}
              label={item.title}
              plain
              onPress={item.readOnly ? () => nav.go('terms', { readOnly: 1 }) : undefined}
              toast={item.readOnly ? undefined : 'Conteúdo disponível pelo suporte'}
            />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.title}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
            </View>
            <Text style={{ color: palette.muted }}>›</Text>
          </ListRow>
        ))}
      </CardList>
      <Notice tone="blue" icon="info">
        A versão vigente é a aprovada e publicada pelo servidor. Quando uma nova versão exige
        aceite, a compra de crédito mostra o texto antes de abrir o Pix.
      </Notice>
    </Page>
  );
}

function Support() {
  const nav = useNav();
  const { palette } = useTheme();
  const items = [
    {
      icon: 'clock' as const,
      title: 'Prazos, cutoff e no-show',
      sub: 'Como T1–T9 funcionam',
      toast: 'Conteúdo em implantação',
    },
    {
      icon: 'shield' as const,
      title: 'Restrição da fila ranqueada',
      sub: 'Contestar a restrição',
      go: 'queue-restricted',
    },
    {
      icon: 'alert' as const,
      title: 'Moderação e denúncia',
      sub: 'Acompanhar caso e recurso',
      go: 'moderation-status',
    },
    {
      icon: 'wallet' as const,
      title: 'Pagamentos e reembolsos',
      sub: 'Pix, ingressos e recibos',
      go: 'booking-history',
    },
    {
      icon: 'alert' as const,
      title: 'Denunciar jogador',
      sub: 'Ofensas, assédio, fraude',
      go: 'report-profile',
    },
  ];
  return (
    <Page title="Ajuda e suporte">
      <CardList>
        {items.map((item, index) => (
          <ListRow
            key={item.title}
            last={index === items.length - 1}
            onPress={() => {
              if ('go' in item && typeof item.go === 'string') {
                nav.go(item.go);
                return;
              }
              if ('toast' in item && typeof item.toast === 'string') {
                nav.toast(item.toast);
              }
            }}
          >
            <IconBtn icon={item.icon} label={item.title} plain go={item.go} toast={item.toast} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.title}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
            </View>
            <Text style={{ color: palette.muted }}>›</Text>
          </ListRow>
        ))}
      </CardList>
      <Btn tone="primary" icon="chat" disabled>
        Atendimento em implantação
      </Btn>
      <Notice tone="blue" icon="shield">
        Toda contestação gera registro e possibilidade de revisão humana.
      </Notice>
    </Page>
  );
}

function About() {
  const { palette } = useTheme();
  const { profile, session, progress } = useApp();
  const tag = profile?.user_id ? profile.user_id.slice(0, 4).toUpperCase() : '----';
  return (
    <Page title="Sobre">
      <Card tone="ink">
        <Text
          style={{
            fontSize: 42,
            lineHeight: 39,
            fontWeight: '900',
            letterSpacing: -2,
            textTransform: 'uppercase',
            color: '#F1F3F0',
          }}
        >
          JOGA<Text style={{ color: '#E53935' }}>.</Text>
        </Text>
        <Txt variant="tiny" color="softOnInk" style={{ marginTop: 6 }}>
          Futebol e vôlei, quadra de verdade.
        </Txt>
        <View style={{ marginTop: 10 }}>
          <Badge tone="lime">BUILD LOCAL · EXPO 58</Badge>
        </View>
      </Card>
      <Card>
        <Kv label="Versão" value="1.0.0" />
        <Kv label="Ambiente" value="Local · sem dados reais" />
        <Kv
          label="Conta"
          value={
            profile?.display_name
              ? `${profile.display_name} #${tag}`
              : session
                ? `#${tag}`
                : 'não autenticado'
          }
        />
        <Kv label="Temporada" value={progress?.season.code ?? '—'} />
      </Card>
      <CardList>
        {[
          {
            icon: 'info' as const,
            title: 'Decisões desta versão',
            sub: 'O que mudou nesta rodada',
            go: 'decisions',
          },
          {
            icon: 'info' as const,
            title: 'Licenças',
            sub: 'Expo, React Native e SVG',
            toast: 'Licenças em implantação',
          },
        ].map((item, index, all) => (
          <ListRow key={item.title} last={index === all.length - 1}>
            <IconBtn icon={item.icon} label={item.title} plain go={item.go} toast={item.toast} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.title}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
            </View>
            <Text style={{ color: palette.muted }}>›</Text>
          </ListRow>
        ))}
      </CardList>
    </Page>
  );
}

function Offline() {
  return (
    <Page title="Conexão">
      <StateScreen
        icon="wifi-off"
        title="Sem conexão"
        text="Você pode ver o que já foi carregado, mas confirmações e pagamentos precisam de conexão."
        actions={
          <>
            <Btn tone="primary" toast="Tentando conectar no protótipo">
              Tentar novamente
            </Btn>
            <Btn tone="ghost" go="lobby-detail">
              Ver dados em cache
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function Error403() {
  return (
    <Page title="Acesso">
      <StateScreen
        icon="lock"
        title="Sem permissão"
        text="Seu vínculo com este lobby, clã ou reserva não permite esta ação."
        actions={
          <>
            <Btn tone="primary" back>
              Voltar
            </Btn>
            <Btn tone="ghost" go="support">
              Falar com suporte
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function ErrorGeneric() {
  return (
    <Page title="Erro">
      <StateScreen
        icon="alert"
        title="Algo deu errado"
        text="Não conseguimos carregar esta tela. Tente novamente. Se o problema continuar, o suporte tem o identificador da sessão."
        actions={
          <>
            <Btn tone="primary" toast="Tentando novamente no protótipo">
              Tentar novamente
            </Btn>
            <Btn tone="ghost" go="support">
              Falar com suporte
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function Loading() {
  const { palette } = useTheme();
  const skeleton = (style: object) => (
    <View
      style={[
        {
          height: 16,
          borderRadius: 10,
          backgroundColor: palette.surface2,
          borderWidth: 1,
          borderColor: palette.line,
        },
        style,
      ]}
    />
  );
  return (
    <Page title="Carregando">
      <Card>
        {skeleton({ width: '60%' })}
        <View style={{ height: 10 }} />
        {skeleton({ width: '80%' })}
        <View style={{ height: 10 }} />
        {skeleton({ width: '40%' })}
        <View style={{ height: 10 }} />
        <View
          style={{
            height: 92,
            borderRadius: 16,
            backgroundColor: palette.surface2,
            borderWidth: 1,
            borderColor: palette.line,
          }}
        />
        <View style={{ height: 10 }} />
        <View
          style={{
            height: 92,
            borderRadius: 16,
            backgroundColor: palette.surface2,
            borderWidth: 1,
            borderColor: palette.line,
          }}
        />
      </Card>
      <Card>
        {skeleton({ width: '80%' })}
        <View style={{ height: 10 }} />
        {skeleton({ width: '60%' })}
        <View style={{ height: 10 }} />
        <View
          style={{
            height: 92,
            borderRadius: 16,
            backgroundColor: palette.surface2,
            borderWidth: 1,
            borderColor: palette.line,
          }}
        />
      </Card>
      <Txt variant="tiny" align="center">
        Buscando suas informações.
      </Txt>
    </Page>
  );
}

function Decisions() {
  const { palette } = useTheme();
  const items = [
    [
      '1',
      'Filas separadas, mesma tela',
      'Casual e ranqueada mantêm mecanismos separados, mas compartilham o componente de fila.',
    ],
    [
      '2',
      'PIX só em pacote e passe',
      'T3 extinto: os ingressos são consumidos na confirmação do lobby.',
    ],
    ['3', 'Check-in GPS + estabelecimento', 'GPS com fallback do estabelecimento.'],
    ['4', 'Notificações dentro do app', 'Central de prazos e ações.'],
    ['5', 'Avatar no cadastro', 'Configurado no onboarding e editável no perfil.'],
    ['6', 'Passe 10/20/30/50', 'Franquia mensal, cobrança trimestral, entrega mês a mês.'],
    [
      '7',
      'Divisão reseta por temporada',
      'Decisão desta rodada. Altera a leitura anterior da ADR 0045 §1.6; registrar ADR.',
    ],
    ['8', 'Medalhas no MVP', 'Bloco separado de insígnias no perfil.'],
    [
      '9',
      'Sem glow, brilho ou neon',
      'Sombras apenas como profundidade; foco com contorno chapado.',
    ],
    ['10', 'Kit e capitão removidos', 'O lobby não tem checklist de kit nem papel de capitão.'],
    [
      '11',
      'Rede é sobre o app',
      'Quadras, horários, densidade e ocupação; não é estatística do jogador.',
    ],
    ['12', '5 abas + seletor', 'Jogar, Partidas, Temporada, Social e Perfil.'],
  ];
  return (
    <Page title="Decisões da v3">
      <Card>
        <View>
          {items.map(([num, title, sub], index) => (
            <View
              key={num}
              style={{
                flexDirection: 'row',
                alignItems: 'flex-start',
                gap: 10,
                paddingVertical: 11,
                borderBottomWidth: index === items.length - 1 ? 0 : 1,
                borderBottomColor: palette.line,
              }}
            >
              <Badge tone={num === '7' ? 'orange' : 'lime'}>{num}</Badge>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>{title}</Text>
                <Text style={{ fontSize: 13, color: palette.muted }}>{sub}</Text>
              </View>
            </View>
          ))}
        </View>
      </Card>
      <Notice tone="orange" icon="alert">
        A decisão 7 precisa ser registrada em ADR para substituir a regra anterior de divisão que
        não resetava.
      </Notice>
    </Page>
  );
}

export const systemScreens: ScreenDef[] = [
  { id: 'settings', tab: 'perfil', render: () => <Settings /> },
  { id: 'accessibility', tab: 'perfil', render: () => <Accessibility /> },
  { id: 'customization', tab: 'perfil', render: () => <Customization /> },
  { id: 'security', tab: 'perfil', render: () => <Security /> },
  { id: 'devices', tab: 'perfil', render: () => <Devices /> },
  { id: 'privacy', tab: 'perfil', render: () => <Privacy /> },
  { id: 'cpf', tab: 'perfil', render: () => <Cpf /> },
  { id: 'lgpd-export', tab: 'perfil', render: () => <LgpdExport /> },
  { id: 'lgpd-delete', tab: 'perfil', render: () => <LgpdDelete /> },
  { id: 'terms-privacy', tab: 'perfil', render: () => <TermsPrivacy /> },
  { id: 'support', tab: 'perfil', render: () => <Support /> },
  { id: 'about', tab: 'perfil', render: () => <About /> },
  { id: 'offline', tab: 'jogar', hidden: true, render: () => <Offline /> },
  { id: 'error-403', tab: 'jogar', hidden: true, render: () => <Error403 /> },
  { id: 'error-generic', tab: 'jogar', hidden: true, render: () => <ErrorGeneric /> },
  { id: 'loading', tab: 'jogar', hidden: true, render: () => <Loading /> },
  { id: 'decisions', tab: 'perfil', render: () => <Decisions /> },
];
