import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { EmptyState, ErrorNotice, SkeletonList } from "../components/Feedback";
import { TextField } from "../components/ui/Field";
import { ArrowRightIcon, BuildingIcon, PlusIcon } from "../components/ui/Icons";
import { PageHeader, SectionHeading } from "../components/ui/PageHeader";
import { useToast } from "../components/ui/toast-context";
import { api } from "../lib/api";
import { formatError, organizationStatusLabel, requestIdOf, roleLabel } from "../lib/format";
import { queryKeys } from "../lib/query";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import { normalizeWhitespace, textError } from "../lib/validation";
import type { Organization } from "../types";

const NAME_RULE = {
  label: "o nome da organização",
  min: 2,
  max: 120,
};

export function OrganizationsPage() {
  useDocumentTitle("Suas organizações");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);

  const organizationsQuery = useQuery({
    queryKey: queryKeys.organizations,
    queryFn: async () => (await api.listOrganizations()).organizations,
  });

  const createMutation = useMutation({
    mutationFn: (organizationName: string) => api.createOrganization(organizationName),
    onSuccess: (organization: Organization) => {
      setName("");
      setNameError(null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.organizations });
      toast.push({
        title: "Organização criada",
        description: "Você entrou como proprietário e já pode configurar o estabelecimento.",
      });
      navigate(`/organizations/${organization.id}`);
    },
  });

  function createOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const error = textError(name, NAME_RULE);
    if (error) {
      setNameError(error);
      document.getElementById("org-name")?.focus();
      return;
    }
    createMutation.mutate(normalizeWhitespace(name));
  }

  const organizations = organizationsQuery.data ?? [];
  const queryError = organizationsQuery.error;

  return (
    <>
      <PageHeader
        eyebrow="JOGA y GESTÃO"
        title="Suas organizações"
        description="Cada organização isola membros, estabelecimentos, reservas e auditoria. Você só vê o que o seu vínculo permite."
      />

      {queryError ? (
        <ErrorNotice
          message={formatError(queryError)}
          requestId={requestIdOf(queryError)}
          onRetry={() => void organizationsQuery.refetch()}
        />
      ) : null}
      {createMutation.error ? (
        <ErrorNotice
          message={formatError(createMutation.error)}
          requestId={requestIdOf(createMutation.error)}
        />
      ) : null}

      <section className="grid grid--sidebar">
        <div className="card">
          <SectionHeading
            title="Organizações vinculadas"
            description="Abra uma organização para gerenciar membros, quadras, reservas e financeiro."
          />
          {organizationsQuery.isPending ? (
            <SkeletonList rows={3} label="Carregando organizações..." />
          ) : organizations.length === 0 ? (
            <EmptyState
              title="Nenhuma organização ainda"
              icon={<BuildingIcon size={28} />}
              action={
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() => document.getElementById("org-name")?.focus()}
                >
                  <PlusIcon size={16} />
                  Criar primeira organização
                </button>
              }
            >
              Crie a primeira organização ao lado para começar a operar no painel.
            </EmptyState>
          ) : (
            <ul className="org-list">
              {organizations.map((organization) => (
                <li key={organization.id}>
                  <Link to={`/organizations/${organization.id}`} className="org-card">
                    <span className="org-card__identity">
                      <span className="org-card__icon" aria-hidden="true">
                        <BuildingIcon size={19} />
                      </span>
                      <span>
                        <strong>{organization.name}</strong>
                        <small>
                          {roleLabel(organization.role)} ·{" "}
                          {organizationStatusLabel(organization.status)}
                        </small>
                      </span>
                    </span>
                    <span className="org-card__arrow" aria-hidden="true">
                      <ArrowRightIcon size={18} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        <aside className="card card--form">
          <SectionHeading
            title="Nova organização"
            description="O criador entra automaticamente como proprietário e pode adicionar administradores e operadores."
            level={2}
          />
          <form className="form" onSubmit={createOrganization} noValidate>
            <TextField
              id="org-name"
              label="Nome da organização ou arena"
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                if (nameError) setNameError(null);
              }}
              error={nameError}
              hint="De 2 a 120 caracteres. Esse nome aparece no painel e na auditoria."
              minLength={2}
              maxLength={120}
              placeholder="Ex.: Arena Tijuca"
              autoComplete="organization"
              required
            />
            <button
              type="submit"
              className="button button--primary button--block"
              disabled={createMutation.isPending}
              aria-busy={createMutation.isPending || undefined}
            >
              {createMutation.isPending ? "Criando..." : "Criar organização"}
            </button>
          </form>
        </aside>
      </section>
    </>
  );
}
