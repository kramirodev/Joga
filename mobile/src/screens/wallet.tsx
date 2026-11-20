import { useEffect, useRef, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import { View } from 'react-native';

import { api, ApiError, newIdempotencyKey } from '../api/client';
import type { PassSubscription, Purchase, TermsVersion, TicketLot } from '../api/types';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import { PaymentPix, paymentState } from '../ui/PaymentPix';
import { Text } from '../ui/text';
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
  ListRow,
  LoadingState,
  Notice,
  Page,
  Row,
  StateScreen,
  TextBtn,
  Txt,
} from '../ui/kit';
import { cents, dateOnly } from '../ui/datetime';
import { Icon } from '../ui/icons';
import {
  BAND_LABELS,
  BAND_ORDER,
  BAND_RANGES,
  TICKETS_BY_BAND,
  TICKET_REFERENCE_CENTS,
} from '../ui/tickets';
import type { ScreenDef } from './types';

const TICKET_PURCHASE_DISABLED_TEXT =
  'A compra de ingressos está desativada nesta versão do JOGA. Seus ingressos atuais continuam válidos e podem ser usados normalmente nas reservas.';

function PurchaseDisabledState() {
  return (
    <Page title="Ingressos">
      <StateScreen
        icon="wallet"
        title="Compra de ingressos indisponível"
        text={TICKET_PURCHASE_DISABLED_TEXT}
        actions={
          <Btn tone="primary" back>
            Voltar
          </Btn>
        }
      />
    </Page>
  );
}

function SourceBadge({ source }: { source: string }) {
  if (source === 'consumption' || source === 'match') return null;
  if (source === 'purchase') return <Badge>COMPRA</Badge>;
  if (source === 'refund') return <Badge tone="blue">DEVOLUÇÃO</Badge>;
  if (source === 'free' || source === 'free_level') return <Badge tone="lime">GRÁTIS</Badge>;
  if (source === 'admin') return <Badge tone="blue">CORTESIA</Badge>;
  if (source === 'pass') return <Badge tone="blue">PASSE</Badge>;
  return <Badge>{source.toUpperCase()}</Badge>;
}

function lotSourceLabel(source: string): string {
  if (source === 'pass') return 'Passe';
  if (source === 'free' || source === 'free_level') return 'Temporada';
  if (source === 'admin') return 'Cortesia';
  if (source === 'purchase') return 'Comprado';
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
        Nenhum lote ativo. Compre ingressos ou conclua uma temporada para receber lotes.
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
                ? `Franquia de ${lot.period ?? 'mês corrente'} · mensal, não acumula`
                : lot.source === 'purchase' || lot.source === 'refund'
                  ? 'Não expira'
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
  const { wallet, loadWallet } = useApp();
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<'unavailable' | 'network' | null>(null);
  const load = () => {
    setLoading(true);
    setFailure(null);
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
  }, [loadWallet]);
  const retry = () => {
    void load();
  };
  const entries =
    wallet?.entries.map((entry) => ({
      amount: entry.amount,
      label:
        entry.source === 'purchase'
          ? 'Compra de pacote'
          : entry.source === 'refund'
            ? 'Devolução'
            : entry.source === 'pass'
              ? 'Franquia do passe'
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
  const sums = lots.reduce(
    (acc, lot) => {
      if (lot.source === 'pass') acc.pass += lot.remaining;
      else if (lot.source === 'purchase') acc.bought += lot.remaining;
      else if (lot.source === 'free') acc.free += lot.remaining;
      return acc;
    },
    { pass: 0, bought: 0, free: 0 },
  );
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
        <View style={{ flexDirection: 'row', gap: 6, marginTop: 12 }}>
          <Badge>PASSE {sums.pass}</Badge>
          <Badge>COMPRADOS {sums.bought}</Badge>
          <Badge>GRÁTIS {sums.free}</Badge>
        </View>
      </Card>
      <Btn tone="ghost" go="wallet-breakdown">
        Ver detalhes
      </Btn>
      <Row between>
        <Txt variant="h3">Lotes ativos</Txt>
        <Txt variant="tiny">{lots.length} lotes</Txt>
      </Row>
      <LotList lots={lots} />
      <Notice tone="blue" icon="info">
        Consumo: passe → nível → comprado. Cada lote mantém a própria validade.
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
            sub: 'Franquia mensal, benefícios e gestão',
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
          text="Compras, uso em partidas e devoluções aparecem aqui."
        />
      )}
      <Notice tone="blue" icon="info">
        Ingresso comprado nunca expira. Franquia do passe e ingressos grátis têm validade própria.
      </Notice>
    </Page>
  );
}

