import { useEffect, useState } from 'react';
import { Image, Text, View } from 'react-native';

import { api, ApiError } from '../api/client';
import type { Purchase, TicketLot } from '../api/types';
import { useApp } from '../state/app';
import { useNav, useTheme } from '../state/context';
import {
  Badge,
  Btn,
  BtnRow,
  Card,
  CardList,
  EmptyState,
  Kv,
  ListRow,
  LoadingState,
  Notice,
  Page,
  QrSvg,
  Row,
  StateScreen,
  TextBtn,
  TimerCard,
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

function CheckoutPackage({ avulso }: { avulso?: boolean }) {
  const nav = useNav();
  const { session, loadWallet } = useApp();
  const packCode =
    typeof nav.params.packCode === 'string' ? nav.params.packCode : avulso ? 'avulso' : 'pequeno';
  const tickets = typeof nav.params.tickets === 'number' ? nav.params.tickets : avulso ? 3 : 10;
  const amount = typeof nav.params.amount === 'number' ? nav.params.amount : avulso ? 1110 : 3400;
  const [purchase, setPurchase] = useState<Purchase | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (session) {
      api.tickets
        .createPurchase(session.accessToken, packCode)
        .then(setPurchase)
        .catch(() => undefined);
    }
  }, [session, packCode]);
  const confirm = async () => {
    setBusy(true);
    try {
      if (purchase && session) {
        try {
          await api.tickets.syncPurchase(session.accessToken, purchase.id);
        } catch {
          // O sync pode não estar disponível em ambiente local; a confirmação abaixo cobre.
        }
        const updated = await api.tickets.confirmPurchase(session.accessToken, purchase.id);
        if (updated.status.toLowerCase() === 'paid') {
          await loadWallet();
          nav.replace(avulso ? 'checkout-3-confirmed' : 'checkout-package-confirmed');
          return;
        }
      }
      nav.replace(avulso ? 'checkout-3-confirmed' : 'checkout-package-pending');
    } catch (error) {
      if (error instanceof ApiError) {
        nav.replace('checkout-package-failed');
      } else {
        nav.replace('checkout-package-pending');
      }
    } finally {
      setBusy(false);
    }
  };
  const payment = purchase?.payment;
  return (
    <Page title="Checkout">
      <Card>
        <Row between>
          <Txt variant="h3">{avulso ? 'Avulso' : 'Pacote pequeno'}</Txt>
          <Badge>{tickets} ingressos</Badge>
        </Row>
        <Row between style={{ marginTop: 10 }}>
          <Txt variant="tiny">Total</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {cents(amount)}
          </Txt>
        </Row>
      </Card>
      <Card style={{ alignItems: 'center' }}>
        {payment?.qr_code_base64 && payment.qr_code_base64.length > 100 ? (
          <Image
            source={{ uri: `data:image/png;base64,${payment.qr_code_base64}` }}
            style={{ width: 168, height: 168 }}
            resizeMode="contain"
          />
        ) : (
          <View
            style={{
              width: 168,
              height: 168,
              borderWidth: 1.5,
              borderColor: '#D5D9D6',
              borderRadius: 8,
              padding: 8,
              backgroundColor: '#F1F3F0',
            }}
          >
            <QrSvg seed={avulso ? 5 : 11} size={152} />
          </View>
        )}
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          Escaneie o QR ou copie o código Pix
        </Txt>
        <View style={{ width: '100%', marginTop: 10 }}>
          <Btn
            tone="ghost"
            icon="copy"
            onPress={() => nav.toast('Código Pix copiado no protótipo')}
          >
            Copiar código Pix
          </Btn>
        </View>
      </Card>
      <TimerCard label="Expiração do Pix" value="09:42" note="pagamento pendente" tone="on" />
      <Notice tone="blue" icon="wallet">
        Seus ingressos entram no saldo após o pagamento.
      </Notice>
      <Btn tone="primary" onPress={confirm} disabled={busy}>
        {busy ? 'Verificando…' : 'Já paguei'}
      </Btn>
    </Page>
  );
}

function CheckoutPending() {
  return (
    <Page title="Aguardando pagamento">
      <StateScreen
        icon="clock"
        title="Pagamento pendente"
        text="Assim que o pagamento for confirmado, os 10 ingressos entram no seu saldo. Você não precisa pagar de novo."
        actions={
          <>
            <Btn tone="primary" toast="Verificação simulada no protótipo">
              Verificar novamente
            </Btn>
            <Btn tone="ghost" go="wallet">
              Voltar à carteira
            </Btn>
          </>
        }
      />
      <Card>
        <Kv label="Pacote" value="10 ingressos" />
        <Kv label="Valor" value="R$ 34,00" />
        <Kv label="Status" value="PENDENTE" />
        <Kv label="Pedido" value="#PIX-8841" />
      </Card>
    </Page>
  );
}

function CheckoutConfirmed({ avulso }: { avulso?: boolean }) {
  return (
    <Page title="Pagamento confirmado">
      <StateScreen
        icon="check"
        title={avulso ? '+3 ingressos' : '+10 ingressos'}
        text="Pagamento confirmado. Os ingressos já estão no seu saldo."
        actions={
          <>
            <Btn tone="primary" go="wallet">
              Voltar à carteira
            </Btn>
            <Btn tone="ghost" toast="Comprovante aberto no protótipo">
              Ver comprovante
            </Btn>
          </>
        }
      />
      <Card>
        <Kv label="Pacote" value={avulso ? '3 ingressos' : '10 ingressos'} />
        <Kv label="Valor" value={avulso ? 'R$ 11,10' : 'R$ 34,00'} />
        <Kv label="Status" value="PAGO" />
        <Kv label="Pedido" value={avulso ? '#PIX-8842' : '#PIX-8841'} />
      </Card>
    </Page>
  );
}

