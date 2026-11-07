import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { EmptyState, ErrorNotice, LoadingBlock } from "../components/Feedback";
import { api } from "../lib/api";
import { formatError, requestIdOf, roleLabel } from "../lib/format";
import { queryKeys } from "../lib/query";
import type { Organization } from "../types";

export function OrganizationsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const organizationsQuery = useQuery({
    queryKey: queryKeys.organizations,
    queryFn: async () => (await api.listOrganizations()).organizations,
  });

  const createMutation = useMutation({
    mutationFn: (organizationName: string) => api.createOrganization(organizationName),
    onSuccess: (organization: Organization) => {
      setName("");
      setNotice("Organização criada. Você entrou como proprietário.");
      void queryClient.invalidateQueries({ queryKey: queryKeys.organizations });
      navigate(`/organizations/${organization.id}`);
    },
  });

  function createOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createMutation.mutate(name);
  }

  const organizations = organizationsQuery.data ?? [];
  const queryError = organizationsQuery.error ?? createMutation.error;

  return (
    <div className="app-shell">
      <AppHeader />
      <main className="page">
        <section className="page-heading">
          <div>
            <p className="eyebrow">JOGA y GESTÃO</p>
            <h1>Suas organizações</h1>
            <p className="muted">
              Cada organização isola membros, estabelecimentos e auditoria. Você só vê o que o seu
              vínculo permite.
            </p>
          </div>
        </section>

        {notice ? (
          <div className="notice notice--success" role="status" aria-live="polite">
            {notice}
          </div>
        ) : null}
        {queryError ? (
          <ErrorNotice
            message={formatError(queryError)}
            requestId={requestIdOf(queryError)}
            onRetry={() => void organizationsQuery.refetch()}
          />
        ) : null}

        <section className="grid grid--sidebar">
          <div className="card">
            <h2>Organizações vinculadas</h2>
            {organizationsQuery.isPending ? (
              <LoadingBlock />
            ) : organizations.length === 0 ? (
              <EmptyState title="Nenhuma organização ainda">
                Crie a primeira organização ao lado para começar.
              </EmptyState>
            ) : (
              <ul className="org-list">
                {organizations.map((organization) => (
                  <li key={organization.id}>
                    <Link to={`/organizations/${organization.id}`} className="org-card">
                      <span>
                        <strong>{organization.name}</strong>
                        <small>
                          {roleLabel(organization.role)} · {organization.status}
                        </small>
                      </span>
                      <span className="org-card__arrow" aria-hidden="true">
                        →
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <aside className="card">
            <h2>Nova organização</h2>
            <p className="muted">
              O criador entra automaticamente como proprietário e pode convidar administradores e
              operadores.
            </p>
            <form className="form" onSubmit={createOrganization}>
              <label className="field">
                <span>Nome da organização ou arena</span>
                <input
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  minLength={2}
                  maxLength={120}
                  placeholder="Ex.: Arena Tijuca"
                  required
                />
              </label>
              <button
                type="submit"
                className="button button--primary"
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? "Criando..." : "Criar organização"}
              </button>
            </form>
          </aside>
        </section>
      </main>
    </div>
  );
}
