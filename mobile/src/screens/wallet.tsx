import { useEffect, useRef, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import { View } from 'react-native';

import { api, ApiError } from '../api/client';
import type { PassSubscription, Purchase, TicketLot } from '../api/types';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import { PaymentPix, paymentState } from '../ui/PaymentPix';
import { Text } from '../ui/text';
import {
  Badge,
  Btn,
  BtnRow,
  Card,
  CardList,
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
import type { ScreenDef } from './types';

function SourceBadge({ source }: { source: string }) {
  if (source === 'consumption' || source === 'match') return null;
  if (source === 'purchase') return <Badge>COMPRA</Badge>;
  if (source === 'refund') return <Badge tone="blue">DEVOLUÇÃO</Badge>;
  if (source === 'free') return <Badge tone="lime">GRÁTIS</Badge>;
  if (source === 'pass') return <Badge tone="blue">PASSE</Badge>;
  return <Badge>{source.toUpperCase()}</Badge>;
}

function lotSourceLabel(source: string): string {
  if (source === 'pass') return 'Passe';
  if (source === 'free') return 'Temporada';
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
              {lot.expires_at ? `Expira em ${dateOnly(lot.expires_at)}` : 'Não expira'}
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
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    loadWallet()
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
  }, [loadWallet]);
  const retry = () => {
    setLoading(true);
    setFailed(false);
    loadWallet()
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };
  const entries =
    wallet?.entries.map((entry) => ({
      amount: entry.amount,
      label:
        entry.source === 'purchase'
          ? 'Compra de pacote'
          : entry.source === 'refund'
            ? 'Devolução · reserva expirada'
            : entry.source === 'pass'
              ? 'Franquia do passe · novembro'
              : entry.source === 'free'
                ? 'Ingressos grátis · nível 20'
                : 'Partida · Arena Sul',
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
  if (failed) {
    return (
      <Page title="Carteira">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar sua carteira"
          text="Verifique a conexão e tente novamente. Seu saldo não foi alterado."
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
      <Page title="Carteira">
        <LoadingState label="Buscando seu saldo." variant="wallet" />
      </Page>
    );
  }
  return (
    <Page title="Carteira">
      <Card tone="ink">
        <Row between>
          <Badge tone="lime">SALDO</Badge>
          <Badge>NÃO TRANSFERÍVEL</Badge>
        </Row>
        <Txt variant="display" color="onInk" style={{ fontSize: 54, marginTop: 12 }}>
          {wallet?.balance ?? 0}
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
      <BtnRow>
        <Btn tone="primary" go="store">
          Comprar ingressos
        </Btn>
        <Btn tone="ghost" go="wallet-breakdown">
          Ver detalhes
        </Btn>
      </BtnRow>
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
  const { wallet } = useApp();
  const lots = [...(wallet?.lots ?? [])].filter((lot) => lot.remaining > 0);
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
    <Page title="Seu saldo">
      <Card tone="lime">
        <Row between>
          <Txt variant="h3">Franquia do passe</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {sums.pass}
          </Txt>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          {sums.pass > 0 ? 'Sujeita ao ciclo do passe' : 'Sem franquia ativa'}
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
          Nunca expiram · reserva permanente
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
      <Btn tone="primary" go="store">
        Comprar mais ingressos
      </Btn>
    </Page>
  );
}

function MatchCost() {
  const { palette } = useTheme();
  const { wallet } = useApp();
  const balance = wallet?.balance ?? 0;
  const enough = balance >= 7;
  return (
    <Page title="Custo da partida">
      <Card>
        <Kv label="Formato" value="Futebol 5x5 · 10 jogadores" />
        <Kv label="Faixa" value="Padrão noite" />
        <Kv label="Atributo visível" value="Coberta · dia/noite" />
        <Kv label="Custo por jogador" value="7 ingressos" />
      </Card>
      <Card>
        <Txt variant="h3">Tabela 5x5</Txt>
        <View style={{ marginTop: 6 }}>
          {[
            ['Econômica dia', '5'],
            ['Econômica noite', '6'],
            ['Padrão dia', '7'],
            ['Padrão noite', '7'],
            ['Coberta', '10'],
            ['Premium', '12'],
          ].map(([label, value], index) => (
            <Row
              key={label}
              between
              style={{
                paddingVertical: 11,
                borderBottomWidth: index === 5 ? 0 : 1,
                borderBottomColor: palette.line,
              }}
            >
              <Text style={{ fontSize: 14, color: palette.ink }}>{label}</Text>
              <Txt variant="num" style={{ fontSize: 16 }}>
                {value}
              </Txt>
            </Row>
          ))}
        </View>
      </Card>
      <Card tone="flat">
        <Row between>
          <View>
            <Txt variant="label">Seu saldo</Txt>
            <Txt variant="num" style={{ fontSize: 30 }}>
              {balance}
            </Txt>
          </View>
          <Badge tone={enough ? 'lime' : 'orange'}>
            {enough ? 'suficiente' : `faltam ${Math.max(0, 7 - balance)}`}
          </Badge>
        </Row>
      </Card>
      {enough ? (
        <Btn tone="primary" go="queue-casual">
          Entrar na fila
        </Btn>
      ) : (
        <Btn tone="primary" go="insufficient-tickets">
          Comprar ingressos
        </Btn>
      )}
      <TextBtn go={enough ? 'store' : 'insufficient-tickets'} muted>
        {enough ? 'Comprar mais ingressos' : 'Entenda como completar o saldo'}
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
  const { session, loadWallet, email, emailReady } = useApp();
  const packCode =
    typeof nav.params.packCode === 'string' ? nav.params.packCode : avulso ? 'avulso' : 'pequeno';
  const [purchase, setPurchase] = useState<Purchase | null>(null);
  const [creating, setCreating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const created = useRef(false);

  useEffect(() => {
    if (created.current || !session || !emailReady || !email) {
      return;
    }
    created.current = true;
    setCreating(true);
    const key = pendingPurchaseKey(packCode);
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
        }
        const createdPurchase = await api.tickets.createPurchase(session.accessToken, packCode);
        await SecureStore.setItemAsync(key, createdPurchase.id);
        setPurchase(createdPurchase);
      } catch (cause) {
        if (cause instanceof ApiError && cause.code === 'payer_email_required') {
          created.current = false;
          nav.replace('payment-email');
          return;
        }
        setError('Não foi possível abrir a cobrança Pix.');
      } finally {
        setCreating(false);
      }
    })();
  }, [attempt, email, emailReady, nav, packCode, session]);

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

  const retry = () => {
    void SecureStore.deleteItemAsync(pendingPurchaseKey(packCode));
    created.current = false;
    setPurchase(null);
    setError(null);
    // O efeito de criação depende deste contador; sem ele, reabrir o checkout
    // reutilizava o estado "nenhuma cobrança" e não gerava um novo Pix.
    setAttempt((current) => current + 1);
  };

  if (!emailReady || creating) {
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

  if (!purchase) {
    return (
      <Page title="Checkout">
        <StateScreen
          icon="wifi-off"
          title="Cobrança indisponível"
          text={error ?? 'Não foi possível abrir o Pix agora. Tente novamente.'}
          actions={
            <>
              <Btn tone="primary" onPress={retry}>
                Tentar novamente
              </Btn>
              <Btn tone="ghost" go="wallet">
                Voltar à carteira
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
            Voltar à carteira
          </Btn>
        </>
      ) : state === 'expired' || state === 'failed' ? (
        <>
          <Notice tone="orange" icon="alert">
            {state === 'expired'
              ? 'O Pix expirou. Nenhum valor foi cobrado; gere uma nova cobrança.'
              : 'O pagamento não foi concluído. Nenhum ingresso foi creditado.'}
          </Notice>
          <Btn tone="primary" onPress={retry}>
            Gerar novo Pix
          </Btn>
        </>
      ) : (
        <Notice tone="blue" icon="wallet">
          Seus ingressos entram no saldo após o pagamento. Esta tela atualiza sozinha a cada 7
          segundos.
        </Notice>
      )}
    </Page>
  );
}

function InsufficientTickets() {
  const { wallet } = useApp();
  const balance = wallet?.balance ?? 0;
  const missing = Math.max(0, 7 - balance);
  const smallPack = missing <= 3;
  return (
    <Page title="Saldo insuficiente">
      <StateScreen
        icon="wallet"
        title={`Faltam ${missing} ingressos`}
        text={`A vaga custa 7 ingressos e você tem ${balance}. O menor pacote que resolve é o de ${smallPack ? 3 : 10} ingressos. Nada foi cobrado.`}
        actions={
          <>
            <Btn tone="primary" go={smallPack ? 'buy-3' : 'store'}>
              {smallPack ? 'Comprar 3 ingressos' : 'Ver pacotes'}
            </Btn>
            <Btn tone="ghost" back>
              Voltar
            </Btn>
          </>
        }
      />
      <Card tone="flat">
        <Row between>
          <Txt variant="tiny">Saldo atual</Txt>
          <Text style={{ fontWeight: '900' }}>{balance}</Text>
        </Row>
        <Row between style={{ marginTop: 6 }}>
          <Txt variant="tiny">Custo da vaga</Txt>
          <Text style={{ fontWeight: '900' }}>7</Text>
        </Row>
        <Row between style={{ marginTop: 6 }}>
          <Txt variant="tiny">Depois da compra</Txt>
          <Text style={{ fontWeight: '900' }}>{balance + (smallPack ? 3 : 10)}</Text>
        </Row>
      </Card>
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
            {index === 1 ? <Badge tone="lime">ESCOLHIDO</Badge> : null}
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
      {plans.length ? (
        <Btn
          tone="primary"
          onPress={() => {
            const chosen = plans[1] ?? plans[0];
            nav.go('checkout-pass', { planCode: chosen.code });
          }}
        >
          {`Assinar ${(plans[1] ?? plans[0]).label}`}
        </Btn>
      ) : (
        <EmptyState
          title="Nenhum plano disponível"
          text="Os planos do passe aparecem aqui quando estiverem à venda."
        />
      )}
      <TextBtn go="pass-past-due" muted>
        Meu passe está em atraso
      </TextBtn>
    </Page>
  );
}

function CheckoutPass() {
  const nav = useNav();
  const { session, passPlans, loadPass, email, emailReady } = useApp();
  const code = typeof nav.params.planCode === 'string' ? nav.params.planCode : 'craque';
  const plan = passPlans.find((item) => item.code === code) ?? {
    code: 'craque',
    label: 'Craque',
    tickets_per_month: 20,
    unit_price_cents: 325,
    price_per_month_cents: 6500,
    quarter_cents: 19500,
  };
  const [subscription, setSubscription] = useState<PassSubscription | null>(null);
  const [creating, setCreating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const created = useRef(false);

  useEffect(() => {
    if (created.current || !session || !emailReady || !email) {
      return;
    }
    created.current = true;
    setCreating(true);
    api.passes
      .subscribe(session.accessToken, plan.code)
      .then(setSubscription)
      .catch((cause) => {
        if (cause instanceof ApiError && cause.code === 'payer_email_required') {
          created.current = false;
          nav.replace('payment-email');
          return;
        }
        setError('Não foi possível abrir a cobrança Pix do passe.');
      })
      .finally(() => setCreating(false));
  }, [attempt, email, emailReady, nav, plan.code, session]);

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
    }
  }, [loadPass, state]);

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

  const retry = async () => {
    if (subscription && session && subscription.status === 'pending') {
      await api.passes.cancel(session.accessToken, subscription.id).catch(() => undefined);
    }
    created.current = false;
    setSubscription(null);
    setError(null);
    setAttempt((current) => current + 1);
  };

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

  if (!subscription) {
    return (
      <Page title="Checkout do passe">
        <StateScreen
          icon="wifi-off"
          title="Cobrança indisponível"
          text={error ?? 'Não foi possível abrir o Pix do passe agora. Tente novamente.'}
          actions={
            <>
              <Btn tone="primary" onPress={retry}>
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
          <Btn tone="primary" onPress={retry}>
            Gerar novo Pix
          </Btn>
        </>
      ) : (
        <Notice tone="blue" icon="lock">
          A franquia é entregue mês a mês. O cancelamento vale para o próximo ciclo. Esta tela
          atualiza sozinha a cada 7 segundos.
        </Notice>
      )}
    </Page>
  );
}

