import { useEffect, useMemo, useState } from 'react';
import { Image, Linking, View } from 'react-native';
import * as Location from 'expo-location';

import { api, apiAssetUrl, ApiError } from '../api/client';
import type {
  BookableVenue,
  BookableVenueDetail,
  BookableVenueSpace,
  Booking,
  BookingPayment as BookingPaymentData,
  MatchSummary,
  ResultView,
  Substitute,
} from '../api/types';
import { useApp } from '../state/app';
import { useNav, useTheme, type Params } from '../state/context';
import { useActiveInterval } from '../state/useActiveInterval';
import { IdentityBadge } from '../ui/IdentityBadge';
import { identityFromSeed } from '../ui/identity';
import { PaymentPix, paymentState } from '../ui/PaymentPix';
import {
  Badge,
  Btn,
  BtnRow,
  Card,
  CardList,
  Check,
  Chip,
  ChipRow,
  EmptyState,
  Input,
  Kv,
  ListRow,
  LoadingState,
  Notice,
  Page,
  Photo,
  PlayerRow,
  Row,
  Seg,
  SegBtn,
  StateScreen,
  Textarea,
  TextBtn,
  TimerCard,
  Txt,
} from '../ui/kit';
import {
  cents,
  dateOnly,
  divisionLabel,
  shortDateTime,
  timeOnly,
  zonedShortDateTime,
  zonedDateOnly,
  zonedTimeOnly,
} from '../ui/datetime';
import {
  PriceBreakdown,
  TicketConversionTable,
  bookingPrice,
  participantPrice,
} from '../ui/PriceBreakdown';
import { formatFamily, referenceBreakdown, TICKET_REFERENCE_CENTS } from '../ui/tickets';
import { Text } from '../ui/text';
import type { ScreenDef } from './types';

type ToastNav = {
  toast: (message: string) => void;
  go: (id: string, params?: Params) => void;
};

type TicketShortage = { needed?: number | null; available?: number | null };

function toastError(nav: ToastNav, error: unknown, shortage?: TicketShortage) {
  if (error instanceof ApiError) {
    if (error.code === 'insufficient_tickets') {
      nav.go('insufficient-tickets', {
        ...(shortage?.needed != null ? { needed: shortage.needed } : {}),
        ...(shortage?.available != null ? { available: shortage.available } : {}),
      });
      return;
    }
    const map: Record<string, string> = {
      payout_not_ready:
        'A quadra ainda não está habilitada para receber repasse. Escolha outra quadra.',
      space_unavailable: 'Esse horário acabou de ser ocupado. Escolha outro horário.',
      insufficient_lead_time:
        'Não há tempo hábil para confirmar esta reserva. Escolha um horário mais tarde.',
      tickets_not_configured: 'A quadra ainda não configurou ingressos para este formato.',
      band_missing: 'A quadra não definiu a faixa de preço para este horário.',
      booking_not_found: 'Reserva não encontrada.',
      forbidden: 'Você não participa deste lobby.',
      network_unavailable: 'Não foi possível falar com o servidor.',
      request_timeout: 'O servidor demorou para responder. Tente novamente.',
      invalid_transition: 'Esta ação não é válida no estado atual da reserva.',
      cancellation_closed: 'O prazo de cancelamento desta reserva já passou.',
      presence_window_closed: 'O pré-check-in ou a confirmação de presença está fora da janela.',
      presence_closed: 'A presença desta reserva já foi encerrada.',
      too_far: 'Você está longe demais da quadra para confirmar a presença.',
      low_accuracy: 'O GPS do aparelho não tem precisão suficiente. Tente novamente.',
      pre_check_in_required: 'Faça o pré-check-in antes de confirmar a presença.',
    };
    if (map[error.code]) {
      nav.toast(map[error.code]);
      return;
    }
    if (error.status === 0) {
      nav.toast('Não foi possível falar com o servidor. Tente novamente.');
      return;
    }
    nav.toast('Não foi possível concluir a ação.');
  } else {
    nav.toast('Não foi possível concluir a ação.');
  }
}

function venueLocation(venue: BookableVenue): string {
  return [venue.address_line, venue.city, venue.state].filter(Boolean).join(' · ');
}

function PublicVenueBadge() {
  return (
    <View accessible accessibilityLabel="Quadra pública" accessibilityRole="text">
      <Badge tone="blue">Quadra pública</Badge>
    </View>
  );
}

function weekdayLabel(day: number): string {
  return ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'][day - 1] ?? 'Dia';
}

function humanizeBand(code: string): string {
  return code.replaceAll('_', ' ');
}

