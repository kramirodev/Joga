import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { EmptyState, ErrorNotice, LoadingBlock } from "../components/Feedback";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth-context";
import { formatDate, formatError, requestIdOf, roleLabel } from "../lib/format";
import { queryKeys } from "../lib/query";
import type { Member, Organization, Role, Venue } from "../types";

type Tab = "members" | "venues" | "audit";

function canReadAudit(role: Role): boolean {
  return role === "OWNER" || role === "ADMIN";
}

function assignableRoles(role: Role): Role[] {
  return role === "OWNER" ? ["OWNER", "ADMIN", "OPERATOR"] : ["OPERATOR"];
}

function MemberRow({
  member,
  organizationId,
  actorRole,
  currentUserId,
  onChanged,
  onNotice,
  onError,
}: {
  member: Member;
  organizationId: string;
  actorRole: Role;
  currentUserId: string | null;
  onChanged: () => Promise<void>;
  onNotice: (message: string) => void;
  onError: (error: unknown) => void;
}) {
  const [role, setRole] = useState<Role>(member.role);
  const manageable = actorRole === "OWNER" || (actorRole === "ADMIN" && member.role === "OPERATOR");
  const isSelf = member.user_id === currentUserId;

  const changeRole = useMutation({
    mutationFn: (nextRole: Role) => api.changeMemberRole(organizationId, member.user_id, nextRole),
    onSuccess: async () => {
      await onChanged();
      onNotice("Papel atualizado.");
    },
    onError: (caught) => onError(caught),
  });

  const removeMember = useMutation({
    mutationFn: () => api.removeMember(organizationId, member.user_id),
    onSuccess: async () => {
      await onChanged();
      onNotice(isSelf ? "Você saiu da organização." : "Membro removido.");
    },
    onError: (caught) => onError(caught),
  });

  const busy = changeRole.isPending || removeMember.isPending;

  function saveRole() {
    if (role === member.role) return;
    changeRole.mutate(role);
  }

  function confirmRemove() {
    const label = member.display_name || member.user_id;
    const action = isSelf ? "Sair da organização" : "Remover este membro";
    if (!window.confirm(`${action} — ${label}?`)) return;
    removeMember.mutate();
  }

  return (
    <li className="member-row">
      <div className="member-row__identity">
        <strong>{member.display_name || "Sem nome de perfil"}</strong>
        <small className="mono">{member.user_id}</small>
        <small>Desde {formatDate(member.created_at)}</small>
      </div>
      <div className="member-row__role">
        {manageable ? (
          <select
            aria-label={`Papel de ${member.display_name || member.user_id}`}
            value={role}
            onChange={(event) => setRole(event.target.value as Role)}
            disabled={busy}
          >
            {assignableRoles(actorRole).map((option) => (
              <option key={option} value={option}>
                {roleLabel(option)}
              </option>
            ))}
          </select>
        ) : (
          <span className={`badge badge--${member.role.toLowerCase()}`}>
            {roleLabel(member.role)}
          </span>
        )}
        {isSelf ? <span className="badge badge--muted">você</span> : null}
      </div>
      {manageable ? (
        <div className="member-row__actions">
          <button
            type="button"
            className="button button--small"
            onClick={saveRole}
            disabled={busy || role === member.role}
          >
            Salvar
          </button>
          <button
            type="button"
            className="button button--small button--danger"
            onClick={confirmRemove}
            disabled={busy}
          >
            {isSelf ? "Sair" : "Remover"}
          </button>
        </div>
      ) : null}
    </li>
  );
}