function WalletBreakdown() {
  const { wallet, loadWallet } = useApp();
  const [loading, setLoading] = useState(!wallet);
  const [failure, setFailure] = useState<'unavailable' | 'network' | null>(null);
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
  const passPeriods = [
    ...new Set(lots.filter((lot) => lot.source === 'pass' && lot.period).map((lot) => lot.period!)),
  ];
  const sums = lots.reduce(
    (acc, lot) => {
      if (lot.source === 'pass') acc.pass += lot.remaining;
      else if (lot.source === 'purchase') acc.bought += lot.remaining;
      else if (lot.source === 'free') acc.free += lot.remaining;
      return acc;
    },
    { pass: 0, bought: 0, free: 0 },
  );
  return (
    <Page title="Seus ingressos">
      <Card tone="lime">
        <Row between>
          <Txt variant="h3">Franquia do passe</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {sums.pass}
          </Txt>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          {sums.pass > 0
            ? `Mensal${passPeriods.length ? ` · ${passPeriods.join(', ')}` : ''} · não acumula`
            : 'Sem franquia ativa'}
        </Txt>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Ingressos comprados</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {sums.bought}
          </Txt>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          Crédito comprado · nunca expira
        </Txt>
      </Card>
      <Card tone="blue">
        <Row between>
          <Txt variant="h3">Ingressos grátis</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {sums.free}
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

function Store() {
  const nav = useNav();
  const { palette } = useTheme();
  const { packs, loadStore } = useApp();
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    loadStore()
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
  }, [loadStore]);
  const retry = () => {
    setLoading(true);
    setFailed(false);
    loadStore()
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };
  const options = packs.map((pack) => ({
    code: pack.code,
    tickets: pack.tickets,
    label: pack.label,
    amount: pack.amount_cents,
    unit: pack.unit_price_cents,
  }));
  const [selected, setSelected] = useState(1);
  const selectedIndex = Math.min(selected, Math.max(0, options.length - 1));
  const current = options[selectedIndex] ?? options[0];
  if (loading) {
    return (
      <Page title="Ingressos">
        <LoadingState label="Buscando pacotes disponíveis." variant="grid" />
      </Page>
    );
  }
  if (failed) {
    return (
      <Page title="Ingressos">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar os pacotes"
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
  if (!current) {
    return (
      <Page title="Ingressos">
        <EmptyState
          title="Nenhum pacote disponível"
          text="Os pacotes de ingressos aparecem aqui quando estiverem à venda."
        />
      </Page>
    );
  }
  return (
    <Page title="Ingressos">
      <Txt variant="lead">
        Pacotes pré-pagos. O ingresso é pessoal, não transferível e não vira dinheiro.
      </Txt>
      <Notice tone="blue" icon="info">
        Crédito comprado não expira. O ingresso é a unidade de consumo por faixa e formato.
      </Notice>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        {options.map((option, index) => (
          <Card
            key={option.code}
            style={{
              width: '47%',
              borderColor: selectedIndex === index ? palette.ink : palette.line,
              borderWidth: selectedIndex === index ? 2 : 1.5,
            }}
            onPress={() => setSelected(index)}
          >
            <Txt variant="label">{option.label}</Txt>
            <Txt variant="num" style={{ fontSize: 38 }}>
              {option.tickets}
            </Txt>
            <Txt variant="tiny">ingressos</Txt>
            <Txt variant="num" style={{ marginTop: 2, fontSize: 15 }}>
              {cents(option.amount)}
            </Txt>
            <Txt variant="tiny" color="soft">
              {cents(option.unit)} por ingresso
            </Txt>
            {index === options.length - 1 ? (
              <View style={{ marginTop: 8, minHeight: 23 }}>
                <Badge tone="lime">MELHOR VALOR</Badge>
              </View>
            ) : (
              <View style={{ marginTop: 8, minHeight: 23 }} />
            )}
          </Card>
        ))}
      </View>
      <Btn
        tone="primary"
        onPress={() =>
          nav.go('checkout-package', {
            packCode: current.code,
            tickets: current.tickets,
            amount: current.amount,
          })
        }
      >
        {`Continuar com ${current.tickets} ingressos`}
      </Btn>
    </Page>
  );
}

function pendingPurchaseKey(packCode: string): string {
  return `joga.pending-purchase.${packCode}`;
}

function pendingPurchaseIdempotencyKey(packCode: string): string {
  return `joga.pending-purchase-key.${packCode}`;
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

function CheckoutPackage({ avulso }: { avulso?: boolean }) {
  const nav = useNav();
  const { palette } = useTheme();
  const { session, loadWallet, email, emailReady } = useApp();
  const packCode =
    typeof nav.params.packCode === 'string' ? nav.params.packCode : avulso ? 'avulso' : 'pequeno';
  const [purchase, setPurchase] = useState<Purchase | null>(null);
  const [creating, setCreating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
          // Sem a versão vigente não é possível saber se o aceite é exigido.
          // A compra tentará sem `terms_version_id` e o servidor responderá.
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
    if (created.current || !session || !emailReady || !email || !termsReady) {
      return;
    }
    if (terms && !termsAccepted) {
      return;
    }
    created.current = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCreating(true);
    const key = pendingPurchaseKey(packCode);
    const idempotencyKey = pendingPurchaseIdempotencyKey(packCode);
    (async () => {
      try {
        const existingId = await SecureStore.getItemAsync(key);
        if (existingId) {
          try {
            const existing = await api.tickets.purchase(session.accessToken, existingId);
            if (paymentState(existing.status, existing.payment?.provider_status) === 'pending') {
              setPurchase(existing);
              return;
            }
          } catch {
            // Cobrança antiga não existe mais; cria uma nova abaixo.
          }
          await SecureStore.deleteItemAsync(key);
          await SecureStore.deleteItemAsync(idempotencyKey);
        }
        // A mesma chave sobrevive a falhas de rede: repetir o POST devolve a
        // mesma cobrança em vez de abrir uma segunda.
        let requestKey = await SecureStore.getItemAsync(idempotencyKey);
        if (!requestKey) {
          requestKey = newIdempotencyKey();
          await SecureStore.setItemAsync(idempotencyKey, requestKey);
        }
        const createdPurchase = await api.tickets.createPurchase(
          session.accessToken,
          packCode,
          requestKey,
          terms?.id,
        );
        await SecureStore.setItemAsync(key, createdPurchase.id);
        setPurchase(createdPurchase);
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
        } else if (cause instanceof ApiError && cause.code === 'ticket_purchase_disabled') {
          setError(TICKET_PURCHASE_DISABLED_TEXT);
        } else if (cause instanceof ApiError && cause.code === 'idempotency_conflict') {
          await SecureStore.deleteItemAsync(idempotencyKey);
          setError(
            'A cobrança anterior tinha outros dados. Tente novamente para gerar um novo Pix.',
          );
        } else {
          setError('Não foi possível abrir a cobrança Pix.');
        }
      } finally {
        setCreating(false);
      }
    })();
  }, [attempt, email, emailReady, nav, packCode, session, terms, termsAccepted, termsReady]);

  useEffect(() => {
    if (!purchase || !session) {
      return;
    }
    if (paymentState(purchase.status, purchase.payment?.provider_status) !== 'pending') {
      return;
    }
    let active = true;
    const timer = setInterval(() => {
      api.tickets
        .syncPurchase(session.accessToken, purchase.id)
        .then((updated) => {
          if (active) {
            setPurchase(updated);
          }
        })
        .catch(() => undefined);
    }, 7000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [purchase, session]);

  const state = purchase
    ? paymentState(purchase.status, purchase.payment?.provider_status)
    : 'pending';

  useEffect(() => {
    if (purchase && state !== 'pending') {
      void SecureStore.deleteItemAsync(pendingPurchaseKey(packCode));
      void SecureStore.deleteItemAsync(pendingPurchaseIdempotencyKey(packCode));
    }
  }, [packCode, purchase, state]);

  useEffect(() => {
    if (state === 'paid') {
      loadWallet().catch(() => undefined);
    }
  }, [loadWallet, state]);

  const refresh = async () => {
    if (!purchase || !session || refreshing) {
      return;
    }
    setRefreshing(true);
    try {
      const updated = await api.tickets.syncPurchase(session.accessToken, purchase.id);
      setPurchase(updated);
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
    // resposta se perdeu, o replay devolve a mesma cobrança.
    created.current = false;
    setPurchase(null);
    setError(null);
    // O efeito de criação depende deste contador; sem ele, reabrir o checkout
    // reutilizava o estado "nenhuma cobrança" e não gerava um novo Pix.
    setAttempt((current) => current + 1);
  };

  const retryNewCharge = async () => {
    await SecureStore.deleteItemAsync(pendingPurchaseKey(packCode));
    await SecureStore.deleteItemAsync(pendingPurchaseIdempotencyKey(packCode));
    created.current = false;
    setPurchase(null);
    setError(null);
    setAttempt((current) => current + 1);
  };

  const acceptTerms = async () => {
    if (!session || !terms || acceptingTerms) {
      return;
    }
    setAcceptingTerms(true);
    try {
      await api.legal.acceptTerms(session.accessToken, terms.id, 'credit_purchase');
      setTermsAccepted(true);
    } catch {
      setError('Não foi possível registrar o aceite dos Termos. Tente novamente.');
    } finally {
      setAcceptingTerms(false);
    }
  };

  if (!emailReady || !termsReady || creating) {
    return (
      <Page title="Checkout">
        <LoadingState label="Abrindo cobrança Pix." variant="cards" />
      </Page>
    );
  }

  if (!email) {
    return (
      <Page title="Checkout">
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

  if (error === TICKET_PURCHASE_DISABLED_TEXT) {
    return <PurchaseDisabledState />;
  }

  if (terms && !termsAccepted && !purchase) {
    return (
      <Page title="Termos da compra">
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
        <Check checked={termsAccepted} onChange={setTermsAccepted}>
          Li e aceito a versão vigente dos Termos de uso para comprar ingressos.
        </Check>
        <Btn tone="primary" onPress={acceptTerms} disabled={termsAccepted || acceptingTerms}>
          {acceptingTerms ? 'Registrando aceite…' : 'Aceitar e abrir Pix'}
        </Btn>
        <Btn tone="ghost" go="wallet">
          Voltar
        </Btn>
      </Page>
    );
  }

  if (!purchase) {
    return (
      <Page title="Checkout">
        <StateScreen
          icon="wifi-off"
          title="Cobrança indisponível"
          text={error ?? 'Não foi possível abrir o Pix agora. Tente novamente.'}
          actions={
            <>
              <Btn tone="primary" onPress={retryCreate}>
                Tentar novamente
              </Btn>
              <Btn tone="ghost" go="wallet">
                Voltar aos ingressos
              </Btn>
            </>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Checkout">
      <Card>
        <Row between>
          <Txt variant="h3">{avulso ? 'Avulso' : 'Pacote pequeno'}</Txt>
          <Badge>{purchase.tickets} ingressos</Badge>
        </Row>
        <Row between style={{ marginTop: 10 }}>
          <Txt variant="tiny">Total</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {cents(purchase.payment?.amount_cents ?? purchase.amount_cents)}
          </Txt>
        </Row>
      </Card>
      <PaymentPix
        payment={purchase.payment}
        purchaseStatus={purchase.status}
        amountCents={purchase.payment?.amount_cents ?? purchase.amount_cents}
        onRefresh={refresh}
        refreshing={refreshing}
      />
      {state === 'paid' ? (
        <>
          <Notice tone="green" icon="check">
            Pagamento confirmado. Os ingressos já estão no seu saldo.
          </Notice>
          <Btn tone="primary" go="wallet">
            Voltar aos ingressos
          </Btn>
        </>
      ) : state === 'expired' || state === 'failed' ? (
        <>
          <Notice tone="orange" icon="alert">
            {state === 'expired'
              ? 'O Pix expirou. Nenhum valor foi cobrado; gere uma nova cobrança.'
              : 'O pagamento não foi concluído. Nenhum ingresso foi creditado.'}
          </Notice>
          <Btn tone="primary" onPress={retryNewCharge}>
            Gerar novo Pix
          </Btn>
        </>
      ) : (
        <Notice tone="blue" icon="wallet">
          Seus ingressos entram no saldo após o pagamento. A tela atualiza automaticamente.
        </Notice>
      )}
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
        text={`Você precisa de ${needed} ingressos e tem ${availableLabel}. A compra de ingressos está desativada nesta versão do JOGA.`}
        actions={
          <Btn tone="primary" back>
            Voltar
          </Btn>
        }
      />
    </Page>
  );
}

function Pass() {
  const { palette } = useTheme();
  const nav = useNav();
  const { passPlans, loadPass } = useApp();
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
        <Badge tone="lime">TEMPORADA + INGRESSOS</Badge>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 30, marginTop: 10, marginBottom: 4 }}
        >
          Jogue o trimestre{'\n'}inteiro.
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          Cobrança única por trimestre. A franquia cai mês a mês, sem adiantar.
        </Txt>
      </Card>
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
                {plan.tickets_per_month} ingressos por mês · cobrança trimestral
              </Text>
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
          text="Os planos do passe aparecem aqui quando estiverem à venda."
        />
      ) : null}
      <Notice tone="blue" icon="info">
        A franquia é mensal e não acumula. Crédito comprado separadamente não expira.
      </Notice>
      <TextBtn go="pass-past-due" muted>
        Meu passe está em atraso
      </TextBtn>
    </Page>
  );
}

function CheckoutPass() {
  const nav = useNav();
  const { session, passPlans, loadPass, email, emailReady } = useApp();
  const code = typeof nav.params.planCode === 'string' ? nav.params.planCode : '';
  const plan = passPlans.find((item) => item.code === code) ?? null;
  const planCode = plan?.code ?? code;
  const [subscription, setSubscription] = useState<PassSubscription | null>(null);
  const [creating, setCreating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const created = useRef(false);

  useEffect(() => {
    if (created.current || !session || !plan || !emailReady || !email) {
      return;
    }
    created.current = true;
    setCreating(true);
    const idempotencyKey = pendingPassIdempotencyKey(planCode);
    (async () => {
      try {
        // Mesma chave + mesmo plano = replay; nunca abre duas cobranças.
        let requestKey = await SecureStore.getItemAsync(idempotencyKey);
        if (!requestKey) {
          requestKey = newIdempotencyKey();
          await SecureStore.setItemAsync(idempotencyKey, requestKey);
        }
        const created = await api.passes.subscribe(session.accessToken, planCode, requestKey);
        await SecureStore.setItemAsync(pendingPassKey(planCode), created.id);
        setSubscription(created);
      } catch (cause) {
        if (cause instanceof ApiError && cause.code === 'payer_email_required') {
          created.current = false;
          nav.replace('payment-email');
          return;
        }
        if (cause instanceof ApiError && cause.code === 'idempotency_conflict') {
          await SecureStore.deleteItemAsync(idempotencyKey);
          setError(
            'A assinatura anterior tinha outro plano. Tente novamente para gerar um novo Pix.',
          );
        } else if (cause instanceof ApiError && cause.code === 'ticket_purchase_disabled') {
          setError(TICKET_PURCHASE_DISABLED_TEXT);
        } else {
          setError('Não foi possível abrir a cobrança Pix do passe.');
        }
      } finally {
        setCreating(false);
      }
    })();
  }, [attempt, email, emailReady, nav, plan, planCode, session]);

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
      void SecureStore.deleteItemAsync(pendingPassKey(planCode));
      void SecureStore.deleteItemAsync(pendingPassIdempotencyKey(planCode));
    }
  }, [loadPass, planCode, state]);

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
    created.current = false;
    setSubscription(null);
    setError(null);
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
    setAttempt((current) => current + 1);
  };

  if (error === TICKET_PURCHASE_DISABLED_TEXT) {
    return <PurchaseDisabledState />;
  }

  if (!emailReady || creating) {
    return (
      <Page title="Checkout do passe">
        <LoadingState label="Abrindo cobrança Pix do passe." variant="cards" />
      </Page>
    );
  }

  if (!email) {
    return (
      <Page title="Checkout do passe">
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
      <Page title="Checkout do passe">
        <EmptyState
          title="Plano indisponível"
          text="Os planos do passe aparecem aqui quando estiverem à venda."
          actions={
            <Btn tone="primary" go="pass">
              Ver planos
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!subscription) {
    return (
      <Page title="Checkout do passe">
        <StateScreen
          icon="wifi-off"
          title="Cobrança indisponível"
          text={error ?? 'Não foi possível abrir o Pix do passe agora. Tente novamente.'}
          actions={
            <>
              <Btn tone="primary" onPress={retryCreate}>
                Tentar novamente
              </Btn>
              <Btn tone="ghost" go="pass">
                Voltar ao passe
              </Btn>
            </>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Checkout do passe">
      <Card>
        <Row between>
          <Txt variant="h3">{plan.label}</Txt>
          <Badge tone="blue">{plan.tickets_per_month}/mês</Badge>
        </Row>
        <Row between style={{ marginTop: 10 }}>
          <Txt variant="tiny">Trimestre</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {cents(subscription.payment?.amount_cents ?? plan.quarter_cents)}
          </Txt>
        </Row>
        <Txt variant="tiny">
          3 meses · {plan.tickets_per_month * 3} ingressos no total, entregues mês a mês
        </Txt>
      </Card>
      <PaymentPix
        payment={subscription.payment}
        purchaseStatus={subscription.status}
        amountCents={subscription.payment?.amount_cents ?? plan.quarter_cents}
        onRefresh={refresh}
        refreshing={refreshing}
      />
      {state === 'paid' ? (
        <>
          <Notice tone="green" icon="check">
            Pagamento confirmado. O passe será ativado e a primeira franquia será entregue no
            próximo ciclo.
          </Notice>
          <Btn tone="primary" go="pass-manage">
            Ver meu passe
          </Btn>
        </>
      ) : state === 'expired' || state === 'failed' ? (
        <>
          <Notice tone="orange" icon="alert">
            O Pix do passe expirou ou não foi concluído. Nenhuma cobrança foi ativada.
          </Notice>
          <Btn tone="primary" onPress={retryNewCharge}>
            Gerar novo Pix
          </Btn>
        </>
      ) : (
        <Notice tone="blue" icon="lock">
          A franquia é entregue mês a mês. O cancelamento vale para o próximo ciclo. A tela atualiza
          automaticamente.
        </Notice>
      )}
    </Page>
  );
}

function PassManage() {
  const { pass, wallet } = useApp();
  if (!pass) {
    return (
      <Page title="Meu passe">
        <EmptyState
          title="Nenhum passe ativo"
          text="Assine o passe para receber a franquia mensal de ingressos."
          actions={
            <Btn tone="primary" go="pass">
              Ver planos
            </Btn>
          }
        />
      </Page>
    );
  }
  const period = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}`;
  const currentLots = (wallet?.lots ?? []).filter(
    (lot) => lot.source === 'pass' && lot.period === period,
  );
  const remaining = currentLots.reduce((sum, lot) => sum + lot.remaining, 0);
  const original = currentLots.reduce((sum, lot) => sum + lot.original_amount, 0);
  const used = Math.max(0, original - remaining);
  const delivered = pass.deliveries.reduce((sum, item) => sum + item.tickets, 0);
  return (
    <Page title="Meu passe">
      <Card tone="ink">
        <Row between>
          <Badge tone={pass.status === 'active' ? 'lime' : 'orange'}>
            {pass.status.toUpperCase()}
          </Badge>
          <Badge>{pass.plan_code.toUpperCase()}</Badge>
        </Row>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 28, marginTop: 10, marginBottom: 4 }}
        >
          {pass.tickets_per_month} ingressos{'\n'}por mês
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          {pass.starts_at ? `Início ${dateOnly(pass.starts_at)}` : 'Início a confirmar'}
          {pass.ends_at ? ` · fim ${dateOnly(pass.ends_at)}` : ''}
        </Txt>
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Franquia de {period}</Txt>
          <Badge tone="blue">{remaining} disponíveis</Badge>
        </Row>
        <Kv label="Franquia do mês" value={String(pass.tickets_per_month)} />
        <Kv label="Usados no mês" value={wallet ? String(used) : 'indisponível'} />
        <Kv label="Disponíveis" value={wallet ? `${remaining} · não acumula` : 'indisponível'} />
        <Kv
          label="Próxima entrega"
          value={pass.next_delivery_at ? dateOnly(pass.next_delivery_at) : 'a confirmar'}
        />
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Franquias entregues</Txt>
          <Badge tone="green">{delivered}</Badge>
        </Row>
        {pass.deliveries.length ? (
          pass.deliveries.map((item) => (
            <Kv
              key={item.month_index}
              label={`Mês ${item.month_index}`}
              value={`${item.tickets} ingressos · ${dateOnly(item.delivered_at)}`}
            />
          ))
        ) : (
          <Txt variant="tiny" style={{ marginTop: 6 }}>
            Nenhuma franquia entregue ainda.
          </Txt>
        )}
      </Card>
      <Notice tone="blue" icon="info">
        A franquia mensal não acumula e não vira crédito. Ingressos comprados separadamente não
        expiram.
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
    <Page title="Passe">
      <StateScreen
        icon="alert"
        title="Passe em atraso"
        text="Quando a cobrança do ciclo não é confirmada, a franquia do mês não é entregue. Fale com o suporte para regularizar; itens de passe podem ser revogados."
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
        <Kv label="Status do passe" value={pass?.status.toUpperCase() ?? 'SEM PASSE'} />
        <Kv
          label="Próxima entrega"
          value={pass?.next_delivery_at ? dateOnly(pass.next_delivery_at) : 'a confirmar'}
        />
        <Kv label="Franquia do mês" value={pass ? `${pass.tickets_per_month} ingressos` : '—'} />
      </Card>
      <Notice tone="orange" icon="info">
        A franquia mensal não acumula. O que não for usado no mês não vira crédito para o mês
        seguinte.
      </Notice>
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
  { id: 'store', tab: 'perfil', render: () => <Store /> },
  { id: 'checkout-package', tab: 'perfil', render: () => <CheckoutPackage /> },
  { id: 'payment-email', tab: 'perfil', render: () => <PaymentEmail /> },
  { id: 'insufficient-tickets', tab: 'jogar', render: () => <InsufficientTickets /> },
  { id: 'buy-3', tab: 'jogar', hidden: true, render: () => <CheckoutPackage avulso /> },
  { id: 'pass', tab: 'perfil', render: () => <Pass /> },
  { id: 'checkout-pass', tab: 'perfil', render: () => <CheckoutPass /> },
  { id: 'pass-manage', tab: 'perfil', render: () => <PassManage /> },
  { id: 'pass-past-due', tab: 'perfil', render: () => <PassPastDue /> },
  { id: 'refund-tickets', tab: 'perfil', render: () => <RefundTickets /> },
];
