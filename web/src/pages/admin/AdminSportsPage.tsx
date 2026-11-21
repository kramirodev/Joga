import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { EmptyState, ErrorNotice, InfoNotice, SkeletonList } from "../../components/Feedback";
import { SelectField, TextareaField, TextField } from "../../components/ui/Field";
import { PencilIcon, PlusIcon, SparkIcon, TrashIcon } from "../../components/ui/Icons";
import { ReasonDialog } from "../../components/ui/Modal";
import { PageHeader, SectionHeading } from "../../components/ui/PageHeader";
import { useToast } from "../../components/ui/toast-context";
import { adminErrorMessage, isForbidden } from "../../lib/admin";
import { ApiError, api } from "../../lib/api";
import { formatMoney, requestIdOf } from "../../lib/format";
import { minimumTickets, requiredTotalCents, ticketsInvariantError } from "../../lib/pricing";
import { queryKeys } from "../../lib/query";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import {
  normalizeWhitespace,
  positiveIntegerError,
  slugError,
  textError,
} from "../../lib/validation";
import type {
  AdminPricingBandSuggestion,
  AdminPricingMode,
  AdminSport,
  AdminSportCreatePayload,
  AdminSportFormat,
  AdminSportUpdatePayload,
} from "../../types";
import { AdminForbiddenState } from "./AdminShared";

const STANDARD_TEAM_SIZES = new Set([3, 5, 6]);
const MAX_FORMATS = 10;
const SCORE_MODELS = [
  { value: "goals", label: "Gols" },
  { value: "sets_points", label: "Sets e pontos" },
];
const ICON_PREVIEW: Record<string, string> = {
  "icon-sport-futebol-5x5": "⚽",
  "icon-sport-volei-6x6": "🏐",
  "icon-sport-futebol-3x3": "⚽",
  "icon-sport-futevolei-3x3": "🏖️",
};

interface FormatDraft {
  name: string;
  slug: string;
  team_size: string;
  duration_minutes: string;
  periods: string;
  score_model: string;
  positions: string;
  pricing_mode: AdminPricingMode | "";
  existing: boolean;
  in_use: boolean;
}

interface SportDraft {
  name: string;
  slug: string;
  icon: string;
  sort_order: string;
  reason: string;
  formats: FormatDraft[];
}

interface SportValidation {
  errors: Record<string, string>;
  create: AdminSportCreatePayload | null;
  update: AdminSportUpdatePayload | null;
}

function iconGlyph(key: string | null | undefined): string {
  if (!key) return "★";
  return ICON_PREVIEW[key] ?? "★";
}

function isStandardTeamSize(teamSize: number): boolean {
  return STANDARD_TEAM_SIZES.has(teamSize);
}

function makeFormatDraft(teamSize = "5"): FormatDraft {
  return {
    name: "",
    slug: "",
    team_size: teamSize,
    duration_minutes: "60",
    periods: "1",
    score_model: "sets_points",
    positions: "",
    pricing_mode: "standard",
    existing: false,
    in_use: false,
  };
}

function makeEmptySportDraft(): SportDraft {
  return {
    name: "",
    slug: "",
    icon: "",
    sort_order: "0",
    reason: "",
    formats: [makeFormatDraft()],
  };
}

function formatParticipants(format: AdminSportFormat): number {
  return format.total_participants;
}

function toFormatDraft(format: AdminSportFormat): FormatDraft {
  return {
    name: format.name,
    slug: format.slug,
    team_size: String(format.team_size),
    duration_minutes: String(format.duration_minutes),
    periods: String(format.period_count),
    score_model: format.score_model,
    positions: format.positions.join(", "),
    pricing_mode: "standard",
    existing: true,
    in_use: Boolean(format.in_use),
  };
}

function toSportDraft(sport: AdminSport): SportDraft {
  return {
    name: sport.name,
    slug: sport.slug,
    icon: sport.icon_key,
    sort_order: String(sport.sort_order),
    reason: "",
    formats: sport.formats.length > 0 ? sport.formats.map(toFormatDraft) : [makeFormatDraft()],
  };
}

