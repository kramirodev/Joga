import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorNotice, InfoNotice, SkeletonList } from "../../components/Feedback";
import { SelectField, TextField } from "../../components/ui/Field";
import { BuildingIcon, MapPinIcon, PlusIcon, SearchIcon } from "../../components/ui/Icons";
import { ConfirmDialog } from "../../components/ui/Modal";
import { SectionHeading } from "../../components/ui/PageHeader";
import { useToast } from "../../components/ui/toast-context";
import { api } from "../../lib/api";
import { cepError, formatCep, normalizeCep } from "../../lib/cep";
import { formatError, precisionLabel, requestIdOf } from "../../lib/format";
import { queryKeys } from "../../lib/query";
import { coordinateError, normalizeWhitespace, textError } from "../../lib/validation";
import type { GeocodingPrecision, Organization, Venue } from "../../types";

const TIMEZONES = [
  { value: "America/Sao_Paulo", label: "Brasília / Sudeste (GMT-3)" },
  { value: "America/Manaus", label: "Manaus (GMT-4)" },
  { value: "America/Cuiaba", label: "Cuiabá (GMT-4)" },
  { value: "America/Campo_Grande", label: "Campo Grande (GMT-4)" },
  { value: "America/Belem", label: "Belém (GMT-3)" },
  { value: "America/Fortaleza", label: "Fortaleza (GMT-3)" },
  { value: "America/Recife", label: "Recife (GMT-3)" },
  { value: "America/Bahia", label: "Salvador (GMT-3)" },
  { value: "America/Rio_Branco", label: "Rio Branco (GMT-5)" },
  { value: "America/Noronha", label: "Fernando de Noronha (GMT-2)" },
];

const initialForm = {
  name: "",
  cep: "",
  number: "",
  city: "",
  state: "",
  address: "",
  latitude: "",
  longitude: "",
  timezone: "America/Sao_Paulo",
};

