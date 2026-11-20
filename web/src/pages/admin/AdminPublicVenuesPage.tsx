import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { EmptyState, ErrorNotice, InfoNotice, SkeletonList } from "../../components/Feedback";
import { CheckboxField, SelectField, TextField } from "../../components/ui/Field";
import { BuildingIcon, MapPinIcon, PlusIcon, TrashIcon } from "../../components/ui/Icons";
import { MoneyField } from "../../components/ui/MoneyField";
import { ReasonDialog } from "../../components/ui/Modal";
import { PageHeader, SectionHeading } from "../../components/ui/PageHeader";
import { Pagination } from "../../components/ui/Pagination";
import { Tabs } from "../../components/ui/Tabs";
import { tabId, tabPanelId } from "../../components/ui/tab-ids";
import { useToast } from "../../components/ui/toast-context";
import { adminErrorMessage, isForbidden } from "../../lib/admin";
import { api } from "../../lib/api";
import { formatMoney, requestIdOf } from "../../lib/format";
import { queryKeys } from "../../lib/query";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import {
  coordinateError,
  digitsOnly,
  moneyError,
  moneyInputFromCents,
  moneyToCents,
  normalizeWhitespace,
  textError,
  timeRangeError,
} from "../../lib/validation";
import type {
  AdminPublicVenue,
  AdminPublicVenueDetail,
  AdminPublicVenueSpace,
  AdminPublicVenueSpacePayload,
  AdminVenueAvailabilityPayload,
  AdminVenueBusinessHourPayload,
} from "../../types";
import { AdminForbiddenState } from "./AdminShared";

const PAGE_SIZE = 20;
const WEEKDAYS = [
  { value: "1", label: "Segunda" },
  { value: "2", label: "Terça" },
  { value: "3", label: "Quarta" },
  { value: "4", label: "Quinta" },
  { value: "5", label: "Sexta" },
  { value: "6", label: "Sábado" },
  { value: "7", label: "Domingo" },
];
const STEPS = [
  { id: "data", label: "1. Dados" },
  { id: "spaces", label: "2. Espaços" },
  { id: "schedule", label: "3. Agenda" },
  { id: "preview", label: "4. Prévia" },
] as const;

type Step = (typeof STEPS)[number]["id"];

interface SpaceDraft {
  id?: string;
  name: string;
  sport_id: string;
  format_id: string;
  price: string;
  status: "active" | "inactive";
}

interface AvailabilityDraft {
  id?: string;
  space_index: number;
  weekday: string;
  start_time: string;
  end_time: string;
}

interface BusinessHourDraft {
  id?: string;
  weekday: string;
  opens_at: string;
  closes_at: string;
}

interface VenueDraft {
  name: string;
  city: string;
  state: string;
  address_line: string;
  postal_code: string;
  latitude: string;
  longitude: string;
  reason: string;
  venue_status: "active" | "inactive";
  spaces: SpaceDraft[];
  availability: AvailabilityDraft[];
  business_hours: BusinessHourDraft[];
}

function makeSpaceDraft(): SpaceDraft {
  return {
    name: "",
    sport_id: "",
    format_id: "",
    price: "",
    status: "active",
  };
}

function makeAvailabilityDraft(spaceIndex = 0): AvailabilityDraft {
  return { space_index: spaceIndex, weekday: "1", start_time: "08:00", end_time: "22:00" };
}

function makeBusinessHourDraft(): BusinessHourDraft {
  return { weekday: "1", opens_at: "06:00", closes_at: "23:00" };
}

function makeEmptyVenueDraft(): VenueDraft {
  return {
    name: "",
    city: "",
    state: "",
    address_line: "",
    postal_code: "",
    latitude: "",
    longitude: "",
    reason: "",
    venue_status: "inactive",
    spaces: [makeSpaceDraft()],
    availability: [makeAvailabilityDraft(0)],
    business_hours: [makeBusinessHourDraft()],
  };
}

function toSpaceDraft(space: AdminPublicVenueSpace): SpaceDraft {
  return {
    id: space.id,
    name: space.name,
    sport_id: space.sport_id ?? "",
    format_id: space.format_id ?? "",
    price: moneyInputFromCents(space.price_cents ?? 0),
    status: space.status,
  };
}

function toVenueDraft(venue: AdminPublicVenueDetail): VenueDraft {
  return {
    name: venue.name,
    city: venue.city ?? "",
    state: venue.state ?? "",
    address_line: venue.address_line ?? "",
    postal_code: venue.postal_code ?? "",
    latitude: venue.latitude === null ? "" : String(venue.latitude),
    longitude: venue.longitude === null ? "" : String(venue.longitude),
    reason: "",
    venue_status: venue.status === "active" ? "active" : "inactive",
    spaces: venue.spaces.length > 0 ? venue.spaces.map(toSpaceDraft) : [makeSpaceDraft()],
    availability: [],
    business_hours: [],
  };
}

function parseCoordinate(value: string): number {
  return Number(value.replace(",", "."));
}