export function OrganizationPage() {
  const { organizationId = "" } = useParams<{ organizationId: string }>();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("members");
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const [newMemberId, setNewMemberId] = useState("");
  const [newMemberRole, setNewMemberRole] = useState<Role>("OPERATOR");

  const [venueName, setVenueName] = useState("");
  const [venueCity, setVenueCity] = useState("");
  const [venueState, setVenueState] = useState("");
  const [venueAddress, setVenueAddress] = useState("");

  const organizationQuery = useQuery({
    queryKey: queryKeys.organization(organizationId),
    queryFn: () => api.getOrganization(organizationId),
    enabled: organizationId.length > 0,
  });
  const organization = organizationQuery.data;

  const membersQuery = useQuery({
    queryKey: queryKeys.members(organizationId),
    queryFn: async () => (await api.listMembers(organizationId)).members,
    enabled: organizationId.length > 0,
  });

  const venuesQuery = useQuery({
    queryKey: queryKeys.venues(organizationId),
    queryFn: async () => (await api.listVenues(organizationId)).venues,
    enabled: organizationId.length > 0,
  });

  const showAudit = organization ? canReadAudit(organization.role) : false;

  const auditQuery = useQuery({
    queryKey: queryKeys.audit(organizationId),
    queryFn: async () => (await api.listAudit(organizationId)).audit,
    enabled: organizationId.length > 0 && showAudit,
  });

  const invalidateMembers = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.members(organizationId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.audit(organizationId) }),
    ]);
  };

  const invalidateVenues = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.venues(organizationId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.audit(organizationId) }),
    ]);
  };

  const renameMutation = useMutation({
    mutationFn: (name: string) => api.updateOrganization(organizationId, name),
    onSuccess: (updated: Organization) => {
      queryClient.setQueryData(queryKeys.organization(organizationId), updated);
      setEditingName(false);
      setNotice("Nome atualizado.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.audit(organizationId) });
    },
  });

  const addMemberMutation = useMutation({
    mutationFn: (payload: { userId: string; role: Role }) =>
      api.addMember(organizationId, payload.userId, payload.role),
    onSuccess: async () => {
      setNewMemberId("");
      setNewMemberRole("OPERATOR");
      setNotice("Membro adicionado.");
      await invalidateMembers();
    },
  });

  const addVenueMutation = useMutation({
    mutationFn: () =>
      api.createVenue(organizationId, {
        name: venueName,
        city: venueCity.trim() || null,
        state: venueState.trim() || null,
        address_line: venueAddress.trim() || null,
      }),
    onSuccess: async () => {
      setVenueName("");
      setVenueCity("");
      setVenueState("");
      setVenueAddress("");
      setNotice("Estabelecimento cadastrado.");
      await invalidateVenues();
    },
  });

  const toggleVenueMutation = useMutation({
    mutationFn: (venue: Venue) =>
      api.updateVenue(organizationId, venue.id, {
        status: venue.status === "active" ? "inactive" : "active",
      }),
    onSuccess: async () => {
      setNotice("Status do estabelecimento atualizado.");
      await invalidateVenues();
    },
  });

  const loading = organizationQuery.isPending || membersQuery.isPending || venuesQuery.isPending;
  const queryError = organizationQuery.error ?? membersQuery.error ?? venuesQuery.error;
  const mutationError =
    renameMutation.error ??
    addMemberMutation.error ??
    addVenueMutation.error ??
    toggleVenueMutation.error;
  const busy =
    renameMutation.isPending ||
    addMemberMutation.isPending ||
    addVenueMutation.isPending ||
    toggleVenueMutation.isPending;

  const members = membersQuery.data ?? [];
  const venues = venuesQuery.data ?? [];
  const audit = auditQuery.data ?? [];
  const activeTab: Tab = tab === "audit" && !showAudit ? "members" : tab;

  function refetchAll() {
    void organizationQuery.refetch();
    void membersQuery.refetch();
    void venuesQuery.refetch();
    if (showAudit) void auditQuery.refetch();
  }

  function saveName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    renameMutation.mutate(nameDraft);
  }

  function addMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    addMemberMutation.mutate({ userId: newMemberId.trim(), role: newMemberRole });
  }

  function addVenue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    addVenueMutation.mutate();
  }

  if (loading) {
    return (
      <div className="app-shell">
        <AppHeader />
        <main className="page">
          <LoadingBlock label="Carregando organização..." />
        </main>
      </div>
    );
  }

  if (queryError || !organization) {
    return (
      <div className="app-shell">
        <AppHeader />
        <main className="page">
          <ErrorNotice
            message={queryError ? formatError(queryError) : "Organização não encontrada."}
            requestId={requestIdOf(queryError)}
            onRetry={refetchAll}
          />
          <Link className="button button--link" to="/">
            Voltar para organizações
          </Link>
        </main>
      </div>
    );
  }

  const canUpdateOrganization = organization.role !== "OPERATOR";
  const canManageMembers = organization.role !== "OPERATOR";
  const roles = assignableRoles(organization.role);

  return (
    <div className="app-shell">
      <AppHeader subtitle={organization.name} />
      <main className="page">
        <nav className="breadcrumb" aria-label="Navegação">
          <Link to="/">Organizações</Link>
          <span aria-hidden="true">/</span>
          <span>{organization.name}</span>
        </nav>

        <section className="page-heading">
          <div>
            <p className="eyebrow">{roleLabel(organization.role)}</p>
            <h1>{organization.name}</h1>
            <p className="muted">
              Status {organization.status} · criada em {formatDate(organization.created_at)}
            </p>
          </div>
          {canUpdateOrganization ? (
            <button
              type="button"
              className="button button--ghost"
              onClick={() => {
                setNameDraft(organization.name);
                setEditingName((current) => !current);
              }}
            >
              {editingName ? "Cancelar edição" : "Editar nome"}
            </button>
          ) : null}
        </section>

        {editingName ? (
          <form className="inline-form" onSubmit={saveName}>
            <label className="field field--inline">
              <span>Nome da organização</span>
              <input
                type="text"
                value={nameDraft}
                onChange={(event) => setNameDraft(event.target.value)}
                minLength={2}
                maxLength={120}
                required
              />
            </label>
            <button type="submit" className="button button--primary" disabled={busy}>
              Salvar nome
            </button>
          </form>
        ) : null}

        {notice ? (
          <div className="notice notice--success" role="status" aria-live="polite">
            {notice}
          </div>
        ) : null}
        {actionError ? (
          <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
        ) : null}
        {mutationError ? (
          <ErrorNotice
            message={formatError(mutationError)}
            requestId={requestIdOf(mutationError)}
          />
        ) : null}

        <div className="tabs" role="tablist" aria-label="Seções da organização">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "members"}
            className={activeTab === "members" ? "tab tab--active" : "tab"}
            onClick={() => setTab("members")}
          >
            Membros <span className="tab__count">{members.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "venues"}
            className={activeTab === "venues" ? "tab tab--active" : "tab"}
            onClick={() => setTab("venues")}
          >
            Estabelecimentos <span className="tab__count">{venues.length}</span>
          </button>
          {showAudit ? (
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "audit"}
              className={activeTab === "audit" ? "tab tab--active" : "tab"}
              onClick={() => setTab("audit")}
            >
              Auditoria
            </button>
          ) : null}
        </div>

        {activeTab === "members" ? (
          <section className="card">
            <div className="section-heading">
              <div>
                <h2>Membros e permissões</h2>
                <p className="muted">
                  {organization.role === "OWNER"
                    ? "Você pode gerenciar proprietários, administradores e operadores."
                    : organization.role === "ADMIN"
                      ? "Você pode gerenciar operadores."
                      : "Você pode consultar os membros, mas não alterá-los."}
                </p>
              </div>
            </div>

            {members.length === 0 ? (
              <EmptyState title="Nenhum membro">A organização ainda não tem vínculos.</EmptyState>
            ) : (
              <ul className="member-list">
                {members.map((member) => (
                  <MemberRow
                    key={`${member.user_id}:${member.role}`}
                    member={member}
                    organizationId={organization.id}
                    actorRole={organization.role}
                    currentUserId={user?.id ?? null}
                    onChanged={invalidateMembers}
                    onNotice={setNotice}
                    onError={(error) => {
                      setNotice(null);
                      setActionError(error);
                    }}
                  />
                ))}
              </ul>
            )}

            {canManageMembers ? (
              <form className="form form--inline" onSubmit={addMember}>
                <h3>Adicionar membro</h3>
                <p className="muted">
                  Informe o UUID da conta JOGA. O usuário pode ser jogador e também administrar o
                  estabelecimento.
                </p>
                <div className="form-row">
                  <label className="field">
                    <span>UUID do usuário</span>
                    <input
                      type="text"
                      value={newMemberId}
                      onChange={(event) => setNewMemberId(event.target.value)}
                      placeholder="00000000-0000-0000-0000-000000000000"
                      required
                    />
                  </label>
                  <label className="field">
                    <span>Papel</span>
                    <select
                      value={newMemberRole}
                      onChange={(event) => setNewMemberRole(event.target.value as Role)}
                    >
                      {roles.map((role) => (
                        <option key={role} value={role}>
                          {roleLabel(role)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <button type="submit" className="button button--primary" disabled={busy}>
                  Adicionar
                </button>
              </form>
            ) : null}
          </section>
        ) : null}

        {activeTab === "venues" ? (
          <section className="stack">
            <div className="card">
              <div className="section-heading">
                <div>
                  <h2>Estabelecimentos</h2>
                  <p className="muted">
                    Perfil comercial vinculado a esta organização. Quadras e agenda pertencem à Fase
                    12.
                  </p>
                </div>
              </div>
              {venues.length === 0 ? (
                <EmptyState title="Nenhum estabelecimento">
                  Cadastre o primeiro perfil comercial abaixo.
                </EmptyState>
              ) : (
                <ul className="venue-list">
                  {venues.map((venue) => (
                    <li key={venue.id} className="venue-row">
                      <div>
                        <strong>{venue.name}</strong>
                        <small>
                          {[venue.city, venue.state].filter(Boolean).join(" · ") ||
                            "Local não informado"}
                        </small>
                        {venue.address_line ? <small>{venue.address_line}</small> : null}
                      </div>
                      <div className="venue-row__actions">
                        <span
                          className={
                            venue.status === "active" ? "badge badge--active" : "badge badge--muted"
                          }
                        >
                          {venue.status === "active" ? "Ativo" : "Inativo"}
                        </span>
                        <button
                          type="button"
                          className="button button--small"
                          onClick={() => toggleVenueMutation.mutate(venue)}
                          disabled={busy}
                        >
                          {venue.status === "active" ? "Desativar" : "Ativar"}
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="card">
              <h2>Novo estabelecimento</h2>
              <form className="form" onSubmit={addVenue}>
                <label className="field">
                  <span>Nome</span>
                  <input
                    type="text"
                    value={venueName}
                    onChange={(event) => setVenueName(event.target.value)}
                    minLength={2}
                    maxLength={120}
                    placeholder="Ex.: Arena Tijuca"
                    required
                  />
                </label>
                <div className="form-row">
                  <label className="field">
                    <span>Cidade</span>
                    <input
                      type="text"
                      value={venueCity}
                      onChange={(event) => setVenueCity(event.target.value)}
                      maxLength={120}
                      placeholder="Rio de Janeiro"
                    />
                  </label>
                  <label className="field field--short">
                    <span>UF</span>
                    <input
                      type="text"
                      value={venueState}
                      onChange={(event) =>
                        setVenueState(event.target.value.replace(/[^a-zA-Z]/g, "").toUpperCase())
                      }
                      minLength={2}
                      maxLength={2}
                      placeholder="RJ"
                    />
                  </label>
                </div>
                <label className="field">
                  <span>Endereço</span>
                  <input
                    type="text"
                    value={venueAddress}
                    onChange={(event) => setVenueAddress(event.target.value)}
                    maxLength={200}
                    placeholder="Rua, número e complemento"
                  />
                </label>
                <button type="submit" className="button button--primary" disabled={busy}>
                  Cadastrar estabelecimento
                </button>
              </form>
            </div>
          </section>
        ) : null}

        {activeTab === "audit" && showAudit ? (
          <section className="card">
            <div className="section-heading">
              <div>
                <h2>Auditoria</h2>
                <p className="muted">
                  Trilha append-only das ações administrativas desta organização.
                </p>
              </div>
            </div>
            {auditQuery.error ? (
              <ErrorNotice
                message={formatError(auditQuery.error)}
                requestId={requestIdOf(auditQuery.error)}
                onRetry={() => void auditQuery.refetch()}
              />
            ) : auditQuery.isPending ? (
              <LoadingBlock label="Carregando auditoria..." />
            ) : audit.length === 0 ? (
              <EmptyState title="Nenhum evento">Ainda não há ações registradas.</EmptyState>
            ) : (
              <ul className="audit-list">
                {audit.map((event) => (
                  <li key={event.id} className="audit-row">
                    <div>
                      <strong>{event.action}</strong>
                      <small>
                        {event.resource_type}
                        {event.resource_id ? ` · ${event.resource_id}` : ""}
                      </small>
                      <small>
                        Ator: {event.actor_user_id ?? "sistema"} · {formatDate(event.created_at)}
                      </small>
                    </div>
                    {event.details ? (
                      <details>
                        <summary>Detalhes</summary>
                        <pre>{JSON.stringify(event.details, null, 2)}</pre>
                      </details>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>
        ) : null}
      </main>
    </div>
  );
}