function PassManage() {
  const { pass } = useApp();
  return (
    <Page title="Meu passe">
      <Card tone="ink">
        <Row between>
          <Badge tone="lime">ATIVO</Badge>
          <Badge>{(pass?.plan_code ?? 'craque').toUpperCase()}</Badge>
        </Row>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 28, marginTop: 10, marginBottom: 4 }}
        >
          {pass?.tickets_per_month ?? 20} ingressos{'\n'}por mês
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          Ciclo 2026-Q4 · renova em 01 mar
        </Txt>
      </Card>
      <Card>
        <Kv label="Franquia de novembro" value={String(pass?.tickets_per_month ?? 20)} />
        <Kv label="Usados no mês" value="12" />
        <Kv label="Disponíveis" value="8 · expiram em 30 nov" />
        <Kv label="Próxima entrega" value="01 dez · 20 ingressos" />
      </Card>
      <Card>
        <Row between>
          <Txt variant="h3">Benefícios ativos</Txt>
          <Badge tone="green">4</Badge>
        </Row>
        <View style={{ flexDirection: 'row', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
          <Badge>TRILHA</Badge>
          <Badge>CEP</Badge>
          <Badge>LOBBY PRIVADO</Badge>
          <Badge>ESTATÍSTICAS</Badge>
        </View>
      </Card>
      <BtnRow>
        <Btn tone="ghost" toast="Histórico aberto no protótipo">
          Histórico de ciclos
        </Btn>
        <Btn tone="ghost" modal="confirm">
          Cancelar renovação
        </Btn>
      </BtnRow>
      <Notice tone="orange" icon="info">
        Cancelar não interrompe o ciclo pago; a franquia continua sendo entregue até o fim.
      </Notice>
    </Page>
  );
}