function Venues() {
  const nav = useNav();
  const { session, profile } = useApp();
  const [venues, setVenues] = useState<BookableVenue[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [query, setQuery] = useState('');
  const [onlyCovered, setOnlyCovered] = useState(false);
  const [maxKm, setMaxKm] = useState<number | null>(10);
  const city = profile?.region?.city ?? null;

  useEffect(() => {
    let active = true;
    api.discovery
      .bookableVenues(session?.accessToken ?? '', { page: 1, pageSize: 20, city })
      .then((result) => {
        if (active) {
          setVenues(result.venues);
          setTotal(result.total);
          setPage(result.page);
        }
      })
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
  }, [session?.accessToken, city]);

  const retry = () => {
    setLoading(true);
    setFailed(false);
    api.discovery
      .bookableVenues(session?.accessToken ?? '', { page: 1, pageSize: 20, city })
      .then((result) => {
        setVenues(result.venues);
        setTotal(result.total);
        setPage(result.page);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };

  const loadMore = async () => {
    if (!session) {
      return;
    }
    setLoadingMore(true);
    try {
      const result = await api.discovery.bookableVenues(session.accessToken, {
        page: page + 1,
        pageSize: 20,
        city,
      });
      setVenues((current) => [...current, ...result.venues]);
      setTotal(result.total);
      setPage(result.page);
    } catch {
      nav.toast('Não foi possível carregar mais quadras.');
    } finally {
      setLoadingMore(false);
    }
  };

  const filtered = venues.filter((venue) => {
    const term = query.trim().toLowerCase();
    if (
      term &&
      ![venue.name, venue.city, venue.address_line ?? ''].some((value) =>
        value.toLowerCase().includes(term),
      )
    ) {
      return false;
    }
    if (onlyCovered && !venue.covered) {
      return false;
    }
    if (maxKm != null && venue.distance_km != null && venue.distance_km > maxKm) {
      return false;
    }
    return true;
  });

  return (
    <Page title="Quadras">
      <Row>
        <Input
          value={query}
          onChangeText={setQuery}
          placeholder="Buscar quadra ou bairro"
          maxLength={60}
          style={{ flex: 1 }}
        />
        <TextBtn modal="filter">Filtrar</TextBtn>
      </Row>
      <ChipRow>
        <Chip on>Futebol 5x5</Chip>
        <Chip on={onlyCovered} onPress={() => setOnlyCovered(!onlyCovered)}>
          Coberta
        </Chip>
        <Chip on={maxKm === 10} onPress={() => setMaxKm(maxKm === 10 ? null : 10)}>
          Até 10 km
        </Chip>
      </ChipRow>
      {loading ? (
        <LoadingState label="Buscando quadras perto de você." variant="venue" />
      ) : failed ? (
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar as quadras"
          text="Verifique a conexão e tente novamente. Sua região continua salva."
          actions={
            <Btn tone="primary" onPress={retry}>
              Tentar novamente
            </Btn>
          }
        />
      ) : filtered.length ? (
        filtered.map((venue) => (
          <Card
            key={venue.id}
            padding={0}
            style={{ overflow: 'hidden' }}
            onPress={() =>
              nav.go('venue-detail', {
                venueId: venue.id,
                venueName: venue.name,
                venueCity: venue.city,
                covered: venue.covered,
              })
            }
          >
            {venue.photo_url && session ? (
              <Image
                source={{
                  uri: apiAssetUrl(venue.photo_url),
                  headers: { Authorization: `Bearer ${session.accessToken}` },
                }}
                style={{ width: '100%', height: 146 }}
                resizeMode="cover"
              />
            ) : (
              <Photo tone={venue.covered ? 'green' : 'orange'} />
            )}
            <View style={{ padding: 14 }}>
              <Row between>
                <View
                  style={{
                    flex: 1,
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: 6,
                    flexWrap: 'wrap',
                  }}
                >
                  <Txt variant="h3" numberOfLines={2} style={{ flexShrink: 1 }}>
                    {venue.name}
                  </Txt>
                  {venue.is_public === true ? <PublicVenueBadge /> : null}
                </View>
                <Badge tone={venue.covered ? 'green' : 'default'}>
                  {venue.covered ? 'COBERTA' : 'ABERTA'}
                </Badge>
              </Row>
              <Txt variant="tiny" numberOfLines={2} style={{ marginTop: 3 }}>
                {venueLocation(venue) || venue.city}
              </Txt>
              <Row between style={{ marginTop: 10 }}>
                <Txt variant="tiny">
                  {venue.spaces_count} {venue.spaces_count === 1 ? 'espaço' : 'espaços'}
                  {venue.distance_km != null ? ` · ${venue.distance_km.toFixed(1)} km` : ''}
                </Txt>
                <View style={{ alignItems: 'flex-end' }}>
                  <Txt variant="num" style={{ fontSize: 18 }}>
                    {cents(venue.min_price_cents)}
                  </Txt>
                  <Txt variant="tiny">a partir</Txt>
                </View>
              </Row>
            </View>
          </Card>
        ))
      ) : venues.length ? (
        <EmptyState
          title="Nenhuma quadra com esses filtros"
          text="Ajuste a busca, a cobertura ou a distância para ver mais quadras."
          actions={
            <Btn
              tone="ghost"
              onPress={() => {
                setQuery('');
                setOnlyCovered(false);
                setMaxKm(null);
              }}
            >
              Limpar filtros
            </Btn>
          }
        />
      ) : (
        <EmptyState
          title={profile?.region ? 'Nenhuma quadra encontrada' : 'Defina sua região'}
          text={
            profile?.region
              ? 'Ainda não há quadras reserváveis nesta região. Tente outra cidade ou volte mais tarde.'
              : 'Defina sua região para descobrir quadras reserváveis perto de você.'
          }
          actions={
            <Btn tone="primary" go="region">
              Definir região
            </Btn>
          }
        />
      )}
      {venues.length < total ? (
        <Btn tone="ghost" onPress={loadMore} disabled={loadingMore}>
          {loadingMore ? 'Carregando…' : 'Carregar mais'}
        </Btn>
      ) : null}
      <Btn tone="ghost" icon="globe" go="stats">
        Ver rede de quadras
      </Btn>
      <Notice icon="image">Fotos revisadas, sem pessoas.</Notice>
    </Page>
  );
}

function SpaceBookingCard({
  space,
  venueId,
  venueName,
  timezone,
}: {
  space: BookableVenueSpace;
  venueId: string;
  venueName: string;
  timezone: string;
}) {
  const nav = useNav();
  const { palette } = useTheme();
  const formats = space.sports.flatMap((sport) => sport.formats);
  const [formatId, setFormatId] = useState(formats[0]?.id ?? '');
  const format = formats.find((item) => item.id === formatId) ?? formats[0];
  const slots = space.next_slots.slice(0, 5);
  const bandLabel = (code: string) =>
    space.availability.find((item) => item.band?.code === code)?.band?.label ?? humanizeBand(code);

  return (
    <Card>
      <Row between>
        <View style={{ flex: 1 }}>
          <Txt variant="h3">{space.name}</Txt>
          <Txt variant="tiny" style={{ marginTop: 3 }}>
            {space.is_covered ? 'Coberta' : 'Aberta'} · {formats.length} formato(s)
          </Txt>
        </View>
        <Badge tone={space.is_covered ? 'green' : 'default'}>
          {space.is_covered ? 'COBERTA' : 'ABERTA'}
        </Badge>
      </Row>

      {formats.length ? (
        <>
          <Txt variant="label" style={{ marginTop: 14 }}>
            Formato
          </Txt>
          <ChipRow style={{ marginTop: 6 }}>
            {formats.map((item) => (
              <Chip key={item.id} on={item.id === format?.id} onPress={() => setFormatId(item.id)}>
                {item.name}
              </Chip>
            ))}
          </ChipRow>
        </>
      ) : (
        <Notice tone="orange" icon="alert">
          Esta quadra ainda não cadastrou formatos.
        </Notice>
      )}

      {format && Object.keys(format.tickets_by_band).length ? (
        <View style={{ marginTop: 10, flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {Object.entries(format.tickets_by_band).map(([code, tickets]) => (
            <Badge key={code}>
              {bandLabel(code).toUpperCase()} · {tickets} INGRESSOS
            </Badge>
          ))}
        </View>
      ) : null}

      <Txt variant="label" style={{ marginTop: 14 }}>
        Próximos horários
      </Txt>
      {slots.length ? (
        <View style={{ marginTop: 6 }}>
          {slots.map((slot) => {
            const tickets = format?.tickets_by_band[slot.band_code] ?? null;
            return (
              <View
                key={`${slot.starts_at}-${slot.band_code}`}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 10,
                  paddingVertical: 11,
                  borderBottomWidth: 1,
                  borderBottomColor: palette.line,
                }}
              >
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                    {zonedShortDateTime(slot.starts_at, timezone)}
                  </Text>
                  <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>
                    {bandLabel(slot.band_code)} · {cents(slot.price_cents)}
                    {tickets != null
                      ? ` · ${tickets} ingressos/vaga`
                      : ' · ingressos não configurados'}
                  </Text>
                </View>
                <Btn
                  small
                  block={false}
                  tone="primary"
                  disabled={!format}
                  onPress={() =>
                    nav.go('booking-request', {
                      venueId,
                      venueName,
                      spaceId: space.id,
                      spaceName: space.name,
                      formatId: format?.id,
                      formatName: format?.name,
                      startsAt: slot.starts_at,
                      endsAt: slot.ends_at,
                      priceCents: slot.price_cents,
                      bandCode: slot.band_code,
                      bandLabel: bandLabel(slot.band_code),
                      ticketsPerSeat: tickets,
                      covered: space.is_covered,
                      timezone,
                    })
                  }
                >
                  Reservar
                </Btn>
              </View>
            );
          })}
        </View>
      ) : (
        <Notice tone="blue" icon="clock">
          Sem horários livres nos próximos dias para esta quadra.
        </Notice>
      )}

      {space.availability.length ? (
        <View style={{ marginTop: 14 }}>
          <Txt variant="label">Agenda semanal</Txt>
          <View style={{ marginTop: 6, gap: 6 }}>
            {space.availability.slice(0, 4).map((item) => (
              <Row key={`${item.weekday}-${item.start_time}-${item.band?.code ?? ''}`} between>
                <Txt variant="tiny">
                  {weekdayLabel(item.weekday)} · {item.start_time.slice(0, 5)}–
                  {item.end_time.slice(0, 5)}
                </Txt>
                <Txt variant="tiny">
                  {item.band?.label ?? 'Sem faixa'} · {cents(item.price_cents)}
                </Txt>
              </Row>
            ))}
          </View>
        </View>
      ) : null}
    </Card>
  );
}

function VenueDetail() {
  const nav = useNav();
  const { session } = useApp();
  const venueId = typeof nav.params.venueId === 'string' ? nav.params.venueId : null;
  const venueName =
    typeof nav.params.venueName === 'string' ? nav.params.venueName : 'Quadra reservável';
  const venueCity = typeof nav.params.venueCity === 'string' ? nav.params.venueCity : '';
  const covered = nav.params.covered === true;
  const [detail, setDetail] = useState<BookableVenueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!venueId || !session) {
      return;
    }
    let active = true;
    api.discovery
      .bookableVenue(session.accessToken, venueId)
      .then((result) => {
        if (active) {
          setDetail(result);
        }
      })
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
  }, [venueId, session]);

  const retry = () => {
    if (!venueId || !session) {
      return;
    }
    setLoading(true);
    setFailed(false);
    api.discovery
      .bookableVenue(session.accessToken, venueId)
      .then(setDetail)
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };

  if (!venueId || !session) {
    return (
      <Page title={venueName}>
        <StateScreen
          icon="pin"
          title="Quadra não informada"
          text="Abra a quadra pela vitrine de quadras reserváveis para ver espaços, horários e preços."
          actions={
            <Btn tone="primary" go="venues">
              Ver quadras
            </Btn>
          }
        />
      </Page>
    );
  }

  if (loading) {
    return (
      <Page title={venueName}>
        <LoadingState label="Buscando horários da quadra." variant="season" />
      </Page>
    );
  }

  if (failed || !detail) {
    return (
      <Page title={venueName}>
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar a quadra"
          text="Verifique a conexão e tente novamente."
          actions={
            <Btn tone="primary" onPress={retry}>
              Tentar novamente
            </Btn>
          }
        />
      </Page>
    );
  }

  const photo = detail.photos[0]?.content_url;
  return (
    <Page title={venueName}>
      {photo && session ? (
        <Image
          source={{
            uri: apiAssetUrl(photo),
            headers: { Authorization: `Bearer ${session.accessToken}` },
          }}
          style={{ width: '100%', height: 170, borderRadius: 16 }}
          resizeMode="cover"
        />
      ) : (
        <Photo tone={covered ? 'green' : 'orange'} />
      )}
      <Row between>
        <View style={{ flex: 1 }}>
          <Txt variant="h2">{venueName}</Txt>
          <Txt variant="tiny" style={{ marginTop: 4 }}>
            {[venueCity, detail.timezone].filter(Boolean).join(' · ')}
          </Txt>
        </View>
        <Badge tone={covered ? 'green' : 'default'}>{covered ? 'COBERTA' : 'ABERTA'}</Badge>
      </Row>
      {detail.is_public === true ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <PublicVenueBadge />
          <Txt variant="tiny">Quadra da plataforma JOGA</Txt>
        </View>
      ) : null}
      <Card tone="flat">
        <Row between>
          <Txt variant="tiny">Espaços reserváveis</Txt>
          <Txt variant="h3">{detail.spaces.length}</Txt>
        </Row>
        <Row between style={{ marginTop: 8 }}>
          <Txt variant="tiny">Confirmação</Txt>
          <Txt variant="tiny">transacional no servidor</Txt>
        </Row>
      </Card>
      {detail.spaces.length ? (
        detail.spaces.map((space) => (
          <SpaceBookingCard
            key={space.id}
            space={space}
            venueId={detail.id}
            venueName={venueName}
            timezone={detail.timezone}
          />
        ))
      ) : (
        <EmptyState
          title="Sem espaços reserváveis"
          text="A quadra ainda não publicou espaços ou horários para reserva."
        />
      )}
      <Notice tone="blue" icon="info">
        Horários são referência. A reserva só é confirmada depois da validação de agenda, pagamento
        e aceite da quadra.
      </Notice>
    </Page>
  );
}

