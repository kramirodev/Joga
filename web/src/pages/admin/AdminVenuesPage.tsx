import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { EmptyState, ErrorNotice, SkeletonList } from "../../components/Feedback";
import { CheckboxField, SelectField, TextField } from "../../components/ui/Field";
import { BuildingIcon, SearchIcon } from "../../components/ui/Icons";
import { ReasonDialog } from "../../components/ui/Modal";
import { PageHeader, SectionHeading } from "../../components/ui/PageHeader";
import { Pagination } from "../../components/ui/Pagination";
import { useToast } from "../../components/ui/toast-context";
import { adminErrorMessage, isForbidden } from "../../lib/admin";
import { ApiError, api } from "../../lib/api";
import { formatDay, organizationStatusLabel, requestIdOf } from "../../lib/format";
import { queryKeys } from "../../lib/query";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { digitsOnly, normalizeWhitespace, textError } from "../../lib/validation";
import type { AdminVenue, AdminVenueUpdatePayload } from "../../types";
import { AdminForbiddenState } from "./AdminShared";

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  { value: "", label: "Todos os status" },
  { value: "active", label: "Ativas" },
  { value: "inactive", label: "Inativas" },
];

const VISIBILITY_OPTIONS = [
  { value: "", label: "Públicas e privadas" },
  { value: "true", label: "Somente públicas" },
  { value: "false", label: "Somente privadas" },
];

type StatusAction = "suspend" | "reactivate";

interface StatusTarget {
  venue: AdminVenue;
  action: StatusAction;
}

interface EditDraft {
  name: string;
  city: string;
  state: string;
  address_line: string;
  postal_code: string;
  latitude: string;
  longitude: string;
  is_public: boolean;
}

function editDraftFrom(venue: AdminVenue): EditDraft {
  return {
    name: venue.name,
    city: venue.city ?? "",
    state: venue.state ?? "",
    address_line: venue.address_line ?? "",
    postal_code: venue.postal_code ?? "",
    latitude: venue.latitude === null ? "" : String(venue.latitude),
    longitude: venue.longitude === null ? "" : String(venue.longitude),
    is_public: venue.is_public,
  };
}

function venueErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 404) {
    return "Quadra não encontrada. Atualize a lista e tente novamente.";
  }
  return adminErrorMessage(error);
}

function coordinateValue(value: string): number {
  return Number(value.replace(",", "."));
}

function spacesLabel(venue: AdminVenue): string {
  if (venue.spaces_count === 0) return "Nenhum espaço";
  return `${venue.active_spaces_count} de ${venue.spaces_count} ${
    venue.spaces_count === 1 ? "espaço ativo" : "espaços ativos"
  }`;
}

function validateEditDraft(draft: EditDraft): Record<string, string> {
  const errors: Record<string, string> = {};

  const nameError = textError(draft.name, { label: "o nome da quadra", min: 2, max: 120 });
  if (nameError) errors["venue-edit-name"] = nameError;

  if (draft.city.trim()) {
    const cityError = textError(draft.city, { label: "a cidade", min: 2, max: 120 });
    if (cityError) errors["venue-edit-city"] = cityError;
  }

  if (draft.state.trim() && !/^[A-Za-z]{2}$/.test(draft.state.trim())) {
    errors["venue-edit-state"] = "Informe a UF com duas letras.";
  }

  if (draft.address_line.trim()) {
    const addressError = textError(draft.address_line, {
      label: "o endereço",
      min: 5,
      max: 200,
    });
    if (addressError) errors["venue-edit-address"] = addressError;
  }

  const postalCode = digitsOnly(draft.postal_code);
  if (postalCode && postalCode.length !== 8) {
    errors["venue-edit-postal-code"] = "CEP inválido. Informe os oito dígitos.";
  }

  const latitude = draft.latitude.trim();
  const longitude = draft.longitude.trim();
  if (Boolean(latitude) !== Boolean(longitude)) {
    errors["venue-edit-geocoding"] = "Preencha latitude e longitude juntas.";
  }
  if (latitude) {
    const value = coordinateValue(latitude);
    if (!Number.isFinite(value) || value < -90 || value > 90) {
      errors["venue-edit-latitude"] = "Latitude deve estar entre -90 e 90.";
    }
  }
  if (longitude) {
    const value = coordinateValue(longitude);
    if (!Number.isFinite(value) || value < -180 || value > 180) {
      errors["venue-edit-longitude"] = "Longitude deve estar entre -180 e 180.";
    }
  }

  return errors;
}