function PassPastDue() {
  return (
    <Page title="Passe">
      <StateScreen
        icon="alert"
        title="Passe em atraso"
        text="A franquia do mês não foi entregue. Você tem 15 dias para regularizar antes do cancelamento. Itens emprestados podem ser revogados."
        actions={
          <>
            <Btn tone="primary" go="checkout-pass">
              Regularizar agora
            </Btn>
            <Btn tone="ghost" go="pass">
              Entender o passe
            </Btn>
          </>
        }
      />
      <Card>
        <Kv label="Status" value="PAST_DUE" />
        <Kv label="Dias restantes" value="12" />
        <Kv label="Franquia do mês" value="suspensa" />
        <Kv label="Itens de passe" value="revogáveis" />
      </Card>
    </Page>
  );
}

function RefundTickets() {
  return (
    <Page title="Reembolso">
      <StateScreen
        icon="check"
        title="+7 ingressos devolvidos"
        text="A reserva expirou antes da confirmação. O valor voltou para o saldo em ingressos, não em dinheiro."
        actions={
          <>
            <Btn tone="primary" go="wallet">
              Ver carteira
            </Btn>
            <Btn tone="ghost" go="booking-history">
              Ver reserva
            </Btn>
          </>
        }
      />
      <Card>
        <Kv label="Motivo" value="Hold expirado" />
        <Kv label="Status" value="REFUNDED" />
        <Kv label="Destino" value="Saldo de ingressos" />
        <Kv label="Prazo" value="Imediato no protótipo" />
      </Card>
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
  { id: 'buy-3', tab: 'jogar', render: () => <CheckoutPackage avulso /> },
  { id: 'pass', tab: 'perfil', render: () => <Pass /> },
  { id: 'checkout-pass', tab: 'perfil', render: () => <CheckoutPass /> },
  { id: 'pass-manage', tab: 'perfil', render: () => <PassManage /> },
  { id: 'pass-past-due', tab: 'perfil', render: () => <PassPastDue /> },
  { id: 'refund-tickets', tab: 'perfil', render: () => <RefundTickets /> },
];