function BookingRequest() {
  const nav = useNav();
  const { session, matches, queue, loadBookings, email, emailReady, wallet } = useApp();
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const venueId = typeof nav.params.venueId === 'string' ? nav.params.venueId : null;
  const venueName = typeof nav.params.venueName === 'string' ? nav.params.venueName : 'Quadra';
  const spaceId = typeof nav.params.spaceId === 'string' ? nav.params.spaceId : null;
  const spaceName = typeof nav.params.spaceName === 'string' ? nav.params.spaceName : 'Espaço';
  const formatName = typeof nav.params.formatName === 'string' ? nav.params.formatName : null;
  const bandLabel = typeof nav.params.bandLabel === 'string' ? nav.params.bandLabel : null;
  const startsAt = typeof nav.params.startsAt === 'string' ? nav.params.startsAt : null;
  const endsAt = typeof nav.params.endsAt === 'string' ? nav.params.endsAt : null;
  const priceCents = typeof nav.params.priceCents === 'number' ? nav.params.priceCents : null;
  const ticketsPerSeat =
    typeof nav.params.ticketsPerSeat === 'number' ? nav.params.ticketsPerSeat : null;
  const covered = nav.params.covered === true;
  const timezone = typeof nav.params.timezone === 'string' ? nav.params.timezone : null;
  const lobbyId =
    (typeof nav.params.lobbyId === 'string' && nav.params.lobbyId) ||
    matches.find((match) => match.lobby_id)?.lobby_id ||
    queue?.lobby?.id ||
    null;

  if (!venueId || !spaceId || !startsAt || !endsAt) {
    return (
      <Page title="Solicitar reserva">
        <EmptyState
          title="Escolha um horário"
          text="Selecione uma quadra, um formato e um horário livre para solicitar a reserva."
          actions={
            <Btn tone="primary" back>
              Voltar
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!lobbyId) {
    return (
      <Page title="Solicitar reserva">
        <StateScreen
          icon="users"
          title="Escolha um lobby primeiro"
          text="A reserva é feita para um lobby existente, com o grupo que vai jogar. Entre em uma partida ou lobby e volte para escolher o horário."
          actions={
            <>
              <Btn tone="primary" onPress={() => nav.go('queue', { mode: 'casual' })}>
                Buscar partida
              </Btn>
              <Btn tone="ghost" go="matches">
                Ver minhas partidas
              </Btn>
            </>
          }
        />
      </Page>
    );
  }

  if (!emailReady) {
    return (
      <Page title="Solicitar reserva">
        <LoadingState label="Verificando seus dados de pagamento." variant="cards" />
      </Page>
    );
  }

  if (!email) {
    return (
      <Page title="Solicitar reserva">
        <StateScreen
          icon="wallet"
          title="E-mail necessário"
          text="A reserva pode gerar uma cobrança Pix. Informe um e-mail para o Mercado Pago antes de solicitar."
          actions={
            <>
              <Btn tone="primary" go="payment-email">
                Informar e-mail
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

  const duration = Math.max(
    1,
    Math.round((new Date(endsAt).getTime() - new Date(startsAt).getTime()) / 60_000),
  );
  const estimate =
    priceCents != null && ticketsPerSeat != null
      ? referenceBreakdown(ticketsPerSeat, priceCents)
      : null;
  const family = formatFamily(formatName);

  const submit = async () => {
    if (!session || busy || !accepted) {
      return;
    }
    setBusy(true);
    try {
      const booking = await api.bookings.create(session.accessToken, {
        lobby_id: lobbyId,
        organization_venue_id: venueId,
        venue_space_id: spaceId,
        starts_at: startsAt,
        ends_at: endsAt,
      });
      await loadBookings();
      nav.replace('booking-t1t2', { bookingId: booking.id });
    } catch (error) {
      if (error instanceof ApiError && error.code === 'payer_email_required') {
        nav.go('payment-email');
        return;
      }
      toastError(nav, error, {
        needed: ticketsPerSeat,
        available: wallet?.balance ?? null,
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page title="Solicitar reserva">
      <Card>
        <Kv label="Quadra" value={venueName} />
        <Kv label="Espaço" value={spaceName} />
        <Kv label="Formato" value={formatName ?? 'A confirmar'} />
        <Kv label="Faixa" value={bandLabel ?? 'Definida na confirmação'} />
        <Kv label="Data e horário" value={zonedShortDateTime(startsAt, timezone)} />
        <Kv label="Duração" value={`${duration} min`} />
        <Kv label="Cobertura" value={covered ? 'Coberta' : 'Aberta'} />
        <Kv label="Custo da quadra" value={priceCents != null ? cents(priceCents) : '—'} />
        <Kv
          label="Ingressos por vaga"
          value={ticketsPerSeat != null ? `${ticketsPerSeat} ingressos` : 'A confirmar'}
        />
      </Card>
      {estimate && priceCents != null && ticketsPerSeat != null ? (
        <Card tone="lime">
          <Row between>
            <Txt variant="tiny">Valor da quadra</Txt>
            <Txt variant="num">{cents(priceCents)}</Txt>
          </Row>
          <Row between style={{ marginTop: 8 }}>
            <Txt variant="tiny">Ingressos por vaga</Txt>
            <Txt variant="num">{ticketsPerSeat}</Txt>
          </Row>
          <Row between style={{ marginTop: 8 }}>
            <Txt variant="tiny">Total de referência por vaga</Txt>
            <Txt variant="num">{cents(estimate.totalCents)}</Txt>
          </Row>
          <Row between style={{ marginTop: 8 }}>
            <Txt variant="tiny">Valor do JOGA (restante)</Txt>
            <Txt variant="num">{cents(estimate.jogaCents)}</Txt>
          </Row>
          <Txt variant="tiny" style={{ marginTop: 8 }}>
            Estimativa com o ingresso de referência a {cents(TICKET_REFERENCE_CENTS)}. Os valores
            finais são congelados pelo servidor na confirmação.
          </Txt>
        </Card>
      ) : null}
      {family ? <TicketConversionTable emphasis={family} /> : null}
      <TimerCard
        label="T2 · resposta do estabelecimento"
        value="até 60 min"
        note="30 min comercial · máximo 60 min"
        tone="on"
      />
      <Notice tone="lime" icon="wallet">
        A faixa e os ingressos por vaga ficam congelados nesta reserva. Reajustes posteriores não
        alteram o valor.
      </Notice>
      <Notice tone="blue" icon="shield">
        A NFS-e do uso do espaço é emitida pelo estabelecimento contra o seu CPF. Informe ou revise
        o CPF no perfil.
      </Notice>
      <TextBtn go="cpf" muted>
        Informar CPF para a nota
      </TextBtn>
      <Check checked={accepted} onChange={setAccepted}>
        Entendo que a vaga só é confirmada após o aceite da quadra e a quitação dos participantes.
      </Check>
      <Btn tone="primary" onPress={submit} disabled={!accepted || busy}>
        {busy ? 'Enviando…' : 'Enviar solicitação'}
      </Btn>
    </Page>
  );
}

function bookingStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    PENDING_CONFIRMATION: 'AGUARDANDO',
    PARTICIPANT_CONFIRMATION: 'CONFIRMAÇÃO',
    PAYMENT_PENDING: 'PAGAMENTO',
    CONFIRMED: 'CONFIRMADA',
    DECLINED: 'RECUSADA',
    EXPIRED: 'EXPIRADA',
    CANCELLED: 'CANCELADA',
    CANCELLED_BY_PLAYER: 'CANCELADA',
    CANCELLED_BY_VENUE: 'CANCELADA PELA QUADRA',
    COMPLETED: 'CONCLUÍDA',
  };
  return labels[status] ?? status.replaceAll('_', ' ');
}

function BookingActions({ booking }: { booking: Booking }) {
  const nav = useNav();
  const { session, loadBookings, wallet } = useApp();
  const [busy, setBusy] = useState(false);
  const ownParticipant =
    booking.participants.find((participant) => participant.user_id === session?.userId) ?? null;
  const ownPayment = ownParticipant
    ? booking.payments.find((item) => item.participant_id === ownParticipant.id)
    : undefined;
  const awaitingConfirmation =
    booking.status === 'PARTICIPANT_CONFIRMATION' &&
    !!ownParticipant &&
    !ownParticipant.confirmed_at &&
    !ownParticipant.declined_at;
  const canCancel = ![
    'CANCELLED',
    'CANCELLED_BY_PLAYER',
    'CANCELLED_BY_VENUE',
    'COMPLETED',
    'EXPIRED',
    'DECLINED',
  ].includes(booking.status);

  const respond = async (decision: 'CONFIRM' | 'DECLINE') => {
    if (!session || busy) {
      return;
    }
    setBusy(true);
    try {
      await api.bookings.participantConfirmation(session.accessToken, booking.id, decision);
      await loadBookings();
      if (decision === 'DECLINE') {
        nav.replace('booking-declined', { bookingId: booking.id });
      } else {
        nav.toast('Participação confirmada.');
      }
    } catch (error) {
      toastError(nav, error, {
        needed: booking.tickets_per_seat,
        available: wallet?.balance ?? null,
      });
    } finally {
      setBusy(false);
    }
  };

  const cancelBooking = async () => {
    if (!session || busy) {
      return;
    }
    setBusy(true);
    try {
      await api.bookings.cancel(
        session.accessToken,
        booking.id,
        'Cancelada pelo jogador no aplicativo.',
      );
      await loadBookings();
      nav.replace('booking-history');
      nav.toast('Reserva cancelada.');
    } catch (error) {
      toastError(nav, error);
    } finally {
      setBusy(false);
    }
  };

  const preCheckIn = async () => {
    if (!session || busy) {
      return;
    }
    setBusy(true);
    try {
      await api.bookings.preCheckIn(session.accessToken, booking.id);
      await loadBookings();
      nav.toast('Pré-check-in confirmado.');
    } catch (error) {
      toastError(nav, error);
    } finally {
      setBusy(false);
    }
  };

  const confirmPresence = async () => {
    if (!session || busy) {
      return;
    }
    setBusy(true);
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (!permission.granted) {
        nav.go('checkin-denied', { bookingId: booking.id });
        return;
      }
      const position = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });
      await api.bookings.confirmPresence(session.accessToken, booking.id, {
        method: 'GPS',
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy_m: Math.max(0, Math.round(position.coords.accuracy ?? 0)),
      });
      await loadBookings();
      nav.toast('Presença confirmada.');
    } catch (error) {
      toastError(nav, error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {awaitingConfirmation ? (
        <BtnRow>
          <Btn tone="primary" onPress={() => respond('CONFIRM')} disabled={busy}>
            Confirmar participação
          </Btn>
          <Btn tone="ghost" onPress={() => respond('DECLINE')} disabled={busy}>
            Recusar
          </Btn>
        </BtnRow>
      ) : null}
      {ownParticipant ? (
        <Row between style={{ marginTop: 2 }}>
          <Txt variant="tiny">Sua confirmação</Txt>
          <Badge tone={ownParticipant.confirmed_at ? 'green' : 'orange'}>
            {ownParticipant.confirmed_at
              ? 'CONFIRMADA'
              : ownParticipant.declined_at
                ? 'RECUSADA'
                : 'PENDENTE'}
          </Badge>
        </Row>
      ) : null}
      {ownPayment && ['PENDING', 'FAILED'].includes(ownPayment.status) ? (
        <Btn tone="primary" onPress={() => nav.go('booking-payment', { bookingId: booking.id })}>
          Pagar minha vaga
        </Btn>
      ) : null}
      {ownParticipant?.presence_status === 'PRESENT' ? (
        <Notice tone="green" icon="check">
          Presença confirmada no local.
        </Notice>
      ) : booking.status === 'CONFIRMED' ? (
        <BtnRow>
          <Btn tone="primary" onPress={confirmPresence} disabled={busy}>
            {busy ? 'Confirmando…' : 'Confirmar presença'}
          </Btn>
          <Btn tone="ghost" onPress={preCheckIn} disabled={busy}>
            Pré-check-in
          </Btn>
        </BtnRow>
      ) : null}
      <Btn tone="primary" go="booking-history">
        Ver histórico de reservas
      </Btn>
      {canCancel ? (
        <Btn
          tone="ghost"
          onPress={() => nav.openModal('cancel-booking', () => void cancelBooking())}
          disabled={busy}
        >
          Cancelar reserva
        </Btn>
      ) : null}
    </>
  );
}

function BookingT1T2() {
  const nav = useNav();
  const { bookings, loadBookings, session } = useApp();
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    loadBookings()
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [loadBookings]);
  const bookingId = typeof nav.params.bookingId === 'string' ? nav.params.bookingId : null;
  const booking: Booking | undefined =
    bookings.find((item) => item.id === bookingId) ?? bookings[0];
  useEffect(() => {
    const status = booking?.status;
    if (status === 'CONFIRMED') {
      nav.replace('booking-confirmed', bookingId ? { bookingId } : undefined);
    } else if (status === 'DECLINED') {
      nav.replace('booking-declined', bookingId ? { bookingId } : undefined);
    } else if (status === 'EXPIRED') {
      nav.replace('booking-expired', bookingId ? { bookingId } : undefined);
    }
  }, [booking?.status, bookingId, nav]);
  if (loading) {
    return (
      <Page title="Acompanhar reserva">
        <LoadingState label="Buscando sua reserva." variant="timers" />
      </Page>
    );
  }
  if (!booking) {
    return (
      <Page title="Acompanhar reserva">
        <EmptyState
          title="Nenhuma reserva em andamento"
          text="Solicite uma quadra para acompanhar T1 e T2 por aqui."
          actions={
            <Btn tone="primary" go="venues">
              Ver quadras
            </Btn>
          }
        />
      </Page>
    );
  }
  const t1 = booking.timers.find((item) => item.timer_type === 'T1');
  const t2 = booking.timers.find((item) => item.timer_type === 'T2');
  const active = booking.participants.filter((participant) => participant.active);
  const confirmed = active.filter((participant) => participant.confirmed_at).length;
  const tickets = booking.tickets_per_seat;
  const ownParticipant =
    booking.participants.find((participant) => participant.user_id === session?.userId) ?? null;
  const ownPrice = participantPrice(ownParticipant);
  return (
    <Page title="Acompanhar reserva">
      <Row between>
        <View style={{ flex: 1 }}>
          <Txt variant="h2">{booking.organization_venue_name}</Txt>
          <Txt variant="tiny" style={{ marginTop: 3 }}>
            {zonedShortDateTime(booking.starts_at, booking.timezone)} · {booking.venue_space_name}
            {booking.format_name ? ` · ${booking.format_name}` : ''}
          </Txt>
        </View>
        <Badge tone="orange">{bookingStatusLabel(booking.status)}</Badge>
      </Row>
      <Card tone="flat">
        <Row between>
          <Txt variant="tiny">Faixa</Txt>
          <Txt variant="h3">{booking.band_label ?? 'a definir'}</Txt>
        </Row>
        <Row between style={{ marginTop: 8 }}>
          <Txt variant="tiny">Ingressos por vaga</Txt>
          <Txt variant="h3">{tickets != null ? `${tickets} ingressos` : 'quitação pendente'}</Txt>
        </Row>
        <Row between style={{ marginTop: 8 }}>
          <Txt variant="tiny">Custo da quadra</Txt>
          <Txt variant="h3">{cents(booking.price_cents)}</Txt>
        </Row>
        {booking.fee_percent_applied > 0 ? (
          <Row between style={{ marginTop: 8 }}>
            <Txt variant="tiny">Percentual de referência congelado</Txt>
            <Txt variant="h3">{(booking.fee_percent_applied / 100).toFixed(2)}%</Txt>
          </Row>
        ) : null}
        <Row between style={{ marginTop: 8 }}>
          <Txt variant="tiny">Versão de preço</Txt>
          <Txt variant="h3">{booking.pricing_version}</Txt>
        </Row>
        {booking.players_per_team != null ? (
          <Row between style={{ marginTop: 8 }}>
            <Txt variant="tiny">Jogadores por time</Txt>
            <Txt variant="h3">{booking.players_per_team}</Txt>
          </Row>
        ) : null}
        {booking.formation_note ? (
          <Txt variant="tiny" style={{ marginTop: 8 }}>
            {booking.formation_note}
          </Txt>
        ) : null}
      </Card>
      {booking.pricing_version !== 'legacy_v0' || booking.total_cents > 0 ? (
        <>
          <PriceBreakdown {...bookingPrice(booking)} tickets={tickets} />
          {ownPrice ? (
            <PriceBreakdown
              {...ownPrice}
              tickets={ownParticipant?.tickets_consumed ?? null}
              feeLabel={ownPrice.fundingSource === 'pix' ? 'Taxa de 20%' : 'Valor do JOGA'}
            />
          ) : null}
        </>
      ) : null}
      <TimerCard
        label="T1 · participação"
        value={
          t1?.status === 'CLOSED' || t1?.status === 'DONE'
            ? 'concluído'
            : `${confirmed}/${active.length}`
        }
        note={`${confirmed} de ${active.length} participantes confirmaram`}
        tone="done"
      />
      <TimerCard
        label="T2 · resposta da quadra"
        value={t2 ? zonedTimeOnly(t2.deadline_at, booking.timezone) : 'aguardando'}
        note={`${booking.organization_venue_name} · prazo ${t2 ? zonedTimeOnly(t2.deadline_at, booking.timezone) : '—'}`}
        tone="on"
      />
      <Card tone="lime">
        <Row between wrap style={{ rowGap: 8 }}>
          <View style={{ flexGrow: 1, flexShrink: 1, flexBasis: '60%', minWidth: 0 }}>
            <Txt variant="label">Quitação</Txt>
            <Txt variant="h3">
              {tickets != null ? `${tickets} ingressos por jogador` : 'Aguardando configuração'}
            </Txt>
          </View>
          <Badge tone="lime">{tickets != null ? 'CONGELADOS' : 'PENDENTE'}</Badge>
        </Row>
      </Card>
      <BookingActions booking={booking} />
    </Page>
  );
}

function BookingConfirmed() {
  const nav = useNav();
  const { bookings, session } = useApp();
  const bookingId = typeof nav.params.bookingId === 'string' ? nav.params.bookingId : null;
  const booking = bookings.find((item) => item.id === bookingId) ?? bookings[0];
  const ownParticipant =
    booking?.participants.find((participant) => participant.user_id === session?.userId) ?? null;
  const ownPrice = participantPrice(ownParticipant);
  return (
    <Page title="Reserva confirmada">
      <StateScreen
        icon="check"
        title="Quadra confirmada"
        text={
          booking
            ? `${booking.organization_venue_name} confirmou a reserva. A faixa e os ingressos por vaga ficaram congelados.`
            : 'A quadra confirmou a reserva. A faixa e os ingressos por vaga ficaram congelados.'
        }
        actions={
          <>
            <Btn tone="primary" go="booking-history">
              Ver minhas reservas
            </Btn>
            <Btn tone="ghost" go="venues">
              Ver outras quadras
            </Btn>
          </>
        }
      />
      <Card>
        <Kv label="Quadra" value={booking?.organization_venue_name ?? '—'} />
        <Kv label="Espaço" value={booking?.venue_space_name ?? '—'} />
        <Kv label="Formato" value={booking?.format_name ?? '—'} />
        <Kv label="Faixa congelada" value={booking?.band_label ?? '—'} />
        <Kv
          label="Horário"
          value={booking ? zonedShortDateTime(booking.starts_at, booking.timezone) : '—'}
        />
        <Kv
          label="Ingressos por vaga"
          value={booking?.tickets_per_seat != null ? `${booking.tickets_per_seat}` : '—'}
        />
      </Card>
      {booking ? (
        <>
          <PriceBreakdown {...bookingPrice(booking)} tickets={booking.tickets_per_seat} />
          {ownPrice ? (
            <>
              <Card tone="lime">
                <Row between>
                  <Txt variant="h3">Sua vaga</Txt>
                  <Badge tone="lime">
                    {ownParticipant?.tickets_consumed
                      ? `${ownParticipant.tickets_consumed} ingressos`
                      : 'quitada'}
                  </Badge>
                </Row>
              </Card>
              <PriceBreakdown
                {...ownPrice}
                tickets={ownParticipant?.tickets_consumed ?? null}
                feeLabel={ownPrice.fundingSource === 'pix' ? 'Taxa de 20%' : 'Valor do JOGA'}
              />
            </>
          ) : null}
          <Card>
            <Txt variant="h3">Documento fiscal</Txt>
            <Txt variant="tiny" style={{ marginTop: 6 }}>
              O estabelecimento emite a NFS-e de uso do espaço contra o seu CPF. O JOGA emite a
              NFS-e de intermediação. O app não inventa número nem referência quando o documento
              ainda não foi emitido.
            </Txt>
            <Row between style={{ marginTop: 10 }}>
              <Txt variant="tiny">Referência da NFS-e</Txt>
              <Badge tone="orange">aguardando emissão</Badge>
            </Row>
            <Btn tone="ghost" go="cpf">
              Informar CPF para a nota
            </Btn>
          </Card>
        </>
      ) : null}
      {booking ? <BookingActions booking={booking} /> : null}
    </Page>
  );
}

function BookingDeclined() {
  return (
    <Page title="Reserva">
      <StateScreen
        icon="alert"
        title="A quadra não aceitou"
        text="O horário ficou indisponível na quadra. Seus ingressos voltam para o saldo."
        actions={
          <>
            <Btn tone="primary" go="venues">
              Buscar outra quadra
            </Btn>
            <Btn tone="ghost" go="lobby-canceled">
              Cancelar lobby
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function BookingExpired() {
  const nav = useNav();
  const { bookings } = useApp();
  const bookingId = typeof nav.params.bookingId === 'string' ? nav.params.bookingId : null;
  const booking = bookings.find((item) => item.id === bookingId) ?? bookings[0];
  return (
    <Page title="Reserva">
      <StateScreen
        icon="clock"
        title="Reserva expirada"
        text="A quadra foi liberada e os ingressos voltaram para o saldo. Já estamos buscando outra partida."
        actions={
          <>
            <Btn tone="primary" go="home">
              Cancelar fila
            </Btn>
            <Btn tone="ghost" go="notifications">
              Ver notificações
            </Btn>
          </>
        }
      />
      <Card>
        <Kv
          label="Ingressos devolvidos"
          value={
            booking?.tickets_per_seat != null ? `${booking.tickets_per_seat} por jogador` : '—'
          }
        />
        <Kv label="Status" value="Devolvido em ingressos" />
      </Card>
    </Page>
  );
}

function CancelCutoff() {
  const { palette } = useTheme();
  return (
    <Page title="Cancelar participação">
      <TimerCard
        label="Cutoff de cancelamento"
        value="7h 12min"
        note="até 14:00 · 6 h antes da partida"
        tone="on"
      />
      <Card>
        <Txt variant="h3">Se você cancelar agora</Txt>
        <View style={{ marginTop: 6 }}>
          {[
            ['T4 abre para substituto', '25% do tempo restante, piso 30 min, teto 12 h', 'orange'],
            ['Você não recebe reembolso', 'Se um substituto pagar, seu ingresso volta', 'orange'],
            [
              'Os demais ficam protegidos',
              'Sem substituto, o lobby é cancelado e os outros recebem',
              'green',
            ],
          ].map(([title, sub, dot], index) => (
            <View
              key={title}
              style={{
                flexDirection: 'row',
                alignItems: 'flex-start',
                gap: 10,
                paddingVertical: 11,
                borderBottomWidth: index === 2 ? 0 : 1,
                borderBottomColor: palette.line,
              }}
            >
              <View
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 4,
                  marginTop: 6,
                  backgroundColor: dot === 'green' ? palette.green : palette.lime,
                }}
              />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>{title}</Text>
                <Text style={{ fontSize: 13, color: palette.muted, marginTop: 2 }}>{sub}</Text>
              </View>
            </View>
          ))}
        </View>
      </Card>
      <Notice tone="red" icon="alert">
        Depois do cutoff não existe cancelamento voluntário com reembolso. A ausência é no-show.
      </Notice>
      <Btn tone="danger" modal="cancel">
        Cancelar e abrir T4
      </Btn>
      <Btn tone="ghost" back>
        Manter vaga
      </Btn>
    </Page>
  );
}

function CancelClosed() {
  return (
    <Page title="Cancelamento">
      <StateScreen
        icon="lock"
        title="Cancelamento fechado"
        text="A partida começa em 4h 58min. O cutoff de 6h já passou. Se você não comparecer, será no-show, sem reembolso, e um substituto pode ocupar a vaga já paga."
        actions={
          <>
            <Btn tone="primary" back>
              Entendi
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

function CheckinPre() {
  const nav = useNav();
  const { matches } = useApp();
  const match = matches.find((item) => item.id === nav.params.matchId) ?? matches[0];
  return (
    <Page title="Pré-check-in">
      <TimerCard
        label="Intenção de presença"
        value={match ? timeOnly(match.check_in_deadline) : '--:--'}
        note={match ? `abre ${timeOnly(match.check_in_opens_at)}` : 'partida não encontrada'}
        tone="on"
      />
      <Card tone="ink">
        <Txt variant="display" color="onInk" style={{ fontSize: 26 }}>
          Você vai{'\n'}comparecer?
        </Txt>
        <Txt variant="tiny" color="softOnInk" style={{ marginTop: 6 }}>
          {match ? shortDateTime(match.scheduled_start_at) : 'Escolha uma partida na agenda.'}
        </Txt>
      </Card>
      <Notice tone="blue" icon="info">
        No ranqueado é obrigatório. No casual é recomendado e ajuda o grupo a se organizar.
      </Notice>
      <Btn
        tone="primary"
        onPress={() => nav.go('checkin-presence', match ? { matchId: match.id } : undefined)}
      >
        Vou comparecer
      </Btn>
      <Btn tone="ghost" go="matches">
        Gerenciar partida
      </Btn>
    </Page>
  );
}

function CheckinPresence() {
  const nav = useNav();
  const { session, matches, loadMatches } = useApp();
  const [busy, setBusy] = useState(false);
  const match = matches.find((item) => item.id === nav.params.matchId) ?? matches[0];
  const confirm = async () => {
    if (busy) {
      return;
    }
    if (!session || !match) {
      nav.toast('Escolha uma partida na agenda para confirmar a presença.');
      return;
    }
    setBusy(true);
    try {
      await api.matches.checkIn(session.accessToken, match.id);
      await loadMatches();
      nav.toast('Presença confirmada.');
    } catch (error) {
      toastError(nav, error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Page title="Confirmar presença">
      <TimerCard
        label="Presença no local"
        value={match ? timeOnly(match.check_in_deadline) : '--:--'}
        note={match ? shortDateTime(match.scheduled_start_at) : 'partida não encontrada'}
        tone="on"
      />
      <Card>
        <Row between>
          <Txt variant="h3">Confirmação no local</Txt>
          <Badge tone="lime">GPS</Badge>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          O servidor valida a distância e a precisão informadas pelo GPS do aparelho.
        </Txt>
      </Card>
      <Btn tone="primary" icon="check" onPress={confirm} disabled={busy}>
        {busy ? 'Confirmando…' : 'Confirmar presença'}
      </Btn>
      <BtnRow>
        <Btn tone="ghost" go="checkin-fallback">
          Pedir confirmação
        </Btn>
        <Btn tone="ghost" go="substitutes">
          Substitutos
        </Btn>
      </BtnRow>
    </Page>
  );
}

function CheckinFallback() {
  return (
    <Page title="Presença">
      <StateScreen
        icon="pin"
        title="GPS indisponível ou fora do raio"
        text="Peça à recepção da quadra para confirmar sua presença no local. A confirmação por GPS pode ser tentada novamente."
        actions={
          <>
            <Btn tone="primary" go="checkin-presence">
              Tentar GPS novamente
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

function CheckinDenied() {
  return (
    <Page title="Localização">
      <StateScreen
        icon="pin"
        title="Sem permissão de localização"
        text="Para confirmar presença por GPS, ative a localização. Se preferir não ativar, peça a confirmação da quadra no local."
        actions={
          <>
            <Btn tone="primary" onPress={() => void Linking.openSettings()}>
              Ativar localização
            </Btn>
            <Btn tone="ghost" go="checkin-fallback">
              Usar fallback do estabelecimento
            </Btn>
          </>
        }
      />
    </Page>
  );
}

function MatchAdapt() {
  return (
    <Page title="Formato adaptado">
      <Card tone="ink">
        <Badge tone="lime">9 PRESENTES</Badge>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 32, marginTop: 10, marginBottom: 4 }}
        >
          4x4 + 1{'\n'}rodízio
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          Recomendação do sistema · não é bloqueio
        </Txt>
      </Card>
      <Card>
        <Txt variant="h3">Presentes</Txt>
        <View style={{ marginTop: 6 }}>
          {['Susan', 'Rafa', 'Bia', 'Marcus_rise', 'Jo', 'Léo', 'Nina', 'Caio', 'Duda'].map(
            (name, index) => (
              <PlayerRow
                key={name}
                name={name}
                role={index === 3 ? 'ausente substituído' : 'presente'}
                identity={identityFromSeed(name)}
              />
            ),
          )}
        </View>
      </Card>
      <Notice tone="orange" icon="info">
        Partida adaptada de 5x5 para 4x4 não conta como 5x5 ranqueado.
      </Notice>
      <Btn tone="primary" go="lobby-detail">
        Aceitar formato
      </Btn>
      <Btn tone="ghost" go="support">
        Ver regra de rodízio
      </Btn>
    </Page>
  );
}

function Substitutes() {
  const nav = useNav();
  const { palette } = useTheme();
  const { matches, bookings, session } = useApp();
  const match = matches.find((item) => item.id === nav.params.matchId) ?? matches[0];
  const lobbyId = match?.lobby_id;
  const booking = bookings.find((item) => item.lobby_id === lobbyId) ?? null;
  const [items, setItems] = useState<Substitute[]>([]);
  useEffect(() => {
    if (session && lobbyId) {
      api.substitutions
        .listQueue(session.accessToken, lobbyId)
        .then((result) => setItems(result.substitutes))
        .catch(() => undefined);
    }
  }, [session, lobbyId]);
  const enter = async () => {
    if (session && lobbyId) {
      try {
        const item = await api.substitutions.joinQueue(session.accessToken, lobbyId);
        setItems((current) => [...current, item]);
        nav.toast('Você entrou na fila de substitutos.');
      } catch (error) {
        toastError(nav, error);
      }
      return;
    }
    nav.toast('Entre na fila a partir de um lobby.');
  };
  const leave = async () => {
    if (session && lobbyId) {
      try {
        await api.substitutions.leaveQueue(session.accessToken, lobbyId);
        setItems((current) => current.filter((item) => item.user_id !== session.userId));
        nav.toast('Você saiu da fila de substitutos.');
      } catch (error) {
        toastError(nav, error);
      }
      return;
    }
    nav.toast('Entre na fila a partir de um lobby.');
  };
  const list = items.map((item, index) => ({
    id: `${item.user_id}-${index}`,
    name: item.status === 'CALLED' ? 'Chamado' : 'Jogador',
    sub: `${item.position}º · ${item.status.toLowerCase()}`,
    ready: item.status === 'CONFIRMED',
  }));
  const called =
    items.find((item) => item.user_id === session?.userId && item.status === 'CALLED') ?? null;
  return (
    <Page title="Fila de substitutos">
      <Card>
        <Row between>
          <Txt variant="h3">Standby</Txt>
          <Badge tone="lime">{items.length} na fila</Badge>
        </Row>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          Chamada só quando o número de ativos fica ímpar. Um por vez, com prazo de 5 min.
        </Txt>
      </Card>
      {list.length === 0 ? (
        <Card>
          <Txt variant="tiny">Ninguém na fila de substitutos deste lobby.</Txt>
        </Card>
      ) : null}
      <CardList>
        {list.map((item, index) => (
          <ListRow key={item.id} last={index === list.length - 1}>
            <IdentityBadge size={34} identity={identityFromSeed(item.id)} palette={palette} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                {item.name}
              </Text>
              <Text style={{ fontSize: 13, color: palette.muted }}>{item.sub}</Text>
            </View>
            <Badge tone={item.ready ? 'green' : 'default'}>
              {item.ready ? 'PRONTO' : 'STANDBY'}
            </Badge>
          </ListRow>
        ))}
      </CardList>
      <Notice tone="blue" icon="info">
        No ranqueado, a fila exige pelo menos 1 substituto em standby. Casual é opcional.
      </Notice>
      <Btn tone="primary" onPress={enter}>
        Entrar na fila
      </Btn>
      <Btn tone="ghost" onPress={leave}>
        Sair da fila
      </Btn>
      {called && booking ? (
        <Btn
          tone="primary"
          onPress={() =>
            nav.go('substitute-called', {
              bookingId: booking.id,
              substitutionId: called.id,
              matchId: match?.id,
            })
          }
        >
          Ver meu chamado
        </Btn>
      ) : null}
    </Page>
  );
}

function SubstituteCalled() {
  const nav = useNav();
  const { matches, bookings, session, loadBookings } = useApp();
  const [busy, setBusy] = useState(false);
  const bookingId = typeof nav.params.bookingId === 'string' ? nav.params.bookingId : null;
  const substitutionId =
    typeof nav.params.substitutionId === 'string' ? nav.params.substitutionId : null;
  const matchId = typeof nav.params.matchId === 'string' ? nav.params.matchId : null;
  const match = matches.find((item) => item.id === matchId) ?? null;
  const booking = bookings.find((item) => item.id === bookingId) ?? null;

  const decide = async (decision: 'accept' | 'decline') => {
    if (!session || !bookingId || !substitutionId || busy) {
      return;
    }
    setBusy(true);
    try {
      if (decision === 'accept') {
        await api.substitutions.accept(session.accessToken, bookingId, substitutionId);
        await loadBookings();
        nav.replace('booking-t1t2', { bookingId });
      } else {
        await api.substitutions.decline(session.accessToken, bookingId, substitutionId);
        nav.back();
      }
    } catch (error) {
      toastError(nav, error);
    } finally {
      setBusy(false);
    }
  };

  if (!bookingId || !substitutionId || !booking) {
    return (
      <Page title="Vaga aberta">
        <EmptyState
          title="Nenhum chamado ativo"
          text="Quando uma vaga abrir e você for chamado, o aceite aparece aqui com o prazo do servidor."
          actions={
            <>
              <Btn tone="primary" go="booking-history">
                Ver minhas reservas
              </Btn>
              <Btn tone="ghost" go="matches">
                Ver partidas
              </Btn>
            </>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Vaga aberta">
      <StateScreen
        icon="bolt"
        title={'Vaga\naberta'}
        text="Você foi chamado para uma vaga desta reserva. O aceite é validado pelo servidor e respeita o prazo da chamada."
      />
      <Card>
        <Kv label="Quadra" value={booking.organization_venue_name} />
        <Kv label="Espaço" value={booking.venue_space_name} />
        <Kv
          label="Horário"
          value={zonedShortDateTime(
            match?.scheduled_start_at ?? booking.starts_at,
            booking.timezone,
          )}
        />
        <Kv label="Formato" value={booking.format_name ?? '—'} />
        <Kv label="Faixa" value={booking.band_label ?? '—'} />
      </Card>
      <Btn tone="primary" onPress={() => decide('accept')} disabled={busy}>
        {busy ? 'Confirmando…' : 'Aceitar vaga'}
      </Btn>
      <Btn tone="ghost" onPress={() => decide('decline')} disabled={busy}>
        Recusar
      </Btn>
      <Notice tone="blue" icon="info">
        A substituição não altera o preço congelado da reserva nem cria uma cobrança nova no app.
      </Notice>
    </Page>
  );
}

function NoShow() {
  return (
    <Page title="Ausência registrada">
      <StateScreen
        icon="alert"
        title="No-show registrado"
        text="Você não confirmou presença até T-15m. A vaga pode ser ocupada por um substituto da fila, sem nova cobrança. Não há reembolso depois do cutoff."
        actions={
          <>
            <Btn tone="primary" go="support">
              Entender a regra
            </Btn>
            <Btn tone="ghost" go="support">
              Contestar
            </Btn>
          </>
        }
      />
      <Card>
        <Kv label="Partida" value="Futebol 5x5 · Arena Sul" />
        <Kv label="Reembolso" value="Sem reembolso" />
        <Kv label="Registro" value="Ausência registrada" />
        <Kv label="Substituto" value="Pode ocupar a vaga paga" />
      </Card>
    </Page>
  );
}

function ResultSelection({
  selected,
  setSelected,
  second,
}: {
  selected: number;
  setSelected: (value: number) => void;
  second?: boolean;
}) {
  const { palette } = useTheme();
  const items = second
    ? [{ title: 'Time A' }, { title: 'Empate' }, { title: 'Time B' }]
    : [{ title: 'Time A venceu' }, { title: 'Empate' }, { title: 'Time B venceu' }];
  return (
    <View style={{ gap: 8 }}>
      {items.map((item, index) => (
        <Card
          key={item.title}
          onPress={() => setSelected(index)}
          style={{
            borderColor: selected === index ? palette.ink : palette.line,
            borderWidth: selected === index ? 2 : 1.5,
          }}
        >
          <Row between>
            <Txt variant="h3">{item.title}</Txt>
            <View
              style={{
                width: 20,
                height: 20,
                borderRadius: 10,
                borderWidth: 2,
                borderColor: selected === index ? palette.ink : palette.line,
                backgroundColor: selected === index ? palette.ink : palette.surface,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {selected === index ? (
                <Text style={{ color: palette.onInk, fontSize: 12, fontWeight: '900' }}>✓</Text>
              ) : null}
            </View>
          </Row>
        </Card>
      ))}
    </View>
  );
}

function ReportResult() {
  const nav = useNav();
  const { session, matches } = useApp();
  const [selected, setSelected] = useState(0);
  const match = matches.find((item) => item.id === nav.params.matchId) ?? matches[0];
  const [result, setResult] = useState<ResultView | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (session && match) {
      api.results
        .get(session.accessToken, match.id)
        .then(setResult)
        .catch(() => undefined);
    }
  }, [session, match]);
  const submit = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    if (session && match) {
      const outcome = selected === 0 ? 'TEAM_1' : selected === 1 ? 'DRAW' : 'TEAM_2';
      try {
        await api.results.submit(session.accessToken, match.id, result?.round ?? 1, outcome);
        nav.reset('matches');
      } catch (error) {
        toastError(nav, error);
      } finally {
        setBusy(false);
      }
      return;
    }
    setBusy(false);
    nav.reset('matches');
  };
  return (
    <Page title="Como foi a partida?">
      <Txt variant="lead">
        {match
          ? `${shortDateTime(match.scheduled_start_at)} · ${match.state.replaceAll('_', ' ')}`
          : 'Partida não carregada'}
      </Txt>
      <ResultSelection selected={selected} setSelected={setSelected} />
      <TimerCard
        label="Prazo de relato"
        value={result?.deadline ? timeOnly(result.deadline) : '--:--'}
        note={result ? `rodada ${result.round ?? 1}` : 'aguardando o servidor'}
        tone="on"
      />
      <Notice tone="blue" icon="info">
        Votos são visíveis aos participantes.
      </Notice>
      <Btn tone="primary" onPress={submit} disabled={busy}>
        {busy ? 'Enviando…' : 'Enviar voto'}
      </Btn>
    </Page>
  );
}

function ResultSecondRound() {
  const nav = useNav();
  const { session, matches } = useApp();
  const [selected, setSelected] = useState(0);
  const [busy, setBusy] = useState(false);
  const match = matches.find((item) => item.id === nav.params.matchId) ?? matches[0];
  const submit = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    if (session && match) {
      const outcome = selected === 0 ? 'TEAM_1' : selected === 1 ? 'DRAW' : 'TEAM_2';
      try {
        await api.results.submit(session.accessToken, match.id, 2, outcome);
      } catch (error) {
        toastError(nav, error);
        setBusy(false);
        return;
      }
    }
    setBusy(false);
    nav.replace('result-review');
  };
  return (
    <Page title="Segunda rodada">
      <TimerCard
        label="Segunda rodada"
        value="04:12"
        note="5 min · sem terceira rodada"
        tone="on"
      />
      <Card tone="orange">
        <Txt variant="h3">A primeira votação ficou exatamente em 50%</Txt>
        <Txt variant="tiny" style={{ marginTop: 6 }}>
          O histórico anterior foi preservado. Escolha novamente; você pode confirmar ou corrigir.
        </Txt>
      </Card>
      <ResultSelection selected={selected} setSelected={setSelected} second />
      <Btn tone="primary" onPress={submit} disabled={busy}>
        {busy ? 'Confirmando…' : 'Confirmar voto'}
      </Btn>
    </Page>
  );
}

function Dispute() {
  const nav = useNav();
  const { session, matches } = useApp();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const match = matches.find((item) => item.id === nav.params.matchId) ?? matches[0];
  const submit = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    if (session && match) {
      try {
        const result = await api.results.get(session.accessToken, match.id);
        if (result.dispute_id) {
          await api.results.submitEvidence(session.accessToken, match.id, result.dispute_id, text);
        }
      } catch (error) {
        toastError(nav, error);
        setBusy(false);
        return;
      }
    }
    setBusy(false);
    nav.replace('result-review');
  };
  return (
    <Page title="Abrir disputa">
      <Card tone="orange">
        <Txt variant="h3">Resultado divergente</Txt>
        <Txt variant="tiny" style={{ marginTop: 5 }}>
          A partida entrou em disputa. A divisão fica congelada até a decisão.
        </Txt>
      </Card>
      <Textarea
        value={text}
        onChangeText={setText}
        maxLength={2000}
        placeholder="Explique o que aconteceu. Até 2.000 caracteres."
      />
      <Row between>
        <Txt variant="tiny">1 justificativa por participante</Txt>
        <Txt variant="tiny">{text.length} / 2.000</Txt>
      </Row>
      <Check checked>Entendo que a divisão fica congelada até a decisão.</Check>
      <Btn tone="primary" onPress={submit} disabled={busy}>
        {busy ? 'Enviando…' : 'Enviar disputa'}
      </Btn>
    </Page>
  );
}

function ResultReview() {
  const nav = useNav();
  const { session, matches } = useApp();
  const matchId = typeof nav.params.matchId === 'string' ? nav.params.matchId : matches[0]?.id;
  const [result, setResult] = useState<ResultView | null>(null);
  const [loading, setLoading] = useState(!!(session && matchId));
  useEffect(() => {
    if (!session || !matchId) {
      return;
    }
    let active = true;
    api.results
      .get(session.accessToken, matchId)
      .then((value) => {
        if (active) {
          setResult(value);
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [matchId, session]);
  if (loading) {
    return (
      <Page title="Resultado">
        <LoadingState label="Consultando o resultado." variant="cards" />
      </Page>
    );
  }
  if (!result) {
    return (
      <Page title="Resultado">
        <StateScreen
          icon="clock"
          title="Resultado indisponível"
          text="A partida ainda não tem resultado publicado ou você não participa dela."
          actions={
            <>
              <Btn tone="primary" go="matches">
                Ver partidas
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
  const votes = result.aggregate?.valid_votes ?? result.valid_votes;
  return (
    <Page title="Resultado">
      <StateScreen
        icon={result.final_result ? 'check' : 'clock'}
        title={result.final_result ? 'Resultado final' : 'Resultado em análise'}
        text={
          result.final_result
            ? `Resultado: ${result.final_result.replaceAll('_', ' ')}.`
            : 'A partida não altera a divisão até a decisão.'
        }
        actions={
          result.can_vote ? (
            <Btn
              tone="primary"
              onPress={() => nav.go('report-result', matchId ? { matchId } : undefined)}
            >
              Relatar resultado
            </Btn>
          ) : (
            <Btn tone="primary" go="matches">
              Ver partidas
            </Btn>
          )
        }
      />
      <Card>
        <Kv label="Status" value={result.state.replaceAll('_', ' ')} />
        <Kv label="Rodada" value={result.round != null ? String(result.round) : '—'} />
        <Kv label="Prazo" value={result.deadline ? shortDateTime(result.deadline) : '—'} />
        <Kv label="Votos válidos" value={votes != null ? String(votes) : 'não divulgado'} />
        <Kv
          label="Seu voto"
          value={result.my_vote ? result.my_vote.outcome.replaceAll('_', ' ') : 'não registrado'}
        />
      </Card>
      <Notice tone="blue" icon="shield">
        A divisão só muda quando o servidor fecha o resultado. Evidências e votos de terceiros não
        são expostos.
      </Notice>
      {result.dispute_id ? (
        <Btn tone="ghost" go="support">
          Falar sobre a disputa
        </Btn>
      ) : null}
    </Page>
  );
}

function matchBadge(state: string) {
  if (state === 'FINALIZED') return <Badge tone="green">FINALIZADA</Badge>;
  if (state === 'DISPUTED' || state === 'RESULT_PENDING')
    return <Badge tone="orange">EM ANÁLISE</Badge>;
  if (state === 'CANCELLED' || state === 'EXPIRED' || state === 'VOIDED')
    return <Badge>ENCERRADA</Badge>;
  return <Badge tone="lime">CONFIRMADA</Badge>;
}

function averageMatchTitle(match: MatchSummary) {
  return `${shortDateTime(match.scheduled_start_at)}`;
}

function Matches() {
  const nav = useNav();
  const { matches, loadMatches } = useApp();
  const [tab, setTab] = useState('Em andamento');
  const [now] = useState(() => Date.now());
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    loadMatches()
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
  }, [loadMatches]);
  const retry = () => {
    setLoading(true);
    setFailed(false);
    loadMatches()
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };
  useActiveInterval(() => loadMatches().catch(() => undefined), 15_000);
  const filtered = useMemo(() => {
    if (tab === 'Próximas') {
      return matches.filter((match) => new Date(match.scheduled_start_at).getTime() > now);
    }
    if (tab === 'Histórico') {
      return matches.filter((match) =>
        ['FINALIZED', 'CANCELLED', 'EXPIRED', 'VOIDED'].includes(match.state),
      );
    }
    return matches.filter((match) =>
      ['PENDING_CONFIRMATION', 'READY', 'IN_PROGRESS', 'RESULT_PENDING', 'DISPUTED'].includes(
        match.state,
      ),
    );
  }, [matches, tab, now]);
  return (
    <Page title="Partidas">
      <Seg>
        {['Em andamento', 'Próximas', 'Histórico'].map((item) => (
          <SegBtn key={item} on={tab === item} onPress={() => setTab(item)}>
            {item}
          </SegBtn>
        ))}
      </Seg>
      {loading ? (
        <LoadingState label="Buscando suas partidas." variant="cards" />
      ) : failed ? (
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar suas partidas"
          text="Verifique a conexão e tente novamente. A partida em andamento continua reservada."
          actions={
            <Btn tone="primary" onPress={retry}>
              Tentar novamente
            </Btn>
          }
        />
      ) : filtered.length > 0 ? (
        filtered.map((match) => (
          <View key={match.id} style={{ gap: 8 }}>
            <Card
              onPress={() =>
                nav.go(match.state === 'FINALIZED' ? 'match-detail' : 'lobby-detail', {
                  matchId: match.id,
                })
              }
            >
              <Row between>
                {matchBadge(match.state)}
                <Txt variant="tiny">{averageMatchTitle(match)}</Txt>
              </Row>
              <Txt variant="h2" style={{ marginTop: 7, marginBottom: 2 }}>
                Partida
              </Txt>
              <Txt variant="tiny">
                {match.state === 'RESULT_PENDING' || match.state === 'DISPUTED'
                  ? 'Resultado divergente · divisão congelada'
                  : `${match.my_status === 'confirmed' ? 'Participação confirmada' : 'Aguardando confirmação'} · ${match.participants?.length ?? 10} jogadores`}
              </Txt>
            </Card>
            {match.state === 'PENDING_CONFIRMATION' ? (
              <Btn tone="primary" small onPress={() => nav.go('lobby-t1', { matchId: match.id })}>
                Confirmar participação
              </Btn>
            ) : match.state === 'RESULT_PENDING' || match.state === 'DISPUTED' ? (
              <BtnRow>
                <Btn
                  tone="primary"
                  small
                  onPress={() => nav.go('report-result', { matchId: match.id })}
                >
                  Relatar resultado
                </Btn>
                <Btn
                  tone="ghost"
                  small
                  onPress={() => nav.go('result-review', { matchId: match.id })}
                >
                  Ver análise
                </Btn>
              </BtnRow>
            ) : match.state !== 'FINALIZED' ? (
              <BtnRow>
                <Btn
                  tone="primary"
                  small
                  onPress={() => nav.go('checkin-pre', { matchId: match.id })}
                >
                  Fazer check-in
                </Btn>
                <Btn
                  tone="ghost"
                  small
                  onPress={() => nav.go('lobby-detail', { matchId: match.id })}
                >
                  Ver lobby
                </Btn>
              </BtnRow>
            ) : null}
          </View>
        ))
      ) : (
        <EmptyState
          title={
            tab === 'Histórico'
              ? 'Nenhuma partida no histórico'
              : tab === 'Próximas'
                ? 'Nenhuma partida futura'
                : 'Nenhuma partida em andamento'
          }
          text="Quando você confirmar uma partida, ela aparece aqui."
          actions={
            <Btn tone="primary" icon="search" onPress={() => nav.go('queue', { mode: 'casual' })}>
              Buscar partida
            </Btn>
          }
        />
      )}
      <Btn tone="ghost" go="match-history">
        Ver histórico completo
      </Btn>
    </Page>
  );
}

function MatchHistory() {
  const nav = useNav();
  const { palette } = useTheme();
  const { matches } = useApp();
  const rows = matches
    .filter((match) => ['FINALIZED', 'CANCELLED', 'EXPIRED', 'VOIDED'].includes(match.state))
    .map((match) => ({
      id: match.id,
      date: dateOnly(match.scheduled_start_at),
      state: match.state,
    }));
  return (
    <Page title="Histórico">
      <ChipRow>
        <Chip on>Todas</Chip>
        <Chip>Futebol 5x5</Chip>
        <Chip>Vôlei 6x6</Chip>
        <Chip>Ranqueada</Chip>
      </ChipRow>
      {rows.length ? (
        <CardList>
          {rows.map((row, index) => (
            <ListRow
              key={row.id}
              last={index === rows.length - 1}
              onPress={() => nav.go('match-detail', { matchId: row.id })}
            >
              <View style={{ flex: 1 }}>
                <Row between>
                  <Text style={{ fontSize: 14, fontWeight: '800', color: palette.ink }}>
                    Partida
                  </Text>
                  <Txt variant="tiny">{row.date}</Txt>
                </Row>
                <Txt variant="tiny">
                  {row.state === 'FINALIZED'
                    ? 'Finalizada'
                    : row.state === 'CANCELLED'
                      ? 'Cancelada'
                      : row.state === 'EXPIRED'
                        ? 'Expirada'
                        : 'Anulada'}
                </Txt>
              </View>
              {matchBadge(row.state)}
            </ListRow>
          ))}
        </CardList>
      ) : (
        <EmptyState
          title="Nenhuma partida no histórico"
          text="Partidas concluídas, canceladas ou expiradas aparecem aqui."
          actions={
            <Btn tone="primary" icon="search" onPress={() => nav.go('queue', { mode: 'casual' })}>
              Buscar partida
            </Btn>
          }
        />
      )}
      <Notice tone="blue" icon="info">
        A divisão é recalculada na virada da temporada. O histórico permanece.
      </Notice>
    </Page>
  );
}

function MatchDetail() {
  const nav = useNav();
  const { palette } = useTheme();
  const { matches, session, ratings, primaryFormatId } = useApp();
  const matchId = typeof nav.params.matchId === 'string' ? nav.params.matchId : null;
  const [detail, setDetail] = useState<MatchSummary | null>(null);
  const match = detail ?? matches.find((item) => item.id === matchId);
  const [result, setResult] = useState<ResultView | null>(null);
  useEffect(() => {
    if (matchId && session) {
      api.results
        .get(session.accessToken, matchId)
        .then(setResult)
        .catch(() => undefined);
      api.matches
        .get(session.accessToken, matchId)
        .then(setDetail)
        .catch(() => undefined);
    }
  }, [matchId, session]);
  const rating = primaryFormatId ? ratings[primaryFormatId] : undefined;
  const participants = match?.participants ?? [];
  const participantNames = participants.length
    ? participants.slice(0, 10).map((item) => item.display_name ?? 'J')
    : [];
  return (
    <Page title="Partida concluída">
      <Card tone="ink">
        <Row between>
          <Badge tone="green">FINALIZADA</Badge>
          <Badge>RANQUEADA</Badge>
        </Row>
        <Txt
          variant="display"
          color="onInk"
          style={{ fontSize: 30, marginTop: 10, marginBottom: 4 }}
        >
          {result?.final_result === 'TEAM_1'
            ? 'Time A venceu'
            : result?.final_result === 'TEAM_2'
              ? 'Time B venceu'
              : result?.final_result === 'DRAW'
                ? 'Empate'
                : 'Resultado não registrado'}
        </Txt>
        <Txt variant="tiny" color="softOnInk">
          {match ? `Partida · ${dateOnly(match.scheduled_start_at)}` : 'Partida'}
        </Txt>
      </Card>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Card style={{ flex: 1 }} padding={12}>
          <Txt variant="label" align="center">
            Divisão
          </Txt>
          <Txt variant="h3" align="center" style={{ marginTop: 4 }}>
            {rating?.provisional ? 'Provisório' : rating ? divisionLabel(rating.division) : '—'}
          </Txt>
          <Txt variant="tiny" align="center">
            atual
          </Txt>
        </Card>
        <Card style={{ flex: 1 }} padding={12}>
          <Txt variant="label" align="center">
            Partidas
          </Txt>
          <Txt variant="num" align="center" style={{ fontSize: 24 }}>
            {rating?.matches_played ?? 0}
          </Txt>
          <Txt variant="tiny" align="center">
            ranqueadas
          </Txt>
        </Card>
      </View>
      <Card>
        <Txt variant="h3">Times</Txt>
        <Row between style={{ marginTop: 8 }}>
          <Txt variant="tiny">Time A · {participants.filter((item) => item.team === 1).length}</Txt>
          <Txt variant="tiny">Time B · {participants.filter((item) => item.team === 2).length}</Txt>
        </Row>
        <View style={{ flexDirection: 'row', marginTop: 8 }}>
          {participantNames.map((name, index) => (
            <View key={index} style={{ marginLeft: index === 0 ? 0 : -6 }}>
              <IdentityBadge size={34} identity={identityFromSeed(name)} palette={palette} />
            </View>
          ))}
        </View>
      </Card>
      <Card>
        <Kv
          label="Presença"
          value={
            participants.length
              ? `${participants.filter((item) => item.status === 'checked_in').length} de ${participants.length}`
              : '—'
          }
        />
        <Kv
          label="Duração"
          value={
            match
              ? `${Math.max(
                  0,
                  Math.round(
                    (new Date(match.scheduled_end_at).getTime() -
                      new Date(match.scheduled_start_at).getTime()) /
                      60_000,
                  ),
                )} min`
              : '—'
          }
        />
        <Kv
          label="Resultado"
          value={
            result?.final_result === 'TEAM_1'
              ? 'Time A venceu'
              : result?.final_result === 'TEAM_2'
                ? 'Time B venceu'
                : result?.final_result === 'DRAW'
                  ? 'Empate'
                  : 'Não registrado'
          }
        />
      </Card>
      <BtnRow>
        <Btn tone="ghost" go="booking-history">
          Ver recibo
        </Btn>
        <Btn tone="ghost" go="support">
          Reportar problema
        </Btn>
      </BtnRow>
    </Page>
  );
}

function BookingPayment() {
  const nav = useNav();
  const { session, bookings, loadBookings } = useApp();
  const bookingId = typeof nav.params.bookingId === 'string' ? nav.params.bookingId : null;
  const [booking, setBooking] = useState<Booking | null>(
    bookings.find((item) => item.id === bookingId) ?? null,
  );
  const [loading, setLoading] = useState(!booking);
  const [refreshing, setRefreshing] = useState(false);
  const [failed, setFailed] = useState(false);

  const reload = async () => {
    if (!session || !bookingId) {
      return null;
    }
    const result = await api.bookings.get(session.accessToken, bookingId);
    setBooking(result);
    return result;
  };

  useEffect(() => {
    let active = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reload()
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookingId, session]);

  // `participant_id` da cobrança é o id da vaga (BookingParticipant.id), não o userId.
  const ownParticipant =
    booking?.participants.find((item) => item.user_id === session?.userId) ?? null;
  const payment: BookingPaymentData | null = ownParticipant
    ? (booking?.payments.find((item) => item.participant_id === ownParticipant.id) ?? null)
    : null;
  const state = payment ? paymentState(payment.status, payment.provider_status) : 'pending';

  useEffect(() => {
    if (!session || !booking || !payment || state !== 'pending') {
      return;
    }
    let active = true;
    const timer = setInterval(() => {
      api.bookings
        .syncPayment(session.accessToken, booking.id, payment.id)
        .then(() => reload())
        .catch(() => undefined);
    }, 7000);
    return () => {
      active = false;
      clearInterval(timer);
      void active;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [booking?.id, payment?.id, session, state]);

  const refresh = async () => {
    if (!session || !booking || !payment || refreshing) {
      return;
    }
    setRefreshing(true);
    try {
      await api.bookings.syncPayment(session.accessToken, booking.id, payment.id);
      await reload();
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === 'payer_email_required') {
        nav.go('payment-email');
        return;
      }
      nav.toast('Não foi possível consultar o pagamento.');
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (state === 'paid') {
      loadBookings().catch(() => undefined);
    }
  }, [loadBookings, state]);

  if (loading) {
    return (
      <Page title="Pagamento da reserva">
        <LoadingState label="Buscando a cobrança da reserva." variant="cards" />
      </Page>
    );
  }

  if (failed || !booking) {
    return (
      <Page title="Pagamento da reserva">
        <StateScreen
          icon="wifi-off"
          title="Não foi possível carregar a reserva"
          text="Verifique a conexão e tente novamente."
          actions={
            <Btn tone="primary" back>
              Voltar
            </Btn>
          }
        />
      </Page>
    );
  }

  if (!payment) {
    return (
      <Page title="Pagamento da reserva">
        <EmptyState
          title="Nenhuma cobrança aberta"
          text="Sua vaga não tem Pix pendente. Se a quadra abrir uma cobrança, ela aparece aqui."
          actions={
            <>
              <Btn tone="primary" onPress={() => loadBookings().catch(() => undefined)}>
                Atualizar
              </Btn>
              <Btn tone="ghost" go="booking-history">
                Minhas reservas
              </Btn>
            </>
          }
        />
      </Page>
    );
  }

  return (
    <Page title="Pagamento da reserva">
      <Card>
        <Txt variant="h3">{booking.organization_venue_name}</Txt>
        <Txt variant="tiny" style={{ marginTop: 4 }}>
          {zonedShortDateTime(booking.starts_at, booking.timezone)} · {booking.venue_space_name}
        </Txt>
        <Row between style={{ marginTop: 10 }}>
          <Txt variant="tiny">Sua vaga</Txt>
          <Txt variant="num" style={{ fontSize: 28 }}>
            {cents(payment.amount_cents)}
          </Txt>
        </Row>
        {ownParticipant ? (
          <>
            <Row between style={{ marginTop: 8 }}>
              <Txt variant="tiny">Valor da quadra</Txt>
              <Txt variant="num">{cents(ownParticipant.space_charge_cents)}</Txt>
            </Row>
            <Row between style={{ marginTop: 6 }}>
              <Txt variant="tiny">Taxa de 20%</Txt>
              <Txt variant="num">{cents(ownParticipant.fee_charge_cents)}</Txt>
            </Row>
          </>
        ) : null}
      </Card>
      <PaymentPix
        payment={payment}
        purchaseStatus={payment.status}
        amountCents={payment.amount_cents}
        onRefresh={refresh}
        refreshing={refreshing}
      />
      {state === 'paid' ? (
        <>
          <Notice tone="green" icon="check">
            Pagamento confirmado. Sua vaga está garantida.
          </Notice>
          <Btn tone="primary" go="booking-history">
            Ver minhas reservas
          </Btn>
        </>
      ) : state === 'expired' || state === 'failed' ? (
        <Notice tone="orange" icon="alert">
          O Pix da reserva expirou ou não foi concluído. Fale com a quadra ou com o suporte para
          reabrir a cobrança.
        </Notice>
      ) : (
        <Notice tone="blue" icon="wallet">
          A reserva será confirmada após o pagamento. Esta tela atualiza sozinha a cada 7 segundos.
        </Notice>
      )}
    </Page>
  );
}

function BookingHistory() {
  const nav = useNav();
  const { bookings, loadBookings } = useApp();
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    loadBookings()
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [loadBookings]);
  const rows = bookings.map((booking) => ({
    id: booking.id,
    date: zonedDateOnly(booking.starts_at, booking.timezone),
    venue: booking.organization_venue_name,
    space: booking.venue_space_name,
    format: booking.format_name,
    band: booking.band_label,
    status: booking.status,
    note:
      booking.tickets_per_seat != null
        ? `${booking.tickets_per_seat} ingressos/vaga`
        : `${booking.seats} vagas`,
  }));
  const toneFor = (status: string) => {
    if (['CONFIRMED', 'COMPLETED'].includes(status)) return 'green' as const;
    if (['PAYMENT_PENDING', 'PENDING_CONFIRMATION'].includes(status)) return 'orange' as const;
    if (['DECLINED', 'EXPIRED', 'CANCELLED'].includes(status)) return 'red' as const;
    return 'default' as const;
  };
  if (loading) {
    return (
      <Page title="Reservas">
        <LoadingState label="Buscando suas reservas." variant="list" />
      </Page>
    );
  }
  if (rows.length === 0) {
    return (
      <Page title="Reservas">
        <EmptyState
          title="Nenhuma reserva ainda"
          text="Quando você solicitar uma quadra, a reserva aparece aqui com status e comprovantes."
          actions={
            <Btn tone="primary" go="venues">
              Ver quadras
            </Btn>
          }
        />
      </Page>
    );
  }
  return (
    <Page title="Reservas">
      <CardList>
        {rows.map((row, index) => (
          <ListRow
            key={row.id}
            last={index === rows.length - 1}
            onPress={() => nav.go('booking-t1t2', { bookingId: row.id })}
          >
            <View style={{ flex: 1 }}>
              <Row between>
                <Text style={{ fontSize: 14, fontWeight: '800' }}>{row.venue}</Text>
                <Txt variant="tiny">{row.date}</Txt>
              </Row>
              <Txt variant="tiny">
                {row.space}
                {row.format ? ` · ${row.format}` : ''}
              </Txt>
              <Txt variant="tiny">
                {row.band ?? 'Faixa a definir'} · {row.note}
              </Txt>
            </View>
            <Badge tone={toneFor(row.status)}>{bookingStatusLabel(row.status)}</Badge>
          </ListRow>
        ))}
      </CardList>
      <Btn tone="ghost" go="refund-tickets">
        Reembolsos
      </Btn>
    </Page>
  );
}

export const venueScreens: ScreenDef[] = [
  { id: 'venues', tab: 'jogar', render: () => <Venues /> },
  { id: 'venue-detail', tab: 'jogar', render: () => <VenueDetail /> },
  { id: 'booking-request', tab: 'jogar', render: () => <BookingRequest /> },
  { id: 'booking-t1t2', tab: 'jogar', render: () => <BookingT1T2 /> },
  { id: 'booking-confirmed', tab: 'jogar', render: () => <BookingConfirmed /> },
  { id: 'booking-payment', tab: 'jogar', render: () => <BookingPayment /> },
  { id: 'booking-declined', tab: 'jogar', render: () => <BookingDeclined /> },
  { id: 'booking-expired', tab: 'jogar', render: () => <BookingExpired /> },
  { id: 'cancel-cutoff', tab: 'jogar', hidden: true, render: () => <CancelCutoff /> },
  { id: 'cancel-closed', tab: 'jogar', hidden: true, render: () => <CancelClosed /> },
  { id: 'checkin-pre', tab: 'jogar', render: () => <CheckinPre /> },
  { id: 'checkin-presence', tab: 'jogar', render: () => <CheckinPresence /> },
  { id: 'checkin-fallback', tab: 'jogar', render: () => <CheckinFallback /> },
  { id: 'checkin-denied', tab: 'jogar', render: () => <CheckinDenied /> },
  { id: 'match-adapt', tab: 'jogar', hidden: true, render: () => <MatchAdapt /> },
  { id: 'substitutes', tab: 'jogar', render: () => <Substitutes /> },
  { id: 'substitute-called', tab: 'jogar', render: () => <SubstituteCalled /> },
  { id: 'no-show', tab: 'jogar', hidden: true, render: () => <NoShow /> },
  { id: 'report-result', tab: 'jogar', render: () => <ReportResult /> },
  { id: 'result-second-round', tab: 'jogar', hidden: true, render: () => <ResultSecondRound /> },
  { id: 'dispute', tab: 'jogar', hidden: true, render: () => <Dispute /> },
  { id: 'result-review', tab: 'jogar', render: () => <ResultReview /> },
  { id: 'matches', tab: 'partidas', render: () => <Matches /> },
  { id: 'match-history', tab: 'partidas', render: () => <MatchHistory /> },
  { id: 'match-detail', tab: 'partidas', render: () => <MatchDetail /> },
  { id: 'booking-history', tab: 'perfil', render: () => <BookingHistory /> },
];
