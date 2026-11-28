import { useEffect, useRef, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import { View } from 'react-native';

import { api, ApiError, newIdempotencyKey } from '../api/client';
import type { PassReceipt, PassSubscription, TermsVersion, TicketLot } from '../api/types';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import { PaymentPix, paymentState } from '../ui/PaymentPix';
import { Text } from '../ui/text';
import {
  cycleStatusLabel,
  freeTickets,
  legacyTickets,
  passStatusLabel,
  planCycleName,
  planDurationLabel,
  planInstallmentsLabel,
  receiptAvailable,
} from '../ui/billing';
import {
  Badge,
  Btn,
  Card,
  CardList,
  Check,
  EmptyState,
  Field,
  Input,
  Kv,
  ListIcon,
  ListRow,
  LoadingState,
  Notice,
  Page,
  Row,
  StateScreen,
  TextBtn,
  Txt,
} from '../ui/kit';
import { cents, dateOnly, shortDateTime } from '../ui/datetime';
import { Icon } from '../ui/icons';
import {
  BAND_LABELS,
  BAND_ORDER,
  BAND_RANGES,
  TICKETS_BY_BAND,
  TICKET_REFERENCE_CENTS,
} from '../ui/tickets';
import type { ScreenDef } from './types';

const TICKET_SALES_DISCONTINUED_TEXT =
  'Os pacotes de ingressos foram substituídos pela assinatura. Escolha um plano para receber a franquia de cada ciclo.';

const SUBSCRIPTION_DISABLED_TEXT =
  'A compra e a assinatura estão indisponíveis nesta versão do JOGA. Seus ingressos e o crédito legado continuam válidos.';

function SubscriptionUnavailableState({ text }: { text: string }) {
  return (
    <Page title="Ingressos">
      <StateScreen
        icon="wallet"
        title="Assinatura indisponível"
        text={text}
        actions={
          <>
            <Btn tone="primary" go="pass">
              Ver planos
            </Btn>
            <Btn tone="ghost" back>
              Voltar
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function SourceBadge({ source }: { source: string }) {
  if (source === 'consumption' || source === 'match') return null;
  if (source === 'purchase') return <Badge tone="green">LEGADO</Badge>;
  if (source === 'refund') return <Badge tone="blue">DEVOLUÇÃO</Badge>;
  if (source === 'free' || source === 'free_level') return <Badge tone="lime">GRÁTIS</Badge>;
  if (source === 'admin') return <Badge tone="blue">CORTESIA</Badge>;
  if (source === 'pass') return <Badge tone="blue">ASSINATURA</Badge>;
  return <Badge>{source.toUpperCase()}</Badge>;
}

function lotSourceLabel(source: string): string {
  if (source === 'pass') return 'Franquia da assinatura';
  if (source === 'free' || source === 'free_level') return 'Temporada';
  if (source === 'admin') return 'Cortesia';
  if (source === 'purchase') return 'Crédito legado';
  if (source === 'refund') return 'Devolução';
  return source;
}

function lotTone(source: string): 'lime' | 'blue' | 'green' | 'default' {
  if (source === 'pass') return 'lime';
  if (source === 'free') return 'blue';
  if (source === 'purchase') return 'green';
  return 'default';
}

function LotList({ lots }: { lots: TicketLot[] }) {
  const { palette } = useTheme();
  if (!lots.length) {
    return (
      <Notice tone="blue" icon="info">
        Nenhum lote ativo. A assinatura entrega a franquia de cada ciclo; o crédito legado permanece
        válido.
      </Notice>
    );
  }
  return (
    <CardList>
      {lots.map((lot, index) => (
        <ListRow key={lot.id} last={index === lots.length - 1}>
          <View style={{ flex: 1 }}>
            <Row between>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {lotSourceLabel(lot.source)}
              </Text>
              <Badge tone={lotTone(lot.source)}>
                {lot.remaining} DE {lot.original_amount}
              </Badge>
            </Row>
            <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>
              {lot.source === 'pass'
                ? `Ciclo ${lot.period ?? 'corrente'} · expira no fim do ciclo, não acumula`
                : lot.source === 'purchase' || lot.source === 'refund'
                  ? 'Crédito anterior à assinatura · não expira'
                  : lot.expires_at
                    ? `Expira em ${dateOnly(lot.expires_at)}`
                    : 'Validade não informada'}
            </Text>
          </View>
        </ListRow>
      ))}
    </CardList>
  );
}

function Wallet() {
  const { palette } = useTheme();
  const nav = useNav();
  const { wallet, pass, loadWallet, loadPass } = useApp();
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<'unavailable' | 'network' | null>(null);
  const [passFailure, setPassFailure] = useState(false);
  const load = () => {
    setLoading(true);
    setFailure(null);
    setPassFailure(false);
    return Promise.all([loadWallet(), loadPass().catch(() => setPassFailure(true))])
      .catch((error) => {
        setFailure(
          error instanceof ApiError && error.code === 'balance_unavailable'
            ? 'unavailable'
            : 'network',
        );
      })
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    let active = true;
    Promise.all([loadWallet(), loadPass().catch(() => setPassFailure(true))])
      .catch((error) => {
        if (active) {
          setFailure(
            error instanceof ApiError && error.code === 'balance_unavailable'
              ? 'unavailable'
              : 'network',
          );
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [loadPass, loadWallet]);
  const retry = () => {
    void load();
  };
  const entries =
    wallet?.entries.map((entry) => ({
      amount: entry.amount,
      label:
        entry.source === 'purchase'
          ? 'Crédito legado'
          : entry.source === 'refund'
            ? 'Devolução'
            : entry.source === 'pass'
              ? 'Franquia da assinatura'
              : entry.source === 'free' || entry.source === 'free_level'
                ? 'Ingresso grátis'
                : entry.source === 'admin'
                  ? 'Cortesia'
                  : entry.source === 'consumption' || entry.source === 'match'
                    ? 'Uso em partida'
                    : 'Movimentação de ingressos',
      date: dateOnly(entry.created_at),
      source: entry.source,
    })) ?? [];
  const lots = [...(wallet?.lots ?? [])]
    .filter((lot) => lot.remaining > 0)
    .sort((left, right) => {
      if (!left.expires_at) return 1;
      if (!right.expires_at) return -1;
      return new Date(left.expires_at).getTime() - new Date(right.expires_at).getTime();
    });
  const legacy = legacyTickets(lots);
  const free = freeTickets(lots);
  const cycle = pass?.current_cycle ?? null;
  const subscriptionRemaining = cycle?.tickets_remaining ?? 0;
  const subscriptionExpiry = cycle?.expires_at ?? cycle?.ends_at ?? null;
  const subscriptionActive = pass?.status === 'active';

  if (failure) {
    return (
      <Page title="Ingressos">
        <StateScreen
          icon="wifi-off"
          title={
            failure === 'unavailable'
              ? 'Saldo temporariamente indisponível'
              : 'Não foi possível carregar seus ingressos'
          }
          text={
            failure === 'unavailable'
              ? 'Não foi possível carregar seu saldo agora. Tente novamente.'
              : 'Verifique a conexão e tente novamente. Seu saldo não foi alterado.'
          }
          actions={
            <Btn tone="primary" onPress={retry}>
              Tentar novamente
            </Btn>
          }
        />
      </Page>
    );
  }
  if (loading) {
    return (
      <Page title="Ingressos">
        <LoadingState label="Buscando seus ingressos." variant="wallet" />
      </Page>
    );
  }
  return (
    <Page title="Ingressos">
      <Card tone="ink">
        <Row between>
          <Badge tone="lime">INGRESSOS</Badge>
          <Badge>NÃO TRANSFERÍVEL</Badge>
        </Row>
        <Txt variant="display" color="onInk" style={{ fontSize: 54, marginTop: 12 }}>
          {wallet ? wallet.balance : '—'}
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          ingressos disponíveis
        </Txt>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 12 }}>
          <Badge>ASSINATURA {subscriptionRemaining}</Badge>
          <Badge>LEGADO {legacy}</Badge>
          <Badge>GRÁTIS {free}</Badge>
        </View>
      </Card>
      <Btn tone="ghost" go="wallet-breakdown">
        Ver detalhes
      </Btn>
      <Card tone={subscriptionActive ? 'lime' : 'surface'}>
        <Row between>
          <Txt variant="h3">Assinatura</Txt>
          <Badge tone={subscriptionActive ? 'lime' : pass ? 'orange' : 'default'}>
            {passStatusLabel(pass?.status)}
          </Badge>
        </Row>
        {pass ? (
          <>
            <Txt variant="tiny" style={{ marginTop: 4 }}>
              {pass.plan_label} · {pass.tickets_per_month} ingressos/mês ·{' '}
              {planDurationLabel(pass.cycle_months)}
            </Txt>
            {cycle ? (
              <View style={{ marginTop: 7 }}>
                <Kv label="Franquia do ciclo" value={`${cycle.tickets_granted} ingressos`} />
                <Kv label="Usados" value={`${cycle.tickets_used}`} />
                <Kv label="Restantes" value={`${cycle.tickets_remaining} · não acumula`} />
                <Kv
                  label="Expira em"
                  value={subscriptionExpiry ? dateOnly(subscriptionExpiry) : 'fim do ciclo'}
                />
              </View>
            ) : (
              <Txt variant="tiny" style={{ marginTop: 6 }}>
                Nenhum ciclo em andamento. A franquia é entregue mês a mês.
              </Txt>
            )}
            <Btn
              tone="ghost"
              onPress={() =>
                nav.go(pass.status === 'pending' ? 'checkout-pass' : 'pass-manage', {
                  planCode: pass.plan_code,
                })
              }
            >
              {pass.status === 'pending' ? 'Continuar pagamento' : 'Gerenciar assinatura'}
            </Btn>
          </>
        ) : passFailure ? (
          <>
            <Txt variant="tiny" style={{ marginTop: 4 }}>
              Não foi possível carregar sua assinatura agora. Seu saldo e o crédito legado não foram
              alterados.
            </Txt>
            <Btn tone="ghost" onPress={retry}>
              Tentar novamente
            </Btn>
          </>
        ) : (
          <>
            <Txt variant="tiny" style={{ marginTop: 4 }}>
              Você ainda não tem assinatura. A franquia é entregue no ciclo e não acumula.
            </Txt>
            <Btn tone="primary" go="pass">
              Ver planos
            </Btn>
          </>
        )}
      </Card>
      <Row between>
        <Txt variant="h3">Lotes ativos</Txt>
        <Txt variant="tiny">{lots.length} lotes</Txt>
      </Row>
      <LotList lots={lots} />
      <Notice tone="blue" icon="info">
        Consumo: franquia da assinatura → nível → crédito legado. Cada lote mantém a própria
        validade.
      </Notice>
      <CardList>
        {[
          {
            icon: 'cal' as const,
            title: 'Custo da partida',
            sub: 'Tabela por formato e faixa de horário',
            go: 'match-cost',
          },
          {
            icon: 'trophy' as const,
            title: 'Passe JOGA',
            sub: 'Planos mensal, trimestral e semestral',
            go: 'pass',
          },
          {
            icon: 'cal' as const,
            title: 'Histórico de reservas',
            sub: 'Reservas e devoluções em ingressos',
            go: 'booking-history',
          },
        ].map((item, index, all) => (
          <ListRow key={item.title} last={index === all.length - 1} onPress={() => nav.go(item.go)}>
            <ListIcon icon={item.icon} />
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
      <Row between>
        <Txt variant="h3">Extrato</Txt>
        <Txt variant="tiny">últimos 30 dias</Txt>
      </Row>
      {entries.length ? (
        <CardList>
          {entries.map((entry, index) => (
            <ListRow key={`${entry.label}-${index}`} last={index === entries.length - 1}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                  {entry.label}
                </Text>
                <Text style={{ fontSize: 13, color: palette.muted }}>{entry.date}</Text>
              </View>
              <View style={{ alignItems: 'flex-end', gap: 2 }}>
                <Txt variant="num" style={{ fontSize: 18 }}>
                  {entry.amount > 0 ? `+${entry.amount}` : `−${Math.abs(entry.amount)}`}
                </Txt>
                <SourceBadge source={entry.source} />
              </View>
            </ListRow>
          ))}
        </CardList>
      ) : (
        <EmptyState
          title="Nenhuma movimentação"
          text="Uso em partidas, franquia da assinatura e devoluções aparecem aqui."
        />
      )}
      <Notice tone="blue" icon="info">
        A franquia da assinatura expira no fim do ciclo e não acumula. O crédito legado continua
        válido e não expira.
      </Notice>
    </Page>
  );
}

function WalletBreakdown() {
  const { wallet, pass, loadWallet, loadPass } = useApp();
  const [loading, setLoading] = useState(!wallet);
  const [failure, setFailure] = useState<'unavailable' | 'network' | null>(null);
  const [passFailure, setPassFailure] = useState(false);
  useEffect(() => {
    loadPass().catch(() => setPassFailure(true));
  }, [loadPass]);
  const reload = () => {
    setFailure(null);
    setLoading(true);
    return loadWallet()
      .catch((error) => {
        setFailure(
          error instanceof ApiError && error.code === 'balance_unavailable'
            ? 'unavailable'
            : 'network',
        );
      })
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    if (wallet) {
      return;
    }
    let active = true;
    loadWallet()
      .catch((error) => {
        if (active) {
          setFailure(
            error instanceof ApiError && error.code === 'balance_unavailable'
              ? 'unavailable'
              : 'network',
          );
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [loadWallet, wallet]);
  if (failure) {
    return (
      <Page title="Seus ingressos">
        <StateScreen
          icon="wifi-off"
          title={
            failure === 'unavailable'
              ? 'Saldo temporariamente indisponível'
              : 'Não foi possível carregar seus ingressos'
          }
          text="Não foi possível carregar seu saldo agora."
          actions={
            <Btn tone="primary" onPress={reload}>
              Tentar novamente
            </Btn>
          }
        />
      </Page>
    );
  }
  if (loading || !wallet) {
    return (
      <Page title="Seus ingressos">
        <LoadingState label="Buscando seus ingressos." variant="wallet" />
      </Page>
    );
  }
  const lots = [...wallet.lots].filter((lot) => lot.remaining > 0);
  const legacy = legacyTickets(lots);
  const free = freeTickets(lots);
  const cycle = pass?.current_cycle ?? null;
  const subscriptionRemaining = cycle?.tickets_remaining ?? 0;
  const subscriptionExpiry = cycle?.expires_at ?? cycle?.ends_at ?? null;
  return (
    <Page title="Seus ingressos">
      <Card tone="lime">
        <Row between>
          <Txt variant="h3">Franquia da assinatura</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {subscriptionRemaining}
          </Txt>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          {cycle
            ? `${pass?.plan_label ?? 'Assinatura'} · ciclo ${cycle.period} · expira em ${
                subscriptionExpiry ? dateOnly(subscriptionExpiry) : 'fim do ciclo'
              } · não acumula`
            : passFailure
              ? 'Assinatura temporariamente indisponível'
              : pass?.status === 'pending'
                ? 'Pagamento pendente · a franquia começa após a confirmação'
                : 'Sem franquia ativa'}
        </Txt>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Crédito legado</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {legacy}
          </Txt>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          Comprado antes da assinatura · nunca expira e não é convertido
        </Txt>
      </Card>
      <Card tone="blue">
        <Row between>
          <Txt variant="h3">Ingressos grátis</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {free}
          </Txt>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          Expira no fim da temporada · não converte em dinheiro
        </Txt>
      </Card>
      <Row between>
        <Txt variant="h3">Lotes e validade</Txt>
        <Badge tone="blue">{lots.length}</Badge>
      </Row>
      <LotList lots={lots} />
    </Page>
  );
}

function MatchCost() {
  const nav = useNav();
  const { wallet } = useApp();
  const balance = wallet?.balance ?? null;
  return (
    <Page title="Custo da partida">
      <Card>
        <Kv label="Unidade" value="Ingresso (ticket)" />
        <Kv label="Valor de referência" value={cents(TICKET_REFERENCE_CENTS)} />
        <Kv label="Seu saldo" value={balance != null ? `${balance} ingressos` : 'Indisponível'} />
      </Card>
      <Card>
        <Txt variant="h3">Tabela de conversão</Txt>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          Ingressos por jogador, definidos pela faixa e pelo formato.
        </Txt>
        <Row style={{ marginTop: 10 }}>
          <Txt variant="label" style={{ flex: 1.4 }}>
            Faixa
          </Txt>
          <Txt variant="label" style={{ flex: 1, textAlign: 'center' }}>
            5x5
          </Txt>
          <Txt variant="label" style={{ flex: 1, textAlign: 'center' }}>
            6x6
          </Txt>
          <Txt variant="label" style={{ flex: 1, textAlign: 'center' }}>
            3x3
          </Txt>
        </Row>
        {BAND_ORDER.map((code) => (
          <Row key={code} between style={{ paddingVertical: 9 }}>
            <View style={{ flex: 1.4 }}>
              <Txt variant="tiny">{BAND_LABELS[code]}</Txt>
              <Txt variant="tiny" color="soft">
                {BAND_RANGES[code]}
              </Txt>
            </View>
            <Txt variant="num" style={{ flex: 1, textAlign: 'center', fontSize: 15 }}>
              {TICKETS_BY_BAND[5][code]}
            </Txt>
            <Txt variant="num" style={{ flex: 1, textAlign: 'center', fontSize: 15 }}>
              {TICKETS_BY_BAND[6][code]}
            </Txt>
            <Txt variant="num" style={{ flex: 1, textAlign: 'center', fontSize: 15 }}>
              {TICKETS_BY_BAND[3][code]}
            </Txt>
          </Row>
        ))}
      </Card>
      <Notice tone="blue" icon="info">
        Valores em reais aparecem antes da confirmação. A taxa de 20% é referência, não o valor
        final.
      </Notice>
      <TextBtn muted onPress={() => nav.go('queue', { mode: 'casual' })}>
        Buscar partida
      </TextBtn>
    </Page>
  );
}

function pendingPassKey(planCode: string): string {
  return `joga.pending-pass.${planCode}`;
}

function pendingPassIdempotencyKey(planCode: string): string {
  return `joga.pending-pass-key.${planCode}`;
}

function PaymentEmail() {
  const nav = useNav();
  const { email, emailReady, saveEmail } = useApp();
  const [value, setValue] = useState(email ?? '');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (emailReady) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setValue(email ?? '');
    }
  }, [email, emailReady]);

  const save = async () => {
    const normalized = value.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(normalized)) {
      nav.toast('Informe um e-mail válido.');
      return;
    }
    setBusy(true);
    try {
      await saveEmail(normalized);
      nav.toast('E-mail salvo.');
      nav.back();
    } catch (error) {
      nav.toast(
        error instanceof ApiError && error.code === 'invalid_email'
          ? 'E-mail inválido.'
          : 'Não foi possível salvar o e-mail.',
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page title="E-mail para pagamento">
      <Notice tone="blue" icon="wallet">
        O Mercado Pago exige um e-mail para emitir a cobrança Pix. Ele não aparece no seu perfil
        público.
      </Notice>
      <Field label="E-mail">
        <Input
          value={value}
          onChangeText={setValue}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          maxLength={254}
          placeholder="voce@exemplo.com"
        />
      </Field>
      <Txt variant="tiny">
        Usaremos este e-mail apenas para a cobrança e o comprovante do pagamento.
      </Txt>
      <Btn tone="primary" onPress={save} disabled={busy || !value.trim()}>
        {busy ? 'Salvando…' : 'Salvar e-mail'}
      </Btn>
    </Page>
  );
}

function InsufficientTickets() {
  const nav = useNav();
  const { wallet, loadWallet } = useApp();
  const parseCount = (value: unknown): number | null => {
    const parsed =
      typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN;
    return Number.isFinite(parsed) && parsed > 0 ? Math.ceil(parsed) : null;
  };
  useEffect(() => {
    // Reaproveita o carregamento global da carteira: sem saldo confirmado a
    // tela não pode afirmar que o jogador tem zero ingressos.
    loadWallet().catch(() => undefined);
  }, [loadWallet]);
  const available = wallet?.balance ?? null;
  const needed =
    parseCount(nav.params.needed) ??
    parseCount(nav.params.required) ??
    parseCount(nav.params.tickets) ??
    (available ?? parseCount(nav.params.available) ?? 0) + 1;
  const availableLabel = available != null ? String(available) : '—';
  return (
    <Page title="Ingressos insuficientes">
      <StateScreen
        icon="wallet"
        title="Ingressos insuficientes"
        text={`Você precisa de ${needed} ingressos e tem ${availableLabel}. Os pacotes foram substituídos pela assinatura: escolha um plano para receber a franquia de cada ciclo. Seu crédito legado continua válido.`}
        actions={
          <>
            <Btn tone="primary" go="pass">
              Ver planos
            </Btn>
            <Btn tone="ghost" back>
              Voltar
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function Pass() {
  const { palette } = useTheme();
  const nav = useNav();
  const { pass, passPlans, loadPass } = useApp();
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    loadPass()
      .catch(() => {
        if (active) {
          setFailed(true);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [loadPass]);
  const retry = () => {
    setLoading(true);
    setFailed(false);
    loadPass()
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };
  const plans = passPlans;
  if (loading) {
    return (
      <Page title="Passe JOGA">
        <LoadingState label="Buscando planos do passe." variant="heroList" />
      </Page>
    );
  }
  if (failed) {
    return (
      <Page title="Passe JOGA">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar o passe"
          text="Verifique a conexão e tente novamente. Nenhuma cobrança foi feita."
          actions={
            <Btn tone="primary" onPress={retry}>
              Tentar novamente
            </Btn>
          }
        />
      </Page>
    );
  }
  return (
    <Page title="Passe JOGA">
      <Card tone="ink">
        <Badge tone="lime">ASSINATURA JOGA</Badge>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 30, marginTop: 10, marginBottom: 4 }}
        >
          Sua franquia{'\n'}a cada ciclo.
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          Cobrança única por ciclo. A franquia cai mês a mês e expira no fim de cada ciclo.
        </Txt>
      </Card>
      {pass ? (
        <Card tone={pass.status === 'active' ? 'lime' : 'surface'}>
          <Row between>
            <Txt variant="h3">Sua assinatura</Txt>
            <Badge tone={pass.status === 'active' ? 'lime' : 'orange'}>
              {passStatusLabel(pass.status)}
            </Badge>
          </Row>
          <Txt variant="tiny" style={{ marginTop: 4 }}>
            {pass.plan_label} · {pass.tickets_per_month} ingressos/mês ·{' '}
            {planDurationLabel(pass.cycle_months)}
          </Txt>
          {pass.current_cycle ? (
            <Kv
              label="Franquia restante"
              value={`${pass.current_cycle.tickets_remaining} de ${pass.current_cycle.tickets_granted}`}
            />
          ) : null}
          <Btn tone="ghost" go="pass-manage">
            Gerenciar assinatura
          </Btn>
        </Card>
      ) : null}
      <Row between>
        <Txt variant="h3">Planos</Txt>
        <Txt variant="tiny">{plans.length} opções</Txt>
      </Row>
      <CardList>
        {plans.map((plan, index) => (
          <ListRow
            key={plan.code}
            last={index === plans.length - 1}
            onPress={() => nav.go('checkout-pass', { planCode: plan.code })}
          >
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {plan.label}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>
                {plan.tickets_per_month} ingressos/mês · {planDurationLabel(plan.months)} ·{' '}
                {planCycleName(plan.months)}
              </Text>
              <Text style={{ fontSize: 12, color: palette.muted }}>
                {planInstallmentsLabel(plan.installments)} · não acumula entre ciclos
              </Text>
            </View>
            <View style={{ alignItems: 'flex-end' }}>
              <Txt variant="num" style={{ fontSize: 18 }}>
                {cents(plan.cycle_total_cents)}
              </Txt>
              <Txt variant="tiny" color="soft">
                {cents(plan.unit_price_cents)}/ingresso
              </Txt>
            </View>
          </ListRow>
        ))}
      </CardList>
      <Card>
        <Txt variant="h3">O que vem junto</Txt>
        <View style={{ marginTop: 6 }}>
          {[
            {
              icon: 'trophy' as const,
              title: 'Trilha de temporada',
              sub: 'Itens de passe e retrospectiva',
            },
            { icon: 'globe' as const, title: 'Busca por CEP', sub: 'Intenção em qualquer região' },
            { icon: 'lock' as const, title: 'Lobby privado', sub: 'Feche a partida para o grupo' },
            {
              icon: 'shield' as const,
              title: 'Estatísticas avançadas',
              sub: 'Evolução, passaporte e rede',
            },
          ].map((item, index) => (
            <View
              key={item.title}
              style={{
                flexDirection: 'row',
                alignItems: 'flex-start',
                gap: 10,
                paddingVertical: 11,
                borderBottomWidth: index === 3 ? 0 : 1,
                borderBottomColor: palette.line,
              }}
            >
              <Icon name={item.icon} size={16} color={palette.ink} />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                  {item.title}
                </Text>
                <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
              </View>
            </View>
          ))}
        </View>
      </Card>
      {plans.length === 0 ? (
        <EmptyState
          title="Nenhum plano disponível"
          text="Os planos da assinatura aparecem aqui quando estiverem à venda."
        />
      ) : null}
      <Notice tone="blue" icon="info">
        A franquia de cada ciclo expira no fim do ciclo e não acumula. O crédito legado continua
        válido e não expira.
      </Notice>
      <TextBtn go="pass-past-due" muted>
        Minha assinatura está em atraso
      </TextBtn>
    </Page>
  );
}

function CheckoutPass() {
  const nav = useNav();
  const { palette } = useTheme();
  const { session, passPlans, loadPass, loadWallet, email, emailReady } = useApp();
  const code = typeof nav.params.planCode === 'string' ? nav.params.planCode : '';
  const plan = passPlans.find((item) => item.code === code) ?? null;
  const planCode = plan?.code ?? code;
  const [subscription, setSubscription] = useState<PassSubscription | null>(null);
  const [creating, setCreating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [terms, setTerms] = useState<TermsVersion | null>(null);
  const [termsReady, setTermsReady] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [acceptingTerms, setAcceptingTerms] = useState(false);
  const created = useRef(false);

  useEffect(() => {
    let active = true;
    api.legal
      .currentTerms()
      .then((result) => {
        if (active) {
          setTerms(result.terms);
        }
      })
      .catch(() => {
        if (active) {
          // Sem a versão vigente, a criação tenta sem `terms_version_id` e o
          // servidor responde se o aceite for realmente exigido.
          setTerms(null);
        }
      })
      .finally(() => {
        if (active) {
          setTermsReady(true);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!session || !emailReady || !email || !termsReady) {
      return;
    }
    if (created.current || !plan) {
      return;
    }
    if (terms && !termsAccepted) {
      return;
    }
    created.current = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCreating(true);
    const storedKey = pendingPassKey(planCode);
    const idempotencyKey = pendingPassIdempotencyKey(planCode);
    (async () => {
      try {
        const existingId = await SecureStore.getItemAsync(storedKey);
        if (existingId) {
          try {
            const existing = await api.passes.subscription(session.accessToken, existingId);
            const existingState = paymentState(existing.status, existing.payment?.provider_status);
            if (existingState === 'pending' || existingState === 'paid') {
              setSubscription(existing);
              return;
            }
          } catch {
            // Contrato antigo não existe mais; abre uma nova cobrança abaixo.
          }
          await SecureStore.deleteItemAsync(storedKey);
          await SecureStore.deleteItemAsync(idempotencyKey);
        }
        // A mesma chave sobrevive a falhas de rede: repetir o POST devolve a
        // mesma assinatura em vez de abrir uma segunda cobrança.
        let requestKey = await SecureStore.getItemAsync(idempotencyKey);
        if (!requestKey) {
          requestKey = newIdempotencyKey();
          await SecureStore.setItemAsync(idempotencyKey, requestKey);
        }
        const created = await api.passes.subscribe(
          session.accessToken,
          planCode,
          requestKey,
          terms?.id,
        );
        await SecureStore.setItemAsync(storedKey, created.id);
        setSubscription(created);
      } catch (cause) {
        if (cause instanceof ApiError && cause.code === 'payer_email_required') {
          created.current = false;
          nav.replace('payment-email');
          return;
        }
        if (cause instanceof ApiError && cause.code === 'terms_not_accepted') {
          const refreshed = await api.legal.currentTerms().catch(() => null);
          if (refreshed) {
            setTerms(refreshed.terms);
          }
          setTermsAccepted(false);
          setError('Aceite a versão vigente dos Termos de uso para continuar.');
          setErrorCode(cause.code);
        } else if (cause instanceof ApiError && cause.code === 'idempotency_conflict') {
          await SecureStore.deleteItemAsync(idempotencyKey);
          await SecureStore.deleteItemAsync(storedKey);
          setError(
            'A assinatura anterior tinha outro plano. Tente novamente para gerar um novo Pix.',
          );
          setErrorCode(cause.code);
        } else if (cause instanceof ApiError && cause.code === 'pass_already_active') {
          setError('Você já tem uma assinatura ativa. Gerencie o contrato atual.');
          setErrorCode(cause.code);
        } else if (cause instanceof ApiError && cause.code === 'ticket_sales_discontinued') {
          setError(TICKET_SALES_DISCONTINUED_TEXT);
          setErrorCode(cause.code);
        } else if (cause instanceof ApiError && cause.code === 'ticket_purchase_disabled') {
          setError(SUBSCRIPTION_DISABLED_TEXT);
          setErrorCode(cause.code);
        } else if (cause instanceof ApiError && cause.code === 'terms_context_unavailable') {
          setError('Não foi possível registrar o aceite agora. Tente novamente.');
          setErrorCode(cause.code);
        } else if (cause instanceof ApiError && cause.code === 'psp_unavailable') {
          setError('O Pix está temporariamente indisponível. Nenhuma cobrança foi aberta.');
          setErrorCode(cause.code);
        } else {
          setError('Não foi possível abrir a cobrança Pix da assinatura.');
          setErrorCode(cause instanceof ApiError ? cause.code : null);
        }
      } finally {
        setCreating(false);
      }
    })();
  }, [attempt, email, emailReady, nav, plan, planCode, session, terms, termsAccepted, termsReady]);

  useEffect(() => {
    if (!subscription || !session) {
      return;
    }
    if (paymentState(subscription.status, subscription.payment?.provider_status) !== 'pending') {
      return;
    }
    let active = true;
    const timer = setInterval(() => {
      api.passes
        .sync(session.accessToken, subscription.id)
        .then((updated) => {
          if (active) {
            setSubscription(updated);
          }
        })
        .catch(() => undefined);
    }, 7000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [subscription, session]);

  const state = subscription
    ? paymentState(subscription.status, subscription.payment?.provider_status)
    : 'pending';

  useEffect(() => {
    if (state === 'paid') {
      loadPass().catch(() => undefined);
      loadWallet().catch(() => undefined);
      void SecureStore.deleteItemAsync(pendingPassKey(planCode));
      void SecureStore.deleteItemAsync(pendingPassIdempotencyKey(planCode));
    }
  }, [loadPass, loadWallet, planCode, state]);

  const refresh = async () => {
    if (!subscription || !session || refreshing) {
      return;
    }
    setRefreshing(true);
    try {
      setSubscription(await api.passes.sync(session.accessToken, subscription.id));
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === 'payer_email_required') {
        nav.replace('payment-email');
        return;
      }
      nav.toast('Não foi possível consultar o pagamento.');
    } finally {
      setRefreshing(false);
    }
  };

  const retryCreate = () => {
    // Mantém a chave de idempotência: se o POST anterior chegou ao servidor e a
    // resposta se perdeu, o replay devolve a mesma assinatura.
    created.current = false;
    setSubscription(null);
    setError(null);
    setErrorCode(null);
    setAttempt((current) => current + 1);
  };

  const retryNewCharge = async () => {
    if (subscription && session && subscription.status === 'pending') {
      await api.passes.cancel(session.accessToken, subscription.id).catch(() => undefined);
    }
    await SecureStore.deleteItemAsync(pendingPassKey(planCode));
    await SecureStore.deleteItemAsync(pendingPassIdempotencyKey(planCode));
    created.current = false;
    setSubscription(null);
    setError(null);
    setErrorCode(null);
    setAttempt((current) => current + 1);
  };

  const acceptTerms = async () => {
    if (!session || !terms || acceptingTerms) {
      return;
    }
    setAcceptingTerms(true);
    try {
      await api.legal.acceptTerms(session.accessToken, terms.id, 'pass_purchase');
      setTermsAccepted(true);
    } catch {
      setError('Não foi possível registrar o aceite dos Termos. Tente novamente.');
      setErrorCode('terms_accept_failed');
    } finally {
      setAcceptingTerms(false);
    }
  };

  if (errorCode === 'ticket_purchase_disabled') {
    return <SubscriptionUnavailableState text={SUBSCRIPTION_DISABLED_TEXT} />;
  }

  if (errorCode === 'pass_already_active') {
    return (
      <Page title="Assinatura">
        <StateScreen
          icon="trophy"
          title="Assinatura já ativa"
          text="Você já tem uma assinatura em vigor. O novo contrato só pode ser aberto quando o atual terminar."
          actions={
            <>
              <Btn tone="primary" go="pass-manage">
                Gerenciar assinatura
              </Btn>
              <Btn tone="ghost" go="pass">
                Ver planos
              </Btn>
            </>
          }
        />
      </Page>
    );
  }

  if (!emailReady || !termsReady || creating) {
    return (
      <Page title="Checkout da assinatura">
        <LoadingState label="Abrindo cobrança Pix da assinatura." variant="cards" />
      </Page>
    );
  }

  if (!email) {
    return (
      <Page title="Checkout da assinatura">
        <StateScreen
          icon="mail"
          title="E-mail necessário"
          text="Antes da primeira cobrança, informe um e-mail para o Mercado Pago emitir o Pix."
          actions={
            <Btn tone="primary" go="payment-email">
              Informar e-mail
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!plan) {
    return (
      <Page title="Checkout da assinatura">
        <EmptyState
          title="Plano indisponível"
          text="Os planos da assinatura aparecem aqui quando estiverem à venda."
          actions={
            <Btn tone="primary" go="pass">
              Ver planos
            </Btn>
          }
        />
      </Page>
    );
  }

  if (terms && !termsAccepted && !subscription) {
    return (
      <Page title="Termos da assinatura">
        <Card>
          <Row between>
            <Txt variant="h3">Termos de uso</Txt>
            <Badge tone="blue">v{terms.version}</Badge>
          </Row>
          <Text
            style={{
              marginTop: 10,
              fontSize: 13,
              lineHeight: 19,
              color: palette.muted,
            }}
          >
            {terms.content}
          </Text>
        </Card>
        {error ? (
          <Notice tone="orange" icon="alert">
            {error}
          </Notice>
        ) : null}
        <Check checked={termsAccepted} onChange={setTermsAccepted}>
          Li e aceito a versão vigente dos Termos de uso para assinar o Passe JOGA.
        </Check>
        <Btn tone="primary" onPress={acceptTerms} disabled={termsAccepted || acceptingTerms}>
          {acceptingTerms ? 'Registrando aceite…' : 'Aceitar e abrir Pix'}
        </Btn>
        <Btn tone="ghost" go="pass">
          Voltar aos planos
        </Btn>
      </Page>
    );
  }

  if (!subscription) {
    return (
      <Page title="Checkout da assinatura">
        <StateScreen
          icon="wifi-off"
          title="Cobrança indisponível"
          text={error ?? 'Não foi possível abrir o Pix da assinatura agora. Tente novamente.'}
          actions={
            <>
              <Btn tone="primary" onPress={retryCreate}>
                Tentar novamente
              </Btn>
              <Btn tone="ghost" go="pass">
                Voltar aos planos
              </Btn>
            </>
          }
        />
      </Page>
    );
  }

  const amountCents =
    subscription.payment?.amount_cents ?? subscription.amount_cents ?? plan.cycle_total_cents;

  return (
    <Page title="Checkout da assinatura">
      <Card>
        <Row between>
          <Txt variant="h3">{subscription.plan_label || plan.label}</Txt>
          <Badge tone="blue">{subscription.tickets_per_month}/mês</Badge>
        </Row>
        <Row between style={{ marginTop: 10 }}>
          <Txt variant="tiny">
            {planCycleName(subscription.cycle_months)} ·{' '}
            {planDurationLabel(subscription.cycle_months)}
          </Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {cents(amountCents)}
          </Txt>
        </Row>
        <Txt variant="tiny">
          {subscription.tickets_per_month * subscription.cycle_months} ingressos no total, entregues
          mês a mês · {cents(subscription.unit_price_cents)} por ingresso
        </Txt>
      </Card>
      <PaymentPix
        payment={subscription.payment}
        purchaseStatus={subscription.status}
        amountCents={amountCents}
        onRefresh={refresh}
        refreshing={refreshing}
      />
      {state === 'paid' ? (
        <>
          <Notice tone="green" icon="check">
            Pagamento confirmado. A assinatura está ativa e a franquia do ciclo já foi entregue.
          </Notice>
          <Btn tone="primary" go="pass-manage">
            Ver minha assinatura
          </Btn>
          {receiptAvailable(subscription) ? (
            <Btn
              tone="ghost"
              onPress={() => nav.go('pass-receipt', { subscriptionId: subscription.id })}
            >
              Ver recibo
            </Btn>
          ) : null}
        </>
      ) : state === 'expired' || state === 'failed' ? (
        <>
          <Notice tone="orange" icon="alert">
            O Pix da assinatura expirou ou não foi concluído. Nenhuma cobrança foi ativada.
          </Notice>
          <Btn tone="primary" onPress={retryNewCharge}>
            Gerar novo Pix
          </Btn>
        </>
      ) : (
        <Notice tone="blue" icon="lock">
          A franquia é entregue mês a mês. Cada ciclo expira no próprio período e não acumula. A
          tela atualiza automaticamente.
        </Notice>
      )}
    </Page>
  );
}

function PassManage() {
  const nav = useNav();
  const { pass, loadPass } = useApp();
  useEffect(() => {
    loadPass().catch(() => undefined);
  }, [loadPass]);
  if (!pass) {
    return (
      <Page title="Minha assinatura">
        <EmptyState
          title="Nenhuma assinatura ativa"
          text="Assine o passe para receber a franquia de ingressos de cada ciclo."
          actions={
            <Btn tone="primary" go="pass">
              Ver planos
            </Btn>
          }
        />
      </Page>
    );
  }
  const cycle = pass.current_cycle;
  const delivered = pass.cycles.reduce(
    (sum, item) =>
      item.status === 'delivered' || item.status === 'closed' ? sum + item.tickets : sum,
    0,
  );
  return (
    <Page title="Minha assinatura">
      <Card tone="ink">
        <Row between>
          <Badge tone={pass.status === 'active' ? 'lime' : 'orange'}>
            {passStatusLabel(pass.status)}
          </Badge>
          <Badge>{planCycleName(pass.cycle_months)}</Badge>
        </Row>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 28, marginTop: 10, marginBottom: 4 }}
        >
          {pass.plan_label}
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          {pass.tickets_per_month} ingressos/mês · {planDurationLabel(pass.cycle_months)} ·{' '}
          {cents(pass.unit_price_cents)} por ingresso
        </Txt>
        <Txt variant="tiny" color="softOnInk" style={{ marginTop: 4 }}>
          {pass.starts_at ? `Início ${dateOnly(pass.starts_at)}` : 'Início a confirmar'}
          {pass.ends_at ? ` · fim ${dateOnly(pass.ends_at)}` : ''}
        </Txt>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">{cycle ? `Ciclo ${cycle.period}` : 'Ciclo corrente'}</Txt>
          <Badge tone="blue">{cycle ? `${cycle.tickets_remaining} restantes` : 'sem uso'}</Badge>
        </Row>
        {cycle ? (
          <>
            <Kv label="Franquia do ciclo" value={`${cycle.tickets_granted} ingressos`} />
            <Kv label="Usados" value={`${cycle.tickets_used}`} />
            <Kv label="Restantes" value={`${cycle.tickets_remaining} · não acumula`} />
            <Kv
              label="Expira em"
              value={
                cycle.expires_at
                  ? dateOnly(cycle.expires_at)
                  : `fim do ciclo (${dateOnly(cycle.ends_at)})`
              }
            />
          </>
        ) : (
          <Txt variant="tiny" style={{ marginTop: 6 }}>
            Nenhum ciclo em andamento. A franquia é entregue no início de cada ciclo.
          </Txt>
        )}
        <Kv
          label="Próxima entrega"
          value={pass.next_delivery_at ? dateOnly(pass.next_delivery_at) : 'sem próxima entrega'}
        />
        <Kv label="Total do ciclo" value={cents(pass.amount_cents)} />
        <Kv label="Forma" value={planInstallmentsLabel(pass.installments)} />
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Ciclos</Txt>
          <Badge tone="green">{delivered} ingressos entregues</Badge>
        </Row>
        {pass.cycles.length ? (
          pass.cycles.map((item) => (
            <Kv
              key={`${item.month_index}-${item.period}`}
              label={`Mês ${item.month_index} · ${item.period}`}
              value={`${item.tickets} ingressos · ${cycleStatusLabel(item.status)}${
                item.delivered_at ? ` · ${dateOnly(item.delivered_at)}` : ''
              }`}
            />
          ))
        ) : (
          <Txt variant="tiny" style={{ marginTop: 6 }}>
            Nenhum ciclo registrado ainda.
          </Txt>
        )}
      </Card>
      {receiptAvailable(pass) ? (
        <Btn onPress={() => nav.go('pass-receipt', { subscriptionId: pass.id })}>Ver recibo</Btn>
      ) : null}
      <Notice tone="blue" icon="info">
        A franquia de cada ciclo expira no fim do ciclo e não vira crédito. O crédito legado
        continua válido e não expira.
      </Notice>
      <Btn tone="ghost" go="support">
        Falar com o suporte
      </Btn>
    </Page>
  );
}

function PassPastDue() {
  const { pass } = useApp();
  return (
    <Page title="Minha assinatura">
      <StateScreen
        icon="alert"
        title="Assinatura em atraso"
        text="Quando o pagamento do ciclo não é confirmado, a franquia daquele ciclo não é entregue. Fale com o suporte para regularizar; itens de passe podem ser revogados."
        actions={
          <>
            <Btn tone="primary" go="pass">
              Ver planos
            </Btn>
            <Btn tone="ghost" go="support">
              Falar com o suporte
            </Btn>
          </>
        }
      />
      <Card>
        <Kv label="Status da assinatura" value={passStatusLabel(pass?.status)} />
        <Kv
          label="Próxima entrega"
          value={pass?.next_delivery_at ? dateOnly(pass.next_delivery_at) : 'a confirmar'}
        />
        <Kv
          label="Franquia do ciclo"
          value={pass?.current_cycle ? `${pass.current_cycle.tickets_remaining} restantes` : '—'}
        />
      </Card>
      <Notice tone="orange" icon="info">
        A franquia de cada ciclo não acumula. O que não for usado no ciclo não vira crédito para o
        ciclo seguinte.
      </Notice>
    </Page>
  );
}

function PassReceiptScreen() {
  const nav = useNav();
  const { session } = useApp();
  const subscriptionId =
    typeof nav.params.subscriptionId === 'string' ? nav.params.subscriptionId : '';
  const [receipt, setReceipt] = useState<PassReceipt | null>(null);
  const [loading, setLoading] = useState(Boolean(session && subscriptionId));
  const [failure, setFailure] = useState<string | null>(
    session && subscriptionId ? null : 'Recibo indisponível.',
  );

  useEffect(() => {
    if (!session || !subscriptionId) {
      return;
    }
    let active = true;
    api.passes
      .receipt(session.accessToken, subscriptionId)
      .then((result) => {
        if (active) {
          setReceipt(result);
          setFailure(null);
        }
      })
      .catch((cause) => {
        if (!active) {
          return;
        }
        if (cause instanceof ApiError && cause.code === 'receipt_not_available') {
          setFailure('O recibo aparece depois da confirmação do pagamento.');
        } else {
          setFailure('Não foi possível carregar o recibo. Tente novamente.');
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [session, subscriptionId]);

  if (loading) {
    return (
      <Page title="Recibo">
        <LoadingState label="Buscando o recibo." variant="cards" />
      </Page>
    );
  }
  if (!receipt) {
    return (
      <Page title="Recibo">
        <StateScreen
          icon="wallet"
          title="Recibo indisponível"
          text={failure ?? 'Não foi possível carregar o recibo.'}
          actions={
            <>
              <Btn tone="primary" go="pass-manage">
                Voltar à assinatura
              </Btn>
              <Btn tone="ghost" back>
                Voltar
              </Btn>
            </>
          }
        />
      </Page>
    );
  }
  return (
    <Page title="Recibo">
      <Card tone="ink">
        <Badge tone="lime">RECIBO INTERNO</Badge>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 28, marginTop: 10, marginBottom: 4 }}
        >
          {cents(receipt.amount_cents)}
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          {receipt.plan_label} · pago em {shortDateTime(receipt.paid_at)}
        </Txt>
      </Card>
      <Card>
        <Kv label="Plano" value={receipt.plan_label} />
        <Kv
          label="Ciclo"
          value={`${planCycleName(receipt.cycle_months)} · ${planDurationLabel(receipt.cycle_months)}`}
        />
        <Kv label="Franquia mensal" value={`${receipt.tickets_per_month} ingressos`} />
        <Kv label="Preço por ingresso" value={cents(receipt.unit_price_cents)} />
        <Kv label="Total do ciclo" value={cents(receipt.cycle_total_cents)} />
        <Kv label="Valor pago" value={cents(receipt.amount_cents)} />
        <Kv label="Data do pagamento" value={shortDateTime(receipt.paid_at)} />
        <Kv label="Identificador" value={receipt.receipt_id} />
        <Kv label="Situação" value={receipt.status.toUpperCase()} />
        {receipt.provider ? <Kv label="Meio de pagamento" value={receipt.provider} /> : null}
      </Card>
      <Notice tone="blue" icon="info">
        Recibo interno — sem documento fiscal. Comprova a compra no JOGA.
      </Notice>
      <Btn tone="ghost" go="pass-manage">
        Voltar à assinatura
      </Btn>
    </Page>
  );
}

function RefundTickets() {
  return (
    <Page title="Devoluções">
      <StateScreen
        icon="wallet"
        title="Devolução em ingressos"
        text="Se a quadra não confirmar ou a reserva expirar antes do prazo, os ingressos voltam para o seu saldo. Depois do prazo ou em falta sem aviso não há devolução."
        actions={
          <>
            <Btn tone="primary" go="wallet">
              Ver meus ingressos
            </Btn>
            <Btn tone="ghost" go="booking-history">
              Ver reservas
            </Btn>
          </>
        }
      />
      <Card>
        <Kv label="Forma" value="Devolução em ingressos" />
        <Kv label="Reembolso parcial" value="Não existe" />
        <Kv label="Dinheiro" value="Não é convertido em saque" />
      </Card>
      <Notice tone="blue" icon="info">
        O crédito comprado não expira. A devolução de uma reserva não altera a validade dos seus
        lotes.
      </Notice>
    </Page>
  );
}

export const walletScreens: ScreenDef[] = [
  { id: 'wallet', tab: 'perfil', render: () => <Wallet /> },
  { id: 'wallet-breakdown', tab: 'perfil', render: () => <WalletBreakdown /> },
  { id: 'match-cost', tab: 'jogar', render: () => <MatchCost /> },
  { id: 'payment-email', tab: 'perfil', render: () => <PaymentEmail /> },
  { id: 'insufficient-tickets', tab: 'jogar', render: () => <InsufficientTickets /> },
  { id: 'pass', tab: 'perfil', render: () => <Pass /> },
  { id: 'checkout-pass', tab: 'perfil', render: () => <CheckoutPass /> },
  { id: 'pass-manage', tab: 'perfil', render: () => <PassManage /> },
  { id: 'pass-receipt', tab: 'perfil', render: () => <PassReceiptScreen /> },
  { id: 'pass-past-due', tab: 'perfil', render: () => <PassPastDue /> },
  { id: 'refund-tickets', tab: 'perfil', render: () => <RefundTickets /> },
];
