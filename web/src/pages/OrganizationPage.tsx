import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ErrorNotice, InfoNotice, SkeletonList } from "../components/Feedback";
import { TextField } from "../components/ui/Field";
import { BuildingIcon } from "../components/ui/Icons";
import { Modal } from "../components/ui/Modal";
import { Breadcrumbs, PageHeader, SectionHeading } from "../components/ui/PageHeader";
import { Tabs } from "../components/ui/Tabs";
import { tabId, tabPanelId } from "../components/ui/tab-ids";
import { useToast } from "../components/ui/toast-context";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth-context";
import {
  cnpjStatusLabel,
  formatDate,
  formatError,
  organizationStatusLabel,
  requestIdOf,
  roleLabel,
  verificationStatusLabel,
} from "../lib/format";
import { queryKeys } from "../lib/query";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import {
  cnpjError,
  cpfError,
  formatCnpj,
  formatCpf,
  normalizeCnpj,
  normalizeCpf,
  normalizeWhitespace,
  textError,
} from "../lib/validation";
import type { BookingListParams, Organization } from "../types";
import { AuditPanel } from "./organization/AuditPanel";
import { BookingsPanel } from "./organization/BookingsPanel";
import { FinancialPanel } from "./organization/FinancialPanel";
import { MembersPanel } from "./organization/MembersPanel";
import { VenuesPanel } from "./organization/VenuesPanel";

type Tab = "members" | "venues" | "bookings" | "financial" | "audit";
const TABS: Tab[] = ["members", "venues", "bookings", "financial", "audit"];

function canReadAudit(role: Organization["role"]): boolean {
  return role === "OWNER" || role === "ADMIN";
}