function CheckoutFailed() {
  return (
    <Page title="Pagamento">
      <StateScreen
        icon="alert"
        title="Pagamento não concluído"
        text="O Pix expirou ou foi recusado. Nenhum ingresso foi creditado e nenhuma cobrança duplicada foi aberta."
        actions={
          <>
            <Btn tone="primary" go="checkout-package">
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
  const { session, passPlans, loadPass } = useApp();
  const code = typeof nav.params.planCode === 'string' ? nav.params.planCode : 'craque';
  const plan = passPlans.find((item) => item.code === code) ?? {
    code: 'craque',
    label: 'Craque',
    tickets_per_month: 20,
    unit_price_cents: 325,
    price_per_month_cents: 6500,
    quarter_cents: 19500,
  };
  const [busy, setBusy] = useState(false);
  const pay = async () => {
    if (!session) {
      nav.replace('checkout-pass-confirmed');
      return;
    }
    setBusy(true);
    try {
      const subscription = await api.passes.subscribe(session.accessToken, plan.code);
      await api.passes.confirm(session.accessToken, subscription.id);
      await loadPass();
      nav.replace('checkout-pass-confirmed');
    } catch (error) {
      if (error instanceof ApiError) {
        nav.toast('Não foi possível concluir o pagamento.');
      } else {
        nav.toast('Não foi possível concluir o pagamento.');
      }
    } finally {
      setBusy(false);
    }
  };
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
            {cents(plan.quarter_cents)}
          </Txt>
        </Row>
        <Txt variant="tiny">
          3 meses · {plan.tickets_per_month * 3} ingressos no total, entregues mês a mês
        </Txt>
      </Card>
      <Card>
        <Kv label="Primeira entrega" value={`01 dez · ${plan.tickets_per_month} ingressos`} />
        <Kv label="Segunda entrega" value={`01 jan · ${plan.tickets_per_month} ingressos`} />
        <Kv label="Terceira entrega" value={`01 fev · ${plan.tickets_per_month} ingressos`} />
        <Kv label="Renovação" value="Pix a cada trimestre" />
      </Card>
      <Card style={{ alignItems: 'center' }}>
        <View
          style={{
            width: 168,
            height: 168,
            borderWidth: 1.5,
            borderColor: '#D5D9D6',
            borderRadius: 8,
            padding: 8,
            backgroundColor: '#F1F3F0',
          }}
        >
          <QrSvg seed={17} size={152} />
        </View>
        <Txt variant="tiny" style={{ marginTop: 8 }}>
          Pix
        </Txt>
      </Card>
      <Notice tone="blue" icon="lock">
        A franquia é entregue mês a mês. Cancelamento vale para o próximo ciclo.
      </Notice>
      <Btn tone="primary" onPress={pay} disabled={busy}>
        {busy ? 'Processando…' : `Pagar ${cents(plan.quarter_cents)}`}
      </Btn>
    </Page>
  );
}

function CheckoutPassConfirmed() {
  const { pass, passPlans } = useApp();
  const plan = passPlans.find((item) => item.code === pass?.plan_code) ?? passPlans[0];
  const label = plan?.label ?? 'Passe';
  const tickets = plan?.tickets_per_month ?? pass?.tickets_per_month ?? 0;
  const amount = plan?.quarter_cents ?? pass?.amount_cents ?? 0;
  return (
    <Page title="Passe ativo">
      <StateScreen
        icon="check"
        title={`Passe ${label} ativo`}
        text={`Pagamento confirmado. A primeira franquia de ${tickets} ingressos será entregue no próximo ciclo.`}
        actions={
          <>
            <Btn tone="primary" go="pass-manage">
              Ver meu passe
            </Btn>
            <Btn tone="ghost" back>
              Voltar
            </Btn>
          </>
        }
      />
      <Card>
        <Kv label="Plano" value={`${label} · ${tickets}/mês`} />
        <Kv label="Trimestre" value={cents(amount)} />
        <Kv label="Status" value="PAGO" />
        <Kv label="Próxima entrega" value="01 dez" />
      </Card>
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
  { id: 'checkout-package-pending', tab: 'perfil', render: () => <CheckoutPending /> },
  { id: 'checkout-package-confirmed', tab: 'perfil', render: () => <CheckoutConfirmed /> },
  { id: 'checkout-package-failed', tab: 'perfil', render: () => <CheckoutFailed /> },
  { id: 'insufficient-tickets', tab: 'jogar', render: () => <InsufficientTickets /> },
  { id: 'buy-3', tab: 'jogar', render: () => <CheckoutPackage avulso /> },
  { id: 'checkout-3-confirmed', tab: 'perfil', render: () => <CheckoutConfirmed avulso /> },
  { id: 'pass', tab: 'perfil', render: () => <Pass /> },
  { id: 'checkout-pass', tab: 'perfil', render: () => <CheckoutPass /> },
  { id: 'checkout-pass-confirmed', tab: 'perfil', render: () => <CheckoutPassConfirmed /> },
  { id: 'pass-manage', tab: 'perfil', render: () => <PassManage /> },
  { id: 'pass-past-due', tab: 'perfil', render: () => <PassPastDue /> },
  { id: 'refund-tickets', tab: 'perfil', render: () => <RefundTickets /> },
];
