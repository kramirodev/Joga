import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { EmptyState, ErrorNotice, SkeletonList } from "../../components/Feedback";
import { Drawer } from "../../components/ui/Drawer";
import { CheckboxField, SelectField, TextareaField, TextField } from "../../components/ui/Field";
import { SearchIcon, UsersIcon } from "../../components/ui/Icons";
import { ConfirmDialog, Modal, ReasonDialog } from "../../components/ui/Modal";
import { PageHeader, SectionHeading } from "../../components/ui/PageHeader";
import { Pagination } from "../../components/ui/Pagination";
import { useToast } from "../../components/ui/toast-context";
import { api } from "../../lib/api";
import {
  auditActionLabel,
  formatDate,
  initials,
  requestIdOf,
  shortId,
  userStatusLabel,
} from "../../lib/format";
import { queryKeys } from "../../lib/query";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import {
  emailError,
  firstErrorId,
  normalizeWhitespace,
  passwordError,
  textError,
} from "../../lib/validation";
import { adminErrorMessage, isForbidden } from "../../lib/admin";
import type { AdminUserSummary } from "../../types";
import { AdminForbiddenState } from "./AdminShared";

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  { value: "", label: "Todos os status" },
  { value: "active", label: "Ativos" },
  { value: "pending", label: "Pendentes" },
  { value: "suspended", label: "Suspensos" },
  { value: "deleted", label: "Excluídos" },
];

type ActionKind = "email" | "password" | "suspend" | "reactivate";

interface ActionTarget {
  kind: ActionKind;
  user: AdminUserSummary;
}

interface AdminActionInput {
  kind: ActionKind;
  user: AdminUserSummary;
  reason: string;
  email?: string;
  until?: string;
}

const ACTION_COPY: Record<
  ActionKind,
  { title: string; description: string; confirm: string; tone: "default" | "danger" }
> = {
  email: {
    title: "Alterar e-mail",
    description:
      "O novo e-mail passa a ser a credencial de acesso. A alteração exige motivo e fica na auditoria.",
    confirm: "Salvar novo e-mail",
    tone: "default",
  },
  password: {
    title: "Redefinir senha",
    description:
      "Um código de redefinição é enviado para o e-mail da conta e todas as sessões são revogadas. Nenhuma senha é exibida ou armazenada no painel.",
    confirm: "Enviar código de redefinição",
    tone: "default",
  },
  suspend: {
    title: "Suspender usuário",
    description:
      "A conta perde o acesso até ser reativada. Informe o motivo; o prazo final é opcional.",
    confirm: "Suspender conta",
    tone: "danger",
  },
  reactivate: {
    title: "Reativar usuário",
    description: "A conta volta a acessar o JOGA. O motivo é obrigatório e fica na auditoria.",
    confirm: "Reativar conta",
    tone: "default",
  },
};

function statusTone(status: string): string {
  switch (status) {
    case "active":
      return "success";
    case "suspended":
      return "danger";
    case "pending":
      return "warning";
    default:
      return "muted";
  }
}

function userDisplayName(user: AdminUserSummary): string {
  return user.display_name?.trim() || user.email || "Sem nome";
}

function userTag(user: AdminUserSummary): string {
  const tag = user.tag?.trim();
  if (!tag) return "";
  return tag.startsWith("#") ? tag : `#${tag}`;
}