export function VenuesPanel({
  organization,
  venues,
  loading,
  error,
  onRetry,
}: {
  organization: Organization;
  venues: Venue[];
  loading: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState<unknown>(null);
  const [statusTarget, setStatusTarget] = useState<Venue | null>(null);
  const [appliedLookup, setAppliedLookup] = useState<{
    postalCode: string;
    latitude: string;
    longitude: string;
    source: string;
    precision: Exclude<GeocodingPrecision, "unresolved">;
  } | null>(null);

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.venues(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.audit(organization.id) }),
    ]);
  };

  const createVenueMutation = useMutation({
    mutationFn: () => {
      const postalCode = normalizeCep(form.cep) ? formatCep(form.cep) : null;
      const unchangedLookup =
        appliedLookup !== null &&
        appliedLookup.postalCode === normalizeCep(form.cep) &&
        appliedLookup.latitude === form.latitude.trim() &&
        appliedLookup.longitude === form.longitude.trim();
      return api.createVenue(organization.id, {
        name: normalizeWhitespace(form.name),
        city: form.city.trim() ? normalizeWhitespace(form.city) : null,
        state: form.state.trim() ? form.state.trim().toUpperCase() : null,
        address_line: form.address.trim() ? normalizeWhitespace(form.address) : null,
        latitude: Number(form.latitude.replace(",", ".")),
        longitude: Number(form.longitude.replace(",", ".")),
        postal_code: postalCode,
        ...(unchangedLookup && appliedLookup
          ? {
              geocoding_source: appliedLookup.source,
              geocoding_precision: appliedLookup.precision,
            }
          : {}),
        timezone: form.timezone,
      });
    },
    onSuccess: async () => {
      setForm(initialForm);
      setErrors({});
      setActionError(null);
      setAppliedLookup(null);
      lookupCepMutation.reset();
      toast.push({
        title: "Estabelecimento cadastrado",
        description: "Agora cadastre quadras, modalidades, preços e expediente.",
      });
      await invalidate();
    },
    onError: (caught) => setActionError(caught),
  });

  const lookupCepMutation = useMutation({
    mutationFn: () => api.lookupPostalCode(form.cep, form.number),
    onSuccess: (result) => {
      const street = result.street?.trim() ?? "";
      const number = form.number.trim();
      const address = street ? [street, number].filter(Boolean).join(", ") : "";
      setForm((current) => ({
        ...current,
        city: result.city || current.city,
        state: result.state || current.state,
        address: address || current.address,
        latitude: result.latitude === null ? "" : String(result.latitude),
        longitude: result.longitude === null ? "" : String(result.longitude),
      }));
      const precision = result.precision;
      if (precision !== "unresolved" && result.latitude !== null && result.longitude !== null) {
        setAppliedLookup({
          postalCode: normalizeCep(form.cep),
          latitude: String(result.latitude),
          longitude: String(result.longitude),
          source: result.source,
          precision,
        });
      } else {
        setAppliedLookup(null);
      }
      setErrors((current) => ({
        ...current,
        cep: "",
        city: "",
        state: "",
        latitude: "",
        longitude: "",
      }));
    },
  });

  const toggleVenueMutation = useMutation({
    mutationFn: (venue: Venue) =>
      api.updateVenue(organization.id, venue.id, {
        status: venue.status === "active" ? "inactive" : "active",
      }),
    onSuccess: async (_result, venue) => {
      setStatusTarget(null);
      toast.push({
        title: venue.status === "active" ? "Estabelecimento desativado" : "Estabelecimento ativado",
        description:
          venue.status === "active"
            ? "Ele deixa de aparecer como opção ativa na descoberta do JOGA."
            : "Ele volta a ficar disponível para as operações do JOGA.",
      });
      await invalidate();
    },
    onError: (caught) => {
      setActionError(caught);
      setStatusTarget(null);
      toast.push({
        title: "Não foi possível alterar o estabelecimento",
        description: formatError(caught),
        tone: "error",
        requestId: requestIdOf(caught),
      });
    },
  });

  function update(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    if (errors[field]) setErrors((current) => ({ ...current, [field]: "" }));
  }

  function lookupCep() {
    const validation = cepError(form.cep);
    if (validation) {
      setErrors((current) => ({ ...current, cep: validation }));
      document.getElementById("venue-cep")?.focus();
      return;
    }
    lookupCepMutation.mutate();
  }

  function createVenue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: Record<string, string> = {};
    const name = textError(form.name, { label: "o nome do estabelecimento", min: 2, max: 120 });
    if (name) next.name = name;
    if (form.city.trim().length > 120) next.city = "A cidade deve ter no máximo 120 caracteres.";
    if (form.state.trim() && !/^[A-Za-z]{2}$/.test(form.state.trim())) {
      next.state = "Informe a UF com duas letras. Ex.: RJ.";
    }
    if (form.address.trim().length > 200) {
      next.address = "O endereço deve ter no máximo 200 caracteres.";
    }
    if (form.cep.trim()) {
      const cep = cepError(form.cep);
      if (cep) next.cep = cep;
    }
    if (form.number.trim().length > 20) {
      next.number = "O número deve ter no máximo 20 caracteres.";
    }
    const coordinates = coordinateError(form.latitude, form.longitude);
    if (coordinates.latitude) next.latitude = coordinates.latitude;
    if (coordinates.longitude) next.longitude = coordinates.longitude;
    if (Object.keys(next).length > 0) {
      setErrors(next);
      const first = [
        "name",
        "cep",
        "number",
        "city",
        "state",
        "address",
        "latitude",
        "longitude",
      ].find((field) => next[field]);
      if (first) document.getElementById(`venue-${first}`)?.focus();
      return;
    }
    createVenueMutation.mutate();
  }

  const displayError = error ?? actionError;
  const lookup = lookupCepMutation.data;
  const lookupAddress = lookup
    ? [lookup.street, lookup.neighborhood, [lookup.city, lookup.state].filter(Boolean).join("/")]
        .filter(Boolean)
        .join(" · ")
    : "";

  return (
    <section className="stack">
      <div className="card">
        <SectionHeading
          title="Estabelecimentos"
          description="Perfil comercial vinculado a esta organização. Quadras, agenda, preços e cobertura são geridos na página de cada estabelecimento."
        />
        {displayError ? (
          <ErrorNotice
            message={formatError(displayError)}
            requestId={requestIdOf(displayError)}
            onRetry={onRetry}
          />
        ) : null}
        {loading ? (
          <SkeletonList rows={2} label="Carregando estabelecimentos..." />
        ) : venues.length === 0 ? (
          <EmptyState
            title="Nenhum estabelecimento"
            icon={<BuildingIcon size={28} />}
            action={
              <button
                type="button"
                className="button button--primary"
                onClick={() => document.getElementById("venue-name")?.focus()}
              >
                <PlusIcon size={16} />
                Cadastrar primeiro estabelecimento
              </button>
            }
          >
            Cadastre o primeiro perfil comercial para abrir quadras, agenda e reservas.
          </EmptyState>
        ) : (
          <ul className="venue-list">
            {venues.map((venue) => (
              <li key={venue.id} className="venue-row">
                <div className="venue-row__identity">
                  <span className="venue-row__icon" aria-hidden="true">
                    <BuildingIcon size={19} />
                  </span>
                  <div>
                    <strong>{venue.name}</strong>
                    <small>
                      <MapPinIcon size={13} />
                      {[venue.city, venue.state].filter(Boolean).join(" · ") ||
                        "Local não informado"}
                      {venue.address_line ? ` · ${venue.address_line}` : ""}
                    </small>
                    {venue.postal_code ? (
                      <small>
                        CEP {formatCep(venue.postal_code)}
                        {venue.geocoding_precision
                          ? ` · ${precisionLabel(venue.geocoding_precision)}`
                          : ""}
                      </small>
                    ) : null}
                    <small>Fuso {venue.timezone}</small>
                  </div>
                </div>
                <div className="venue-row__actions">
                  <span
                    className={
                      venue.status === "active" ? "badge badge--active" : "badge badge--muted"
                    }
                  >
                    {venue.status === "active" ? "Ativo" : "Inativo"}
                  </span>
                  <Link
                    className="button button--small button--primary"
                    to={`/organizations/${organization.id}/venues/${venue.id}`}
                  >
                    Quadras e agenda
                  </Link>
                  <button
                    type="button"
                    className="button button--small"
                    onClick={() => {
                      if (venue.status === "active") setStatusTarget(venue);
                      else toggleVenueMutation.mutate(venue);
                    }}
                    disabled={toggleVenueMutation.isPending}
                  >
                    {venue.status === "active" ? "Desativar" : "Ativar"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card card--form">
        <SectionHeading
          title="Novo estabelecimento"
          description="Informe o CEP para preencher endereço e coordenadas automaticamente. A precisão do CEP é de logradouro, então confira o ponto antes de salvar."
        />
        <form className="form" onSubmit={createVenue} noValidate>
          <TextField
            id="venue-name"
            label="Nome"
            value={form.name}
            onChange={(event) => update("name", event.target.value)}
            error={errors.name}
            hint="De 2 a 120 caracteres. Ex.: Arena Tijuca."
            maxLength={120}
            placeholder="Ex.: Arena Tijuca"
            autoComplete="organization"
            required
          />
          <div className="form-row">
            <TextField
              id="venue-cep"
              label="CEP"
              value={formatCep(form.cep)}
              onChange={(event) => update("cep", normalizeCep(event.target.value))}
              error={errors.cep}
              hint="Opcional. Preenche endereço e coordenadas."
              maxLength={9}
              inputMode="numeric"
              autoComplete="postal-code"
              placeholder="20541-004"
            />
            <TextField
              id="venue-number"
              label="Número"
              value={form.number}
              onChange={(event) => update("number", event.target.value)}
              error={errors.number}
              hint="Opcional. Ajuda a precisar o ponto."
              maxLength={20}
              placeholder="1200"
              inputClassName="input--short"
            />
          </div>
          <div className="form-actions">
            <button
              type="button"
              className="button button--small button--ghost"
              onClick={lookupCep}
              disabled={lookupCepMutation.isPending}
              aria-busy={lookupCepMutation.isPending || undefined}
            >
              <SearchIcon size={16} />
              {lookupCepMutation.isPending ? "Buscando..." : "Buscar CEP"}
            </button>
            <span className="field__hint">
              Preenche cidade, UF, endereço e coordenadas a partir do CEP.
            </span>
          </div>

          {lookupCepMutation.isSuccess && lookup ? (
            <InfoNotice>
              <p>
                <strong>{lookupAddress || "Endereço localizado pelo CEP."}</strong>
              </p>
              <p>
                Precisão: {precisionLabel(lookup.precision)}.
                {lookup.precision === "unresolved"
                  ? " O CEP foi localizado sem coordenada; informe latitude e longitude abaixo."
                  : " Confira o endereço e ajuste as coordenadas se necessário."}
              </p>
            </InfoNotice>
          ) : null}

          {lookupCepMutation.error ? (
            <ErrorNotice
              message={formatError(lookupCepMutation.error)}
              requestId={requestIdOf(lookupCepMutation.error)}
              onRetry={() => lookupCepMutation.mutate()}
            />
          ) : null}

          <div className="form-row">
            <TextField
              id="venue-city"
              label="Cidade"
              value={form.city}
              onChange={(event) => update("city", event.target.value)}
              error={errors.city}
              hint="Opcional."
              maxLength={120}
              placeholder="Rio de Janeiro"
              autoComplete="address-level2"
            />
            <TextField
              id="venue-state"
              label="UF"
              value={form.state}
              onChange={(event) =>
                update("state", event.target.value.replace(/[^a-zA-Z]/g, "").toUpperCase())
              }
              error={errors.state}
              hint="Opcional. Duas letras."
              maxLength={2}
              placeholder="RJ"
              autoComplete="address-level1"
              inputClassName="input--short"
            />
          </div>
          <TextField
            id="venue-address"
            label="Endereço"
            value={form.address}
            onChange={(event) => update("address", event.target.value)}
            error={errors.address}
            hint="Rua, número e complemento. Opcional, mas recomendado."
            maxLength={200}
            placeholder="Rua das Laranjeiras, 123"
            autoComplete="street-address"
          />
          <div className="form-row">
            <TextField
              id="venue-latitude"
              label="Latitude"
              value={form.latitude}
              onChange={(event) => update("latitude", event.target.value)}
              error={errors.latitude}
              hint="Preenchida pelo CEP. Ajuste se necessário."
              inputMode="decimal"
              placeholder="-22.934"
              required
            />
            <TextField
              id="venue-longitude"
              label="Longitude"
              value={form.longitude}
              onChange={(event) => update("longitude", event.target.value)}
              error={errors.longitude}
              hint="Preenchida pelo CEP. Ajuste se necessário."
              inputMode="decimal"
              placeholder="-43.201"
              required
            />
          </div>
          <p className="field__hint">
            Se precisar ajustar, copie as coordenadas do ponto exato em um mapa. Elas são usadas na
            descoberta de quadras do aplicativo.
          </p>
          <SelectField
            id="venue-timezone"
            label="Fuso horário"
            value={form.timezone}
            onChange={(event) => update("timezone", event.target.value)}
            hint="Usado para prazos, agenda e horários exibidos aos jogadores."
          >
            {TIMEZONES.map((timezone) => (
              <option key={timezone.value} value={timezone.value}>
                {timezone.label}
              </option>
            ))}
          </SelectField>
          <button
            type="submit"
            className="button button--primary"
            disabled={createVenueMutation.isPending}
            aria-busy={createVenueMutation.isPending || undefined}
          >
            {createVenueMutation.isPending ? "Cadastrando..." : "Cadastrar estabelecimento"}
          </button>
        </form>
      </div>

      <ConfirmDialog
        open={Boolean(statusTarget)}
        title="Desativar estabelecimento?"
        description={
          statusTarget
            ? `${statusTarget.name} deixa de aparecer como opção ativa na descoberta. Reservas já confirmadas não são canceladas por esta ação.`
            : undefined
        }
        tone="danger"
        confirmLabel="Desativar"
        busy={toggleVenueMutation.isPending}
        onConfirm={() => {
          if (statusTarget) toggleVenueMutation.mutate(statusTarget);
        }}
        onClose={() => setStatusTarget(null)}
      >
        {toggleVenueMutation.error ? (
          <ErrorNotice
            message={formatError(toggleVenueMutation.error)}
            requestId={requestIdOf(toggleVenueMutation.error)}
          />
        ) : null}
      </ConfirmDialog>
    </section>
  );
}
