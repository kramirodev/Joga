import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";

import { EmptyState, ErrorNotice, InfoNotice, SkeletonList } from "../../components/Feedback";
import { CheckboxField, SelectField, TextField } from "../../components/ui/Field";
import { MoneyField } from "../../components/ui/MoneyField";
import { CalendarIcon, ClockIcon, PlusIcon } from "../../components/ui/Icons";
import { ConfirmDialog, Modal } from "../../components/ui/Modal";
import { SectionHeading } from "../../components/ui/PageHeader";
import { useToast } from "../../components/ui/toast-context";
import { api } from "../../lib/api";
import { formatDateRange, formatError, formatMoney, requestIdOf } from "../../lib/format";
import { queryKeys } from "../../lib/query";
import {
  dateRangeError,
  moneyError,
  moneyInputFromCents,
  moneyToCents,
  normalizeWhitespace,
  positiveIntegerError,
  textError,
  timeRangeError,
} from "../../lib/validation";
import type {
  BusinessHour,
  Organization,
  PricingBand,
  SportCatalogItem,
  Venue,
  VenueAvailability,
  VenueBlackout,
  VenueClosure,
  VenueSpace,
} from "../../types";

const WEEKDAYS = [
  { value: 1, label: "Segunda-feira" },
  { value: 2, label: "Terça-feira" },
  { value: 3, label: "Quarta-feira" },
  { value: 4, label: "Quinta-feira" },
  { value: 5, label: "Sexta-feira" },
  { value: 6, label: "Sábado" },
  { value: 7, label: "Domingo" },
];

function weekdayLabel(value: number): string {
  return WEEKDAYS.find((item) => item.value === value)?.label ?? String(value);
}

function clock(value: string): string {
  return value.slice(0, 5);
}

function bandForPrice(bands: PricingBand[], cents: number | null): PricingBand | null {
  if (cents === null || cents <= 0) return null;
  return (
    bands
      .filter((band) => band.max_price_cents >= cents)
      .sort((a, b) => a.max_price_cents - b.max_price_cents)[0] ?? null
  );
}

const INITIAL_SPACE = { name: "", description: "", covered: false };
const INITIAL_WINDOW = {
  weekday: 1,
  startTime: "18:00",
  endTime: "22:00",
  price: "120,00",
  slotMinutes: "60",
};
const INITIAL_HOURS = { weekday: 1, opensAt: "09:00", closesAt: "18:00" };
const INITIAL_CLOSURE = { start: "", end: "", reason: "" };
const INITIAL_BLACKOUT = { start: "", end: "", reason: "", reference: "" };