export function AdminUsersPage() {
  useDocumentTitle("Usuários");
  const queryClient = useQueryClient();
  const toast = useToast();

  const [queryDraft, setQueryDraft] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [copiedTag, setCopiedTag] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    email: "",
    display_name: "",
    password: "",
    reason: "",
    verify_email: false,
  });
  const [createErrors, setCreateErrors] = useState<Record<string, string>>({});

  const [action, setAction] = useState<ActionTarget | null>(null);
  const [reason, setReason] = useState("");
  const [actionEmail, setActionEmail] = useState("");
  const [actionUntil, setActionUntil] = useState("");
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState<unknown>(null);
  const [revokeTarget, setRevokeTarget] = useState<AdminUserSummary | null>(null);
  const [revokeReason, setRevokeReason] = useState("");
  const [revokeError, setRevokeError] = useState<string | null>(null);
  const [revokeRequestError, setRevokeRequestError] = useState<unknown>(null);

  const usersQuery = useQuery({
    queryKey: queryKeys.adminUsers(query, status, page),
    queryFn: () => api.listAdminUsers({ query, status, page }),
    placeholderData: keepPreviousData,
  });

  const detailQuery = useQuery({
    queryKey: queryKeys.adminUser(selectedId ?? ""),
    queryFn: () => api.getAdminUser(selectedId ?? ""),
    enabled: Boolean(selectedId),
  });

  const auditQuery = useQuery({
    queryKey: queryKeys.adminUserAudit(selectedId ?? ""),
    queryFn: () => api.listAdminUserAudit(selectedId ?? ""),
    enabled: Boolean(selectedId),
  });

  const users = usersQuery.data?.users ?? [];
  const total = usersQuery.data?.total ?? 0;
  const pageSize = usersQuery.data?.page_size ?? PAGE_SIZE;
  const currentPage = usersQuery.data?.page ?? page;
  const detail = detailQuery.data ?? null;
  const selectedSummary = users.find((item) => item.id === selectedId) ?? null;
  const audit = auditQuery.data?.events ?? [];

  async function invalidateUsers(userId = selectedId) {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
      userId ? queryClient.invalidateQueries({ queryKey: queryKeys.adminUser(userId) }) : null,
    ]);
  }

  function openDetail(userId: string) {
    setSelectedId(userId);
  }

  async function copyTag(tag: string) {
    if (!navigator.clipboard?.writeText) return;
    try {
      await navigator.clipboard.writeText(tag);
      setCopiedTag(tag);
      window.setTimeout(() => {
        setCopiedTag((current) => (current === tag ? null : current));
      }, 2000);
    } catch {
      // Sem permissão de área de transferência: a tag continua visível para cópia manual.
    }
  }

  function resetCreateForm() {
    setCreateForm({
      email: "",
      display_name: "",
      password: "",
      reason: "",
      verify_email: false,
    });
    setCreateErrors({});
  }

  function openCreate() {
    createMutation.reset();
    resetCreateForm();
    setCreateOpen(true);
  }

  function closeCreate() {
    if (createMutation.isPending) return;
    setCreateOpen(false);
    resetCreateForm();
    createMutation.reset();
  }

  function closeDetail() {
    setSelectedId(null);
    setActionError(null);
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuery(queryDraft.trim());
    setPage(1);
  }

  function clearFilters() {
    setQueryDraft("");
    setQuery("");
    setStatus("");
    setPage(1);
  }

  const createMutation = useMutation({
    mutationFn: () =>
      api.createAdminUser({
        email: createForm.email.trim(),
        password: createForm.password,
        display_name: normalizeWhitespace(createForm.display_name),
        verify_email: createForm.verify_email,
        reason: createForm.reason.trim(),
      }),
    onSuccess: async (user) => {
      setCreateOpen(false);
      resetCreateForm();
      toast.push({
        title: "Usuário criado",
        description: createForm.verify_email
          ? "A conta foi criada com e-mail verificado. A exceção ficou registrada na auditoria."
          : "A conta foi criada com e-mail não verificado.",
      });
      await invalidateUsers(user.id);
      createMutation.reset();
    },
    onError: () => setCreateErrors({}),
  });

  const actionMutation = useMutation({
    mutationFn: async (input: AdminActionInput) => {
      switch (input.kind) {
        case "email":
          return api.updateAdminUserEmail(input.user.id, {
            email: input.email ?? "",
            reason: input.reason,
          });
        case "password":
          return api.resetAdminUserPassword(input.user.id, { reason: input.reason });
        case "suspend":
          return api.suspendAdminUser(input.user.id, {
            reason: input.reason,
            ...(input.until ? { until: input.until } : {}),
          });
        case "reactivate":
          return api.reactivateAdminUser(input.user.id, { reason: input.reason });
      }
    },
    onSuccess: async (_result, input) => {
      setAction(null);
      setReason("");
      setActionEmail("");
      setActionUntil("");
      setActionErrors({});
      setActionError(null);
      const titles: Record<ActionKind, string> = {
        email: "E-mail atualizado",
        password: "Código enviado para o e-mail da conta",
        suspend: "Usuário suspenso",
        reactivate: "Usuário reativado",
      };
      toast.push({
        title: titles[input.kind],
        description:
          input.kind === "password"
            ? "As sessões foram revogadas e o código de redefinição foi enviado para o e-mail da conta."
            : "A ação foi registrada na auditoria.",
      });
      await invalidateUsers(input.user.id);
      actionMutation.reset();
    },
    onError: (caught) => setActionError(caught),
  });

  const revokeMutation = useMutation({
    mutationFn: () => api.revokeAdminUserSessions(revokeTarget?.id ?? "", { reason: revokeReason }),
    onSuccess: async () => {
      setRevokeTarget(null);
      setRevokeReason("");
      setRevokeError(null);
      setRevokeRequestError(null);
      toast.push({
        title: "Sessões revogadas",
        description: "A ação foi registrada na auditoria.",
      });
      await invalidateUsers(revokeTarget?.id ?? null);
    },
    onError: (caught) => setRevokeRequestError(caught),
  });

  function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    const emailValidation = emailError(createForm.email);
    if (emailValidation) errors.email = emailValidation;
    const nameValidation = textError(createForm.display_name, {
      label: "o nome de exibição",
      min: 2,
      max: 60,
    });
    if (nameValidation) errors.display_name = nameValidation;
    const passwordValidation = passwordError(createForm.password, createForm.email);
    if (passwordValidation) errors.password = passwordValidation;
    const reasonValidation = textError(createForm.reason, {
      label: "o motivo",
      min: 3,
      max: 500,
    });
    if (reasonValidation) errors.reason = reasonValidation;
    if (Object.keys(errors).length > 0) {
      setCreateErrors(errors);
      const first = firstErrorId(errors, ["email", "display_name", "password", "reason"]);
      if (first) document.getElementById(`admin-create-${first}`)?.focus();
      return;
    }
    setCreateErrors({});
    createMutation.mutate();
  }

  function openAction(kind: ActionKind, user: AdminUserSummary) {
    setAction({ kind, user });
    setReason("");
    setActionEmail(user.email ?? "");
    setActionUntil("");
    setActionErrors({});
    setActionError(null);
  }

  function confirmAction() {
    if (!action) return;
    const errors: Record<string, string> = {};
    const reasonValidation = textError(reason, { label: "o motivo", min: 3, max: 500 });
    if (reasonValidation) errors.reason = reasonValidation;
    if (action.kind === "email") {
      const emailValidation = emailError(actionEmail);
      if (emailValidation) {
        errors.email = emailValidation;
      } else if (
        actionEmail.trim().toLowerCase() === (action.user.email ?? "").trim().toLowerCase()
      ) {
        errors.email = "Informe um e-mail diferente do atual.";
      }
    }
    if (action.kind === "suspend" && actionUntil.trim()) {
      const parsed = new Date(actionUntil);
      if (Number.isNaN(parsed.getTime())) {
        errors.until = "Informe uma data e hora válidas.";
      } else if (parsed.getTime() <= Date.now()) {
        errors.until = "A suspensão deve terminar no futuro.";
      }
    }
    if (Object.keys(errors).length > 0) {
      setActionErrors(errors);
      const first = firstErrorId(errors, ["email", "until"]);
      if (first) document.getElementById(`admin-action-${first}`)?.focus();
      return;
    }
    setActionErrors({});
    actionMutation.mutate({
      kind: action.kind,
      user: action.user,
      reason: reason.trim(),
      email: action.kind === "email" ? actionEmail.trim() : undefined,
      until:
        action.kind === "suspend" && actionUntil.trim()
          ? new Date(actionUntil).toISOString()
          : undefined,
    });
  }

  function confirmRevoke() {
    const validation = textError(revokeReason, { label: "o motivo", min: 3, max: 500 });
    if (validation) {
      setRevokeError(validation);
      return;
    }
    setRevokeError(null);
    revokeMutation.mutate();
  }

  const copy = action ? ACTION_COPY[action.kind] : null;

  return (
    <>
      <PageHeader
        eyebrow="JOGA y ADMINISTRAÇÃO"
        title="Usuários"
        description="Busca paginada, detalhe auditável e ações administrativas com motivo. Nenhuma senha é exibida ou armazenada no navegador."
      />

      <section className="card">
        <SectionHeading
          title="Contas da plataforma"
          description="A API mascara o CPF e registra cada ação administrativa."
          actions={
            <button type="button" className="button button--primary" onClick={openCreate}>
              <UsersIcon size={16} />
              Novo usuário
            </button>
          }
        />

        <form className="filters-form filters-form--search" onSubmit={submitSearch} noValidate>
          <TextField
            id="admin-user-query"
            label="Buscar"
            value={queryDraft}
            onChange={(event) => setQueryDraft(event.target.value)}
            placeholder="Nome, tag, e-mail ou CPF"
            maxLength={120}
          />
          <SelectField
            id="admin-user-status"
            label="Status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </SelectField>
          <div className="filters-form__actions">
            <button type="submit" className="button" disabled={usersQuery.isFetching}>
              <SearchIcon size={16} />
              Buscar
            </button>
            <button type="button" className="button button--ghost" onClick={clearFilters}>
              Limpar
            </button>
          </div>
        </form>

        {usersQuery.error ? (
          isForbidden(usersQuery.error) ? (
            <AdminForbiddenState />
          ) : (
            <ErrorNotice
              message={adminErrorMessage(usersQuery.error)}
              requestId={requestIdOf(usersQuery.error)}
              onRetry={() => void usersQuery.refetch()}
            />
          )
        ) : usersQuery.isPending ? (
          <SkeletonList rows={4} label="Carregando usuários..." />
        ) : users.length === 0 ? (
          <EmptyState title="Nenhum usuário encontrado" icon={<UsersIcon size={28} />}>
            {query || status
              ? "Ajuste a busca ou o filtro de status para encontrar outra conta."
              : "Ainda não há contas cadastradas na plataforma."}
          </EmptyState>
        ) : (
          <ul className="admin-list">
            {users.map((user) => {
              const tag = userTag(user);
              return (
                <li key={user.id}>
                  <button
                    type="button"
                    className={selectedId === user.id ? "admin-row admin-row--active" : "admin-row"}
                    onClick={() => openDetail(user.id)}
                    aria-pressed={selectedId === user.id}
                  >
                    <span className="admin-row__identity">
                      <span className="avatar avatar--small" aria-hidden="true">
                        {initials(userDisplayName(user))}
                      </span>
                      <span>
                        <strong>
                          {userDisplayName(user)}
                          {tag ? <span className="admin-tag">{tag}</span> : null}
                        </strong>
                        <small>
                          {user.email ?? "Sem e-mail"} · desde {formatDate(user.created_at)}
                        </small>
                      </span>
                    </span>
                    <span className={`badge badge--${statusTone(user.status)}`}>
                      {userStatusLabel(user.status)}
                    </span>
                  </button>
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
          disabled={usersQuery.isFetching}
        />
      </section>

      <Drawer
        open={Boolean(selectedId)}
        title="Detalhe do usuário"
        description={detail?.email ?? selectedSummary?.email ?? undefined}
        closeLabel="Fechar detalhe do usuário"
        onClose={closeDetail}
        footer={
          <div className="drawer__footer-row">
            <button type="button" className="button button--ghost" onClick={closeDetail}>
              Fechar
            </button>
          </div>
        }
      >
        {detailQuery.isPending ? (
          <SkeletonList rows={4} label="Carregando detalhe..." />
        ) : detailQuery.error ? (
          isForbidden(detailQuery.error) ? (
            <AdminForbiddenState />
          ) : (
            <ErrorNotice
              message={adminErrorMessage(detailQuery.error)}
              requestId={requestIdOf(detailQuery.error)}
              onRetry={() => void detailQuery.refetch()}
            />
          )
        ) : detail ? (
          <>
            <div className="admin-detail__heading">
              <span className="avatar" aria-hidden="true">
                {initials(userDisplayName(detail))}
              </span>
              <div>
                <strong>{userDisplayName(detail)}</strong>
                {userTag(detail) ? (
                  <span className="admin-detail__tagline">
                    <span className="admin-tag">{userTag(detail)}</span>
                    <button
                      type="button"
                      className="button button--small button--ghost admin-tag__copy"
                      onClick={() => void copyTag(userTag(detail))}
                    >
                      {copiedTag === userTag(detail) ? "Copiado" : "Copiar tag"}
                    </button>
                  </span>
                ) : null}
                <small>{detail.email ?? "Sem e-mail cadastrado"}</small>
              </div>
              <span className={`badge badge--${statusTone(detail.status)}`}>
                {userStatusLabel(detail.status)}
              </span>
            </div>

            <dl className="admin-meta">
              <div>
                <dt>ID</dt>
                <dd className="mono">{detail.id}</dd>
              </div>
              <div>
                <dt>CPF</dt>
                <dd>{detail.cpf_masked ?? "Não informado"}</dd>
              </div>
              <div>
                <dt>Criado em</dt>
                <dd>{formatDate(detail.created_at)}</dd>
              </div>
              {detail.updated_at ? (
                <div>
                  <dt>Atualizado em</dt>
                  <dd>{formatDate(detail.updated_at)}</dd>
                </div>
              ) : null}
              {detail.suspended_until ? (
                <div>
                  <dt>Suspenso até</dt>
                  <dd>{formatDate(detail.suspended_until)}</dd>
                </div>
              ) : null}
              {typeof detail.email_verified === "boolean" ? (
                <div>
                  <dt>E-mail verificado</dt>
                  <dd>{detail.email_verified ? "Sim" : "Não"}</dd>
                </div>
              ) : null}
            </dl>

            <div className="admin-actions" aria-label="Ações do usuário">
              <button
                type="button"
                className="button button--small"
                onClick={() => openAction("email", detail)}
              >
                Alterar e-mail
              </button>
              <button
                type="button"
                className="button button--small"
                onClick={() => openAction("password", detail)}
              >
                Redefinir senha
              </button>
              {detail.status === "suspended" ? (
                <button
                  type="button"
                  className="button button--small"
                  onClick={() => openAction("reactivate", detail)}
                >
                  Reativar
                </button>
              ) : (
                <button
                  type="button"
                  className="button button--small button--danger"
                  onClick={() => openAction("suspend", detail)}
                >
                  Suspender
                </button>
              )}
              <button
                type="button"
                className="button button--small button--danger"
                onClick={() => {
                  setRevokeTarget(detail);
                  setRevokeReason("");
                  setRevokeError(null);
                  setRevokeRequestError(null);
                }}
              >
                Revogar sessões
              </button>
            </div>

            {actionError && !action ? (
              <ErrorNotice
                message={adminErrorMessage(actionError)}
                requestId={requestIdOf(actionError)}
              />
            ) : null}

            <section className="admin-subsection">
              <SectionHeading
                title="Auditoria da conta"
                description="Trilha append-only das ações administrativas e de segurança."
                level={3}
              />
              {auditQuery.error ? (
                isForbidden(auditQuery.error) ? (
                  <AdminForbiddenState />
                ) : (
                  <ErrorNotice
                    message={adminErrorMessage(auditQuery.error)}
                    requestId={requestIdOf(auditQuery.error)}
                    onRetry={() => void auditQuery.refetch()}
                  />
                )
              ) : auditQuery.isPending ? (
                <SkeletonList rows={3} label="Carregando auditoria..." />
              ) : audit.length === 0 ? (
                <EmptyState title="Nenhum evento">
                  Ainda não há ações registradas para esta conta.
                </EmptyState>
              ) : (
                <ul className="audit-list">
                  {audit.map((event) => (
                    <li key={event.id} className="audit-row">
                      <div className="audit-row__main">
                        <strong>{auditActionLabel(event.action)}</strong>
                        <small>
                          Ator:{" "}
                          {event.actor_user_id ? `#${shortId(event.actor_user_id)}` : "sistema"} ·{" "}
                          {formatDate(event.created_at)}
                        </small>
                        {event.reason ? <small>Motivo: {event.reason}</small> : null}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        ) : (
          <EmptyState title="Usuário não encontrado" icon={<UsersIcon size={28} />}>
            O registro pode ter sido removido ou está fora do seu acesso.
          </EmptyState>
        )}
      </Drawer>

      <Modal
        open={createOpen}
        title="Novo usuário"
        description="A conta é criada pela administração da plataforma. A senha não é gravada no navegador e o motivo fica na auditoria."
        onClose={closeCreate}
        size="lg"
        footer={
          <>
            <button
              type="button"
              className="button button--ghost"
              onClick={closeCreate}
              disabled={createMutation.isPending}
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="admin-create-user"
              className="button button--primary"
              disabled={createMutation.isPending}
              aria-busy={createMutation.isPending || undefined}
            >
              {createMutation.isPending ? "Criando..." : "Criar usuário"}
            </button>
          </>
        }
      >
        <form id="admin-create-user" className="form" onSubmit={submitCreate} noValidate>
          <TextField
            id="admin-create-email"
            label="E-mail"
            type="email"
            value={createForm.email}
            onChange={(event) => {
              setCreateForm((current) => ({ ...current, email: event.target.value }));
              if (createErrors.email) setCreateErrors((current) => ({ ...current, email: "" }));
            }}
            error={createErrors.email}
            autoComplete="off"
            inputMode="email"
            maxLength={254}
            required
            data-autofocus
          />
          <TextField
            id="admin-create-display_name"
            label="Nome de exibição"
            value={createForm.display_name}
            onChange={(event) => {
              setCreateForm((current) => ({ ...current, display_name: event.target.value }));
              if (createErrors.display_name) {
                setCreateErrors((current) => ({ ...current, display_name: "" }));
              }
            }}
            error={createErrors.display_name}
            hint="De 2 a 60 caracteres."
            maxLength={60}
            required
          />
          <TextField
            id="admin-create-password"
            label="Senha inicial"
            type="password"
            value={createForm.password}
            onChange={(event) => {
              setCreateForm((current) => ({ ...current, password: event.target.value }));
              if (createErrors.password)
                setCreateErrors((current) => ({ ...current, password: "" }));
            }}
            error={createErrors.password}
            hint="De 10 a 128 caracteres. A senha fica apenas em memória durante o envio."
            autoComplete="new-password"
            maxLength={128}
            required
          />
          <TextareaField
            id="admin-create-reason"
            label="Motivo"
            value={createForm.reason}
            onChange={(event) => {
              setCreateForm((current) => ({ ...current, reason: event.target.value }));
              if (createErrors.reason) setCreateErrors((current) => ({ ...current, reason: "" }));
            }}
            error={createErrors.reason}
            hint="Obrigatório. Fica registrado na auditoria administrativa."
            maxLength={500}
            rows={3}
            required
          />
          <CheckboxField
            id="admin-create-verify-email"
            label="Marcar e-mail como verificado"
            hint="Exceção auditada. Por padrão a conta nasce com e-mail não verificado."
            checked={createForm.verify_email}
            onChange={(checked) =>
              setCreateForm((current) => ({ ...current, verify_email: checked }))
            }
          />
          {createMutation.error ? (
            <ErrorNotice
              message={adminErrorMessage(createMutation.error)}
              requestId={requestIdOf(createMutation.error)}
            />
          ) : null}
        </form>
      </Modal>

      <ReasonDialog
        open={Boolean(action)}
        title={copy?.title ?? "Ação administrativa"}
        description={copy?.description}
        label="Motivo"
        value={reason}
        onChange={(value) => {
          setReason(value);
          if (actionErrors.reason) setActionErrors((current) => ({ ...current, reason: "" }));
        }}
        error={actionErrors.reason ?? null}
        placeholder="Descreva o motivo desta ação"
        maxLength={500}
        minLength={3}
        confirmLabel={copy?.confirm ?? "Confirmar"}
        tone={copy?.tone ?? "default"}
        busy={actionMutation.isPending}
        onConfirm={confirmAction}
        onClose={() => {
          if (actionMutation.isPending) return;
          setAction(null);
          setReason("");
          setActionEmail("");
          setActionUntil("");
          setActionErrors({});
          setActionError(null);
        }}
      >
        {action ? (
          <div className="dialog-summary">
            <strong>
              {userDisplayName(action.user)}
              {userTag(action.user) ? (
                <span className="admin-tag">{userTag(action.user)}</span>
              ) : null}
            </strong>
            <span>{action.user.email ?? "Sem e-mail"}</span>
          </div>
        ) : null}
        {action?.kind === "email" ? (
          <TextField
            id="admin-action-email"
            label="Novo e-mail"
            type="email"
            value={actionEmail}
            onChange={(event) => {
              setActionEmail(event.target.value);
              if (actionErrors.email) setActionErrors((current) => ({ ...current, email: "" }));
            }}
            error={actionErrors.email}
            autoComplete="off"
            inputMode="email"
            maxLength={254}
            required
          />
        ) : null}
        {action?.kind === "suspend" ? (
          <TextField
            id="admin-action-until"
            label="Suspender até (opcional)"
            type="datetime-local"
            value={actionUntil}
            onChange={(event) => {
              setActionUntil(event.target.value);
              if (actionErrors.until) setActionErrors((current) => ({ ...current, until: "" }));
            }}
            error={actionErrors.until}
            hint="Sem data, a suspensão fica vigente até a reativação manual."
          />
        ) : null}
        {actionError ? (
          <ErrorNotice
            message={adminErrorMessage(actionError)}
            requestId={requestIdOf(actionError)}
          />
        ) : null}
      </ReasonDialog>

      <ConfirmDialog
        open={Boolean(revokeTarget)}
        title="Revogar sessões?"
        description="Todos os dispositivos conectados serão desconectados. O motivo é obrigatório e fica na auditoria."
        tone="danger"
        confirmLabel="Revogar sessões agora"
        busy={revokeMutation.isPending}
        onConfirm={confirmRevoke}
        onClose={() => {
          if (revokeMutation.isPending) return;
          setRevokeTarget(null);
          setRevokeReason("");
          setRevokeError(null);
          setRevokeRequestError(null);
        }}
      >
        {revokeTarget ? (
          <div className="dialog-summary">
            <strong>
              {userDisplayName(revokeTarget)}
              {userTag(revokeTarget) ? (
                <span className="admin-tag">{userTag(revokeTarget)}</span>
              ) : null}
            </strong>
            <span>{revokeTarget.email ?? "Sem e-mail"}</span>
          </div>
        ) : null}
        <TextField
          id="admin-revoke-reason"
          label="Motivo"
          value={revokeReason}
          onChange={(event) => {
            setRevokeReason(event.target.value);
            if (revokeError) setRevokeError(null);
          }}
          error={revokeError}
          placeholder="Descreva o motivo da revogação"
          maxLength={500}
          minLength={3}
          required
        />
        {revokeRequestError ? (
          <ErrorNotice
            message={adminErrorMessage(revokeRequestError)}
            requestId={requestIdOf(revokeRequestError)}
          />
        ) : null}
      </ConfirmDialog>
    </>
  );
}