export function OrganizationPage() {
  const { organizationId = "" } = useParams<{ organizationId: string }>();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [verifyDraft, setVerifyDraft] = useState({ cnpj: "", cpf: "" });
  const [verifyErrors, setVerifyErrors] = useState<Record<string, string>>({});
  const [bookingParams, setBookingParams] = useState<BookingListParams>({
    limit: 50,
    offset: 0,
  });

  const organizationQuery = useQuery({
    queryKey: queryKeys.organization(organizationId),
    queryFn: () => api.getOrganization(organizationId),
    enabled: organizationId.length > 0,
  });
  const organization = organizationQuery.data;

  const membersQuery = useQuery({
    queryKey: queryKeys.members(organizationId),
    queryFn: async () => (await api.listMembers(organizationId)).members,
    enabled: Boolean(organization),
  });
  const venuesQuery = useQuery({
    queryKey: queryKeys.venues(organizationId),
    queryFn: async () => (await api.listVenues(organizationId)).venues,
    enabled: Boolean(organization),
  });
  const bookingsQuery = useQuery({
    queryKey: [...queryKeys.bookings(organizationId), bookingParams],
    queryFn: () => api.listOrganizationBookings(organizationId, bookingParams),
    enabled: Boolean(organization),
    placeholderData: keepPreviousData,
  });

  const members = membersQuery.data ?? [];
  const venues = venuesQuery.data ?? [];
  const bookingsPage = bookingsQuery.data;
  const bookings = bookingsPage?.bookings ?? [];
  const bookingsTotal = bookingsPage?.total ?? 0;
  const bookingsLimit = bookingsPage?.limit ?? bookingParams.limit ?? 50;
  const bookingsOffset = bookingsPage?.offset ?? bookingParams.offset ?? 0;
  const showAudit = organization ? canReadAudit(organization.role) : false;

  const requestedTab = searchParams.get("tab") as Tab | null;
  const activeTab: Tab =
    requestedTab && TABS.includes(requestedTab) && (requestedTab !== "audit" || showAudit)
      ? requestedTab
      : "members";

  useDocumentTitle(organization?.name ?? "Organização");

  const renameMutation = useMutation({
    mutationFn: (name: string) => api.updateOrganization(organizationId, name),
    onSuccess: (updated: Organization) => {
      queryClient.setQueryData(queryKeys.organization(organizationId), updated);
      setEditingName(false);
      setNameError(null);
      toast.push({
        title: "Nome atualizado",
        description: "A alteração foi registrada na auditoria.",
      });
      void queryClient.invalidateQueries({ queryKey: queryKeys.audit(organizationId) });
    },
    onError: (caught) => setNameError(formatError(caught)),
  });

  const verifyMutation = useMutation({
    mutationFn: () =>
      api.verifyOrganization(organizationId, {
        cnpj: normalizeCnpj(verifyDraft.cnpj),
        cpf: normalizeCpf(verifyDraft.cpf),
      }),
    onSuccess: (updated: Organization) => {
      queryClient.setQueryData(queryKeys.organization(organizationId), updated);
      setVerifyOpen(false);
      setVerifyDraft({ cnpj: "", cpf: "" });
      setVerifyErrors({});
      toast.push({
        title: "CNPJ verificado",
        description: "A organização está regularizada e já pode cadastrar e publicar quadras.",
      });
      void queryClient.invalidateQueries({ queryKey: queryKeys.organizations });
      void queryClient.invalidateQueries({ queryKey: queryKeys.venues(organizationId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.audit(organizationId) });
    },
  });

  function openVerification() {
    if (!organization) return;
    verifyMutation.reset();
    setVerifyDraft({ cnpj: organization.cnpj ? formatCnpj(organization.cnpj) : "", cpf: "" });
    setVerifyErrors({});
    setVerifyOpen(true);
  }

  function closeVerification() {
    if (verifyMutation.isPending) return;
    setVerifyOpen(false);
    setVerifyDraft({ cnpj: "", cpf: "" });
    setVerifyErrors({});
    verifyMutation.reset();
  }

  function submitVerification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (verifyMutation.isPending) return;
    const next: Record<string, string> = {};
    const cnpjValidation = cnpjError(verifyDraft.cnpj);
    if (cnpjValidation) next.cnpj = cnpjValidation;
    const cpfValidation = cpfError(verifyDraft.cpf);
    if (cpfValidation) next.cpf = cpfValidation;
    if (Object.keys(next).length > 0) {
      setVerifyErrors(next);
      document.getElementById(next.cnpj ? "org-verify-cnpj" : "org-verify-cpf")?.focus();
      return;
    }
    setVerifyErrors({});
    verifyMutation.mutate();
  }

  function setTab(next: Tab) {
    const params = new URLSearchParams(searchParams);
    params.set("tab", next);
    setSearchParams(params);
  }

  function changeBookingParams(next: BookingListParams) {
    setBookingParams({
      status: next.status ?? null,
      from: next.from ?? null,
      to: next.to ?? null,
      limit: next.limit ?? 50,
      offset: next.offset ?? 0,
    });
  }

  function beginRename() {
    if (!organization) return;
    setNameDraft(organization.name);
    setNameError(null);
    setEditingName(true);
    window.setTimeout(() => document.getElementById("organization-name")?.focus(), 0);
  }

  function saveName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validation = textError(nameDraft, {
      label: "o nome da organização",
      min: 2,
      max: 120,
    });
    if (validation) {
      setNameError(validation);
      document.getElementById("organization-name")?.focus();
      return;
    }
    renameMutation.mutate(normalizeWhitespace(nameDraft));
  }

  if (organizationQuery.isPending) {
    return <SkeletonList rows={4} label="Carregando organização..." />;
  }

  if (organizationQuery.error || !organization) {
    return (
      <>
        <ErrorNotice
          message={
            organizationQuery.error
              ? formatError(organizationQuery.error)
              : "Organização não encontrada."
          }
          requestId={requestIdOf(organizationQuery.error)}
          onRetry={() => void organizationQuery.refetch()}
        />
        <Link className="button button--link" to="/">
          Voltar para organizações
        </Link>
      </>
    );
  }

  const canUpdateOrganization = organization.role !== "OPERATOR";
  const verified = organization.verification_status === "verified";
  const hasBookingFilters = Boolean(bookingParams.status || bookingParams.from || bookingParams.to);
  const tabItems = [
    { id: "members", label: "Membros", count: members.length },
    { id: "venues", label: "Estabelecimentos", count: venues.length },
    { id: "bookings", label: "Reservas", count: hasBookingFilters ? undefined : bookingsTotal },
    { id: "financial", label: "Financeiro" },
    ...(showAudit ? [{ id: "audit", label: "Auditoria" }] : []),
  ];

  return (
    <>
      <Breadcrumbs items={[{ label: "Organizações", to: "/" }, { label: organization.name }]} />

      <PageHeader
        eyebrow={roleLabel(organization.role)}
        title={organization.name}
        description={
          <>
            <span
              className={
                organization.status === "active" ? "badge badge--success" : "badge badge--muted"
              }
            >
              {organizationStatusLabel(organization.status)}
            </span>{" "}
            Organização criada em {formatDate(organization.created_at)}.
          </>
        }
        actions={
          canUpdateOrganization ? (
            <button
              type="button"
              className={editingName ? "button button--ghost" : "button"}
              onClick={() => {
                if (editingName) {
                  setEditingName(false);
                  setNameError(null);
                } else {
                  beginRename();
                }
              }}
            >
              {editingName ? "Cancelar edição" : "Editar nome"}
            </button>
          ) : null
        }
      />

      {editingName ? (
        <div className="card card--form">
          <form className="inline-form" onSubmit={saveName} noValidate>
            <TextField
              id="organization-name"
              label="Nome da organização"
              className="field--inline"
              value={nameDraft}
              onChange={(event) => {
                setNameDraft(event.target.value);
                if (nameError) setNameError(null);
              }}
              error={nameError}
              hint="De 2 a 120 caracteres."
              minLength={2}
              maxLength={120}
              required
            />
            <button
              type="submit"
              className="button button--primary"
              disabled={renameMutation.isPending}
              aria-busy={renameMutation.isPending || undefined}
            >
              {renameMutation.isPending ? "Salvando..." : "Salvar nome"}
            </button>
          </form>
        </div>
      ) : null}

      <section className="card">
        <SectionHeading
          title="Cadastro empresarial"
          description="O CNPJ é verificado na Receita Federal e reconferido periodicamente. Quadras só podem ser publicadas com o cadastro regular."
          actions={
            !verified && canUpdateOrganization ? (
              <button type="button" className="button button--primary" onClick={openVerification}>
                Verificar CNPJ
              </button>
            ) : null
          }
        />
        <dl className="admin-meta">
          <div>
            <dt>CNPJ</dt>
            <dd>{organization.cnpj ? formatCnpj(organization.cnpj) : "Não informado"}</dd>
          </div>
          <div>
            <dt>Situação na Receita</dt>
            <dd>{cnpjStatusLabel(organization.cnpj_status)}</dd>
          </div>
          <div>
            <dt>Verificação</dt>
            <dd>
              <span
                className={
                  verified
                    ? "badge badge--success"
                    : organization.verification_status === "invalid"
                      ? "badge badge--danger"
                      : "badge badge--warning"
                }
              >
                {verificationStatusLabel(organization.verification_status)}
              </span>
            </dd>
          </div>
          <div>
            <dt>Verificado em</dt>
            <dd>
              {organization.cnpj_verified_at ? formatDate(organization.cnpj_verified_at) : "—"}
            </dd>
          </div>
          <div>
            <dt>Próxima conferência</dt>
            <dd>
              {organization.cnpj_next_check_at ? formatDate(organization.cnpj_next_check_at) : "—"}
            </dd>
          </div>
        </dl>
        {!verified && canUpdateOrganization ? (
          <InfoNotice>
            {organization.verification_status === "invalid"
              ? "A verificação do CNPJ não está válida. As quadras desta organização ficam fora da descoberta até a regularização."
              : "Esta organização ainda não teve o CNPJ verificado. Cadastrar quadras e publicar continuam bloqueados até a aprovação."}
          </InfoNotice>
        ) : null}
      </section>

      <div className="context-note">
        <BuildingIcon size={17} />
        <span>
          Você está vendo apenas os dados desta organização. O acesso a outra organização exige um
          vínculo próprio.
        </span>
      </div>

      <Tabs
        items={tabItems}
        active={activeTab}
        onChange={(id) => setTab(id as Tab)}
        idBase="organization"
        ariaLabel="Seções da organização"
      />

      <div
        role="tabpanel"
        id={tabPanelId("organization", activeTab)}
        aria-labelledby={tabId("organization", activeTab)}
        tabIndex={0}
        className="tab-panel"
      >
        {activeTab === "members" ? (
          <MembersPanel
            organization={organization}
            members={members}
            currentUserId={user?.id ?? null}
            loading={membersQuery.isPending}
            error={membersQuery.error}
            onRetry={() => void membersQuery.refetch()}
          />
        ) : null}

        {activeTab === "venues" ? (
          <VenuesPanel
            organization={organization}
            venues={venues}
            loading={venuesQuery.isPending}
            error={venuesQuery.error}
            onRetry={() => void venuesQuery.refetch()}
          />
        ) : null}

        {activeTab === "bookings" ? (
          <BookingsPanel
            organization={organization}
            bookings={bookings}
            total={bookingsTotal}
            limit={bookingsLimit}
            offset={bookingsOffset}
            filters={bookingParams}
            onParamsChange={changeBookingParams}
            loading={bookingsQuery.isPending}
            fetching={bookingsQuery.isFetching}
            error={bookingsQuery.error}
            onRetry={() => void bookingsQuery.refetch()}
          />
        ) : null}

        {activeTab === "financial" ? <FinancialPanel organization={organization} /> : null}

        {activeTab === "audit" && showAudit ? (
          <AuditPanel organizationId={organization.id} />
        ) : null}
      </div>

      <Modal
        open={verifyOpen}
        title="Verificar CNPJ"
        description="Confirme o CNPJ ativo e o CPF de um responsável no QSA. O CPF é enviado apenas nesta etapa e não fica visível no painel."
        onClose={closeVerification}
        footer={
          <>
            <button
              type="button"
              className="button button--ghost"
              onClick={closeVerification}
              disabled={verifyMutation.isPending}
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="organization-verification-form"
              className="button button--primary"
              disabled={verifyMutation.isPending}
              aria-busy={verifyMutation.isPending || undefined}
            >
              {verifyMutation.isPending ? "Verificando..." : "Verificar CNPJ"}
            </button>
          </>
        }
      >
        <form
          id="organization-verification-form"
          className="form"
          onSubmit={submitVerification}
          noValidate
        >
          {verifyMutation.error ? (
            <ErrorNotice
              message={formatError(verifyMutation.error)}
              requestId={requestIdOf(verifyMutation.error)}
            />
          ) : null}
          <TextField
            id="org-verify-cnpj"
            label="CNPJ"
            value={verifyDraft.cnpj}
            onChange={(event) => {
              setVerifyDraft((current) => ({
                ...current,
                cnpj: formatCnpj(event.target.value),
              }));
              if (verifyErrors.cnpj) setVerifyErrors((current) => ({ ...current, cnpj: "" }));
            }}
            error={verifyErrors.cnpj}
            hint="O CNPJ aprovado não pode ser trocado depois."
            maxLength={18}
            inputMode="numeric"
            autoComplete="off"
            required
            data-autofocus
          />
          <TextField
            id="org-verify-cpf"
            label="CPF do responsável"
            value={verifyDraft.cpf}
            onChange={(event) => {
              setVerifyDraft((current) => ({
                ...current,
                cpf: formatCpf(event.target.value),
              }));
              if (verifyErrors.cpf) setVerifyErrors((current) => ({ ...current, cpf: "" }));
            }}
            error={verifyErrors.cpf}
            hint="Precisa constar no QSA do CNPJ. Não reexibimos este valor."
            maxLength={14}
            inputMode="numeric"
            autoComplete="off"
            required
          />
        </form>
      </Modal>
    </>
  );
}
