import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { EmptyState, ErrorNotice, InfoNotice, SkeletonList } from "../components/Feedback";
import { TextField } from "../components/ui/Field";
import { ArrowRightIcon, BuildingIcon, PlusIcon } from "../components/ui/Icons";
import { PageHeader, SectionHeading } from "../components/ui/PageHeader";
import { useToast } from "../components/ui/toast-context";
import { api } from "../lib/api";
import { formatError, organizationStatusLabel, requestIdOf, roleLabel } from "../lib/format";
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
  const [form, setForm] = useState({ name: "", cnpj: "", cpf: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const organizationsQuery = useQuery({
    queryKey: queryKeys.organizations,
    queryFn: async () => (await api.listOrganizations()).organizations,
  });

  const createMutation = useMutation({
    mutationFn: (payload: { name: string; cnpj: string; cpf: string }) =>
      api.createOrganization(payload),
    onSuccess: (organization: Organization) => {
      // O CPF só existe no formulário; depois do envio ele nunca é reexibido.
      setForm({ name: "", cnpj: "", cpf: "" });
      setErrors({});
      void queryClient.invalidateQueries({ queryKey: queryKeys.organizations });
      toast.push({
        title: "Organização criada",
        description:
          "O CNPJ foi verificado. Você entrou como proprietário e já pode configurar o estabelecimento.",
      });
      navigate(`/organizations/${organization.id}`);
    },
  });

  function update(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    if (errors[field]) setErrors((current) => ({ ...current, [field]: "" }));
  }

  function createOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: Record<string, string> = {};
    const nameError = textError(form.name, NAME_RULE);
    if (nameError) next.name = nameError;
    const cnpjValidation = cnpjError(form.cnpj);
    if (cnpjValidation) next.cnpj = cnpjValidation;
    const cpfValidation = cpfError(form.cpf);
    if (cpfValidation) next.cpf = cpfValidation;
    if (Object.keys(next).length > 0) {
      setErrors(next);
      const first = ["name", "cnpj", "cpf"].find((field) => next[field]);
      if (first) document.getElementById(`org-${first}`)?.focus();
      return;
    }
    createMutation.mutate({
      name: normalizeWhitespace(form.name),
      cnpj: normalizeCnpj(form.cnpj),
      cpf: normalizeCpf(form.cpf),
    });
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
                  className="button button--ghost"
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
            description="O criador entra automaticamente como proprietário. O CNPJ precisa estar ativo e o CPF deve ser de um responsável no QSA."
            level={2}
          />
          <form className="form" onSubmit={createOrganization} noValidate>
            <TextField
              id="org-name"
              label="Nome da organização ou arena"
              value={form.name}
              onChange={(event) => update("name", event.target.value)}
              error={errors.name}
              hint="De 2 a 120 caracteres. Esse nome aparece no painel e na auditoria."
              minLength={2}
              maxLength={120}
              placeholder="Ex.: Arena Tijuca"
              autoComplete="organization"
              required
            />
            <TextField
              id="org-cnpj"
              label="CNPJ"
              value={form.cnpj}
              onChange={(event) => update("cnpj", formatCnpj(event.target.value))}
              error={errors.cnpj}
              hint="Somente CNPJ ativo de empresa com atividade esportiva."
              maxLength={18}
              inputMode="numeric"
              autoComplete="off"
              placeholder="00.000.000/0000-00"
              required
            />
            <TextField
              id="org-cpf"
              label="CPF do responsável"
              value={form.cpf}
              onChange={(event) => update("cpf", formatCpf(event.target.value))}
              error={errors.cpf}
              hint="Precisa ser de um sócio do QSA. Não guardamos nem exibimos o CPF no painel depois do envio."
              maxLength={14}
              inputMode="numeric"
              autoComplete="off"
              placeholder="000.000.000-00"
              required
            />
            <InfoNotice>
              A verificação consulta a Receita Federal. Se o CNPJ estiver inativo, com atividade
              incompatível ou o CPF não estiver no QSA, a organização não é criada.
            </InfoNotice>
            <button
              type="submit"
              className="button button--primary button--block"
              disabled={createMutation.isPending}
              aria-busy={createMutation.isPending || undefined}
            >
              {createMutation.isPending ? "Verificando CNPJ..." : "Verificar CNPJ e criar"}
            </button>
          </form>
        </aside>
      </section>
    </>
  );
}
