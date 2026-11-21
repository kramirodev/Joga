import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { EmptyState, ErrorNotice, InfoNotice, SkeletonList } from "../../components/Feedback";
import { SelectField, TextField } from "../../components/ui/Field";
import { CalendarIcon, ClockIcon, MapPinIcon } from "../../components/ui/Icons";
import { MoneyField } from "../../components/ui/MoneyField";
import { ReasonDialog } from "../../components/ui/Modal";
import { Breadcrumbs, PageHeader, SectionHeading } from "../../components/ui/PageHeader";
import { Tabs } from "../../components/ui/Tabs";
import { tabId, tabPanelId } from "../../components/ui/tab-ids";
import { useToast } from "../../components/ui/toast-context";
import { adminErrorMessage, isForbidden } from "../../lib/admin";
import { api } from "../../lib/api";
import { formatError, formatMoney, requestIdOf } from "../../lib/format";
import { queryKeys } from "../../lib/query";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import {
  moneyError,
  moneyInputFromCents,
  moneyToCents,
  normalizeWhitespace,
  positiveIntegerError,
  textError,
  timeRangeError,
} from "../../lib/validation";
import type {
  AdminPublicVenueSpace,
  AdminPublicVenueSpacePayload,
  AdminVenueAvailability,
  AdminVenueBusinessHour,
  AdminVenueAvailabilityPayload,
  AdminVenueBusinessHourPayload,
} from "../../types";
import { AdminForbiddenState } from "./AdminShared";
import { PhotosPanel } from "../venue/PhotosPanel";

const WEEKDAYS = [
  { value: 1, label: "Segunda-feira" },
  { value: 2, label: "Terça-feira" },
  { value: 3, label: "Quarta-feira" },
  { value: 4, label: "Quinta-feira" },
  { value: 5, label: "Sexta-feira" },
  { value: 6, label: "Sábado" },
  { value: 7, label: "Domingo" },
];

const INITIAL_SPACE = {
  name: "",
  sportId: "",
  formatId: "",
  price: "",
  status: "active" as "active" | "inactive",
};

const INITIAL_WINDOW = {
  weekday: 1,
  startTime: "08:00",
  endTime: "22:00",
  price: "",
  slotMinutes: "60",
};

const INITIAL_HOURS = { weekday: 1, opensAt: "06:00", closesAt: "23:00" };

type Tab = "spaces" | "schedule" | "photos";

function weekdayLabel(value: number): string {
  return WEEKDAYS.find((item) => item.value === value)?.label ?? String(value);
}

function clock(value: string): string {
  return value.slice(0, 5);
}

function venueError(error: unknown): string {
  return adminErrorMessage(error);
}

function spaceToDraft(space: AdminPublicVenueSpace) {
  return {
    name: space.name,
    sportId: space.sport_id ?? "",
    formatId: space.format_id ?? "",
    price: moneyInputFromCents(space.price_cents ?? 0),
    status: space.status,
  };
}