export function SpacesPanel({
  organization,
  venue,
  spaces,
  sports,
  bands,
  selectedSpaceId,
  onSelectSpace,
}: {
  organization: Organization;
  venue: Venue;
  spaces: VenueSpace[];
  sports: SportCatalogItem[];
  bands: PricingBand[];
  selectedSpaceId: string | null;
  onSelectSpace: (spaceId: string) => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const selectedSpace = spaces.find((space) => space.id === selectedSpaceId) ?? null;

  const [spaceForm, setSpaceForm] = useState(INITIAL_SPACE);
  const [spaceErrors, setSpaceErrors] = useState<Record<string, string>>({});
  const [sportDraft, setSportDraft] = useState<{ spaceId: string; ids: string[] } | null>(null);

  const [windowForm, setWindowForm] = useState(INITIAL_WINDOW);
  const [windowErrors, setWindowErrors] = useState<Record<string, string>>({});

  const [hoursForm, setHoursForm] = useState(INITIAL_HOURS);
  const [hoursErrors, setHoursErrors] = useState<Record<string, string>>({});

  const [closureForm, setClosureForm] = useState(INITIAL_CLOSURE);
  const [closureErrors, setClosureErrors] = useState<Record<string, string>>({});

  const [blackoutForm, setBlackoutForm] = useState(INITIAL_BLACKOUT);
  const [blackoutErrors, setBlackoutErrors] = useState<Record<string, string>>({});

  const [priceTarget, setPriceTarget] = useState<VenueAvailability | null>(null);
  const [priceDraft, setPriceDraft] = useState("");
  const [priceError, setPriceError] = useState<string | null>(null);

  const [deleteSpaceTarget, setDeleteSpaceTarget] = useState<VenueSpace | null>(null);
  const [deleteWindowTarget, setDeleteWindowTarget] = useState<VenueAvailability | null>(null);
  const [deleteHourTarget, setDeleteHourTarget] = useState<BusinessHour | null>(null);
  const [deleteClosureTarget, setDeleteClosureTarget] = useState<VenueClosure | null>(null);
  const [deleteBlackoutTarget, setDeleteBlackoutTarget] = useState<VenueBlackout | null>(null);

  const [actionError, setActionError] = useState<unknown>(null);

  const availabilityQuery = useQuery({
    queryKey: queryKeys.availability(organization.id, venue.id, selectedSpaceId ?? ""),
    queryFn: async () =>
      (await api.listAvailability(organization.id, venue.id, selectedSpaceId ?? "")).availability,
    enabled: Boolean(selectedSpaceId),
  });
  const blackoutsQuery = useQuery({
    queryKey: queryKeys.blackouts(organization.id, venue.id, selectedSpaceId ?? ""),
    queryFn: async () =>
      (await api.listBlackouts(organization.id, venue.id, selectedSpaceId ?? "")).blackouts,
    enabled: Boolean(selectedSpaceId),
  });
  const businessHoursQuery = useQuery({
    queryKey: queryKeys.businessHours(organization.id, venue.id),
    queryFn: async () => (await api.listBusinessHours(organization.id, venue.id)).business_hours,
  });
  const closuresQuery = useQuery({
    queryKey: queryKeys.closures(organization.id, venue.id),
    queryFn: async () => (await api.listClosures(organization.id, venue.id)).closures,
  });

  const availability = useMemo(
    () =>
      [...(availabilityQuery.data ?? [])].sort(
        (a, b) => a.weekday - b.weekday || a.start_time.localeCompare(b.start_time),
      ),
    [availabilityQuery.data],
  );
  const blackouts = useMemo(
    () => [...(blackoutsQuery.data ?? [])].sort((a, b) => a.starts_at.localeCompare(b.starts_at)),
    [blackoutsQuery.data],
  );
  const businessHours = useMemo(
    () =>
      [...(businessHoursQuery.data ?? [])].sort(
        (a, b) => a.weekday - b.weekday || a.opens_at.localeCompare(b.opens_at),
      ),
    [businessHoursQuery.data],
  );
  const closures = useMemo(
    () => [...(closuresQuery.data ?? [])].sort((a, b) => a.starts_at.localeCompare(b.starts_at)),
    [closuresQuery.data],
  );

  const sportIds =
    sportDraft && sportDraft.spaceId === selectedSpace?.id
      ? sportDraft.ids
      : (selectedSpace?.sports.map((sport) => sport.id) ?? []);
  const originalSportIds = selectedSpace?.sports.map((sport) => sport.id) ?? [];
  const sportsDirty = [...sportIds].sort().join("|") !== [...originalSportIds].sort().join("|");

  const maxPriceCents = bands.length
    ? Math.max(...bands.map((band) => band.max_price_cents))
    : undefined;
  const windowPriceCents = moneyToCents(windowForm.price);
  const previewBand = bandForPrice(bands, windowPriceCents);

  function invalidateSpaces() {
    void queryClient.invalidateQueries({ queryKey: queryKeys.spaces(organization.id, venue.id) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.audit(organization.id) });
  }

  function invalidateSchedule() {
    if (selectedSpaceId) {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.availability(organization.id, venue.id, selectedSpaceId),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.blackouts(organization.id, venue.id, selectedSpaceId),
      });
    }
    void queryClient.invalidateQueries({ queryKey: queryKeys.audit(organization.id) });
  }

  function invalidateHours() {
    void queryClient.invalidateQueries({
      queryKey: queryKeys.businessHours(organization.id, venue.id),
    });
    void queryClient.invalidateQueries({
      queryKey: queryKeys.closures(organization.id, venue.id),
    });
    void queryClient.invalidateQueries({ queryKey: queryKeys.audit(organization.id) });
  }

  function fail(caught: unknown) {
    setActionError(caught);
  }

  const createSpaceMutation = useMutation({
    mutationFn: () =>
      api.createSpace(organization.id, venue.id, {
        name: normalizeWhitespace(spaceForm.name),
        description: spaceForm.description.trim()
          ? normalizeWhitespace(spaceForm.description)
          : null,
        is_covered: spaceForm.covered,
      }),
    onSuccess: (space) => {
      setSpaceForm(INITIAL_SPACE);
      setSpaceErrors({});
      setActionError(null);
      onSelectSpace(space.id);
      toast.push({
        title: "Quadra criada",
        description: "Agora defina modalidades, janelas de agenda e expediente.",
      });
      invalidateSpaces();
    },
    onError: fail,
  });

  const updateSpaceMutation = useMutation({
    mutationFn: (space: VenueSpace) =>
      api.updateSpace(organization.id, venue.id, space.id, { is_covered: !space.is_covered }),
    onSuccess: () => {
      toast.push({
        title: "Cobertura atualizada",
        description: "O atributo já aparece na descoberta.",
      });
      invalidateSpaces();
    },
    onError: fail,
  });

  const deleteSpaceMutation = useMutation({
    mutationFn: (space: VenueSpace) => api.deleteSpace(organization.id, venue.id, space.id),
    onSuccess: () => {
      setDeleteSpaceTarget(null);
      toast.push({
        title: "Quadra removida",
        description: "A agenda vinculada também foi removida.",
      });
      invalidateSpaces();
    },
    onError: fail,
  });

  const sportsMutation = useMutation({
    mutationFn: () =>
      api.replaceSpaceSports(organization.id, venue.id, selectedSpace?.id ?? "", sportIds),
    onSuccess: () => {
      setSportDraft(null);
      toast.push({ title: "Modalidades atualizadas" });
      invalidateSpaces();
    },
    onError: fail,
  });

  const availabilityMutation = useMutation({
    mutationFn: () =>
      api.createAvailability(organization.id, venue.id, selectedSpace?.id ?? "", {
        weekday: windowForm.weekday,
        start_time: `${windowForm.startTime}:00`,
        end_time: `${windowForm.endTime}:00`,
        price_cents: moneyToCents(windowForm.price) ?? 0,
        slot_minutes: Number(windowForm.slotMinutes),
      }),
    onSuccess: () => {
      setWindowErrors({});
      setActionError(null);
      toast.push({ title: "Janela de agenda criada" });
      invalidateSchedule();
    },
    onError: fail,
  });

  const updatePriceMutation = useMutation({
    mutationFn: ({ item, cents }: { item: VenueAvailability; cents: number }) =>
      api.updateAvailability(organization.id, venue.id, item.space_id, item.id, {
        price_cents: cents,
      }),
    onSuccess: () => {
      setPriceTarget(null);
      toast.push({
        title: "Preço atualizado",
        description: "Reservas existentes mantêm o valor congelado.",
      });
      invalidateSchedule();
    },
    onError: fail,
  });

  const deleteAvailabilityMutation = useMutation({
    mutationFn: (item: VenueAvailability) =>
      api.deleteAvailability(organization.id, venue.id, item.space_id, item.id),
    onSuccess: () => {
      setDeleteWindowTarget(null);
      toast.push({ title: "Janela removida" });
      invalidateSchedule();
    },
    onError: fail,
  });

  const businessHourMutation = useMutation({
    mutationFn: () =>
      api.createBusinessHour(organization.id, venue.id, {
        weekday: hoursForm.weekday,
        opens_at: `${hoursForm.opensAt}:00`,
        closes_at: `${hoursForm.closesAt}:00`,
      }),
    onSuccess: () => {
      setHoursErrors({});
      toast.push({
        title: "Expediente adicionado",
        description: "O prazo T2 passa a contar dentro deste horário.",
      });
      invalidateHours();
    },
    onError: fail,
  });

  const deleteBusinessHourMutation = useMutation({
    mutationFn: (id: string) => api.deleteBusinessHour(organization.id, venue.id, id),
    onSuccess: () => {
      setDeleteHourTarget(null);
      toast.push({ title: "Expediente removido" });
      invalidateHours();
    },
    onError: fail,
  });

  const closureMutation = useMutation({
    mutationFn: () =>
      api.createClosure(organization.id, venue.id, {
        starts_at: new Date(closureForm.start).toISOString(),
        ends_at: new Date(closureForm.end).toISOString(),
        reason: normalizeWhitespace(closureForm.reason),
      }),
    onSuccess: () => {
      setClosureForm(INITIAL_CLOSURE);
      setClosureErrors({});
      toast.push({ title: "Fechamento adicionado" });
      invalidateHours();
    },
    onError: fail,
  });

  const deleteClosureMutation = useMutation({
    mutationFn: (id: string) => api.deleteClosure(organization.id, venue.id, id),
    onSuccess: () => {
      setDeleteClosureTarget(null);
      toast.push({ title: "Fechamento removido" });
      invalidateHours();
    },
    onError: fail,
  });

  const blackoutMutation = useMutation({
    mutationFn: () =>
      api.createBlackout(organization.id, venue.id, selectedSpace?.id ?? "", {
        starts_at: new Date(blackoutForm.start).toISOString(),
        ends_at: new Date(blackoutForm.end).toISOString(),
        reason: normalizeWhitespace(blackoutForm.reason),
        external_reference: blackoutForm.reference.trim()
          ? normalizeWhitespace(blackoutForm.reference)
          : null,
      }),
    onSuccess: () => {
      setBlackoutForm(INITIAL_BLACKOUT);
      setBlackoutErrors({});
      toast.push({ title: "Bloqueio criado" });
      invalidateSchedule();
    },
    onError: fail,
  });

  const deleteBlackoutMutation = useMutation({
    mutationFn: (item: VenueBlackout) =>
      api.deleteBlackout(organization.id, venue.id, item.space_id, item.id),
    onSuccess: () => {
      setDeleteBlackoutTarget(null);
      toast.push({ title: "Bloqueio removido" });
      invalidateSchedule();
    },
    onError: fail,
  });

  function createSpace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: Record<string, string> = {};
    const nameError = textError(spaceForm.name, {
      label: "o nome da quadra",
      min: 1,
      max: 120,
    });
    if (nameError) next.name = nameError;
    if (spaceForm.description.trim().length > 280) {
      next.description = "A descrição deve ter no máximo 280 caracteres.";
    }
    if (Object.keys(next).length > 0) {
      setSpaceErrors(next);
      document.getElementById(next.name ? "space-name" : "space-description")?.focus();
      return;
    }
    createSpaceMutation.mutate();
  }

  function createWindow(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSpace) return;
    const next: Record<string, string> = {};
    const timeError = timeRangeError(windowForm.startTime, windowForm.endTime);
    if (timeError) next.time = timeError;
    const priceError = moneyError(windowForm.price, {
      label: "o preço",
      maxCents: maxPriceCents,
    });
    if (priceError) next.price = priceError;
    const slotError = positiveIntegerError(
      Number(windowForm.slotMinutes),
      15,
      240,
      "a duração da vaga",
    );
    if (slotError) next.slot = slotError;
    if (Object.keys(next).length > 0) {
      setWindowErrors(next);
      const first = next.time ? "window-start" : next.price ? "window-price" : "window-slot";
      document.getElementById(first)?.focus();
      return;
    }
    setWindowErrors({});
    setActionError(null);
    availabilityMutation.mutate();
  }

  function createHours(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const timeError = timeRangeError(hoursForm.opensAt, hoursForm.closesAt);
    if (timeError) {
      setHoursErrors({ time: timeError });
      document.getElementById("hours-open")?.focus();
      return;
    }
    setHoursErrors({});
    businessHourMutation.mutate();
  }

  function createClosure(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: Record<string, string> = {};
    const rangeError = dateRangeError(closureForm.start, closureForm.end, {
      requireFuture: true,
    });
    if (rangeError) next.range = rangeError;
    const reasonError = textError(closureForm.reason, {
      label: "o motivo",
      max: 200,
    });
    if (reasonError) next.reason = reasonError;
    if (Object.keys(next).length > 0) {
      setClosureErrors(next);
      document.getElementById(next.range ? "closure-start" : "closure-reason")?.focus();
      return;
    }
    setClosureErrors({});
    closureMutation.mutate();
  }

  function createBlackout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSpace) return;
    const next: Record<string, string> = {};
    const rangeError = dateRangeError(blackoutForm.start, blackoutForm.end, {
      requireFuture: true,
    });
    if (rangeError) next.range = rangeError;
    const reasonError = textError(blackoutForm.reason, {
      label: "o motivo",
      max: 200,
    });
    if (reasonError) next.reason = reasonError;
    if (blackoutForm.reference.trim().length > 120) {
      next.reference = "A referência deve ter no máximo 120 caracteres.";
    }
    if (Object.keys(next).length > 0) {
      setBlackoutErrors(next);
      const first = next.range
        ? "blackout-start"
        : next.reason
          ? "blackout-reason"
          : "blackout-reference";
      document.getElementById(first)?.focus();
      return;
    }
    setBlackoutErrors({});
    blackoutMutation.mutate();
  }

  function openPrice(item: VenueAvailability) {
    setActionError(null);
    setPriceTarget(item);
    setPriceDraft(moneyInputFromCents(item.price_cents));
    setPriceError(null);
  }

  function savePrice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!priceTarget) return;
    const cents = moneyToCents(priceDraft);
    const validation = moneyError(priceDraft, { label: "o preço", maxCents: maxPriceCents });
    if (validation || cents === null) {
      setPriceError(validation ?? "Informe o preço.");
      document.getElementById("price-value")?.focus();
      return;
    }
    setPriceError(null);
    updatePriceMutation.mutate({ item: priceTarget, cents });
  }

  const actionFailed = actionError ? (
    <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
  ) : null;

  return (
    <section className="grid grid--sidebar">
      <div className="stack">
        <div className="card">
          <SectionHeading
            title="Quadras e espaços"
            description="Cada quadra tem modalidades, agenda e preço próprios."
          />
          {spaces.length === 0 ? (
            <EmptyState
              title="Nenhuma quadra cadastrada"
              icon={<CalendarIcon size={28} />}
              action={
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() => document.getElementById("space-name")?.focus()}
                >
                  <PlusIcon size={16} />
                  Cadastrar primeira quadra
                </button>
              }
            >
              Cadastre a primeira quadra para abrir a agenda e receber reservas.
            </EmptyState>
          ) : (
            <ul className="space-list">
              {spaces.map((space) => (
                <li key={space.id}>
                  <button
                    type="button"
                    className={
                      space.id === selectedSpaceId ? "space-card space-card--active" : "space-card"
                    }
                    onClick={() => onSelectSpace(space.id)}
                    aria-pressed={space.id === selectedSpaceId}
                  >
                    <span className="space-card__main">
                      <strong>{space.name}</strong>
                      <small>
                        {space.sports.map((sport) => sport.name).join(" · ") || "Sem modalidade"}
                      </small>
                    </span>
                    <span className="space-card__badges">
                      <span className="badge badge--muted">
                        {space.status === "active" ? "Ativa" : "Inativa"}
                      </span>
                      {space.is_covered ? (
                        <span className="badge badge--success">Coberta</span>
                      ) : null}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <form className="form form--inline" onSubmit={createSpace} noValidate>
            <h3>Nova quadra</h3>
            <TextField
              id="space-name"
              label="Nome da quadra"
              value={spaceForm.name}
              onChange={(event) => {
                setSpaceForm((current) => ({ ...current, name: event.target.value }));
                if (spaceErrors.name) setSpaceErrors((current) => ({ ...current, name: "" }));
              }}
              error={spaceErrors.name}
              hint="De 1 a 120 caracteres. Ex.: Quadra 1."
              maxLength={120}
              placeholder="Ex.: Quadra 1"
              required
            />
            <TextField
              id="space-description"
              label="Descrição"
              value={spaceForm.description}
              onChange={(event) => {
                setSpaceForm((current) => ({ ...current, description: event.target.value }));
                if (spaceErrors.description) {
                  setSpaceErrors((current) => ({ ...current, description: "" }));
                }
              }}
              error={spaceErrors.description}
              hint="Opcional. Piso, iluminação e outras características."
              maxLength={280}
              placeholder="Piso sintético, iluminação LED..."
            />
            <CheckboxField
              id="space-covered"
              label="Quadra coberta"
              hint="A cobertura aparece como atributo visível no JOGA."
              checked={spaceForm.covered}
              onChange={(checked) => setSpaceForm((current) => ({ ...current, covered: checked }))}
            />
            <button
              type="submit"
              className="button button--primary"
              disabled={createSpaceMutation.isPending}
              aria-busy={createSpaceMutation.isPending || undefined}
            >
              {createSpaceMutation.isPending ? "Cadastrando..." : "Cadastrar quadra"}
            </button>
            {actionFailed}
          </form>
        </div>
      </div>

      <div className="stack">
        {!selectedSpace ? (
          <div className="card">
            <EmptyState title="Selecione uma quadra" icon={<CalendarIcon size={28} />}>
              Escolha uma quadra para editar modalidades, agenda, expediente e bloqueios.
            </EmptyState>
          </div>
        ) : (
          <>
            <div className="card">
              <SectionHeading
                title={selectedSpace.name}
                description={selectedSpace.description || "Sem descrição."}
                actions={
                  <>
                    <button
                      type="button"
                      className="button button--small"
                      disabled={updateSpaceMutation.isPending}
                      onClick={() => updateSpaceMutation.mutate(selectedSpace)}
                    >
                      {selectedSpace.is_covered ? "Marcar descoberta" : "Marcar coberta"}
                    </button>
                    <button
                      type="button"
                      className="button button--small button--danger"
                      onClick={() => {
                        setActionError(null);
                        setDeleteSpaceTarget(selectedSpace);
                      }}
                    >
                      Remover quadra
                    </button>
                  </>
                }
              />

              <fieldset className="fieldset">
                <legend>Modalidades</legend>
                <p className="field__hint">
                  Selecione as modalidades aceitas nesta quadra. Elas aparecem na descoberta do
                  aplicativo.
                </p>
                <div className="checkbox-grid">
                  {sports.map((sport) => (
                    <label key={sport.id} className="checkbox">
                      <input
                        type="checkbox"
                        checked={sportIds.includes(sport.id)}
                        onChange={(event) => {
                          const next = event.target.checked
                            ? [...sportIds, sport.id]
                            : sportIds.filter((id) => id !== sport.id);
                          setSportDraft({ spaceId: selectedSpace.id, ids: next });
                        }}
                      />
                      <span>{sport.name}</span>
                    </label>
                  ))}
                </div>
                <div className="form-actions">
                  <button
                    type="button"
                    className="button button--primary"
                    onClick={() => sportsMutation.mutate()}
                    disabled={sportsMutation.isPending || !sportsDirty}
                  >
                    {sportsMutation.isPending ? "Salvando..." : "Salvar modalidades"}
                  </button>
                  {sportsDirty ? <span className="hint">Alterações não salvas.</span> : null}
                </div>
              </fieldset>
            </div>

            <div className="card">
              <SectionHeading
                title="Agenda semanal"
                description="Janelas recorrentes, preço e duração da vaga. A faixa é calculada pelo servidor a partir do preço."
              />
              {availabilityQuery.error ? (
                <ErrorNotice
                  message={formatError(availabilityQuery.error)}
                  requestId={requestIdOf(availabilityQuery.error)}
                  onRetry={() => void availabilityQuery.refetch()}
                />
              ) : availabilityQuery.isPending ? (
                <SkeletonList rows={2} label="Carregando agenda..." />
              ) : availability.length === 0 ? (
                <EmptyState title="Nenhuma janela" icon={<ClockIcon size={26} />}>
                  Defina horários e preços para esta quadra abrir reservas.
                </EmptyState>
              ) : (
                <ul className="schedule-list">
                  {availability.map((item) => (
                    <li key={item.id} className="schedule-row">
                      <span className="schedule-row__main">
                        <strong>{weekdayLabel(item.weekday)}</strong>
                        <small>
                          {clock(item.start_time)}–{clock(item.end_time)} ·{" "}
                          {formatMoney(item.price_cents)} · {item.slot_minutes} min ·{" "}
                          {bands.find((band) => band.id === item.band_id)?.label ??
                            "Faixa não configurada"}
                        </small>
                      </span>
                      <div className="schedule-row__actions">
                        <button
                          type="button"
                          className="button button--small"
                          onClick={() => openPrice(item)}
                        >
                          Reajustar preço
                        </button>
                        <button
                          type="button"
                          className="button button--small button--danger"
                          onClick={() => {
                            setActionError(null);
                            setDeleteWindowTarget(item);
                          }}
                        >
                          Remover
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              <form className="form form--inline" onSubmit={createWindow} noValidate>
                <h3>Nova janela</h3>
                <div className="form-row form-row--three">
                  <SelectField
                    id="window-weekday"
                    label="Dia"
                    value={windowForm.weekday}
                    onChange={(event) =>
                      setWindowForm((current) => ({
                        ...current,
                        weekday: Number(event.target.value),
                      }))
                    }
                  >
                    {WEEKDAYS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </SelectField>
                  <TextField
                    id="window-start"
                    label="Início"
                    type="time"
                    value={windowForm.startTime}
                    onChange={(event) => {
                      setWindowForm((current) => ({ ...current, startTime: event.target.value }));
                      if (windowErrors.time)
                        setWindowErrors((current) => ({ ...current, time: "" }));
                    }}
                    error={windowErrors.time}
                    required
                  />
                  <TextField
                    id="window-end"
                    label="Fim"
                    type="time"
                    value={windowForm.endTime}
                    onChange={(event) => {
                      setWindowForm((current) => ({ ...current, endTime: event.target.value }));
                      if (windowErrors.time)
                        setWindowErrors((current) => ({ ...current, time: "" }));
                    }}
                    error={windowErrors.time}
                    required
                  />
                </div>
                <div className="form-row">
                  <MoneyField
                    id="window-price"
                    label="Preço da janela"
                    value={windowForm.price}
                    onChange={(value) => {
                      setWindowForm((current) => ({ ...current, price: value }));
                      if (windowErrors.price) {
                        setWindowErrors((current) => ({ ...current, price: "" }));
                      }
                    }}
                    error={windowErrors.price}
                    hint={
                      windowPriceCents !== null && previewBand
                        ? `Faixa calculada: ${previewBand.label} (teto ${formatMoney(
                            previewBand.max_price_cents,
                          )}).`
                        : maxPriceCents !== undefined
                          ? `Teto máximo: ${formatMoney(maxPriceCents)}.`
                          : "Faixas de preço indisponíveis no momento."
                    }
                    required
                  />
                  <TextField
                    id="window-slot"
                    label="Duração da vaga (min)"
                    type="number"
                    min={15}
                    max={240}
                    step={5}
                    value={windowForm.slotMinutes}
                    onChange={(event) => {
                      setWindowForm((current) => ({ ...current, slotMinutes: event.target.value }));
                      if (windowErrors.slot) {
                        setWindowErrors((current) => ({ ...current, slot: "" }));
                      }
                    }}
                    error={windowErrors.slot}
                    hint="De 15 a 240 minutos."
                    required
                  />
                </div>
                <button
                  type="submit"
                  className="button button--primary"
                  disabled={availabilityMutation.isPending}
                  aria-busy={availabilityMutation.isPending || undefined}
                >
                  {availabilityMutation.isPending ? "Adicionando..." : "Adicionar janela"}
                </button>
              </form>
            </div>

            <div className="card">
              <SectionHeading
                title="Expediente e fechamentos"
                description="O prazo de resposta da quadra (T2) conta somente dentro do expediente. Sem expediente, o backend usa tempo corrido."
              />
              {businessHoursQuery.error ? (
                <ErrorNotice
                  message={formatError(businessHoursQuery.error)}
                  requestId={requestIdOf(businessHoursQuery.error)}
                  onRetry={() => void businessHoursQuery.refetch()}
                />
              ) : businessHoursQuery.isPending ? (
                <SkeletonList rows={2} label="Carregando expediente..." />
              ) : businessHours.length === 0 ? (
                <EmptyState title="Nenhum expediente" icon={<ClockIcon size={26} />}>
                  Cadastre os dias e horários em que a quadra responde solicitações.
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
                      <button
                        type="button"
                        className="button button--small button--danger"
                        onClick={() => {
                          setActionError(null);
                          setDeleteHourTarget(item);
                        }}
                      >
                        Remover
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <form className="form form--inline" onSubmit={createHours} noValidate>
                <h3>Novo expediente</h3>
                <div className="form-row form-row--three">
                  <SelectField
                    id="hours-weekday"
                    label="Dia"
                    value={hoursForm.weekday}
                    onChange={(event) =>
                      setHoursForm((current) => ({
                        ...current,
                        weekday: Number(event.target.value),
                      }))
                    }
                  >
                    {WEEKDAYS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </SelectField>
                  <TextField
                    id="hours-open"
                    label="Abre"
                    type="time"
                    value={hoursForm.opensAt}
                    onChange={(event) => {
                      setHoursForm((current) => ({ ...current, opensAt: event.target.value }));
                      if (hoursErrors.time) setHoursErrors({});
                    }}
                    error={hoursErrors.time}
                    required
                  />
                  <TextField
                    id="hours-close"
                    label="Fecha"
                    type="time"
                    value={hoursForm.closesAt}
                    onChange={(event) => {
                      setHoursForm((current) => ({ ...current, closesAt: event.target.value }));
                      if (hoursErrors.time) setHoursErrors({});
                    }}
                    error={hoursErrors.time}
                    required
                  />
                </div>
                <button
                  type="submit"
                  className="button button--primary"
                  disabled={businessHourMutation.isPending}
                  aria-busy={businessHourMutation.isPending || undefined}
                >
                  {businessHourMutation.isPending ? "Adicionando..." : "Adicionar expediente"}
                </button>
              </form>

              <h3>Fechamentos e feriados</h3>
              {closuresQuery.error ? (
                <ErrorNotice
                  message={formatError(closuresQuery.error)}
                  requestId={requestIdOf(closuresQuery.error)}
                  onRetry={() => void closuresQuery.refetch()}
                />
              ) : closures.length === 0 ? (
                <EmptyState title="Nenhum fechamento">
                  Feriados, recessos e exceções de funcionamento aparecem aqui.
                </EmptyState>
              ) : (
                <ul className="schedule-list">
                  {closures.map((item) => (
                    <li key={item.id} className="schedule-row">
                      <span className="schedule-row__main">
                        <strong>{item.reason}</strong>
                        <small>
                          {formatDateRange(item.starts_at, item.ends_at, venue.timezone)}
                        </small>
                      </span>
                      <button
                        type="button"
                        className="button button--small button--danger"
                        onClick={() => {
                          setActionError(null);
                          setDeleteClosureTarget(item);
                        }}
                      >
                        Remover
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <form className="form form--inline" onSubmit={createClosure} noValidate>
                <div className="form-row">
                  <TextField
                    id="closure-start"
                    label="Início do fechamento"
                    type="datetime-local"
                    value={closureForm.start}
                    onChange={(event) => {
                      setClosureForm((current) => ({ ...current, start: event.target.value }));
                      if (closureErrors.range)
                        setClosureErrors((current) => ({ ...current, range: "" }));
                    }}
                    error={closureErrors.range}
                    required
                  />
                  <TextField
                    id="closure-end"
                    label="Fim do fechamento"
                    type="datetime-local"
                    value={closureForm.end}
                    onChange={(event) => {
                      setClosureForm((current) => ({ ...current, end: event.target.value }));
                      if (closureErrors.range)
                        setClosureErrors((current) => ({ ...current, range: "" }));
                    }}
                    error={closureErrors.range}
                    required
                  />
                </div>
                <TextField
                  id="closure-reason"
                  label="Motivo"
                  value={closureForm.reason}
                  onChange={(event) => {
                    setClosureForm((current) => ({ ...current, reason: event.target.value }));
                    if (closureErrors.reason)
                      setClosureErrors((current) => ({ ...current, reason: "" }));
                  }}
                  error={closureErrors.reason}
                  maxLength={200}
                  placeholder="Feriado, recesso, manutenção..."
                  required
                />
                <button
                  type="submit"
                  className="button button--primary"
                  disabled={closureMutation.isPending}
                  aria-busy={closureMutation.isPending || undefined}
                >
                  {closureMutation.isPending ? "Adicionando..." : "Adicionar fechamento"}
                </button>
              </form>
            </div>

            <div className="card">
              <SectionHeading
                title="Bloqueios e reservas externas"
                description="Registre horários vendidos fora do JOGA, manutenções e exceções para evitar conflito com reservas."
              />
              <InfoNotice>
                <p>
                  Um bloqueio aqui não cria reserva. Ele apenas remove o intervalo da
                  disponibilidade desta quadra.
                </p>
              </InfoNotice>
              {blackoutsQuery.error ? (
                <ErrorNotice
                  message={formatError(blackoutsQuery.error)}
                  requestId={requestIdOf(blackoutsQuery.error)}
                  onRetry={() => void blackoutsQuery.refetch()}
                />
              ) : blackoutsQuery.isPending ? (
                <SkeletonList rows={2} label="Carregando bloqueios..." />
              ) : blackouts.length === 0 ? (
                <EmptyState title="Nenhum bloqueio" icon={<CalendarIcon size={26} />}>
                  Feriados, manutenção ou horários vendidos fora do JOGA aparecem aqui.
                </EmptyState>
              ) : (
                <ul className="schedule-list">
                  {blackouts.map((item) => (
                    <li key={item.id} className="schedule-row">
                      <span className="schedule-row__main">
                        <strong>{item.reason}</strong>
                        <small>
                          {formatDateRange(item.starts_at, item.ends_at, venue.timezone)}
                          {item.external_reference ? ` · ${item.external_reference}` : ""}
                        </small>
                      </span>
                      <button
                        type="button"
                        className="button button--small button--danger"
                        onClick={() => {
                          setActionError(null);
                          setDeleteBlackoutTarget(item);
                        }}
                      >
                        Remover
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <form className="form form--inline" onSubmit={createBlackout} noValidate>
                <h3>Novo bloqueio</h3>
                <div className="form-row">
                  <TextField
                    id="blackout-start"
                    label="Início"
                    type="datetime-local"
                    value={blackoutForm.start}
                    onChange={(event) => {
                      setBlackoutForm((current) => ({ ...current, start: event.target.value }));
                      if (blackoutErrors.range)
                        setBlackoutErrors((current) => ({ ...current, range: "" }));
                    }}
                    error={blackoutErrors.range}
                    required
                  />
                  <TextField
                    id="blackout-end"
                    label="Fim"
                    type="datetime-local"
                    value={blackoutForm.end}
                    onChange={(event) => {
                      setBlackoutForm((current) => ({ ...current, end: event.target.value }));
                      if (blackoutErrors.range)
                        setBlackoutErrors((current) => ({ ...current, range: "" }));
                    }}
                    error={blackoutErrors.range}
                    required
                  />
                </div>
                <TextField
                  id="blackout-reason"
                  label="Motivo"
                  value={blackoutForm.reason}
                  onChange={(event) => {
                    setBlackoutForm((current) => ({ ...current, reason: event.target.value }));
                    if (blackoutErrors.reason)
                      setBlackoutErrors((current) => ({ ...current, reason: "" }));
                  }}
                  error={blackoutErrors.reason}
                  maxLength={200}
                  placeholder="Feriado, manutenção, reserva externa..."
                  required
                />
                <TextField
                  id="blackout-reference"
                  label="Referência externa (opcional)"
                  value={blackoutForm.reference}
                  onChange={(event) => {
                    setBlackoutForm((current) => ({ ...current, reference: event.target.value }));
                    if (blackoutErrors.reference) {
                      setBlackoutErrors((current) => ({ ...current, reference: "" }));
                    }
                  }}
                  error={blackoutErrors.reference}
                  hint="Um identificador do controle externo, sem dados pessoais."
                  maxLength={120}
                />
                <button
                  type="submit"
                  className="button button--primary"
                  disabled={blackoutMutation.isPending}
                  aria-busy={blackoutMutation.isPending || undefined}
                >
                  {blackoutMutation.isPending ? "Adicionando..." : "Adicionar bloqueio"}
                </button>
              </form>
            </div>
          </>
        )}
      </div>

      <Modal
        open={Boolean(priceTarget)}
        title="Reajustar preço da janela"
        description={
          priceTarget
            ? `${weekdayLabel(priceTarget.weekday)} · ${clock(priceTarget.start_time)}–${clock(
                priceTarget.end_time,
              )}. Reservas existentes mantêm o valor congelado.`
            : undefined
        }
        onClose={
          updatePriceMutation.isPending
            ? () => undefined
            : () => {
                setPriceTarget(null);
                setActionError(null);
              }
        }
        closeOnOverlay={!updatePriceMutation.isPending}
        size="sm"
        footer={
          <>
            <button
              type="button"
              className="button button--ghost"
              onClick={() => {
                setPriceTarget(null);
                setActionError(null);
              }}
              disabled={updatePriceMutation.isPending}
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="price-form"
              className="button button--primary"
              disabled={updatePriceMutation.isPending}
              aria-busy={updatePriceMutation.isPending || undefined}
            >
              {updatePriceMutation.isPending ? "Salvando..." : "Salvar preço"}
            </button>
          </>
        }
      >
        <form id="price-form" className="form" onSubmit={savePrice} noValidate>
          <MoneyField
            id="price-value"
            label="Novo preço"
            value={priceDraft}
            onChange={(value) => {
              setPriceDraft(value);
              if (priceError) setPriceError(null);
            }}
            error={priceError}
            hint={
              maxPriceCents !== undefined
                ? `Teto máximo da faixa: ${formatMoney(maxPriceCents)}.`
                : undefined
            }
            required
            autoFocus
          />
          {actionFailed}
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteSpaceTarget)}
        title="Remover quadra?"
        description={
          deleteSpaceTarget
            ? `${deleteSpaceTarget.name} e a agenda vinculada serão removidas. Esta ação é auditada.`
            : undefined
        }
        tone="danger"
        confirmLabel="Remover quadra"
        busy={deleteSpaceMutation.isPending}
        onConfirm={() => {
          if (deleteSpaceTarget) deleteSpaceMutation.mutate(deleteSpaceTarget);
        }}
        onClose={() => {
          setDeleteSpaceTarget(null);
          setActionError(null);
        }}
      >
        {actionFailed}
      </ConfirmDialog>

      <ConfirmDialog
        open={Boolean(deleteWindowTarget)}
        title="Remover janela da agenda?"
        description="A janela deixa de aceitar novas reservas. Reservas existentes não são alteradas por esta ação."
        tone="danger"
        confirmLabel="Remover janela"
        busy={deleteAvailabilityMutation.isPending}
        onConfirm={() => {
          if (deleteWindowTarget) deleteAvailabilityMutation.mutate(deleteWindowTarget);
        }}
        onClose={() => {
          setDeleteWindowTarget(null);
          setActionError(null);
        }}
      >
        {actionFailed}
      </ConfirmDialog>

      <ConfirmDialog
        open={Boolean(deleteHourTarget)}
        title="Remover expediente?"
        description="Sem expediente neste dia, o backend volta a considerar tempo corrido para o prazo T2."
        tone="danger"
        confirmLabel="Remover expediente"
        busy={deleteBusinessHourMutation.isPending}
        onConfirm={() => {
          if (deleteHourTarget) deleteBusinessHourMutation.mutate(deleteHourTarget.id);
        }}
        onClose={() => {
          setDeleteHourTarget(null);
          setActionError(null);
        }}
      >
        {actionFailed}
      </ConfirmDialog>

      <ConfirmDialog
        open={Boolean(deleteClosureTarget)}
        title="Remover fechamento?"
        description={
          deleteClosureTarget
            ? `${deleteClosureTarget.reason} · ${formatDateRange(
                deleteClosureTarget.starts_at,
                deleteClosureTarget.ends_at,
                venue.timezone,
              )}.`
            : undefined
        }
        tone="danger"
        confirmLabel="Remover fechamento"
        busy={deleteClosureMutation.isPending}
        onConfirm={() => {
          if (deleteClosureTarget) deleteClosureMutation.mutate(deleteClosureTarget.id);
        }}
        onClose={() => {
          setDeleteClosureTarget(null);
          setActionError(null);
        }}
      >
        {actionFailed}
      </ConfirmDialog>

      <ConfirmDialog
        open={Boolean(deleteBlackoutTarget)}
        title="Remover bloqueio?"
        description={
          deleteBlackoutTarget
            ? `${deleteBlackoutTarget.reason} · ${formatDateRange(
                deleteBlackoutTarget.starts_at,
                deleteBlackoutTarget.ends_at,
                venue.timezone,
              )}. O intervalo volta a ficar disponível para reservas.`
            : undefined
        }
        tone="danger"
        confirmLabel="Remover bloqueio"
        busy={deleteBlackoutMutation.isPending}
        onConfirm={() => {
          if (deleteBlackoutTarget) deleteBlackoutMutation.mutate(deleteBlackoutTarget);
        }}
        onClose={() => {
          setDeleteBlackoutTarget(null);
          setActionError(null);
        }}
      >
        {actionFailed}
      </ConfirmDialog>
    </section>
  );
}