export function AdminPublicVenuesPage() {
  useDocumentTitle("Quadras públicas");
  const queryClient = useQueryClient();
  const toast = useToast();

  const [activeFilter, setActiveFilter] = useState("");
  const [page, setPage] = useState(1);

  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [step, setStep] = useState<Step>("data");
  const [draft, setDraft] = useState<VenueDraft>(makeEmptyVenueDraft);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<unknown>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishNow, setPublishNow] = useState(true);
  const [cepLoading, setCepLoading] = useState(false);
  const [cepMessage, setCepMessage] = useState<string | null>(null);

  const [statusTarget, setStatusTarget] = useState<{
    venue: AdminPublicVenue;
    action: "activate" | "deactivate";
  } | null>(null);
  const [statusReason, setStatusReason] = useState("");
  const [statusReasonError, setStatusReasonError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<unknown>(null);

  const venuesQuery = useQuery({
    queryKey: queryKeys.adminVenues(activeFilter, page),
    queryFn: () => api.listAdminPublicVenues({ active: activeFilter, page }),
    placeholderData: keepPreviousData,
  });
  const sportsQuery = useQuery({
    queryKey: queryKeys.sports,
    queryFn: async () => (await api.listSports()).sports,
  });
  const bandsQuery = useQuery({
    queryKey: queryKeys.bands,
    queryFn: async () => (await api.listBands()).bands,
  });

  const venues = venuesQuery.data?.venues ?? [];
  const total = venuesQuery.data?.total ?? 0;
  const pageSize = venuesQuery.data?.page_size ?? PAGE_SIZE;
  const currentPage = venuesQuery.data?.page ?? page;
  const sports = sportsQuery.data ?? [];
  const maxBandCents = Math.max(0, ...(bandsQuery.data ?? []).map((band) => band.max_price_cents));

  const statusMutation = useMutation({
    mutationFn: (input: {
      venue: AdminPublicVenue;
      action: "activate" | "deactivate";
      reason: string;
    }) =>
      input.action === "activate"
        ? api.activateAdminPublicVenue(input.venue.id, input.reason)
        : api.deactivateAdminPublicVenue(input.venue.id, input.reason),
    onSuccess: async (_venue, input) => {
      setStatusTarget(null);
      setStatusReason("");
      setStatusReasonError(null);
      setStatusError(null);
      toast.push({
        title: input.action === "activate" ? "Quadra publicada" : "Quadra desativada",
        description:
          input.action === "activate"
            ? "A quadra volta a aparecer na descoberta."
            : "A quadra sai da descoberta; o histórico de reservas é preservado.",
      });
      await queryClient.invalidateQueries({ queryKey: ["admin", "venues"] });
    },
    onError: (caught) => setStatusError(caught),
  });

  function openCreate() {
    setFormMode("create");
    setEditingId(null);
    setDraft(makeEmptyVenueDraft());
    setErrors({});
    setFormError(null);
    setStep("data");
    setPublishNow(true);
    setCepMessage(null);
    window.setTimeout(() => {
      document.getElementById("venue-form")?.scrollIntoView?.({ block: "start" });
      document.getElementById("venue-name")?.focus();
    }, 0);
  }

  async function openEdit(venue: AdminPublicVenue) {
    setFormMode("edit");
    setEditingId(venue.id);
    setErrors({});
    setFormError(null);
    setStep("data");
    setPublishNow(false);
    setCepMessage(null);
    setFormLoading(true);
    try {
      const detail = await api.getAdminPublicVenue(venue.id);
      const availabilityLists = await Promise.all(
        detail.spaces.map((space) => api.listAdminPublicVenueAvailability(detail.id, space.id)),
      );
      const businessHours = await api.listAdminPublicVenueBusinessHours(detail.id);
      const nextDraft = toVenueDraft(detail);
      nextDraft.availability = availabilityLists.flatMap((list, spaceIndex) =>
        list.map((item) => ({
          id: item.id,
          space_index: spaceIndex,
          weekday: String(item.weekday),
          start_time: item.start_time,
          end_time: item.end_time,
        })),
      );
      nextDraft.business_hours = businessHours.map((item) => ({
        id: item.id,
        weekday: String(item.weekday),
        opens_at: item.opens_at,
        closes_at: item.closes_at,
      }));
      setDraft(nextDraft);
    } catch (caught) {
      setFormError(caught);
    } finally {
      setFormLoading(false);
    }
    window.setTimeout(() => {
      document.getElementById("venue-form")?.scrollIntoView?.({ block: "start" });
      document.getElementById("venue-name")?.focus();
    }, 0);
  }

  function closeForm() {
    if (saving) return;
    setFormMode(null);
    setEditingId(null);
    setErrors({});
    setFormError(null);
    setCepMessage(null);
  }

  function updateDraft(
    patch: Partial<
      Pick<
        VenueDraft,
        | "name"
        | "city"
        | "state"
        | "address_line"
        | "postal_code"
        | "latitude"
        | "longitude"
        | "reason"
      >
    >,
  ) {
    setDraft((current) => ({ ...current, ...patch }));
    setErrors({});
  }

  function updateSpace(index: number, patch: Partial<SpaceDraft>) {
    setDraft((current) => ({
      ...current,
      spaces: current.spaces.map((space, position) =>
        position === index ? { ...space, ...patch } : space,
      ),
    }));
    setErrors({});
  }

  function addSpace() {
    setDraft((current) => ({ ...current, spaces: [...current.spaces, makeSpaceDraft()] }));
  }

  function removeSpace(index: number) {
    setDraft((current) => ({
      ...current,
      spaces: current.spaces.filter((_space, position) => position !== index),
      availability: current.availability
        .filter((window) => window.space_index !== index)
        .map((window) => ({
          ...window,
          space_index: window.space_index > index ? window.space_index - 1 : window.space_index,
        })),
    }));
    setErrors({});
  }

  function updateAvailability(index: number, patch: Partial<AvailabilityDraft>) {
    setDraft((current) => ({
      ...current,
      availability: current.availability.map((window, position) =>
        position === index ? { ...window, ...patch } : window,
      ),
    }));
    setErrors({});
  }

  function addAvailability(spaceIndex: number) {
    setDraft((current) => ({
      ...current,
      availability: [...current.availability, makeAvailabilityDraft(spaceIndex)],
    }));
  }

  function removeAvailability(index: number) {
    setDraft((current) => ({
      ...current,
      availability: current.availability.filter((_window, position) => position !== index),
    }));
    setErrors({});
  }

  function updateBusinessHour(index: number, patch: Partial<BusinessHourDraft>) {
    setDraft((current) => ({
      ...current,
      business_hours: current.business_hours.map((window, position) =>
        position === index ? { ...window, ...patch } : window,
      ),
    }));
    setErrors({});
  }

  function addBusinessHour() {
    setDraft((current) => ({
      ...current,
      business_hours: [...current.business_hours, makeBusinessHourDraft()],
    }));
  }

  function removeBusinessHour(index: number) {
    setDraft((current) => ({
      ...current,
      business_hours: current.business_hours.filter((_window, position) => position !== index),
    }));
    setErrors({});
  }

  async function lookupCep() {
    const cep = digitsOnly(draft.postal_code);
    if (cep.length !== 8) {
      setErrors((current) => ({
        ...current,
        "venue-postal-code": "CEP inválido. Informe os oito dígitos.",
      }));
      return;
    }
    setCepLoading(true);
    setCepMessage(null);
    try {
      const result = await api.lookupPostalCode(cep);
      setDraft((current) => ({
        ...current,
        postal_code: result.postal_code,
        city: result.city || current.city,
        state: result.state || current.state,
        address_line: result.street || current.address_line,
        latitude:
          result.latitude !== null && result.latitude !== undefined
            ? String(result.latitude)
            : current.latitude,
        longitude:
          result.longitude !== null && result.longitude !== undefined
            ? String(result.longitude)
            : current.longitude,
      }));
      setCepMessage(
        result.latitude === null || result.longitude === null
          ? "CEP localizado sem coordenadas. Informe latitude e longitude manualmente."
          : "CEP localizado e coordenadas preenchidas.",
      );
    } catch (caught) {
      setCepMessage(adminErrorMessage(caught));
    } finally {
      setCepLoading(false);
    }
  }

  function validateData(current: VenueDraft): Record<string, string> {
    const next: Record<string, string> = {};
    const nameError = textError(current.name, { label: "o nome da quadra", min: 2, max: 120 });
    if (nameError) next["venue-name"] = nameError;
    const cityError = textError(current.city, { label: "a cidade", min: 2, max: 120 });
    if (cityError) next["venue-city"] = cityError;
    if (!/^[A-Za-z]{2}$/.test(current.state.trim())) {
      next["venue-state"] = "Informe a UF com duas letras.";
    }
    const addressError = textError(current.address_line, {
      label: "o endereço",
      min: 5,
      max: 200,
    });
    if (addressError) next["venue-address"] = addressError;
    const cep = digitsOnly(current.postal_code);
    if (cep && cep.length !== 8) {
      next["venue-postal-code"] = "CEP inválido. Informe os oito dígitos.";
    }
    const coordinates = coordinateError(current.latitude, current.longitude);
    if (!current.latitude.trim() || !current.longitude.trim()) {
      next["venue-geocoding"] =
        "Informe o CEP com coordenadas ou preencha latitude e longitude antes de publicar.";
    }
    if (coordinates.latitude) next["venue-latitude"] = coordinates.latitude;
    if (coordinates.longitude) next["venue-longitude"] = coordinates.longitude;
    const reasonError = textError(current.reason, { label: "o motivo", min: 3, max: 500 });
    if (reasonError) next["venue-reason"] = reasonError;
    return next;
  }

  function validateSpaces(current: VenueDraft): Record<string, string> {
    const next: Record<string, string> = {};
    if (current.spaces.length === 0) {
      next["venue-spaces"] = "Adicione pelo menos um espaço.";
      return next;
    }

    current.spaces.forEach((space, index) => {
      const prefix = `venue-space-${index}`;
      const nameError = textError(space.name, { label: "o nome do espaço", min: 2, max: 120 });
      if (nameError) next[`${prefix}-name`] = nameError;
      if (!space.sport_id) next[`${prefix}-sport`] = "Escolha a modalidade.";
      if (!space.format_id) next[`${prefix}-format`] = "Escolha o formato.";
      const priceCents = moneyToCents(space.price);
      if (priceCents === null || priceCents <= 0) {
        next[`${prefix}-price`] =
          "O preço do espaço não está configurado em nenhuma faixa. Ajuste o valor antes de publicar.";
      } else if (maxBandCents > 0 && priceCents > maxBandCents) {
        next[`${prefix}-price`] =
          "O preço do espaço não está configurado em nenhuma faixa. Ajuste o valor antes de publicar.";
      } else {
        const priceValidation = moneyError(space.price, {
          label: "o preço do espaço",
          minCents: 1,
        });
        if (priceValidation) next[`${prefix}-price`] = priceValidation;
      }
    });

    if (!current.spaces.some((space) => space.status === "active")) {
      next["venue-spaces"] = "A quadra precisa de pelo menos um espaço ativo para ser publicada.";
    }
    return next;
  }

  function validateSchedule(current: VenueDraft): Record<string, string> {
    const next: Record<string, string> = {};
    current.availability.forEach((window, index) => {
      const error = timeRangeError(window.start_time, window.end_time);
      if (error) next[`venue-availability-${index}-time`] = error;
    });
    current.business_hours.forEach((window, index) => {
      const error = timeRangeError(window.opens_at, window.closes_at);
      if (error) next[`venue-hours-${index}-time`] = error;
    });
    const publishing = formMode === "create" ? publishNow : current.venue_status === "active";
    if (publishing) {
      current.spaces.forEach((space, index) => {
        if (space.status !== "active") return;
        if (!current.availability.some((window) => window.space_index === index)) {
          next[`venue-space-${index}-availability`] =
            "Adicione ao menos uma janela semanal para publicar este espaço.";
        }
      });
    }
    return next;
  }

  function validateAll(current: VenueDraft): Record<string, string> {
    return {
      ...validateData(current),
      ...validateSpaces(current),
      ...validateSchedule(current),
    };
  }

  function focusFirst(next: Record<string, string>): void {
    const first = Object.keys(next)[0];
    if (!first) return;
    if (first === "venue-geocoding") {
      document.getElementById("venue-postal-code")?.focus();
      return;
    }
    if (first === "venue-spaces") {
      document.getElementById("venue-space-0-name")?.focus();
      return;
    }
    document.getElementById(first)?.focus();
  }

  function goToStep(next: Step) {
    setStep(next);
    setErrors({});
  }

  function nextStep() {
    const stepErrors =
      step === "data"
        ? validateData(draft)
        : step === "spaces"
          ? validateSpaces(draft)
          : validateSchedule(draft);
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors);
      focusFirst(stepErrors);
      return;
    }
    const currentIndex = STEPS.findIndex((item) => item.id === step);
    const next = STEPS[currentIndex + 1];
    if (next) goToStep(next.id);
  }

  function previousStep() {
    const currentIndex = STEPS.findIndex((item) => item.id === step);
    const previous = STEPS[currentIndex - 1];
    if (previous) goToStep(previous.id);
  }

  function openStatus(venue: AdminPublicVenue, action: "activate" | "deactivate") {
    setStatusTarget({ venue, action });
    setStatusReason("");
    setStatusReasonError(null);
    setStatusError(null);
  }

  function confirmStatus() {
    if (!statusTarget) return;
    const validation = textError(statusReason, { label: "o motivo", min: 3, max: 500 });
    if (validation) {
      setStatusReasonError(validation);
      return;
    }
    setStatusReasonError(null);
    statusMutation.mutate({
      venue: statusTarget.venue,
      action: statusTarget.action,
      reason: statusReason.trim(),
    });
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const allErrors = validateAll(draft);
    if (Object.keys(allErrors).length > 0) {
      setErrors(allErrors);
      const dataErrors = Object.keys(allErrors).some(
        (key) =>
          key.startsWith("venue-") &&
          !key.startsWith("venue-space") &&
          !key.startsWith("venue-availability") &&
          !key.startsWith("venue-hours"),
      );
      const spaceErrors = Object.keys(allErrors).some(
        (key) => key.startsWith("venue-space") || key === "venue-spaces",
      );
      setStep(dataErrors ? "data" : spaceErrors ? "spaces" : "schedule");
      focusFirst(allErrors);
      return;
    }

    setSaving(true);
    setFormError(null);
    let venueId = editingId;
    try {
      const reason = draft.reason.trim();
      const venuePayload = {
        name: normalizeWhitespace(draft.name),
        city: normalizeWhitespace(draft.city),
        state: draft.state.trim().toUpperCase(),
        address_line: normalizeWhitespace(draft.address_line),
        postal_code: digitsOnly(draft.postal_code) || null,
        latitude: parseCoordinate(draft.latitude),
        longitude: parseCoordinate(draft.longitude),
        is_public: true as const,
        reason,
      };

      if (venueId) {
        await api.updateAdminPublicVenue(venueId, venuePayload);
      } else {
        const created = await api.createAdminPublicVenue(venuePayload);
        venueId = created.id;
        setEditingId(created.id);
        setFormMode("edit");
      }

      const savedSpaces: SpaceDraft[] = draft.spaces.map((space) => ({ ...space }));
      const savedIds: string[] = [];
      for (let index = 0; index < savedSpaces.length; index += 1) {
        const space = savedSpaces[index];
        const payload: AdminPublicVenueSpacePayload = {
          name: normalizeWhitespace(space.name),
          sport_id: space.sport_id,
          format_id: space.format_id,
          price_cents: moneyToCents(space.price) ?? 0,
          status: space.status,
          reason,
        };
        const saved = space.id
          ? await api.updateAdminPublicVenueSpace(venueId, space.id, payload)
          : await api.createAdminPublicVenueSpace(venueId, payload);
        savedIds[index] = saved.id;
        savedSpaces[index] = { ...space, id: saved.id };
      }
      setDraft((current) => ({ ...current, spaces: savedSpaces.map((item) => ({ ...item })) }));

      // Agenda: o backend guarda uma linha por janela; reconciliar por espaço.
      for (let index = 0; index < savedSpaces.length; index += 1) {
        const spaceId = savedIds[index];
        const priceCents = moneyToCents(savedSpaces[index].price) ?? 0;
        const currentRows = await api.listAdminPublicVenueAvailability(venueId, spaceId);
        const desired = draft.availability.filter((window) => window.space_index === index);
        const desiredIds = new Set(desired.map((window) => window.id).filter(Boolean));
        for (const row of currentRows) {
          if (!desiredIds.has(row.id)) {
            await api.deleteAdminPublicVenueAvailability(venueId, row.id, spaceId, reason);
          }
        }
        for (const window of desired) {
          const payload: AdminVenueAvailabilityPayload = {
            space_id: spaceId,
            weekday: Number(window.weekday),
            start_time: window.start_time,
            end_time: window.end_time,
            price_cents: priceCents,
            reason,
          };
          if (window.id) {
            await api.updateAdminPublicVenueAvailability(venueId, window.id, payload);
          } else {
            await api.createAdminPublicVenueAvailability(venueId, payload);
          }
        }
      }

      const currentHours = await api.listAdminPublicVenueBusinessHours(venueId);
      const desiredHourIds = new Set(
        draft.business_hours.map((window) => window.id).filter(Boolean),
      );
      for (const row of currentHours) {
        if (!desiredHourIds.has(row.id)) {
          await api.deleteAdminPublicVenueBusinessHour(venueId, row.id, reason);
        }
      }
      for (const window of draft.business_hours) {
        const payload: AdminVenueBusinessHourPayload = {
          weekday: Number(window.weekday),
          opens_at: window.opens_at,
          closes_at: window.closes_at,
          reason,
        };
        if (window.id) {
          await api.updateAdminPublicVenueBusinessHour(venueId, window.id, payload);
        } else {
          await api.createAdminPublicVenueBusinessHour(venueId, payload);
        }
      }

      if (publishNow) {
        await api.activateAdminPublicVenue(venueId, reason);
      }

      toast.push({
        title: publishNow ? "Quadra pública publicada" : "Quadra pública salva",
        description: publishNow
          ? "A quadra aparece na descoberta com os espaços ativos."
          : "A quadra ficou inativa e não aparece na descoberta.",
      });
      setFormMode(null);
      setEditingId(null);
      setErrors({});
      await queryClient.invalidateQueries({ queryKey: ["admin", "venues"] });
    } catch (caught) {
      setFormError(caught);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="JOGA y ADMINISTRAÇÃO"
        title="Quadras públicas"
        description="Catálogo da plataforma, com CEP, coordenadas, espaços, agenda e publicação controlada por motivo."
      />

      <section className="card">
        <SectionHeading
          title="Quadras da plataforma"
          description="Quadras públicas aparecem na descoberta quando estão ativas e têm ao menos um espaço ativo."
          actions={
            <button type="button" className="button button--primary" onClick={openCreate}>
              <PlusIcon size={16} />
              Nova quadra pública
            </button>
          }
        />

        <div className="toolbar">
          <SelectField
            id="admin-venue-active-filter"
            label="Status da quadra"
            className="field--compact"
            value={activeFilter}
            onChange={(event) => {
              setActiveFilter(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todas</option>
            <option value="true">Ativas</option>
            <option value="false">Inativas</option>
          </SelectField>
        </div>

        {venuesQuery.error ? (
          isForbidden(venuesQuery.error) ? (
            <AdminForbiddenState />
          ) : (
            <ErrorNotice
              message={adminErrorMessage(venuesQuery.error)}
              requestId={requestIdOf(venuesQuery.error)}
              onRetry={() => void venuesQuery.refetch()}
            />
          )
        ) : venuesQuery.isPending ? (
          <SkeletonList rows={4} label="Carregando quadras públicas..." />
        ) : venues.length === 0 ? (
          <EmptyState title="Nenhuma quadra pública" icon={<BuildingIcon size={28} />}>
            Crie a primeira quadra pública para exibi-la na descoberta do app.
          </EmptyState>
        ) : (
          <ul className="admin-list">
            {venues.map((venue) => {
              const venueActive = venue.status === "active";
              const discoverable = venue.is_public && venueActive && venue.spaces_count > 0;
              return (
                <li key={venue.id}>
                  <div className="admin-row">
                    <span className="admin-row__identity">
                      <span className="sport-row__icon" aria-hidden="true">
                        <MapPinIcon size={18} />
                      </span>
                      <span>
                        <strong>{venue.name}</strong>
                        <small>
                          {venue.city ?? "—"}/{venue.state ?? "—"} · {venue.spaces_count} espaço(s)
                        </small>
                      </span>
                    </span>
                    <span className={venueActive ? "badge badge--success" : "badge badge--muted"}>
                      {venueActive ? "Ativa" : "Inativa"}
                    </span>
                    <span className={discoverable ? "badge badge--info" : "badge badge--muted"}>
                      {discoverable ? "Na descoberta" : "Fora da descoberta"}
                    </span>
                    <div className="sport-row__actions">
                      <button
                        type="button"
                        className="button button--small button--ghost"
                        onClick={() => void openEdit(venue)}
                      >
                        Editar
                      </button>
                      {venueActive ? (
                        <button
                          type="button"
                          className="button button--small button--danger"
                          onClick={() => openStatus(venue, "deactivate")}
                        >
                          Desativar
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="button button--small button--primary"
                          onClick={() => openStatus(venue, "activate")}
                        >
                          Publicar
                        </button>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        <Pagination
          total={total}
          limit={pageSize}
          offset={(currentPage - 1) * pageSize}
          onChange={(offset) => setPage(Math.floor(offset / pageSize) + 1)}
          disabled={venuesQuery.isFetching}
        />
      </section>

      {formMode ? (
        <section className="card" id="venue-form">
          <SectionHeading
            title={formMode === "edit" ? `Editar ${draft.name || "quadra"}` : "Nova quadra pública"}
            description="A publicação exige coordenadas, ao menos um espaço ativo e preço coberto por faixa."
            actions={
              <button type="button" className="button button--ghost" onClick={closeForm}>
                Cancelar
              </button>
            }
          />
          {formLoading ? (
            <SkeletonList rows={4} label="Carregando agenda da quadra..." />
          ) : (
            <>
              <Tabs
                items={STEPS.map((item) => ({ id: item.id, label: item.label }))}
                active={step}
                onChange={(id) => goToStep(id as Step)}
                idBase="admin-venue"
                ariaLabel="Etapas da quadra pública"
              />
              <form className="form" onSubmit={save} noValidate>
                <div
                  role="tabpanel"
                  id={tabPanelId("admin-venue", step)}
                  aria-labelledby={tabId("admin-venue", step)}
                  tabIndex={0}
                  className="tab-panel"
                >
                  {step === "data" ? (
                    <>
                      <div className="form-row form-row--three">
                        <TextField
                          id="venue-name"
                          label="Nome da quadra"
                          value={draft.name}
                          onChange={(event) => updateDraft({ name: event.target.value })}
                          error={errors["venue-name"]}
                          maxLength={120}
                          required
                        />
                        <TextField
                          id="venue-city"
                          label="Cidade"
                          value={draft.city}
                          onChange={(event) => updateDraft({ city: event.target.value })}
                          error={errors["venue-city"]}
                          maxLength={120}
                          required
                        />
                        <TextField
                          id="venue-state"
                          label="UF"
                          value={draft.state}
                          onChange={(event) =>
                            updateDraft({ state: event.target.value.toUpperCase() })
                          }
                          error={errors["venue-state"]}
                          maxLength={2}
                          required
                        />
                      </div>
                      <TextField
                        id="venue-address"
                        label="Endereço"
                        value={draft.address_line}
                        onChange={(event) => updateDraft({ address_line: event.target.value })}
                        error={errors["venue-address"]}
                        maxLength={200}
                        required
                      />
                      <div className="form-row">
                        <TextField
                          id="venue-postal-code"
                          label="CEP"
                          value={draft.postal_code}
                          onChange={(event) => updateDraft({ postal_code: event.target.value })}
                          error={errors["venue-postal-code"]}
                          inputMode="numeric"
                          maxLength={9}
                        />
                        <div className="field">
                          <span className="field__label">Buscar coordenadas</span>
                          <button
                            type="button"
                            className="button"
                            onClick={() => void lookupCep()}
                            disabled={cepLoading}
                          >
                            {cepLoading ? "Buscando..." : "Buscar CEP"}
                          </button>
                          {cepMessage ? <p className="field__hint">{cepMessage}</p> : null}
                        </div>
                      </div>
                      <div className="form-row">
                        <TextField
                          id="venue-latitude"
                          label="Latitude"
                          value={draft.latitude}
                          onChange={(event) => updateDraft({ latitude: event.target.value })}
                          error={errors["venue-latitude"]}
                          hint="Entre -90 e 90."
                          inputMode="decimal"
                          required
                        />
                        <TextField
                          id="venue-longitude"
                          label="Longitude"
                          value={draft.longitude}
                          onChange={(event) => updateDraft({ longitude: event.target.value })}
                          error={errors["venue-longitude"]}
                          hint="Entre -180 e 180."
                          inputMode="decimal"
                          required
                        />
                      </div>
                      {errors["venue-geocoding"] ? (
                        <p className="field__error" role="alert">
                          {errors["venue-geocoding"]}
                        </p>
                      ) : null}
                      <TextField
                        id="venue-reason"
                        label="Motivo"
                        value={draft.reason}
                        onChange={(event) => updateDraft({ reason: event.target.value })}
                        error={errors["venue-reason"]}
                        hint="Obrigatório. Fica registrado na auditoria."
                        maxLength={500}
                        required
                      />
                    </>
                  ) : null}

                  {step === "spaces" ? (
                    <>
                      {sportsQuery.error ? (
                        <ErrorNotice
                          message={adminErrorMessage(sportsQuery.error)}
                          requestId={requestIdOf(sportsQuery.error)}
                          onRetry={() => void sportsQuery.refetch()}
                        />
                      ) : null}
                      {errors["venue-spaces"] ? (
                        <p className="field__error" role="alert">
                          {errors["venue-spaces"]}
                        </p>
                      ) : null}
                      {draft.spaces.map((space, index) => {
                        const sport = sports.find((item) => item.id === space.sport_id);
                        return (
                          <div key={index} className="format-editor">
                            <div className="format-editor__header">
                              <strong>Espaço {index + 1}</strong>
                              {!space.id && draft.spaces.length > 1 ? (
                                <button
                                  type="button"
                                  className="button button--small button--ghost"
                                  onClick={() => removeSpace(index)}
                                >
                                  <TrashIcon size={15} />
                                  Remover
                                </button>
                              ) : null}
                            </div>
                            <div className="form-row form-row--three">
                              <TextField
                                id={`venue-space-${index}-name`}
                                label="Nome do espaço"
                                value={space.name}
                                onChange={(event) =>
                                  updateSpace(index, { name: event.target.value })
                                }
                                error={errors[`venue-space-${index}-name`]}
                                maxLength={120}
                                required
                              />
                              <SelectField
                                id={`venue-space-${index}-sport`}
                                label="Modalidade"
                                value={space.sport_id}
                                onChange={(event) => {
                                  const nextSport = sports.find(
                                    (item) => item.id === event.target.value,
                                  );
                                  updateSpace(index, {
                                    sport_id: event.target.value,
                                    format_id: nextSport?.formats[0]?.id ?? "",
                                  });
                                }}
                                error={errors[`venue-space-${index}-sport`]}
                                required
                              >
                                <option value="">Selecione</option>
                                {sports.map((item) => (
                                  <option key={item.id} value={item.id}>
                                    {item.name}
                                  </option>
                                ))}
                              </SelectField>
                              <SelectField
                                id={`venue-space-${index}-format`}
                                label="Formato"
                                value={space.format_id}
                                onChange={(event) =>
                                  updateSpace(index, { format_id: event.target.value })
                                }
                                error={errors[`venue-space-${index}-format`]}
                                required
                              >
                                <option value="">Selecione</option>
                                {(sport?.formats ?? []).map((format) => (
                                  <option key={format.id} value={format.id}>
                                    {format.name}
                                  </option>
                                ))}
                              </SelectField>
                            </div>
                            <div className="form-row">
                              <MoneyField
                                id={`venue-space-${index}-price`}
                                label="Preço do espaço"
                                value={space.price}
                                onChange={(value) => updateSpace(index, { price: value })}
                                error={errors[`venue-space-${index}-price`]}
                                hint="O valor precisa caber em uma faixa ativa."
                              />
                              <SelectField
                                id={`venue-space-${index}-status`}
                                label="Status"
                                value={space.status}
                                onChange={(event) =>
                                  updateSpace(index, {
                                    status: event.target.value as "active" | "inactive",
                                  })
                                }
                              >
                                <option value="active">Ativo</option>
                                <option value="inactive">Inativo</option>
                              </SelectField>
                            </div>
                          </div>
                        );
                      })}
                      <button type="button" className="button button--small" onClick={addSpace}>
                        <PlusIcon size={15} />
                        Adicionar espaço
                      </button>
                    </>
                  ) : null}

                  {step === "schedule" ? (
                    <>
                      <SectionHeading
                        title="Disponibilidade semanal"
                        description="Janelas recorrentes por dia da semana."
                        level={3}
                      />
                      {draft.spaces.map((space, spaceIndex) => {
                        const windows = draft.availability
                          .map((window, position) => ({ window, position }))
                          .filter((item) => item.window.space_index === spaceIndex);
                        const priceCents = moneyToCents(space.price);
                        return (
                          <div key={spaceIndex} className="format-editor">
                            <div className="format-editor__header">
                              <strong>{space.name || `Espaço ${spaceIndex + 1}`}</strong>
                              <small>
                                Preço da janela:{" "}
                                {priceCents !== null && priceCents > 0
                                  ? formatMoney(priceCents)
                                  : "defina o preço do espaço"}
                              </small>
                            </div>
                            {errors[`venue-space-${spaceIndex}-availability`] ? (
                              <p
                                className="field__error"
                                role="alert"
                                tabIndex={-1}
                                id={`venue-space-${spaceIndex}-availability`}
                              >
                                {errors[`venue-space-${spaceIndex}-availability`]}
                              </p>
                            ) : null}
                            {windows.length === 0 ? (
                              <p className="hint">
                                Nenhuma janela. Adicione ao menos uma para publicar o espaço.
                              </p>
                            ) : null}
                            {windows.map(({ window, position }) => (
                              <div
                                key={window.id ?? `${spaceIndex}-${position}`}
                                className="form-row form-row--three"
                              >
                                <SelectField
                                  id={`venue-availability-${position}-weekday`}
                                  label="Dia"
                                  value={window.weekday}
                                  onChange={(event) =>
                                    updateAvailability(position, {
                                      weekday: event.target.value,
                                    })
                                  }
                                >
                                  {WEEKDAYS.map((day) => (
                                    <option key={day.value} value={day.value}>
                                      {day.label}
                                    </option>
                                  ))}
                                </SelectField>
                                <TextField
                                  id={`venue-availability-${position}-start`}
                                  label="Início"
                                  type="time"
                                  value={window.start_time}
                                  onChange={(event) =>
                                    updateAvailability(position, {
                                      start_time: event.target.value,
                                    })
                                  }
                                  required
                                />
                                <TextField
                                  id={`venue-availability-${position}-end`}
                                  label="Fim"
                                  type="time"
                                  value={window.end_time}
                                  onChange={(event) =>
                                    updateAvailability(position, {
                                      end_time: event.target.value,
                                    })
                                  }
                                  error={errors[`venue-availability-${position}-time`]}
                                  required
                                />
                                <button
                                  type="button"
                                  className="button button--small button--ghost"
                                  onClick={() => removeAvailability(position)}
                                >
                                  <TrashIcon size={15} />
                                  Remover
                                </button>
                              </div>
                            ))}
                            <button
                              type="button"
                              className="button button--small"
                              onClick={() => addAvailability(spaceIndex)}
                            >
                              <PlusIcon size={15} />
                              Adicionar janela
                            </button>
                          </div>
                        );
                      })}

                      <SectionHeading
                        title="Expediente"
                        description="Horário de funcionamento da quadra."
                        level={3}
                      />
                      {draft.business_hours.map((window, index) => (
                        <div key={index} className="form-row form-row--three">
                          <SelectField
                            id={`venue-hours-${index}-weekday`}
                            label="Dia"
                            value={window.weekday}
                            onChange={(event) =>
                              updateBusinessHour(index, { weekday: event.target.value })
                            }
                          >
                            {WEEKDAYS.map((day) => (
                              <option key={day.value} value={day.value}>
                                {day.label}
                              </option>
                            ))}
                          </SelectField>
                          <TextField
                            id={`venue-hours-${index}-opens`}
                            label="Abre"
                            type="time"
                            value={window.opens_at}
                            onChange={(event) =>
                              updateBusinessHour(index, { opens_at: event.target.value })
                            }
                            required
                          />
                          <TextField
                            id={`venue-hours-${index}-closes`}
                            label="Fecha"
                            type="time"
                            value={window.closes_at}
                            onChange={(event) =>
                              updateBusinessHour(index, { closes_at: event.target.value })
                            }
                            error={errors[`venue-hours-${index}-time`]}
                            required
                          />
                          <button
                            type="button"
                            className="button button--small button--ghost"
                            onClick={() => removeBusinessHour(index)}
                          >
                            <TrashIcon size={15} />
                            Remover
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        className="button button--small"
                        onClick={addBusinessHour}
                      >
                        <PlusIcon size={15} />
                        Adicionar expediente
                      </button>
                    </>
                  ) : null}

                  {step === "preview" ? (
                    <>
                      <div className="public-venue-preview">
                        <div className="public-venue-preview__heading">
                          <span className="sport-preview__icon" aria-hidden="true">
                            <MapPinIcon size={20} />
                          </span>
                          <div>
                            <span className="badge badge--success">Pública</span>
                            <strong>{draft.name || "Nome da quadra"}</strong>
                            <small>
                              {draft.city || "Cidade"}/{draft.state || "UF"}
                            </small>
                          </div>
                        </div>
                        <p className="hint">
                          {draft.address_line || "Endereço"}
                          {draft.postal_code ? ` · CEP ${draft.postal_code}` : ""}
                        </p>
                        <p className="hint">
                          Coordenadas: {draft.latitude || "—"}, {draft.longitude || "—"}
                        </p>
                        <div className="public-venue-preview__spaces">
                          {draft.spaces.map((space, index) => (
                            <div key={index} className="public-venue-preview__space">
                              <strong>{space.name || `Espaço ${index + 1}`}</strong>
                              <small>
                                {sports.find((item) => item.id === space.sport_id)?.name ??
                                  "modalidade"}{" "}
                                · {formatMoney(moneyToCents(space.price) ?? 0)}
                              </small>
                              <span className="badge badge--muted">
                                {space.status === "active" ? "Ativo" : "Inativo"}
                              </span>
                            </div>
                          ))}
                        </div>
                        <p className="hint">
                          {draft.availability.length} janela(s) semanal(is) ·{" "}
                          {draft.business_hours.length} expediente(s)
                        </p>
                      </div>
                      {formMode === "create" ? (
                        <CheckboxField
                          id="venue-publish-now"
                          label="Publicar na descoberta ao salvar"
                          hint="A publicação exige ao menos um espaço ativo com preço em faixa."
                          checked={publishNow}
                          onChange={setPublishNow}
                        />
                      ) : (
                        <InfoNotice>
                          Para publicar ou desativar, use as ações da lista. A edição preserva o
                          estado atual da quadra.
                        </InfoNotice>
                      )}
                    </>
                  ) : null}
                </div>

                {formError ? (
                  <ErrorNotice
                    message={adminErrorMessage(formError)}
                    requestId={requestIdOf(formError)}
                  />
                ) : null}

                <div className="form-actions">
                  <button
                    type="button"
                    className="button button--ghost"
                    onClick={previousStep}
                    disabled={step === "data" || saving}
                  >
                    Voltar
                  </button>
                  {step !== "preview" ? (
                    <button type="button" className="button button--primary" onClick={nextStep}>
                      Avançar
                    </button>
                  ) : (
                    <button
                      type="submit"
                      className="button button--primary"
                      disabled={saving}
                      aria-busy={saving || undefined}
                    >
                      {saving
                        ? "Salvando..."
                        : formMode === "edit"
                          ? "Salvar alterações"
                          : publishNow
                            ? "Criar e publicar"
                            : "Criar como inativa"}
                    </button>
                  )}
                  <button
                    type="button"
                    className="button button--ghost"
                    onClick={closeForm}
                    disabled={saving}
                  >
                    Cancelar
                  </button>
                </div>
              </form>
            </>
          )}
        </section>
      ) : null}

      <ReasonDialog
        open={Boolean(statusTarget)}
        title={statusTarget?.action === "activate" ? "Publicar quadra" : "Desativar quadra"}
        description={
          statusTarget?.action === "activate"
            ? "A quadra volta a aparecer na descoberta quando houver espaço ativo com preço configurado."
            : "A quadra sai da descoberta. O histórico de reservas é preservado."
        }
        label="Motivo"
        value={statusReason}
        onChange={(value) => {
          setStatusReason(value);
          if (statusReasonError) setStatusReasonError(null);
        }}
        error={statusReasonError}
        maxLength={500}
        minLength={3}
        confirmLabel={statusTarget?.action === "activate" ? "Publicar quadra" : "Desativar quadra"}
        tone={statusTarget?.action === "deactivate" ? "danger" : "default"}
        busy={statusMutation.isPending}
        onConfirm={confirmStatus}
        onClose={() => {
          if (statusMutation.isPending) return;
          setStatusTarget(null);
          setStatusReason("");
          setStatusReasonError(null);
          setStatusError(null);
        }}
      >
        {statusTarget ? (
          <div className="dialog-summary">
            <strong>{statusTarget.venue.name}</strong>
            <span>
              {statusTarget.venue.city}/{statusTarget.venue.state}
            </span>
          </div>
        ) : null}
        {statusError ? (
          <ErrorNotice
            message={adminErrorMessage(statusError)}
            requestId={requestIdOf(statusError)}
          />
        ) : null}
      </ReasonDialog>
    </>
  );
}