export function AdminVenueDetailPage() {
  const { venueId = "" } = useParams<{ venueId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const toast = useToast();

  const [spaceDraft, setSpaceDraft] = useState(INITIAL_SPACE);
  const [spaceEditing, setSpaceEditing] = useState<AdminPublicVenueSpace | null>(null);
  const [spaceReason, setSpaceReason] = useState("");
  const [spaceErrors, setSpaceErrors] = useState<Record<string, string>>({});

  const [windowDraft, setWindowDraft] = useState(INITIAL_WINDOW);
  const [windowEditing, setWindowEditing] = useState<AdminVenueAvailability | null>(null);
  const [windowReason, setWindowReason] = useState("");
  const [windowErrors, setWindowErrors] = useState<Record<string, string>>({});
  const [windowDeleteTarget, setWindowDeleteTarget] = useState<AdminVenueAvailability | null>(null);
  const [windowDeleteReason, setWindowDeleteReason] = useState("");

  const [hoursDraft, setHoursDraft] = useState(INITIAL_HOURS);
  const [hoursEditing, setHoursEditing] = useState<AdminVenueBusinessHour | null>(null);
  const [hoursReason, setHoursReason] = useState("");
  const [hoursErrors, setHoursErrors] = useState<Record<string, string>>({});
  const [hoursDeleteTarget, setHoursDeleteTarget] = useState<AdminVenueBusinessHour | null>(null);
  const [hoursDeleteReason, setHoursDeleteReason] = useState("");

  const venueQuery = useQuery({
    queryKey: queryKeys.adminVenue(venueId),
    queryFn: () => api.getAdminVenue(venueId),
    enabled: venueId.length > 0,
  });
  const venue = venueQuery.data;
  const canManage = Boolean(venue?.organization_is_platform);

  const sportsQuery = useQuery({
    queryKey: queryKeys.sports,
    queryFn: async () => (await api.listSports()).sports,
  });
  const bandsQuery = useQuery({
    queryKey: queryKeys.bands,
    queryFn: async () => (await api.listBands()).bands,
  });

  const spaces = useMemo(() => venue?.spaces ?? [], [venue?.spaces]);
  const requestedSpace = searchParams.get("space");
  const selectedSpaceId =
    requestedSpace && spaces.some((space) => space.id === requestedSpace)
      ? requestedSpace
      : (spaces[0]?.id ?? null);
  const selectedSpace = spaces.find((space) => space.id === selectedSpaceId) ?? null;

  const availabilityQuery = useQuery({
    queryKey: [...queryKeys.adminVenueAvailability(venueId), selectedSpaceId ?? ""],
    queryFn: () => api.listAdminPublicVenueAvailability(venueId, selectedSpaceId ?? ""),
    enabled: canManage && Boolean(selectedSpaceId),
  });
  const businessHoursQuery = useQuery({
    queryKey: queryKeys.adminVenueBusinessHours(venueId),
    queryFn: () => api.listAdminPublicVenueBusinessHours(venueId),
    enabled: canManage,
  });
  const photosQuery = useQuery({
    queryKey: queryKeys.photos(venue?.organization_id ?? "", venue?.id ?? ""),
    queryFn: () => api.listPhotos(venue?.organization_id ?? "", venue?.id ?? ""),
    enabled: canManage,
  });

  const requestedTab = searchParams.get("tab");
  const tab: Tab =
    canManage && (requestedTab === "schedule" || requestedTab === "photos")
      ? requestedTab
      : "spaces";

  useDocumentTitle(venue?.name ?? "Quadra");

  const sports = sportsQuery.data ?? [];
  const bands = bandsQuery.data ?? [];
  const maxPriceCents = bands.length
    ? Math.max(...bands.map((band) => band.max_price_cents))
    : undefined;
  const spacesCount = spaces.length;

  function setTab(next: Tab) {
    const params = new URLSearchParams(searchParams);
    params.set("tab", next);
    setSearchParams(params);
  }

  function selectSpace(spaceId: string) {
    const params = new URLSearchParams(searchParams);
    params.set("space", spaceId);
    params.set("tab", "schedule");
    setSearchParams(params);
  }

  function invalidateVenue() {
    void queryClient.invalidateQueries({ queryKey: queryKeys.adminVenue(venueId) });
    void queryClient.invalidateQueries({ queryKey: ["admin", "venues"] });
  }

  function invalidateAvailability() {
    void queryClient.invalidateQueries({
      queryKey: [...queryKeys.adminVenueAvailability(venueId), selectedSpaceId ?? ""],
    });
  }

  function invalidateHours() {
    void queryClient.invalidateQueries({
      queryKey: queryKeys.adminVenueBusinessHours(venueId),
    });
  }

  const saveSpaceMutation = useMutation({
    mutationFn: (payload: AdminPublicVenueSpacePayload) => {
      if (spaceEditing) {
        return api.updateAdminPublicVenueSpace(venueId, spaceEditing.id, payload);
      }
      return api.createAdminPublicVenueSpace(venueId, payload);
    },
    onSuccess: () => {
      setSpaceDraft(INITIAL_SPACE);
      setSpaceEditing(null);
      setSpaceReason("");
      setSpaceErrors({});
      toast.push({
        title: "Espaço salvo",
        description: "Modalidade, preço e status já valem para a agenda e a descoberta.",
      });
      invalidateVenue();
    },
    onError: (caught) => setSpaceErrors({ form: venueError(caught) }),
  });

  const saveWindowMutation = useMutation({
    mutationFn: (payload: AdminVenueAvailabilityPayload) => {
      if (windowEditing) {
        return api.updateAdminPublicVenueAvailability(venueId, windowEditing.id, payload);
      }
      return api.createAdminPublicVenueAvailability(venueId, payload);
    },
    onSuccess: () => {
      setWindowDraft(INITIAL_WINDOW);
      setWindowEditing(null);
      setWindowReason("");
      setWindowErrors({});
      toast.push({
        title: "Janela salva",
        description: "Reservas existentes mantêm o preço congelado.",
      });
      invalidateAvailability();
    },
    onError: (caught) => setWindowErrors({ form: venueError(caught) }),
  });

  const deleteWindowMutation = useMutation({
    mutationFn: (input: { item: AdminVenueAvailability; reason: string }) =>
      api.deleteAdminPublicVenueAvailability(
        venueId,
        input.item.id,
        input.item.space_id,
        input.reason,
      ),
    onSuccess: () => {
      setWindowDeleteTarget(null);
      setWindowDeleteReason("");
      toast.push({ title: "Janela removida" });
      invalidateAvailability();
    },
    onError: (caught) => setWindowErrors({ form: venueError(caught) }),
  });

  const saveHoursMutation = useMutation({
    mutationFn: (payload: AdminVenueBusinessHourPayload) => {
      if (hoursEditing) {
        return api.updateAdminPublicVenueBusinessHour(venueId, hoursEditing.id, payload);
      }
      return api.createAdminPublicVenueBusinessHour(venueId, payload);
    },
    onSuccess: () => {
      setHoursDraft(INITIAL_HOURS);
      setHoursEditing(null);
      setHoursReason("");
      setHoursErrors({});
      toast.push({ title: "Expediente salvo" });
      invalidateHours();
    },
    onError: (caught) => setHoursErrors({ form: venueError(caught) }),
  });

  const deleteHoursMutation = useMutation({
    mutationFn: (input: { item: AdminVenueBusinessHour; reason: string }) =>
      api.deleteAdminPublicVenueBusinessHour(venueId, input.item.id, input.reason),
    onSuccess: () => {
      setHoursDeleteTarget(null);
      setHoursDeleteReason("");
      toast.push({ title: "Expediente removido" });
      invalidateHours();
    },
    onError: (caught) => setHoursErrors({ form: venueError(caught) }),
  });

  function editSpace(space: AdminPublicVenueSpace) {
    setSpaceEditing(space);
    setSpaceDraft(spaceToDraft(space));
    setSpaceReason("");
    setSpaceErrors({});
  }

  function resetSpaceForm() {
    setSpaceEditing(null);
    setSpaceDraft(INITIAL_SPACE);
    setSpaceReason("");
    setSpaceErrors({});
  }

  function submitSpace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saveSpaceMutation.isPending) return;
    const next: Record<string, string> = {};
    const nameError = textError(spaceDraft.name, { label: "o nome do espaço", min: 1, max: 120 });
    if (nameError) next.name = nameError;
    if (!spaceDraft.sportId) next.sport = "Escolha a modalidade.";
    if (!spaceDraft.formatId) next.format = "Escolha o formato.";
    const priceError = moneyError(spaceDraft.price, {
      label: "o preço do espaço",
      minCents: 1,
      maxCents: maxPriceCents,
    });
    if (priceError) next.price = priceError;
    const reasonError = textError(spaceReason, { label: "o motivo", min: 3, max: 500 });
    if (reasonError) next.reason = reasonError;
    if (Object.keys(next).length > 0) {
      setSpaceErrors(next);
      const first = next.name
        ? "admin-space-name"
        : next.sport
          ? "admin-space-sport"
          : next.format
            ? "admin-space-format"
            : next.price
              ? "admin-space-price"
              : "admin-space-reason";
      document.getElementById(first)?.focus();
      return;
    }
    setSpaceErrors({});
    saveSpaceMutation.mutate({
      name: normalizeWhitespace(spaceDraft.name),
      sport_id: spaceDraft.sportId,
      format_id: spaceDraft.formatId,
      price_cents: moneyToCents(spaceDraft.price) ?? 0,
      status: spaceDraft.status,
      reason: spaceReason.trim(),
    });
  }

  function openWindow(item: AdminVenueAvailability) {
    setWindowEditing(item);
    setWindowDraft({
      weekday: item.weekday,
      startTime: clock(item.start_time),
      endTime: clock(item.end_time),
      price: moneyInputFromCents(item.price_cents),
      slotMinutes: String(item.slot_minutes),
    });
    setWindowReason("");
    setWindowErrors({});
  }

  function resetWindowForm() {
    setWindowEditing(null);
    setWindowDraft(INITIAL_WINDOW);
    setWindowReason("");
    setWindowErrors({});
  }

  function submitWindow(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSpace || saveWindowMutation.isPending) return;
    const next: Record<string, string> = {};
    const timeError = timeRangeError(windowDraft.startTime, windowDraft.endTime);
    if (timeError) next.time = timeError;
    const priceError = moneyError(windowDraft.price, {
      label: "o preço da janela",
      minCents: 1,
      maxCents: maxPriceCents,
    });
    if (priceError) next.price = priceError;
    const slotError = positiveIntegerError(
      Number(windowDraft.slotMinutes),
      15,
      240,
      "a duração da vaga",
    );
    if (slotError) next.slot = slotError;
    const reasonError = textError(windowReason, { label: "o motivo", min: 3, max: 500 });
    if (reasonError) next.reason = reasonError;
    if (Object.keys(next).length > 0) {
      setWindowErrors(next);
      const first = next.time
        ? "admin-window-start"
        : next.price
          ? "admin-window-price"
          : next.slot
            ? "admin-window-slot"
            : "admin-window-reason";
      document.getElementById(first)?.focus();
      return;
    }
    setWindowErrors({});
    saveWindowMutation.mutate({
      space_id: selectedSpace.id,
      weekday: windowDraft.weekday,
      start_time: `${windowDraft.startTime}:00`,
      end_time: `${windowDraft.endTime}:00`,
      price_cents: moneyToCents(windowDraft.price) ?? 0,
      slot_minutes: Number(windowDraft.slotMinutes),
      reason: windowReason.trim(),
    });
  }

  function openHours(item: AdminVenueBusinessHour) {
    setHoursEditing(item);
    setHoursDraft({
      weekday: item.weekday,
      opensAt: clock(item.opens_at),
      closesAt: clock(item.closes_at),
    });
    setHoursReason("");
    setHoursErrors({});
  }

  function resetHoursForm() {
    setHoursEditing(null);
    setHoursDraft(INITIAL_HOURS);
    setHoursReason("");
    setHoursErrors({});
  }

  function submitHours(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saveHoursMutation.isPending) return;
    const next: Record<string, string> = {};
    const timeError = timeRangeError(hoursDraft.opensAt, hoursDraft.closesAt);
    if (timeError) next.time = timeError;
    const reasonError = textError(hoursReason, { label: "o motivo", min: 3, max: 500 });
    if (reasonError) next.reason = reasonError;
    if (Object.keys(next).length > 0) {
      setHoursErrors(next);
      document.getElementById(next.time ? "admin-hours-open" : "admin-hours-reason")?.focus();
      return;
    }
    setHoursErrors({});
    saveHoursMutation.mutate({
      weekday: hoursDraft.weekday,
      opens_at: `${hoursDraft.opensAt}:00`,
      closes_at: `${hoursDraft.closesAt}:00`,
      reason: hoursReason.trim(),
    });
  }

  function confirmDeleteWindow() {
    if (!windowDeleteTarget) return;
    const validation = textError(windowDeleteReason, { label: "o motivo", min: 3, max: 500 });
    if (validation) {
      setWindowErrors({ deleteReason: validation });
      return;
    }
    setWindowErrors({});
    deleteWindowMutation.mutate({
      item: windowDeleteTarget,
      reason: windowDeleteReason.trim(),
    });
  }

  function confirmDeleteHours() {
    if (!hoursDeleteTarget) return;
    const validation = textError(hoursDeleteReason, { label: "o motivo", min: 3, max: 500 });
    if (validation) {
      setHoursErrors({ deleteReason: validation });
      return;
    }
    setHoursErrors({});
    deleteHoursMutation.mutate({
      item: hoursDeleteTarget,
      reason: hoursDeleteReason.trim(),
    });
  }

  if (venueQuery.isPending) {
    return <SkeletonList rows={5} label="Carregando quadra..." />;
  }

  if (venueQuery.error || !venue) {
    return (
      <>
        {isForbidden(venueQuery.error) ? (
          <AdminForbiddenState />
        ) : (
          <ErrorNotice
            message={venueQuery.error ? formatError(venueQuery.error) : "Quadra não encontrada."}
            requestId={requestIdOf(venueQuery.error)}
            onRetry={() => void venueQuery.refetch()}
          />
        )}
        <Link className="button button--link" to="/admin/venues">
          Voltar para quadras
        </Link>
      </>
    );
  }

  const detail = venue;
  const availability = availabilityQuery.data ?? [];
  const businessHours = businessHoursQuery.data ?? [];
  const photos = photosQuery.data?.photos ?? [];
  const canReviewPhotos = photosQuery.data?.can_review ?? false;

  return (
    <>
      <Breadcrumbs items={[{ label: "Quadras", to: "/admin/venues" }, { label: detail.name }]} />

      <PageHeader
        eyebrow="JOGA y ADMINISTRAÇÃO"
        title={detail.name}
        description={
          <>
            <span
              className={detail.status === "active" ? "badge badge--success" : "badge badge--muted"}
            >
              {detail.status === "active" ? "Ativa" : "Inativa"}
            </span>{" "}
            <span className="badge badge--info">
              {detail.organization_name || "Organização não informada"}
            </span>{" "}
            <span className="inline-meta">
              <MapPinIcon size={15} />
              {[detail.city, detail.state].filter(Boolean).join(" · ") || "Local não informado"}
              {detail.address_line ? ` · ${detail.address_line}` : ""}
            </span>
          </>
        }
        actions={
          <Link className="button button--ghost" to="/admin/venues">
            Voltar para a lista
          </Link>
        }
      />

      <Tabs
        items={[
          { id: "spaces", label: "Espaços", count: spacesCount },
          ...(canManage
            ? [
                { id: "schedule", label: "Agenda" },
                { id: "photos", label: "Fotos", count: photos.length },
              ]
            : []),
        ]}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
        idBase="admin-venue-detail"
        ariaLabel="Seções da quadra"
      />

      <div
        role="tabpanel"
        id={tabPanelId("admin-venue-detail", tab)}
        aria-labelledby={tabId("admin-venue-detail", tab)}
        tabIndex={0}
        className="tab-panel"
      >
        {tab === "spaces" ? (
          <section className={canManage ? "grid grid--sidebar" : undefined}>
            <div className="card">
              <SectionHeading
                title="Espaços da quadra"
                description="Cada espaço tem modalidade, formato, preço e status próprios."
                actions={
                  canManage && spaceEditing ? (
                    <button
                      type="button"
                      className="button button--small button--ghost"
                      onClick={resetSpaceForm}
                    >
                      Cancelar edição
                    </button>
                  ) : null
                }
              />
              {!canManage ? (
                <InfoNotice>
                  Esta quadra pertence a uma organização parceira. Os espaços, a agenda e as fotos
                  são geridos pela própria organização; a administração da plataforma apenas modera
                  a quadra.
                </InfoNotice>
              ) : null}
              {spaces.length === 0 ? (
                <EmptyState title="Nenhum espaço" icon={<CalendarIcon size={28} />}>
                  {canManage
                    ? "Crie o primeiro espaço para abrir a agenda e a descoberta."
                    : "A organização ainda não cadastrou espaços nesta quadra."}
                </EmptyState>
              ) : (
                <ul className="space-list">
                  {spaces.map((space) => {
                    const sport = sports.find((item) => item.id === space.sport_id);
                    return (
                      <li key={space.id}>
                        <div className="schedule-row">
                          <span className="schedule-row__main">
                            <strong>{space.name}</strong>
                            <small>
                              {sport?.name ?? "Modalidade não informada"} ·{" "}
                              {space.price_cents !== null
                                ? formatMoney(space.price_cents)
                                : "Preço não configurado"}
                            </small>
                          </span>
                          <div className="schedule-row__actions">
                            <span
                              className={
                                space.status === "active"
                                  ? "badge badge--success"
                                  : "badge badge--muted"
                              }
                            >
                              {space.status === "active" ? "Ativo" : "Inativo"}
                            </span>
                            {canManage ? (
                              <>
                                <button
                                  type="button"
                                  className="button button--small"
                                  onClick={() => editSpace(space)}
                                  aria-label={`Editar espaço ${space.name}`}
                                >
                                  Editar
                                </button>
                                <button
                                  type="button"
                                  className="button button--small button--ghost"
                                  onClick={() => selectSpace(space.id)}
                                >
                                  Agenda
                                </button>
                              </>
                            ) : null}
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {canManage ? (
              <div className="card card--form">
                <SectionHeading
                  title={spaceEditing ? `Editar ${spaceEditing.name}` : "Novo espaço"}
                  description="O preço precisa caber em uma faixa ativa. A alteração fica registrada na auditoria."
                  level={2}
                />
                <form className="form" onSubmit={submitSpace} noValidate>
                  {spaceErrors.form ? <ErrorNotice message={spaceErrors.form} /> : null}
                  <TextField
                    id="admin-space-name"
                    label="Nome do espaço"
                    value={spaceDraft.name}
                    onChange={(event) =>
                      setSpaceDraft((current) => ({ ...current, name: event.target.value }))
                    }
                    error={spaceErrors.name}
                    maxLength={120}
                    placeholder="Ex.: Quadra 1"
                    required
                  />
                  <SelectField
                    id="admin-space-sport"
                    label="Modalidade"
                    value={spaceDraft.sportId}
                    onChange={(event) => {
                      const sport = sports.find((item) => item.id === event.target.value);
                      setSpaceDraft((current) => ({
                        ...current,
                        sportId: event.target.value,
                        formatId: sport?.formats[0]?.id ?? "",
                      }));
                    }}
                    error={spaceErrors.sport}
                    required
                  >
                    <option value="">Selecione</option>
                    {sports.map((sport) => (
                      <option key={sport.id} value={sport.id}>
                        {sport.name}
                      </option>
                    ))}
                  </SelectField>
                  <SelectField
                    id="admin-space-format"
                    label="Formato"
                    value={spaceDraft.formatId}
                    onChange={(event) =>
                      setSpaceDraft((current) => ({ ...current, formatId: event.target.value }))
                    }
                    error={spaceErrors.format}
                    required
                  >
                    <option value="">Selecione</option>
                    {(sports.find((item) => item.id === spaceDraft.sportId)?.formats ?? []).map(
                      (format) => (
                        <option key={format.id} value={format.id}>
                          {format.name}
                        </option>
                      ),
                    )}
                  </SelectField>
                  <MoneyField
                    id="admin-space-price"
                    label="Preço do espaço"
                    value={spaceDraft.price}
                    onChange={(value) => setSpaceDraft((current) => ({ ...current, price: value }))}
                    error={spaceErrors.price}
                    hint={
                      maxPriceCents !== undefined
                        ? `Teto máximo da faixa: ${formatMoney(maxPriceCents)}.`
                        : "Faixas de preço indisponíveis no momento."
                    }
                    required
                  />
                  <SelectField
                    id="admin-space-status"
                    label="Status"
                    value={spaceDraft.status}
                    onChange={(event) =>
                      setSpaceDraft((current) => ({
                        ...current,
                        status: event.target.value as "active" | "inactive",
                      }))
                    }
                  >
                    <option value="active">Ativo</option>
                    <option value="inactive">Inativo</option>
                  </SelectField>
                  <TextField
                    id="admin-space-reason"
                    label="Motivo"
                    value={spaceReason}
                    onChange={(event) => setSpaceReason(event.target.value)}
                    error={spaceErrors.reason}
                    hint="Obrigatório. Fica na auditoria."
                    maxLength={500}
                    required
                  />
                  <button
                    type="submit"
                    className="button button--primary"
                    disabled={saveSpaceMutation.isPending}
                    aria-busy={saveSpaceMutation.isPending || undefined}
                  >
                    {saveSpaceMutation.isPending
                      ? "Salvando..."
                      : spaceEditing
                        ? "Salvar espaço"
                        : "Criar espaço"}
                  </button>
                </form>
              </div>
            ) : null}
          </section>
        ) : null}

        {tab === "schedule" ? (
          spaces.length === 0 ? (
            <div className="card">
              <EmptyState title="Crie um espaço primeiro" icon={<CalendarIcon size={28} />}>
                A agenda é definida por espaço. Volte à aba Espaços e cadastre o primeiro.
              </EmptyState>
            </div>
          ) : (
            <section className="grid grid--sidebar">
              <div className="stack">
                <div className="card">
                  <SectionHeading
                    title="Disponibilidade semanal"
                    description="Janelas recorrentes por espaço, com preço e duração da vaga."
                    actions={
                      windowEditing ? (
                        <button
                          type="button"
                          className="button button--small button--ghost"
                          onClick={resetWindowForm}
                        >
                          Cancelar edição
                        </button>
                      ) : null
                    }
                  />
                  <SelectField
                    id="admin-schedule-space"
                    label="Espaço"
                    value={selectedSpaceId ?? ""}
                    onChange={(event) => selectSpace(event.target.value)}
                  >
                    {spaces.map((space) => (
                      <option key={space.id} value={space.id}>
                        {space.name}
                      </option>
                    ))}
                  </SelectField>
                  {availabilityQuery.error ? (
                    <ErrorNotice
                      message={venueError(availabilityQuery.error)}
                      requestId={requestIdOf(availabilityQuery.error)}
                      onRetry={() => void availabilityQuery.refetch()}
                    />
                  ) : availabilityQuery.isPending ? (
                    <SkeletonList rows={2} label="Carregando agenda..." />
                  ) : availability.length === 0 ? (
                    <EmptyState title="Nenhuma janela" icon={<ClockIcon size={26} />}>
                      Defina os horários em que este espaço aceita reservas.
                    </EmptyState>
                  ) : (
                    <ul className="schedule-list">
                      {availability.map((item) => (
                        <li key={item.id} className="schedule-row">
                          <span className="schedule-row__main">
                            <strong>{weekdayLabel(item.weekday)}</strong>
                            <small>
                              {clock(item.start_time)}–{clock(item.end_time)} ·{" "}
                              {formatMoney(item.price_cents)} · {item.slot_minutes} min
                            </small>
                          </span>
                          <div className="schedule-row__actions">
                            <button
                              type="button"
                              className="button button--small"
                              onClick={() => openWindow(item)}
                            >
                              Editar
                            </button>
                            <button
                              type="button"
                              className="button button--small button--danger"
                              onClick={() => {
                                setWindowErrors({});
                                setWindowDeleteReason("");
                                setWindowDeleteTarget(item);
                              }}
                            >
                              Remover
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="card">
                  <SectionHeading
                    title="Expediente"
                    description="Horário de funcionamento da quadra. O prazo de resposta conta dentro dele."
                    actions={
                      hoursEditing ? (
                        <button
                          type="button"
                          className="button button--small button--ghost"
                          onClick={resetHoursForm}
                        >
                          Cancelar edição
                        </button>
                      ) : null
                    }
                  />
                  {businessHoursQuery.error ? (
                    <ErrorNotice
                      message={venueError(businessHoursQuery.error)}
                      requestId={requestIdOf(businessHoursQuery.error)}
                      onRetry={() => void businessHoursQuery.refetch()}
                    />
                  ) : businessHours.length === 0 ? (
                    <EmptyState title="Nenhum expediente" icon={<ClockIcon size={26} />}>
                      Cadastre os dias e horários de funcionamento.
                    </EmptyState>
                  ) : (
                    <ul className="schedule-list">
                      {businessHours.map((item) => (
                        <li key={item.id} className="schedule-row">
                          <span className="schedule-row__main">
                            <strong>{weekdayLabel(item.weekday)}</strong>
                            <small>
                              {clock(item.opens_at)}–{clock(item.closes_at)}
                            </small>
                          </span>
                          <div className="schedule-row__actions">
                            <button
                              type="button"
                              className="button button--small"
                              onClick={() => openHours(item)}
                            >
                              Editar
                            </button>
                            <button
                              type="button"
                              className="button button--small button--danger"
                              onClick={() => {
                                setHoursErrors({});
                                setHoursDeleteReason("");
                                setHoursDeleteTarget(item);
                              }}
                            >
                              Remover
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              <div className="stack">
                <div className="card card--form">
                  <SectionHeading
                    title={windowEditing ? "Editar janela" : "Nova janela"}
                    description={`Espaço selecionado: ${selectedSpace?.name ?? "—"}.`}
                    level={2}
                  />
                  <form className="form" onSubmit={submitWindow} noValidate>
                    {windowErrors.form ? <ErrorNotice message={windowErrors.form} /> : null}
                    <div className="form-row">
                      <SelectField
                        id="admin-window-weekday"
                        label="Dia"
                        value={windowDraft.weekday}
                        onChange={(event) =>
                          setWindowDraft((current) => ({
                            ...current,
                            weekday: Number(event.target.value),
                          }))
                        }
                      >
                        {WEEKDAYS.map((day) => (
                          <option key={day.value} value={day.value}>
                            {day.label}
                          </option>
                        ))}
                      </SelectField>
                      <TextField
                        id="admin-window-slot"
                        label="Duração da vaga (min)"
                        type="number"
                        min={15}
                        max={240}
                        step={5}
                        value={windowDraft.slotMinutes}
                        onChange={(event) =>
                          setWindowDraft((current) => ({
                            ...current,
                            slotMinutes: event.target.value,
                          }))
                        }
                        error={windowErrors.slot}
                        required
                      />
                    </div>
                    <div className="form-row">
                      <TextField
                        id="admin-window-start"
                        label="Início"
                        type="time"
                        value={windowDraft.startTime}
                        onChange={(event) =>
                          setWindowDraft((current) => ({
                            ...current,
                            startTime: event.target.value,
                          }))
                        }
                        error={windowErrors.time}
                        required
                      />
                      <TextField
                        id="admin-window-end"
                        label="Fim"
                        type="time"
                        value={windowDraft.endTime}
                        onChange={(event) =>
                          setWindowDraft((current) => ({
                            ...current,
                            endTime: event.target.value,
                          }))
                        }
                        error={windowErrors.time}
                        required
                      />
                    </div>
                    <MoneyField
                      id="admin-window-price"
                      label="Preço da janela"
                      value={windowDraft.price}
                      onChange={(value) =>
                        setWindowDraft((current) => ({ ...current, price: value }))
                      }
                      error={windowErrors.price}
                      hint="O valor precisa caber em uma faixa ativa."
                      required
                    />
                    <TextField
                      id="admin-window-reason"
                      label="Motivo"
                      value={windowReason}
                      onChange={(event) => setWindowReason(event.target.value)}
                      error={windowErrors.reason}
                      hint="Obrigatório. Fica na auditoria."
                      maxLength={500}
                      required
                    />
                    <button
                      type="submit"
                      className="button button--primary"
                      disabled={saveWindowMutation.isPending || !selectedSpace}
                      aria-busy={saveWindowMutation.isPending || undefined}
                    >
                      {saveWindowMutation.isPending
                        ? "Salvando..."
                        : windowEditing
                          ? "Salvar janela"
                          : "Adicionar janela"}
                    </button>
                  </form>
                </div>

                <div className="card card--form">
                  <SectionHeading
                    title={hoursEditing ? "Editar expediente" : "Novo expediente"}
                    description="Dias e horários em que a quadra responde solicitações."
                    level={2}
                  />
                  <form className="form" onSubmit={submitHours} noValidate>
                    {hoursErrors.form ? <ErrorNotice message={hoursErrors.form} /> : null}
                    <SelectField
                      id="admin-hours-weekday"
                      label="Dia"
                      value={hoursDraft.weekday}
                      onChange={(event) =>
                        setHoursDraft((current) => ({
                          ...current,
                          weekday: Number(event.target.value),
                        }))
                      }
                    >
                      {WEEKDAYS.map((day) => (
                        <option key={day.value} value={day.value}>
                          {day.label}
                        </option>
                      ))}
                    </SelectField>
                    <div className="form-row">
                      <TextField
                        id="admin-hours-open"
                        label="Abre"
                        type="time"
                        value={hoursDraft.opensAt}
                        onChange={(event) =>
                          setHoursDraft((current) => ({
                            ...current,
                            opensAt: event.target.value,
                          }))
                        }
                        error={hoursErrors.time}
                        required
                      />
                      <TextField
                        id="admin-hours-close"
                        label="Fecha"
                        type="time"
                        value={hoursDraft.closesAt}
                        onChange={(event) =>
                          setHoursDraft((current) => ({
                            ...current,
                            closesAt: event.target.value,
                          }))
                        }
                        required
                      />
                    </div>
                    <TextField
                      id="admin-hours-reason"
                      label="Motivo"
                      value={hoursReason}
                      onChange={(event) => setHoursReason(event.target.value)}
                      error={hoursErrors.reason}
                      hint="Obrigatório. Fica na auditoria."
                      maxLength={500}
                      required
                    />
                    <button
                      type="submit"
                      className="button button--primary"
                      disabled={saveHoursMutation.isPending}
                      aria-busy={saveHoursMutation.isPending || undefined}
                    >
                      {saveHoursMutation.isPending
                        ? "Salvando..."
                        : hoursEditing
                          ? "Salvar expediente"
                          : "Adicionar expediente"}
                    </button>
                  </form>
                </div>
              </div>
            </section>
          )
        ) : null}

        {tab === "photos" && detail.organization_is_platform ? (
          photosQuery.error ? (
            <ErrorNotice
              message={venueError(photosQuery.error)}
              requestId={requestIdOf(photosQuery.error)}
              onRetry={() => void photosQuery.refetch()}
            />
          ) : photosQuery.isPending ? (
            <SkeletonList rows={3} label="Carregando fotos..." />
          ) : (
            <PhotosPanel
              organization={{ id: detail.organization_id }}
              venue={{ id: detail.id }}
              spaces={spaces.map((space) => ({ id: space.id, name: space.name }))}
              photos={photos}
              canReview={canReviewPhotos}
              loading={photosQuery.isPending}
              error={photosQuery.error}
              onRetry={() => void photosQuery.refetch()}
            />
          )
        ) : null}
      </div>

      <ReasonDialog
        open={Boolean(windowDeleteTarget)}
        title="Remover janela"
        description="A janela deixa de aceitar novas reservas. Reservas já confirmadas não são canceladas."
        label="Motivo"
        value={windowDeleteReason}
        onChange={(value) => {
          setWindowDeleteReason(value);
          if (windowErrors.deleteReason) {
            setWindowErrors((current) => ({ ...current, deleteReason: "" }));
          }
        }}
        error={windowErrors.deleteReason}
        placeholder="Descreva o que motivou a remoção"
        minLength={3}
        maxLength={500}
        confirmLabel="Remover janela"
        tone="danger"
        busy={deleteWindowMutation.isPending}
        onConfirm={confirmDeleteWindow}
        onClose={() => {
          if (deleteWindowMutation.isPending) return;
          setWindowDeleteTarget(null);
          setWindowDeleteReason("");
        }}
      >
        {deleteWindowMutation.error ? (
          <ErrorNotice message={venueError(deleteWindowMutation.error)} />
        ) : null}
        {windowDeleteTarget ? (
          <p className="hint">
            {weekdayLabel(windowDeleteTarget.weekday)} · {clock(windowDeleteTarget.start_time)}–
            {clock(windowDeleteTarget.end_time)}
          </p>
        ) : null}
      </ReasonDialog>

      <ReasonDialog
        open={Boolean(hoursDeleteTarget)}
        title="Remover expediente"
        description="O horário deixa de contar para o prazo de resposta da quadra."
        label="Motivo"
        value={hoursDeleteReason}
        onChange={(value) => {
          setHoursDeleteReason(value);
          if (hoursErrors.deleteReason) {
            setHoursErrors((current) => ({ ...current, deleteReason: "" }));
          }
        }}
        error={hoursErrors.deleteReason}
        placeholder="Descreva o que motivou a remoção"
        minLength={3}
        maxLength={500}
        confirmLabel="Remover expediente"
        tone="danger"
        busy={deleteHoursMutation.isPending}
        onConfirm={confirmDeleteHours}
        onClose={() => {
          if (deleteHoursMutation.isPending) return;
          setHoursDeleteTarget(null);
          setHoursDeleteReason("");
        }}
      >
        {deleteHoursMutation.error ? (
          <ErrorNotice message={venueError(deleteHoursMutation.error)} />
        ) : null}
      </ReasonDialog>
    </>
  );
}