function updatePayloadFrom(draft: EditDraft, reason: string): AdminVenueUpdatePayload {
  const payload: AdminVenueUpdatePayload = {
    reason,
    is_public: draft.is_public,
  };

  const name = normalizeWhitespace(draft.name);
  if (name) payload.name = name;

  const city = normalizeWhitespace(draft.city);
  if (city) payload.city = city;

  const state = draft.state.trim().toUpperCase();
  if (state) payload.state = state;

  const address = normalizeWhitespace(draft.address_line);
  if (address) payload.address_line = address;

  const postalCode = digitsOnly(draft.postal_code);
  if (postalCode) payload.postal_code = postalCode;

  const latitude = draft.latitude.trim();
  if (latitude) payload.latitude = coordinateValue(latitude);

  const longitude = draft.longitude.trim();
  if (longitude) payload.longitude = coordinateValue(longitude);

  return payload;
}

export function AdminVenuesPage() {
  useDocumentTitle("Quadras");
  const queryClient = useQueryClient();
  const toast = useToast();

  const [queryDraft, setQueryDraft] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [visibility, setVisibility] = useState("");
  const [page, setPage] = useState(1);

  const [statusTarget, setStatusTarget] = useState<StatusTarget | null>(null);
  const [statusReason, setStatusReason] = useState("");
  const [statusReasonError, setStatusReasonError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<unknown>(null);

  const [editTarget, setEditTarget] = useState<AdminVenue | null>(null);
  const [editDraft, setEditDraft] = useState<EditDraft | null>(null);
  const [editReason, setEditReason] = useState("");
  const [editErrors, setEditErrors] = useState<Record<string, string>>({});
  const [editError, setEditError] = useState<unknown>(null);

  const venuesQuery = useQuery({
    queryKey: queryKeys.adminVenueDirectory(query, status, visibility, page),
    queryFn: () =>
      api.listAdminVenues({
        q: query || undefined,
        status: status === "active" || status === "inactive" ? status : undefined,
        is_public: visibility === "" ? undefined : visibility === "true",
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  const venues = venuesQuery.data?.venues ?? [];
  const total = venuesQuery.data?.total ?? 0;
  const pageSize = venuesQuery.data?.page_size ?? PAGE_SIZE;
  const currentPage = venuesQuery.data?.page ?? page;
  const hasFilters = query !== "" || status !== "" || visibility !== "";

  const statusMutation = useMutation({
    mutationFn: (input: StatusTarget & { reason: string }) =>
      input.action === "suspend"
        ? api.suspendAdminVenue(input.venue.id, input.reason)
        : api.reactivateAdminVenue(input.venue.id, input.reason),
    onSuccess: async (_venue, input) => {
      setStatusTarget(null);
      setStatusReason("");
      setStatusReasonError(null);
      setStatusError(null);
      toast.push({
        title: input.action === "suspend" ? "Quadra suspensa" : "Quadra reativada",
        description:
          input.action === "suspend"
            ? "A quadra saiu da descoberta e não aceita novas reservas. Reservas existentes, histórico e valores continuam preservados."
            : "A quadra voltou a aparecer na descoberta e a aceitar novas reservas.",
      });
      await queryClient.invalidateQueries({ queryKey: ["admin", "venues"] });
    },
    onError: (caught) => setStatusError(caught),
  });

  const editMutation = useMutation({
    mutationFn: (input: { venue: AdminVenue; payload: AdminVenueUpdatePayload }) =>
      api.updateAdminVenue(input.venue.id, input.payload),
    onSuccess: async () => {
      setEditTarget(null);
      setEditDraft(null);
      setEditReason("");
      setEditErrors({});
      setEditError(null);
      toast.push({
        title: "Quadra atualizada",
        description: "Os dados cadastrais foram salvos. A alteração ficou registrada na auditoria.",
      });
      await queryClient.invalidateQueries({ queryKey: ["admin", "venues"] });
    },
    onError: (caught) => setEditError(caught),
  });

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuery(queryDraft.trim());
    setPage(1);
  }

  function clearFilters() {
    setQueryDraft("");
    setQuery("");
    setStatus("");
    setVisibility("");
    setPage(1);
  }

  function openStatus(venue: AdminVenue, action: StatusAction) {
    statusMutation.reset();
    setStatusTarget({ venue, action });
    setStatusReason("");
    setStatusReasonError(null);
    setStatusError(null);
  }

  function closeStatus() {
    if (statusMutation.isPending) return;
    setStatusTarget(null);
    setStatusReason("");
    setStatusReasonError(null);
    setStatusError(null);
    statusMutation.reset();
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
      venue: statusTarget.venue,
      action: statusTarget.action,
      reason: statusReason.trim(),
    });
  }

  function openEdit(venue: AdminVenue) {
    editMutation.reset();
    setEditTarget(venue);
    setEditDraft(editDraftFrom(venue));
    setEditReason("");
    setEditErrors({});
    setEditError(null);
  }

  function closeEdit() {
    if (editMutation.isPending) return;
    setEditTarget(null);
    setEditDraft(null);
    setEditReason("");
    setEditErrors({});
    setEditError(null);
    editMutation.reset();
  }

  function updateEditDraft(patch: Partial<EditDraft>) {
    setEditDraft((current) => (current ? { ...current, ...patch } : current));
    setEditErrors({});
  }

  function focusFirstEditError(errors: Record<string, string>) {
    const first = Object.keys(errors)[0];
    if (!first) return;
    if (first === "venue-edit-geocoding") {
      document.getElementById("venue-edit-latitude")?.focus();
      return;
    }
    if (first === "reason") {
      document.querySelector<HTMLElement>("[data-autofocus]")?.focus();
      return;
    }
    document.getElementById(first)?.focus();
  }

  function saveEdit() {
    if (!editTarget || !editDraft || editMutation.isPending) return;
    const errors = validateEditDraft(editDraft);
    const reasonError = textError(editReason, { label: "o motivo", min: 3, max: 500 });
    if (reasonError) errors.reason = reasonError;
    if (Object.keys(errors).length > 0) {
      setEditErrors(errors);
      focusFirstEditError(errors);
      return;
    }
    setEditErrors({});
    editMutation.mutate({
      venue: editTarget,
      payload: updatePayloadFrom(editDraft, editReason.trim()),
    });
  }

  return (
    <>
      <PageHeader
        eyebrow="JOGA y ADMINISTRAÇÃO"
        title="Quadras"
        description="Consulte as quadras de todas as organizações, suspenda ou reative com motivo e corrija dados cadastrais. As ações preservam reservas, histórico e valores."
      />

      <section className="card">
        <SectionHeading
          title="Todas as quadras"
          description="A busca considera nome, cidade e endereço. A suspensão vale imediatamente para a descoberta e para novas reservas."
        />

        <form className="filters-form filters-form--venues" role="search" onSubmit={submitSearch}>
          <TextField
            id="admin-venues-search"
            label="Buscar"
            type="search"
            value={queryDraft}
            onChange={(event) => setQueryDraft(event.target.value)}
            placeholder="Nome, cidade ou endereço"
            maxLength={120}
          />
          <SelectField
            id="admin-venues-status"
            label="Status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </SelectField>
          <SelectField
            id="admin-venues-visibility"
            label="Visibilidade"
            value={visibility}
            onChange={(event) => {
              setVisibility(event.target.value);
              setPage(1);
            }}
          >
            {VISIBILITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </SelectField>
          <div className="filters-form__actions">
            <button type="submit" className="button button--small">
              <SearchIcon size={15} />
              Buscar
            </button>
            <button
              type="button"
              className="button button--small button--ghost"
              onClick={clearFilters}
              disabled={!hasFilters && !queryDraft}
            >
              Limpar filtros
            </button>
          </div>
        </form>

        {venuesQuery.error ? (
          isForbidden(venuesQuery.error) ? (
            <AdminForbiddenState />
          ) : (
            <ErrorNotice
              message={venueErrorMessage(venuesQuery.error)}
              requestId={requestIdOf(venuesQuery.error)}
              onRetry={() => void venuesQuery.refetch()}
            />
          )
        ) : venuesQuery.isPending ? (
          <SkeletonList rows={5} label="Carregando quadras..." />
        ) : venues.length === 0 ? (
          <EmptyState title="Nenhuma quadra encontrada" icon={<BuildingIcon size={28} />}>
            {hasFilters
              ? "Ajuste os filtros ou limpe a busca para ver outras quadras."
              : "Quando uma organização cadastrar uma quadra, ela aparece aqui para moderação."}
          </EmptyState>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table admin-table--venues">
              <caption className="sr-only">
                Quadras de todas as organizações, com status, visibilidade, espaços e ações de
                moderação
              </caption>
              <thead>
                <tr>
                  <th scope="col">Quadra</th>
                  <th scope="col">Organização</th>
                  <th scope="col">Status</th>
                  <th scope="col">Pública</th>
                  <th scope="col" className="admin-table__hide-medium">
                    Espaços
                  </th>
                  <th scope="col" className="admin-table__hide-medium">
                    Criada em
                  </th>
                  <th scope="col">
                    <span className="sr-only">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {venues.map((venue) => {
                  const active = venue.status === "active";
                  return (
                    <tr key={venue.id}>
                      <th scope="row" data-label="Quadra">
                        <span className="admin-table__cell">
                          <strong>{venue.name}</strong>
                          <small>
                            {venue.city ?? "Cidade não informada"}
                            {venue.state ? `/${venue.state}` : ""}
                          </small>
                        </span>
                      </th>
                      <td data-label="Organização">
                        <span className="admin-table__cell">
                          <strong>{venue.organization_name || "Organização não informada"}</strong>
                          <small>
                            {venue.organization_is_platform
                              ? "Plataforma"
                              : `Organização ${organizationStatusLabel(venue.organization_status).toLowerCase()}`}
                          </small>
                        </span>
                      </td>
                      <td data-label="Status">
                        <span className="admin-table__cell">
                          <span className={active ? "badge badge--success" : "badge badge--muted"}>
                            {active ? "Ativa" : "Inativa"}
                          </span>
                        </span>
                      </td>
                      <td data-label="Pública">
                        <span className="admin-table__cell">
                          <span
                            className={venue.is_public ? "badge badge--info" : "badge badge--muted"}
                          >
                            {venue.is_public ? "Pública" : "Privada"}
                          </span>
                        </span>
                      </td>
                      <td data-label="Espaços" className="admin-table__hide-medium">
                        <span className="admin-table__cell">{spacesLabel(venue)}</span>
                      </td>
                      <td data-label="Criada em" className="admin-table__hide-medium">
                        <span className="admin-table__cell">{formatDay(venue.created_at)}</span>
                      </td>
                      <td data-label="Ações" className="admin-table__actions">
                        <div className="sport-row__actions">
                          {active ? (
                            <button
                              type="button"
                              className="button button--small button--danger"
                              onClick={() => openStatus(venue, "suspend")}
                              disabled={statusMutation.isPending}
                              aria-label={`Suspender ${venue.name}`}
                            >
                              Suspender
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="button button--small button--primary"
                              onClick={() => openStatus(venue, "reactivate")}
                              disabled={statusMutation.isPending}
                              aria-label={`Reativar ${venue.name}`}
                            >
                              Reativar
                            </button>
                          )}
                          <button
                            type="button"
                            className="button button--small button--ghost"
                            onClick={() => openEdit(venue)}
                            aria-label={`Editar ${venue.name}`}
                          >
                            Editar
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <Pagination
          total={total}
          limit={pageSize}
          offset={(currentPage - 1) * pageSize}
          onChange={(offset) => setPage(Math.floor(offset / pageSize) + 1)}
          disabled={venuesQuery.isFetching}
        />
      </section>

      <ReasonDialog
        open={Boolean(statusTarget)}
        title={statusTarget?.action === "suspend" ? "Suspender quadra" : "Reativar quadra"}
        description={
          statusTarget?.action === "suspend"
            ? "A quadra sai da descoberta e não aceita novas reservas. Reservas existentes, histórico e valores são preservados."
            : "A quadra volta a aparecer na descoberta e a aceitar novas reservas. O motivo fica registrado na auditoria."
        }
        label="Motivo"
        value={statusReason}
        onChange={(value) => {
          setStatusReason(value);
          setStatusReasonError(null);
        }}
        error={statusReasonError}
        placeholder="Descreva o que motivou a ação"
        minLength={3}
        maxLength={500}
        confirmLabel={statusTarget?.action === "suspend" ? "Suspender quadra" : "Reativar quadra"}
        tone={statusTarget?.action === "suspend" ? "danger" : "default"}
        busy={statusMutation.isPending}
        onConfirm={confirmStatus}
        onClose={closeStatus}
      >
        {statusError ? (
          <ErrorNotice
            message={venueErrorMessage(statusError)}
            requestId={requestIdOf(statusError)}
          />
        ) : null}
      </ReasonDialog>

      <ReasonDialog
        open={Boolean(editTarget && editDraft)}
        title={editTarget ? `Editar ${editTarget.name}` : "Editar quadra"}
        description="Corrija apenas dados cadastrais. Preços, agenda e reservas não são alterados. Campos em branco mantêm o valor atual."
        label="Motivo"
        value={editReason}
        onChange={(value) => {
          setEditReason(value);
          setEditErrors((current) => {
            if (!current.reason) return current;
            const next = { ...current };
            delete next.reason;
            return next;
          });
        }}
        error={editErrors.reason}
        placeholder="Descreva o que motivou a correção"
        minLength={3}
        maxLength={500}
        confirmLabel="Salvar alterações"
        busy={editMutation.isPending}
        onConfirm={saveEdit}
        onClose={closeEdit}
      >
        {editError ? (
          <ErrorNotice message={venueErrorMessage(editError)} requestId={requestIdOf(editError)} />
        ) : null}
        {editDraft ? (
          <>
            <TextField
              id="venue-edit-name"
              label="Nome da quadra"
              value={editDraft.name}
              onChange={(event) => updateEditDraft({ name: event.target.value })}
              error={editErrors["venue-edit-name"]}
              maxLength={120}
              required
              data-autofocus
            />
            <div className="form-row form-row--three">
              <TextField
                id="venue-edit-city"
                label="Cidade"
                value={editDraft.city}
                onChange={(event) => updateEditDraft({ city: event.target.value })}
                error={editErrors["venue-edit-city"]}
                maxLength={120}
              />
              <TextField
                id="venue-edit-state"
                label="UF"
                value={editDraft.state}
                onChange={(event) => updateEditDraft({ state: event.target.value.toUpperCase() })}
                error={editErrors["venue-edit-state"]}
                hint="Duas letras."
                maxLength={2}
              />
              <TextField
                id="venue-edit-postal-code"
                label="CEP"
                value={editDraft.postal_code}
                onChange={(event) => updateEditDraft({ postal_code: event.target.value })}
                error={editErrors["venue-edit-postal-code"]}
                inputMode="numeric"
                maxLength={9}
              />
            </div>
            <TextField
              id="venue-edit-address"
              label="Endereço"
              value={editDraft.address_line}
              onChange={(event) => updateEditDraft({ address_line: event.target.value })}
              error={editErrors["venue-edit-address"]}
              maxLength={200}
            />
            <div className="form-row">
              <TextField
                id="venue-edit-latitude"
                label="Latitude"
                value={editDraft.latitude}
                onChange={(event) => updateEditDraft({ latitude: event.target.value })}
                error={editErrors["venue-edit-latitude"]}
                hint="Entre -90 e 90."
                inputMode="decimal"
              />
              <TextField
                id="venue-edit-longitude"
                label="Longitude"
                value={editDraft.longitude}
                onChange={(event) => updateEditDraft({ longitude: event.target.value })}
                error={editErrors["venue-edit-longitude"]}
                hint="Entre -180 e 180."
                inputMode="decimal"
              />
            </div>
            {editErrors["venue-edit-geocoding"] ? (
              <p className="field__error" role="alert">
                {editErrors["venue-edit-geocoding"]}
              </p>
            ) : null}
            <CheckboxField
              id="venue-edit-public"
              label="Aparece na descoberta do aplicativo"
              checked={editDraft.is_public}
              onChange={(checked) => updateEditDraft({ is_public: checked })}
              hint="Quadras privadas ficam fora do catálogo público, mesmo quando ativas."
            />
          </>
        ) : null}
      </ReasonDialog>
    </>
  );
}
