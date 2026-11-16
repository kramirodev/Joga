import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { EmptyState, ErrorNotice, SkeletonList } from "../../components/Feedback";
import { SelectField, TextField } from "../../components/ui/Field";
import { UsersIcon } from "../../components/ui/Icons";
import { ConfirmDialog } from "../../components/ui/Modal";
import { SectionHeading } from "../../components/ui/PageHeader";
import { useToast } from "../../components/ui/toast-context";
import { api } from "../../lib/api";
import {
  formatDate,
  formatError,
  initials,
  requestIdOf,
  roleLabel,
  shortId,
} from "../../lib/format";
import { queryKeys } from "../../lib/query";
import { uuidError } from "../../lib/validation";
import type { Member, Organization, Role } from "../../types";

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
  onNotice: (title: string) => void;
  onError: (error: unknown) => void;
}) {
  const navigate = useNavigate();
  const [role, setRole] = useState<Role>(member.role);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const manageable = actorRole === "OWNER" || (actorRole === "ADMIN" && member.role === "OPERATOR");
  const isSelf = member.user_id === currentUserId;
  const displayName = member.display_name || "Membro sem nome";

  const changeRole = useMutation({
    mutationFn: (nextRole: Role) => api.changeMemberRole(organizationId, member.user_id, nextRole),
    onSuccess: async () => {
      await onChanged();
      onNotice("Papel atualizado.");
    },
    onError,
  });

  const removeMember = useMutation({
    mutationFn: () => api.removeMember(organizationId, member.user_id),
    onSuccess: async () => {
      setConfirmOpen(false);
      if (isSelf) {
        navigate("/", { replace: true });
        onNotice("Você saiu da organização.");
        return;
      }
      await onChanged();
      onNotice("Membro removido.");
    },
    onError,
  });

  const busy = changeRole.isPending || removeMember.isPending;

  function saveRole() {
    if (role === member.role) return;
    changeRole.mutate(role);
  }

  return (
    <li className="member-row">
      <div className="member-row__identity">
        <span className="avatar" aria-hidden="true">
          {initials(member.display_name)}
        </span>
        <div className="member-row__text">
          <strong>{displayName}</strong>
          <small className="mono" title="Identificador da conta JOGA">
            #{shortId(member.user_id)}
          </small>
          <small>Desde {formatDate(member.created_at)}</small>
        </div>
      </div>

      <div className="member-row__role">
        {manageable ? (
          <SelectField
            id={`member-role-${member.user_id}`}
            label={`Papel de ${displayName}`}
            className="field--compact"
            value={role}
            onChange={(event) => setRole(event.target.value as Role)}
            disabled={busy}
            hint={undefined}
          >
            {assignableRoles(actorRole).map((option) => (
              <option key={option} value={option}>
                {roleLabel(option)}
              </option>
            ))}
          </SelectField>
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
            {changeRole.isPending ? "Salvando..." : "Salvar papel"}
          </button>
          <button
            type="button"
            className="button button--small button--danger"
            onClick={() => setConfirmOpen(true)}
            disabled={busy}
          >
            {isSelf ? "Sair" : "Remover"}
          </button>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirmOpen}
        title={isSelf ? "Sair da organização?" : "Remover membro?"}
        description={
          isSelf
            ? "Você perderá o acesso a esta organização. Se for o último proprietário, a operação será recusada pelo servidor."
            : `${displayName} perderá o acesso a membros, estabelecimentos, reservas e auditoria desta organização.`
        }
        tone="danger"
        confirmLabel={isSelf ? "Sair da organização" : "Remover membro"}
        busy={removeMember.isPending}
        onConfirm={() => removeMember.mutate()}
        onClose={() => setConfirmOpen(false)}
      >
        {removeMember.error ? (
          <ErrorNotice
            message={formatError(removeMember.error)}
            requestId={requestIdOf(removeMember.error)}
          />
        ) : null}
      </ConfirmDialog>
    </li>
  );
}

export function MembersPanel({
  organization,
  members,
  currentUserId,
  loading,
  error,
  onRetry,
}: {
  organization: Organization;
  members: Member[];
  currentUserId: string | null;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [newMemberId, setNewMemberId] = useState("");
  const [newMemberRole, setNewMemberRole] = useState<Role>("OPERATOR");
  const [idError, setIdError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const canManageMembers = organization.role !== "OPERATOR";
  const roles = assignableRoles(organization.role);

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.members(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.audit(organization.id) }),
    ]);
  };

  const addMemberMutation = useMutation({
    mutationFn: (payload: { userId: string; role: Role }) =>
      api.addMember(organization.id, payload.userId, payload.role),
    onSuccess: async () => {
      setNewMemberId("");
      setNewMemberRole("OPERATOR");
      setIdError(null);
      setActionError(null);
      toast.push({
        title: "Membro adicionado",
        description: "O novo vínculo já pode acessar os recursos permitidos pelo papel.",
      });
      await invalidate();
    },
    onError: (caught) => setActionError(caught),
  });

  function addMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validation = uuidError(newMemberId, "o UUID da conta JOGA");
    if (validation) {
      setIdError(validation);
      document.getElementById("new-member-id")?.focus();
      return;
    }
    addMemberMutation.mutate({ userId: newMemberId.trim(), role: newMemberRole });
  }

  const hasError = error ?? actionError;

  return (
    <section className="stack">
      <div className="card">
        <SectionHeading
          title="Membros e permissões"
          description={
            organization.role === "OWNER"
              ? "Você pode gerenciar proprietários, administradores e operadores."
              : organization.role === "ADMIN"
                ? "Você pode gerenciar operadores. Proprietários e administradores só podem ser alterados por um proprietário."
                : "Você pode consultar os membros, mas não alterá-los."
          }
        />
        {hasError ? (
          <ErrorNotice
            message={formatError(hasError)}
            requestId={requestIdOf(hasError)}
            onRetry={onRetry}
          />
        ) : null}

        {loading ? (
          <SkeletonList rows={3} label="Carregando membros..." />
        ) : members.length === 0 ? (
          <EmptyState title="Nenhum membro" icon={<UsersIcon size={28} />}>
            A organização ainda não tem vínculos. Adicione o primeiro membro abaixo.
          </EmptyState>
        ) : (
          <ul className="member-list">
            {members.map((member) => (
              <MemberRow
                key={`${member.user_id}:${member.role}`}
                member={member}
                organizationId={organization.id}
                actorRole={organization.role}
                currentUserId={currentUserId}
                onChanged={invalidate}
                onNotice={(title) => toast.push({ title })}
                onError={(caught) => {
                  setActionError(caught);
                  toast.push({
                    title: "Não foi possível alterar o membro",
                    description: formatError(caught),
                    tone: "error",
                    requestId: requestIdOf(caught),
                  });
                }}
              />
            ))}
          </ul>
        )}
      </div>

      {canManageMembers ? (
        <div className="card card--form">
          <SectionHeading
            title="Adicionar membro"
            description="Informe o identificador da conta JOGA. A pessoa pode ser jogadora e também administrar o estabelecimento."
          />
          <form className="form" onSubmit={addMember} noValidate>
            <TextField
              id="new-member-id"
              label="UUID da conta JOGA"
              value={newMemberId}
              onChange={(event) => {
                setNewMemberId(event.target.value);
                if (idError) setIdError(null);
              }}
              error={idError}
              hint="São 36 caracteres no formato 00000000-0000-0000-0000-000000000000. O convite por telefone ainda não está disponível no backend."
              placeholder="00000000-0000-0000-0000-000000000000"
              autoComplete="off"
              spellCheck={false}
              inputClassName="mono"
              maxLength={36}
              required
            />
            <SelectField
              id="new-member-role"
              label="Papel"
              value={newMemberRole}
              onChange={(event) => setNewMemberRole(event.target.value as Role)}
              hint={
                organization.role === "OWNER"
                  ? "Proprietário gerencia todos os papéis; administrador gerencia operadores."
                  : "Administradores só podem adicionar operadores."
              }
            >
              {roles.map((role) => (
                <option key={role} value={role}>
                  {roleLabel(role)}
                </option>
              ))}
            </SelectField>
            <button
              type="submit"
              className="button button--primary"
              disabled={addMemberMutation.isPending}
              aria-busy={addMemberMutation.isPending || undefined}
            >
              {addMemberMutation.isPending ? "Adicionando..." : "Adicionar membro"}
            </button>
          </form>
        </div>
      ) : (
        <div className="card">
          <p className="muted">
            Seu papel de operador permite consultar a equipe, mas não adicionar ou remover membros.
          </p>
        </div>
      )}
    </section>
  );
}