function parsePositions(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function formatPricingMode(format: FormatDraft): AdminPricingMode | "" {
  const teamSize = Number(format.team_size);
  return isStandardTeamSize(teamSize) ? "standard" : format.pricing_mode;
}

function validateSportDraft(
  draft: SportDraft,
  options: { editing: boolean; iconKeys: string[] | null },
): SportValidation {
  const errors: Record<string, string> = {};

  const nameError = textError(draft.name, { label: "o nome do esporte", min: 2, max: 80 });
  if (nameError) errors["sport-name"] = nameError;
  const sportSlugError = slugError(draft.slug, "o slug do esporte");
  if (sportSlugError) errors["sport-slug"] = sportSlugError;
  const iconError = textError(draft.icon, { label: "a chave do ícone", min: 2, max: 64 });
  if (iconError) {
    errors["sport-icon"] = iconError;
  } else if (options.iconKeys && !options.iconKeys.includes(draft.icon)) {
    errors["sport-icon"] = "Escolha um ícone ativo do catálogo.";
  }
  const orderError = positiveIntegerError(Number(draft.sort_order), 0, 9999, "a ordem de exibição");
  if (orderError) errors["sport-sort-order"] = orderError;
  const reasonError = textError(draft.reason, { label: "o motivo", min: 3, max: 500 });
  if (reasonError) errors["sport-reason"] = reasonError;

  const base = {
    name: normalizeWhitespace(draft.name),
    icon_key: draft.icon.trim().toLowerCase(),
    sort_order: Number(draft.sort_order),
    reason: draft.reason.trim(),
  };

  if (options.editing) {
    return {
      errors,
      create: null,
      update: Object.keys(errors).length > 0 ? null : base,
    };
  }

  if (draft.formats.length === 0) {
    errors["sport-formats"] = "Adicione pelo menos um formato.";
  } else if (draft.formats.length > MAX_FORMATS) {
    errors["sport-formats"] = `Use no máximo ${MAX_FORMATS} formatos.`;
  }

  const usedSlugs = new Set<string>();
  draft.formats.forEach((format, index) => {
    const prefix = `sport-format-${index}`;
    const formatNameError = textError(format.name, {
      label: "o nome do formato",
      min: 2,
      max: 80,
    });
    if (formatNameError) errors[`${prefix}-name`] = formatNameError;

    const formatSlugError = slugError(format.slug, "o slug do formato");
    if (formatSlugError) {
      errors[`${prefix}-slug`] = formatSlugError;
    } else {
      const cleanSlug = format.slug.trim().toLowerCase();
      if (usedSlugs.has(cleanSlug)) {
        errors[`${prefix}-slug`] = "Já existe um formato com esse slug.";
      }
      usedSlugs.add(cleanSlug);
    }

    const teamSize = Number(format.team_size);
    const teamSizeError = positiveIntegerError(teamSize, 1, 20, "o número de jogadores por equipe");
    if (teamSizeError) errors[`${prefix}-team-size`] = teamSizeError;

    const durationError = positiveIntegerError(
      Number(format.duration_minutes),
      5,
      240,
      "a duração",
    );
    if (durationError) errors[`${prefix}-duration`] = durationError;

    const periodsError = positiveIntegerError(
      Number(format.periods),
      1,
      20,
      "o número de períodos",
    );
    if (periodsError) errors[`${prefix}-periods`] = periodsError;

    if (!SCORE_MODELS.some((model) => model.value === format.score_model)) {
      errors[`${prefix}-score`] = "Escolha um modelo de pontuação válido.";
    }

    if (!isStandardTeamSize(teamSize) && !format.pricing_mode) {
      errors[`${prefix}-mode`] = "Escolha explicitamente o modo de preço para este formato.";
    }

    const positions = parsePositions(format.positions);
    if (positions.length > 20) {
      errors[`${prefix}-positions`] = "Use no máximo 20 posições.";
    } else if (positions.some((position) => position.length > 40)) {
      errors[`${prefix}-positions`] = "Cada posição deve ter no máximo 40 caracteres.";
    }
  });

  if (Object.keys(errors).length > 0) {
    return { errors, create: null, update: null };
  }

  return {
    errors,
    create: {
      ...base,
      slug: draft.slug.trim().toLowerCase(),
      formats: draft.formats.map((format) => ({
        name: normalizeWhitespace(format.name),
        slug: format.slug.trim().toLowerCase(),
        team_size: Number(format.team_size),
        players_per_team: Number(format.team_size),
        duration_minutes: Number(format.duration_minutes),
        period_count: Number(format.periods),
        score_model: format.score_model,
        positions: parsePositions(format.positions),
      })),
    },
    update: null,
  };
}

function FormatPricingPreview({ format, index }: { format: FormatDraft; index: number }) {
  const teamSize = Number(format.team_size);
  const mode = formatPricingMode(format);
  const enabled = Number.isInteger(teamSize) && teamSize >= 1 && teamSize <= 20 && Boolean(mode);
  const query = useQuery({
    queryKey: queryKeys.adminPricingSuggestion(teamSize, mode || "none"),
    queryFn: () => api.getAdminPricingSuggestion(teamSize, mode as AdminPricingMode),
    enabled,
    retry: false,
  });

  if (!enabled) {
    return (
      <p className="hint" id={`sport-format-${index}-pricing`}>
        {teamSize >= 1 && teamSize <= 20 && !mode
          ? "Escolha o modo de preço para ver o k sugerido."
          : "Informe um tamanho de equipe válido para ver o k sugerido."}
      </p>
    );
  }

  if (query.isPending) {
    return (
      <p className="hint" id={`sport-format-${index}-pricing`}>
        Calculando k sugerido...
      </p>
    );
  }

  if (query.error) {
    return (
      <p className="field__error" id={`sport-format-${index}-pricing`} role="alert">
        {adminErrorMessage(query.error)}
      </p>
    );
  }

  const bands = query.data?.bands ?? [];
  return (
    <div className="format-pricing-preview" id={`sport-format-${index}-pricing`}>
      <p className="hint">
        k sugerido ·{" "}
        {query.data?.mode === "contingency" ? "contingência sem 20%" : "padrão com 20%"}
      </p>
      <div className="format-pricing-preview__bands">
        {bands.map((band) => (
          <span key={band.code} className="badge badge--muted">
            {band.label}: <strong>{band.tickets}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

export function AdminSportsPage() {
  useDocumentTitle("Esportes");
  const queryClient = useQueryClient();
  const toast = useToast();

  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editingSlug, setEditingSlug] = useState<string | null>(null);
  const [draft, setDraft] = useState<SportDraft>(makeEmptySportDraft);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saveError, setSaveError] = useState<unknown>(null);
  const [preflightPending, setPreflightPending] = useState(false);

  const [statusTarget, setStatusTarget] = useState<{
    sport: AdminSport;
    action: "activate" | "deactivate";
  } | null>(null);
  const [statusReason, setStatusReason] = useState("");
  const [statusReasonError, setStatusReasonError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<unknown>(null);

  const [teamSizeInput, setTeamSizeInput] = useState("5");
  const [pricingMode, setPricingMode] = useState<AdminPricingMode | "">("standard");
  const [pricingTarget, setPricingTarget] = useState<{
    band: AdminPricingBandSuggestion;
    teamSize: number;
    mode: AdminPricingMode;
  } | null>(null);
  const [ticketsInput, setTicketsInput] = useState("");
  const [pricingReason, setPricingReason] = useState("");
  const [pricingReasonError, setPricingReasonError] = useState<string | null>(null);
  const [pricingError, setPricingError] = useState<unknown>(null);

  const sportsQuery = useQuery({
    queryKey: queryKeys.adminSports,
    queryFn: async () => (await api.listAdminSports()).sports,
  });

  const visualCatalogQuery = useQuery({
    queryKey: queryKeys.adminVisualCatalog,
    queryFn: () => api.listVisualCatalog(),
    retry: false,
  });

  const iconOptions = (visualCatalogQuery.data?.items ?? []).filter(
    (item) => item.kind === "icon" && item.active !== false,
  );
  const iconKeys = visualCatalogQuery.isSuccess ? iconOptions.map((item) => item.key) : null;

  const teamSizeNumber = Number(teamSizeInput);
  const teamSizeValid =
    Number.isInteger(teamSizeNumber) && teamSizeNumber >= 1 && teamSizeNumber <= 20;
  const teamSizeStandard = teamSizeValid && isStandardTeamSize(teamSizeNumber);
  const effectivePricingMode: AdminPricingMode | "" = teamSizeStandard ? "standard" : pricingMode;

  const pricingQuery = useQuery({
    queryKey: queryKeys.adminPricingSuggestion(
      teamSizeValid ? teamSizeNumber : 0,
      effectivePricingMode || "none",
    ),
    queryFn: () =>
      api.getAdminPricingSuggestion(teamSizeNumber, effectivePricingMode as AdminPricingMode),
    enabled: teamSizeValid && Boolean(effectivePricingMode),
  });

  const sports = sportsQuery.data ?? [];
  const bands = pricingQuery.data?.bands ?? [];

  const saveMutation = useMutation({
    mutationFn: (
      input: { create: AdminSportCreatePayload } | { update: AdminSportUpdatePayload },
    ) =>
      "create" in input
        ? api.createAdminSport(input.create)
        : api.updateAdminSport(editingSlug ?? "", input.update),
    onSuccess: async (_sport, input) => {
      toast.push({
        title: "create" in input ? "Esporte criado" : "Esporte atualizado",
        description:
          "create" in input
            ? "O esporte nasce desativado; configure as seis faixas e publique quando estiver pronto."
            : "A alteração foi registrada na auditoria.",
      });
      setFormMode(null);
      setEditingSlug(null);
      setErrors({});
      setSaveError(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminSports });
    },
    onError: (caught) => setSaveError(caught),
  });

  const statusMutation = useMutation({
    mutationFn: (input: {
      sport: AdminSport;
      action: "activate" | "deactivate";
      reason: string;
    }) =>
      input.action === "activate"
        ? api.activateAdminSport(input.sport.slug, input.reason)
        : api.deactivateAdminSport(input.sport.slug, input.reason),
    onSuccess: async (_sport, input) => {
      setStatusTarget(null);
      setStatusReason("");
      setStatusReasonError(null);
      setStatusError(null);
      toast.push({
        title: input.action === "activate" ? "Esporte publicado" : "Esporte desativado",
        description: "A alteração foi registrada na auditoria.",
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminSports });
    },
    onError: (caught) => setStatusError(caught),
  });

  const pricingMutation = useMutation({
    mutationFn: (input: {
      band: AdminPricingBandSuggestion;
      teamSize: number;
      mode: AdminPricingMode;
      tickets: number;
      reason: string;
    }) =>
      api.updateAdminBandTickets({
        band_code: input.band.code,
        team_size: input.teamSize,
        tickets: input.tickets,
        mode: input.mode,
        reason: input.reason,
      }),
    onSuccess: async (_result, input) => {
      setPricingTarget(null);
      setTicketsInput("");
      setPricingReason("");
      setPricingReasonError(null);
      setPricingError(null);
      toast.push({
        title: "Tabela de tickets atualizada",
        description: `Faixa ${input.band.label} · formato ${input.teamSize}x${input.teamSize}.`,
      });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.adminPricingSuggestion(input.teamSize, input.mode),
      });
    },
    onError: (caught) => setPricingError(caught),
  });

  function openCreate() {
    setFormMode("create");
    setEditingSlug(null);
    setDraft(makeEmptySportDraft());
    setErrors({});
    setSaveError(null);
    focusForm();
  }

  function openEdit(sport: AdminSport) {
    setFormMode("edit");
    setEditingSlug(sport.slug);
    setDraft(toSportDraft(sport));
    setErrors({});
    setSaveError(null);
    focusForm();
  }

  function closeForm() {
    setFormMode(null);
    setEditingSlug(null);
    setErrors({});
    setSaveError(null);
  }

  function focusForm() {
    window.setTimeout(() => {
      document.getElementById("sport-form")?.scrollIntoView?.({ block: "start" });
      document.getElementById("sport-name")?.focus();
    }, 0);
  }

  function updateDraft(
    patch: Partial<Pick<SportDraft, "name" | "slug" | "icon" | "sort_order" | "reason">>,
  ) {
    setDraft((current) => ({ ...current, ...patch }));
    setErrors({});
  }

  function updateFormat(index: number, patch: Partial<FormatDraft>) {
    setDraft((current) => ({
      ...current,
      formats: current.formats.map((format, position) =>
        position === index ? { ...format, ...patch } : format,
      ),
    }));
    setErrors({});
  }

  function addFormat() {
    setDraft((current) => ({
      ...current,
      formats:
        current.formats.length >= MAX_FORMATS
          ? current.formats
          : [...current.formats, makeFormatDraft()],
    }));
  }

  function removeFormat(index: number) {
    setDraft((current) => ({
      ...current,
      formats: current.formats.filter((_format, position) => position !== index),
    }));
    setErrors({});
  }

  async function preflightPricing(formats: FormatDraft[]): Promise<Record<string, string>> {
    const preflightErrors: Record<string, string> = {};
    const seen = new Set<string>();
    for (const [index, format] of formats.entries()) {
      const teamSize = Number(format.team_size);
      const mode = formatPricingMode(format);
      if (!Number.isInteger(teamSize) || !mode) continue;
      const cacheKey = `${teamSize}:${mode}`;
      if (seen.has(cacheKey)) continue;
      seen.add(cacheKey);
      try {
        await queryClient.fetchQuery({
          queryKey: queryKeys.adminPricingSuggestion(teamSize, mode),
          queryFn: () => api.getAdminPricingSuggestion(teamSize, mode),
          retry: false,
          staleTime: 0,
        });
      } catch (caught) {
        if (caught instanceof ApiError && caught.code === "pricing_not_configured") {
          preflightErrors["sport-formats"] =
            `O preço do formato ${teamSize}x${teamSize} ainda não está configurado. Configure as seis faixas antes de salvar.`;
        } else if (
          caught instanceof ApiError &&
          ["pricing_mode_required", "invalid_pricing_mode"].includes(caught.code)
        ) {
          preflightErrors[`sport-format-${index}-mode`] =
            "Escolha explicitamente o modo de preço para este formato.";
        } else {
          preflightErrors["sport-formats"] = adminErrorMessage(caught);
        }
        break;
      }
    }
    return preflightErrors;
  }

  async function submitSport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saveMutation.isPending || preflightPending) return;
    const validation = validateSportDraft(draft, {
      editing: formMode === "edit",
      iconKeys,
    });
    if (Object.keys(validation.errors).length > 0) {
      setErrors(validation.errors);
      const first = Object.keys(validation.errors)[0];
      if (first) document.getElementById(first)?.focus();
      return;
    }

    setErrors({});
    setSaveError(null);

    if (formMode === "create") {
      if (!validation.create) return;
      setPreflightPending(true);
      const preflightErrors = await preflightPricing(draft.formats);
      setPreflightPending(false);
      if (Object.keys(preflightErrors).length > 0) {
        setErrors(preflightErrors);
        const first = Object.keys(preflightErrors)[0];
        if (first) document.getElementById(first)?.focus();
        return;
      }
      saveMutation.mutate({ create: validation.create });
      return;
    }

    if (validation.update) {
      saveMutation.mutate({ update: validation.update });
    }
  }

  function openStatus(sport: AdminSport, action: "activate" | "deactivate") {
    setStatusTarget({ sport, action });
    setStatusReason("");
    setStatusReasonError(null);
    setStatusError(null);
  }

  function confirmStatus() {
    if (!statusTarget || statusMutation.isPending) return;
    const validation = textError(statusReason, { label: "o motivo", min: 3, max: 500 });
    if (validation) {
      setStatusReasonError(validation);
      return;
    }
    setStatusReasonError(null);
    statusMutation.mutate({
      sport: statusTarget.sport,
      action: statusTarget.action,
      reason: statusReason.trim(),
    });
  }

  function openPricing(band: AdminPricingBandSuggestion) {
    if (!teamSizeValid || !effectivePricingMode) return;
    setPricingTarget({
      band,
      teamSize: teamSizeNumber,
      mode: effectivePricingMode as AdminPricingMode,
    });
    setTicketsInput(String(band.tickets));
    setPricingReason("");
    setPricingReasonError(null);
    setPricingError(null);
  }

  const pricingTickets = Number(ticketsInput);
  const pricingTicketsError = pricingTarget
    ? ticketsInvariantError(
        pricingTarget.band.max_price_cents,
        pricingTarget.teamSize,
        pricingTickets,
        pricingTarget.mode,
      )
    : null;

  function confirmPricing() {
    if (!pricingTarget) return;
    if (
      ticketsInvariantError(
        pricingTarget.band.max_price_cents,
        pricingTarget.teamSize,
        pricingTickets,
        pricingTarget.mode,
      )
    ) {
      return;
    }
    const validation = textError(pricingReason, { label: "o motivo", min: 3, max: 500 });
    if (validation) {
      setPricingReasonError(validation);
      return;
    }
    setPricingReasonError(null);
    pricingMutation.mutate({
      band: pricingTarget.band,
      teamSize: pricingTarget.teamSize,
      mode: pricingTarget.mode,
      tickets: pricingTickets,
      reason: pricingReason.trim(),
    });
  }

  const catalogUnavailable = visualCatalogQuery.isError;
  const selectedIconUnavailable =
    Boolean(draft.icon) && !iconOptions.some((item) => item.key === draft.icon);

  return (
    <>
      <PageHeader
        eyebrow="JOGA y ADMINISTRAÇÃO"
        title="Esportes"
        description="Catálogo estruturado, prévia de exibição, publicação com motivo e tabela de tickets com invariante protegido."
      />

      <section className="card">
        <SectionHeading
          title="Catálogo de modalidades"
          description="Formatos definem equipe, participantes, duração, períodos, pontuação e posições."
          actions={
            <button type="button" className="button button--primary" onClick={openCreate}>
              <PlusIcon size={16} />
              Novo esporte
            </button>
          }
        />

        {sportsQuery.error ? (
          isForbidden(sportsQuery.error) ? (
            <AdminForbiddenState />
          ) : (
            <ErrorNotice
              message={adminErrorMessage(sportsQuery.error)}
              requestId={requestIdOf(sportsQuery.error)}
              onRetry={() => void sportsQuery.refetch()}
            />
          )
        ) : sportsQuery.isPending ? (
          <SkeletonList rows={3} label="Carregando esportes..." />
        ) : sports.length === 0 ? (
          <EmptyState title="Nenhum esporte cadastrado" icon={<SparkIcon size={28} />}>
            Crie a primeira modalidade com formatos, pontuação e posições.
          </EmptyState>
        ) : (
          <ul className="sport-list">
            {sports.map((sport) => (
              <li key={sport.slug} className="sport-row">
                <div className="sport-row__identity">
                  <span className="sport-row__icon" aria-hidden="true">
                    {iconGlyph(sport.icon_key)}
                  </span>
                  <div>
                    <strong>{sport.name}</strong>
                    <small className="mono">{sport.slug}</small>
                    <small>{sport.formats.length} formato(s)</small>
                  </div>
                </div>
                <div className="sport-row__formats">
                  {sport.formats.slice(0, 4).map((format) => (
                    <span key={format.slug} className="badge badge--muted">
                      {format.name} · {format.team_size}x{format.team_size} ·{" "}
                      {formatParticipants(format)} jogadores
                    </span>
                  ))}
                  {sport.formats.length > 4 ? (
                    <span className="badge badge--muted">+{sport.formats.length - 4}</span>
                  ) : null}
                </div>
                <span className={sport.active ? "badge badge--success" : "badge badge--muted"}>
                  {sport.active ? "Publicado" : "Desativado"}
                </span>
                <div className="sport-row__actions">
                  <button
                    type="button"
                    className="button button--small button--ghost"
                    onClick={() => openEdit(sport)}
                  >
                    <PencilIcon size={15} />
                    Editar
                  </button>
                  {sport.active ? (
                    <button
                      type="button"
                      className="button button--small button--danger"
                      onClick={() => openStatus(sport, "deactivate")}
                    >
                      Desativar
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="button button--small button--primary"
                      onClick={() => openStatus(sport, "activate")}
                    >
                      Publicar
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {formMode ? (
        <section className="grid grid--sidebar" id="sport-form">
          <div className="card card--form">
            <SectionHeading
              title={formMode === "edit" ? `Editar ${draft.name || "esporte"}` : "Novo esporte"}
              description="Os campos abaixo formam o catálogo exibido no app do jogador."
              actions={
                <button type="button" className="button button--ghost" onClick={closeForm}>
                  Cancelar
                </button>
              }
            />
            <form className="form" onSubmit={submitSport} noValidate>
              <div className="form-row">
                <TextField
                  id="sport-name"
                  label="Nome"
                  value={draft.name}
                  onChange={(event) => updateDraft({ name: event.target.value })}
                  error={errors["sport-name"]}
                  hint="De 2 a 80 caracteres."
                  maxLength={80}
                  required
                />
                <TextField
                  id="sport-slug"
                  label="Slug"
                  value={draft.slug}
                  onChange={(event) => updateDraft({ slug: event.target.value })}
                  error={errors["sport-slug"]}
                  hint={
                    formMode === "edit"
                      ? "O slug de criação identifica a rota e não muda na edição."
                      : "Minúsculas, números e hífens."
                  }
                  maxLength={40}
                  readOnly={formMode === "edit"}
                  required
                />
              </div>

              <div className="form-row">
                <div className="field">
                  {catalogUnavailable ? (
                    <>
                      <InfoNotice>
                        Catálogo de ícones indisponível. Informe a chave manualmente; o backend
                        rejeita chaves inexistentes.
                      </InfoNotice>
                      <TextField
                        id="sport-icon"
                        label="Chave do ícone (icon_key)"
                        value={draft.icon}
                        onChange={(event) => updateDraft({ icon: event.target.value })}
                        error={errors["sport-icon"]}
                        hint="Ex.: icon-sport-futebol-5x5."
                        maxLength={64}
                        required
                      />
                    </>
                  ) : (
                    <SelectField
                      id="sport-icon"
                      label="Ícone"
                      value={draft.icon}
                      onChange={(event) => updateDraft({ icon: event.target.value })}
                      error={errors["sport-icon"]}
                      hint="Apenas ícones ativos do catálogo visual."
                      disabled={visualCatalogQuery.isPending}
                      required
                    >
                      <option value="">
                        {visualCatalogQuery.isPending
                          ? "Carregando ícones..."
                          : "Selecione um ícone"}
                      </option>
                      {selectedIconUnavailable ? (
                        <option value={draft.icon} disabled>
                          {draft.icon} (indisponível)
                        </option>
                      ) : null}
                      {iconOptions.map((item) => (
                        <option key={item.key} value={item.key}>
                          {item.name} — {item.key}
                        </option>
                      ))}
                    </SelectField>
                  )}
                </div>
                <TextField
                  id="sport-sort-order"
                  label="Ordem de exibição"
                  type="number"
                  min={0}
                  max={9999}
                  value={draft.sort_order}
                  onChange={(event) => updateDraft({ sort_order: event.target.value })}
                  error={errors["sport-sort-order"]}
                  hint="Menor número aparece primeiro."
                  required
                />
              </div>

              <fieldset className="fieldset">
                <legend>Formatos</legend>
                {errors["sport-formats"] ? (
                  <p className="field__error" role="alert">
                    {errors["sport-formats"]}
                  </p>
                ) : null}
                {draft.formats.map((format, index) => {
                  const teamSizeValue = Number(format.team_size);
                  const standard = isStandardTeamSize(teamSizeValue);
                  return (
                    <div key={index} className="format-editor">
                      <div className="format-editor__header">
                        <strong>Formato {index + 1}</strong>
                        {formMode !== "edit" && draft.formats.length > 1 ? (
                          <button
                            type="button"
                            className="button button--small button--ghost"
                            onClick={() => removeFormat(index)}
                          >
                            <TrashIcon size={15} />
                            Remover
                          </button>
                        ) : null}
                      </div>

                      {formMode === "edit" ? (
                        <p className="hint">
                          {format.in_use
                            ? "Formato em uso por reservas. Crie um novo formato para mudar o tamanho da equipe."
                            : "Edição de formato ainda não disponível."}
                        </p>
                      ) : null}

                      <div className="form-row form-row--three">
                        <TextField
                          id={`sport-format-${index}-name`}
                          label="Nome do formato"
                          value={format.name}
                          onChange={(event) => updateFormat(index, { name: event.target.value })}
                          error={errors[`sport-format-${index}-name`]}
                          maxLength={80}
                          disabled={formMode === "edit"}
                          required
                        />
                        <TextField
                          id={`sport-format-${index}-slug`}
                          label="Slug do formato"
                          value={format.slug}
                          onChange={(event) => updateFormat(index, { slug: event.target.value })}
                          error={errors[`sport-format-${index}-slug`]}
                          maxLength={40}
                          disabled={formMode === "edit"}
                          required
                        />
                        <TextField
                          id={`sport-format-${index}-team-size`}
                          label="Jogadores por equipe"
                          type="number"
                          min={1}
                          max={20}
                          value={format.team_size}
                          onChange={(event) =>
                            updateFormat(index, {
                              team_size: event.target.value,
                              pricing_mode: isStandardTeamSize(Number(event.target.value))
                                ? "standard"
                                : "",
                            })
                          }
                          error={errors[`sport-format-${index}-team-size`]}
                          hint="team_size"
                          disabled={formMode === "edit"}
                          required
                        />
                      </div>
                      <div className="form-row form-row--three">
                        <TextField
                          id={`sport-format-${index}-players`}
                          label="Total de jogadores"
                          value={
                            Number.isInteger(teamSizeValue) && teamSizeValue > 0
                              ? String(teamSizeValue * 2)
                              : ""
                          }
                          readOnly
                          hint="Equipe × 2."
                        />
                        <TextField
                          id={`sport-format-${index}-duration`}
                          label="Duração (min)"
                          type="number"
                          min={5}
                          max={240}
                          value={format.duration_minutes}
                          onChange={(event) =>
                            updateFormat(index, { duration_minutes: event.target.value })
                          }
                          error={errors[`sport-format-${index}-duration`]}
                          disabled={formMode === "edit"}
                          required
                        />
                        <TextField
                          id={`sport-format-${index}-periods`}
                          label="Períodos"
                          type="number"
                          min={1}
                          max={20}
                          value={format.periods}
                          onChange={(event) => updateFormat(index, { periods: event.target.value })}
                          error={errors[`sport-format-${index}-periods`]}
                          disabled={formMode === "edit"}
                          required
                        />
                      </div>
                      <div className="form-row">
                        <SelectField
                          id={`sport-format-${index}-score`}
                          label="Modelo de pontuação"
                          value={format.score_model}
                          onChange={(event) =>
                            updateFormat(index, { score_model: event.target.value })
                          }
                          error={errors[`sport-format-${index}-score`]}
                          hint="O backend aceita sets_points ou goals."
                          disabled={formMode === "edit"}
                          required
                        >
                          {SCORE_MODELS.map((model) => (
                            <option key={model.value} value={model.value}>
                              {model.label}
                            </option>
                          ))}
                        </SelectField>
                        <TextField
                          id={`sport-format-${index}-positions`}
                          label="Posições"
                          value={format.positions}
                          onChange={(event) =>
                            updateFormat(index, { positions: event.target.value })
                          }
                          error={errors[`sport-format-${index}-positions`]}
                          hint="Opcional. Separe por vírgula. Ex.: Goleiro, Fixo, Ala, Pivô."
                          maxLength={400}
                          disabled={formMode === "edit"}
                        />
                      </div>
                      {!standard && formMode !== "edit" ? (
                        <SelectField
                          id={`sport-format-${index}-mode`}
                          label="Modo de preço"
                          value={format.pricing_mode}
                          onChange={(event) =>
                            updateFormat(index, {
                              pricing_mode: event.target.value as AdminPricingMode | "",
                            })
                          }
                          error={errors[`sport-format-${index}-mode`]}
                          hint="Obrigatório para formatos fora de 3x3, 5x5 e 6x6."
                          required
                        >
                          <option value="">Selecione o modo</option>
                          <option value="standard">Padrão (20%)</option>
                          <option value="contingency">Contingência (sem 20%)</option>
                        </SelectField>
                      ) : null}
                      {formMode === "create" ? (
                        <FormatPricingPreview format={format} index={index} />
                      ) : null}
                    </div>
                  );
                })}
                {formMode !== "edit" ? (
                  <button
                    type="button"
                    className="button button--small"
                    onClick={addFormat}
                    disabled={draft.formats.length >= MAX_FORMATS}
                  >
                    <PlusIcon size={15} />
                    Adicionar formato
                  </button>
                ) : null}
              </fieldset>

              <TextareaField
                id="sport-reason"
                label="Motivo"
                value={draft.reason}
                onChange={(event) => updateDraft({ reason: event.target.value })}
                error={errors["sport-reason"]}
                hint="Obrigatório. Fica registrado na auditoria administrativa."
                maxLength={500}
                rows={3}
                required
              />

              {saveError ? (
                <ErrorNotice
                  message={adminErrorMessage(saveError)}
                  requestId={requestIdOf(saveError)}
                />
              ) : null}

              <div className="form-actions">
                <button type="button" className="button button--ghost" onClick={closeForm}>
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="button button--primary"
                  disabled={saveMutation.isPending || preflightPending}
                  aria-busy={saveMutation.isPending || preflightPending || undefined}
                >
                  {saveMutation.isPending || preflightPending
                    ? "Salvando..."
                    : formMode === "edit"
                      ? "Salvar alterações"
                      : "Criar esporte"}
                </button>
              </div>
            </form>
          </div>

          <aside className="card sport-preview" aria-label="Prévia de exibição">
            <SectionHeading
              title="Prévia de exibição"
              description="Aproximação do cartão exibido no app. O backend é a autoridade dos dados."
            />
            <div className="sport-preview__hero">
              <span className="sport-preview__icon" aria-hidden="true">
                {iconGlyph(draft.icon)}
              </span>
              <div>
                <strong>{draft.name || "Nome do esporte"}</strong>
                <small className="mono">{draft.slug || "slug"}</small>
                <small className="mono">{draft.icon || "icon_key"}</small>
              </div>
            </div>
            {draft.formats.map((format, index) => {
              const team = Number(format.team_size);
              const duration = Number(format.duration_minutes);
              const periods = Number(format.periods);
              const positions = parsePositions(format.positions);
              return (
                <div key={index} className="sport-preview__format">
                  <div className="sport-preview__format-heading">
                    <strong>{format.name || `Formato ${index + 1}`}</strong>
                    {format.score_model ? (
                      <span className="badge badge--info">{format.score_model}</span>
                    ) : null}
                  </div>
                  <small>
                    {Number.isInteger(team) && team > 0 ? (
                      <>
                        {team}x{team} · {team * 2} jogadores
                      </>
                    ) : (
                      "Equipe a definir"
                    )}
                    {Number.isFinite(duration) && duration > 0 ? ` · ${duration} min` : ""}
                    {Number.isFinite(periods) && periods > 0 ? ` · ${periods} período(s)` : ""}
                  </small>
                  {positions.length > 0 ? (
                    <div className="sport-preview__positions">
                      {positions.map((position) => (
                        <span key={position} className="badge badge--muted">
                          {position}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <small className="muted">Posições a definir.</small>
                  )}
                </div>
              );
            })}
          </aside>
        </section>
      ) : null}

      <section className="card">
        <SectionHeading
          title="Preço e tickets"
          description="Seis faixas, k sugerido, invariante e preço por jogador. O override exige motivo."
        />

        <InfoNotice>
          <p>
            Invariante: <code>k × R$ 3,10 × jogadores ≥ total do modo</code>. No modo padrão, o
            total é 20% acima do teto; na contingência, é o próprio teto. O backend é a autoridade.
          </p>
        </InfoNotice>

        <div className="toolbar">
          <TextField
            id="admin-pricing-team-size"
            label="Equipe para preço"
            className="field--compact"
            type="number"
            min={1}
            max={20}
            value={teamSizeInput}
            onChange={(event) => {
              const value = event.target.value;
              setTeamSizeInput(value);
              setPricingMode(isStandardTeamSize(Number(value)) ? "standard" : "");
            }}
            error={teamSizeValid ? null : "Informe um valor inteiro entre 1 e 20."}
            hint="3x3, 5x5 e 6x6 usam o modo padrão."
          />
          {!teamSizeStandard && teamSizeValid ? (
            <SelectField
              id="admin-pricing-mode"
              label="Modo de preço"
              className="field--compact"
              value={pricingMode}
              onChange={(event) => setPricingMode(event.target.value as AdminPricingMode | "")}
              error={pricingMode ? null : "Escolha explicitamente o modo de preço."}
              hint="Obrigatório para formatos fora de 3x3, 5x5 e 6x6."
              required
            >
              <option value="">Selecione o modo</option>
              <option value="standard">Padrão (20%)</option>
              <option value="contingency">Contingência (sem 20%)</option>
            </SelectField>
          ) : null}
        </div>

        {pricingQuery.error ? (
          isForbidden(pricingQuery.error) ? (
            <AdminForbiddenState />
          ) : (
            <ErrorNotice
              message={adminErrorMessage(pricingQuery.error)}
              requestId={requestIdOf(pricingQuery.error)}
              onRetry={() => void pricingQuery.refetch()}
            />
          )
        ) : !teamSizeValid || !effectivePricingMode ? (
          <EmptyState title="Escolha o formato">
            Informe o tamanho de equipe e, quando necessário, o modo de preço.
          </EmptyState>
        ) : pricingQuery.isPending ? (
          <SkeletonList rows={6} label="Carregando faixas..." />
        ) : bands.length === 0 ? (
          <EmptyState title="Nenhuma faixa configurada">
            A API não devolveu faixas para este formato.
          </EmptyState>
        ) : (
          <div className="pricing-table-wrap">
            <table className="pricing-table">
              <caption className="sr-only">
                Faixas de preço, k sugerido, preço por jogador e invariante
              </caption>
              <thead>
                <tr>
                  <th scope="col">Faixa</th>
                  <th scope="col">Teto</th>
                  <th scope="col">k sugerido</th>
                  <th scope="col">Por jogador</th>
                  <th scope="col">Invariante</th>
                  <th scope="col">Ação</th>
                </tr>
              </thead>
              <tbody>
                {bands.map((band) => (
                  <tr key={band.code}>
                    <th scope="row">
                      <strong>{band.label}</strong>
                      <small className="mono">{band.code}</small>
                    </th>
                    <td>{formatMoney(band.max_price_cents)}</td>
                    <td>{band.tickets}</td>
                    <td>{formatMoney(band.player_price_cents)}</td>
                    <td>
                      <span
                        className={
                          band.invariant_ok ? "badge badge--success" : "badge badge--danger"
                        }
                      >
                        {band.invariant_ok ? "Cobre" : "Viola"}
                      </span>
                      <small className="muted">
                        mín.{" "}
                        {minimumTickets(
                          band.max_price_cents,
                          teamSizeNumber,
                          effectivePricingMode as AdminPricingMode,
                        )}
                      </small>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="button button--small button--ghost"
                        onClick={() => openPricing(band)}
                      >
                        Ajustar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <ReasonDialog
        open={Boolean(statusTarget)}
        title={statusTarget?.action === "activate" ? "Publicar esporte" : "Desativar esporte"}
        description={
          statusTarget?.action === "activate"
            ? "A modalidade volta a aparecer no catálogo quando o preço estiver configurado. O motivo é obrigatório."
            : "A modalidade deixa de aparecer no catálogo. O histórico é preservado. O motivo é obrigatório."
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
        confirmLabel={
          statusTarget?.action === "activate" ? "Publicar esporte" : "Desativar esporte"
        }
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
            <strong>{statusTarget.sport.name}</strong>
            <span className="mono">{statusTarget.sport.slug}</span>
          </div>
        ) : null}
        {statusError ? (
          <ErrorNotice
            message={adminErrorMessage(statusError)}
            requestId={requestIdOf(statusError)}
          />
        ) : null}
      </ReasonDialog>

      <ReasonDialog
        open={Boolean(pricingTarget)}
        title="Ajustar tickets da faixa"
        description={
          pricingTarget
            ? `${pricingTarget.band.label} · ${pricingTarget.teamSize}x${pricingTarget.teamSize} · ${
                pricingTarget.mode === "standard" ? "padrão (20%)" : "contingência (sem 20%)"
              }`
            : undefined
        }
        label="Motivo do override"
        value={pricingReason}
        onChange={(value) => {
          setPricingReason(value);
          if (pricingReasonError) setPricingReasonError(null);
        }}
        error={pricingReasonError}
        maxLength={500}
        minLength={3}
        confirmLabel="Salvar tickets"
        busy={pricingMutation.isPending}
        confirmDisabled={Boolean(pricingTicketsError)}
        onConfirm={confirmPricing}
        onClose={() => {
          if (pricingMutation.isPending) return;
          setPricingTarget(null);
          setTicketsInput("");
          setPricingReason("");
          setPricingReasonError(null);
          setPricingError(null);
        }}
      >
        {pricingTarget ? (
          <>
            <div className="dialog-summary">
              <strong>{pricingTarget.band.label}</strong>
              <span>
                Teto {formatMoney(pricingTarget.band.max_price_cents)} · total exigido por jogador{" "}
                {formatMoney(
                  Math.ceil(
                    requiredTotalCents(pricingTarget.band.max_price_cents, pricingTarget.mode) /
                      (pricingTarget.teamSize * 2),
                  ),
                )}
              </span>
            </div>
            <TextField
              id="pricing-tickets"
              label="Tickets por jogador (k)"
              type="number"
              min={1}
              max={1000}
              value={ticketsInput}
              onChange={(event) => setTicketsInput(event.target.value)}
              error={pricingTicketsError}
              hint={`Mínimo ${pricingTarget.band.tickets}. Preço por jogador: ${formatMoney(
                Math.max(0, pricingTickets) * 310,
              )}.`}
              required
            />
            <p className="hint">
              Invariante: {Math.max(0, pricingTickets)} × R$ 3,10 × {pricingTarget.teamSize * 2} ≥{" "}
              {formatMoney(
                requiredTotalCents(pricingTarget.band.max_price_cents, pricingTarget.mode),
              )}
              .
            </p>
          </>
        ) : null}
        {pricingError ? (
          <ErrorNotice
            message={adminErrorMessage(pricingError)}
            requestId={requestIdOf(pricingError)}
          />
        ) : null}
      </ReasonDialog>
    </>
  );
}
