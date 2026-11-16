import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { EmptyState, ErrorNotice, InfoNotice, SkeletonList } from "../../components/Feedback";
import { SelectField, TextareaField, TextField } from "../../components/ui/Field";
import { PhoneField } from "../../components/ui/PhoneField";
import { Modal } from "../../components/ui/Modal";
import { Pagination } from "../../components/ui/Pagination";
import { SectionHeading } from "../../components/ui/PageHeader";
import { useToast } from "../../components/ui/toast-context";
import { api } from "../../lib/api";
import {
  disputeStatusLabel,
  formatDate,
  formatDateRange,
  formatError,
  formatMoney,
  ledgerEntryLabel,
  payoutStatusLabel,
  releaseStatusLabel,
  requestIdOf,
  shortId,
} from "../../lib/format";
import { DEFAULT_COUNTRY, toE164 } from "../../lib/phone";
import { queryKeys } from "../../lib/query";
import {
  cnpjError,
  formatCnpj,
  normalizeCnpj,
  pixKeyError,
  type PixKeyType,
} from "../../lib/validation";
import type { Organization, Receivable } from "../../types";

const PIX_TYPE_LABELS: Record<PixKeyType, string> = {
  cnpj: "CNPJ",
  email: "E-mail",
  phone: "Telefone",
  random: "Chave aleatória",
};

const PIX_PLACEHOLDERS: Record<PixKeyType, string> = {
  cnpj: "00.000.000/0000-00",
  email: "financeiro@arena.com.br",
  phone: "11 98765-4321",
  random: "00000000-0000-0000-0000-000000000000",
};

const PAGE_SIZE = 50;

export function FinancialPanel({ organization }: { organization: Organization }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [receivableOffset, setReceivableOffset] = useState(0);
  const [statementOffset, setStatementOffset] = useState(0);
  const [disputeOffset, setDisputeOffset] = useState(0);

  const [cnpjInput, setCnpjInput] = useState("");
  const [keyType, setKeyType] = useState<PixKeyType>("cnpj");
  const [keyValue, setKeyValue] = useState("");
  const [phoneDigits, setPhoneDigits] = useState("");
  const [payoutErrors, setPayoutErrors] = useState<Record<string, string>>({});
  const [payoutError, setPayoutError] = useState<unknown>(null);

  const [disputeTarget, setDisputeTarget] = useState<Receivable | null>(null);
  const [disputeReason, setDisputeReason] = useState("");
  const [disputeEvidence, setDisputeEvidence] = useState("");
  const [disputeErrors, setDisputeErrors] = useState<Record<string, string>>({});
  const [disputeActionError, setDisputeActionError] = useState<unknown>(null);

  const canManage = organization.role === "OWNER" || organization.role === "ADMIN";

  const summaryQuery = useQuery({
    queryKey: queryKeys.financialSummary(organization.id),
    queryFn: () => api.getOrganizationFinancialSummary(organization.id),
  });
  const receivablesQuery = useQuery({
    queryKey: [...queryKeys.receivables(organization.id), PAGE_SIZE, receivableOffset],
    queryFn: () => api.listReceivables(organization.id, PAGE_SIZE, receivableOffset),
    placeholderData: keepPreviousData,
  });
  const statementQuery = useQuery({
    queryKey: [...queryKeys.statement(organization.id), PAGE_SIZE, statementOffset],
    queryFn: () => api.getFinancialStatement(organization.id, PAGE_SIZE, statementOffset),
    placeholderData: keepPreviousData,
  });
  const disputesQuery = useQuery({
    queryKey: [...queryKeys.disputes(organization.id), PAGE_SIZE, disputeOffset],
    queryFn: () => api.listFinancialDisputes(organization.id, PAGE_SIZE, disputeOffset),
    placeholderData: keepPreviousData,
  });

  const summary = summaryQuery.data;
  const receivables = receivablesQuery.data?.receivables ?? [];
  const receivablesTotal = receivablesQuery.data?.total ?? 0;
  const statement = statementQuery.data?.entries ?? [];
  const statementTotal = statementQuery.data?.total ?? 0;
  const disputes = disputesQuery.data?.disputes ?? [];
  const disputesTotal = disputesQuery.data?.total ?? 0;
  const error =
    summaryQuery.error ?? receivablesQuery.error ?? statementQuery.error ?? disputesQuery.error;
  const loading =
    summaryQuery.isPending ||
    receivablesQuery.isPending ||
    statementQuery.isPending ||
    disputesQuery.isPending;

  const invalidateFinancial = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.financialSummary(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.receivables(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.statement(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.disputes(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.audit(organization.id) }),
    ]);
  };

  const payoutMutation = useMutation({
    mutationFn: (payload: { legal_document: string; pix_key_type: string; pix_key: string }) =>
      api.updatePayout(organization.id, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.organization(organization.id), updated);
      setCnpjInput("");
      setKeyValue("");
      setPhoneDigits("");
      setPayoutErrors({});
      setPayoutError(null);
      toast.push({
        title: "Destino de repasse atualizado",
        description:
          "O CNPJ e a chave Pix foram registrados. O status de prontidão vem do servidor.",
      });
      void queryClient.invalidateQueries({ queryKey: queryKeys.audit(organization.id) });
    },
    onError: (caught) => setPayoutError(caught),
  });

  const disputeMutation = useMutation({
    mutationFn: () =>
      api.openFinancialDispute(organization.id, {
        booking_id: disputeTarget?.booking_id ?? "",
        reason: disputeReason.trim(),
        evidence: disputeEvidence.trim() || null,
      }),
    onSuccess: async () => {
      setDisputeTarget(null);
      setDisputeReason("");
      setDisputeEvidence("");
      setDisputeErrors({});
      setDisputeActionError(null);
      toast.push({
        title: "Contestação registrada",
        description: "O repasse desta reserva fica suspenso até a análise.",
      });
      await invalidateFinancial();
    },
    onError: (caught) => setDisputeActionError(caught),
  });

  function normalizedPixKey(): string {
    if (keyType === "cnpj") return normalizeCnpj(keyValue);
    if (keyType === "email") return keyValue.trim().toLowerCase();
    if (keyType === "phone") return toE164(DEFAULT_COUNTRY, phoneDigits);
    return keyValue.trim();
  }

  function savePayout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: Record<string, string> = {};
    const documentValidation = cnpjError(cnpjInput);
    if (documentValidation) next.document = documentValidation;
    const keyValidation = pixKeyError(keyType, normalizedPixKey());
    if (keyValidation) next.key = keyValidation;
    if (Object.keys(next).length > 0) {
      setPayoutErrors(next);
      const first = next.document ? "payout-document" : "payout-key";
      document.getElementById(first)?.focus();
      return;
    }
    setPayoutErrors({});
    setPayoutError(null);
    payoutMutation.mutate({
      legal_document: normalizeCnpj(cnpjInput),
      pix_key_type: keyType,
      pix_key: normalizedPixKey(),
    });
  }

  function openDispute(receivable: Receivable) {
    setDisputeTarget(receivable);
    setDisputeReason("");
    setDisputeEvidence("");
    setDisputeErrors({});
    setDisputeActionError(null);
  }

  function submitDispute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: Record<string, string> = {};
    if (!disputeReason.trim()) next.reason = "Informe o motivo da contestação.";
    else if (disputeReason.trim().length > 500) {
      next.reason = "O motivo deve ter no máximo 500 caracteres.";
    }
    if (disputeEvidence.length > 2000) {
      next.evidence = "A evidência deve ter no máximo 2.000 caracteres.";
    }
    if (Object.keys(next).length > 0) {
      setDisputeErrors(next);
      document.getElementById(next.reason ? "dispute-reason" : "dispute-evidence")?.focus();
      return;
    }
    setDisputeErrors({});
    setDisputeActionError(null);
    disputeMutation.mutate();
  }

  return (
    <section className="stack">
      <div className="card">
        <SectionHeading
          title="Financeiro"
          description="Extrato, repasses e contestações das reservas originadas no JOGA."
        />
        <InfoNotice>
          <p>
            Cobranças e reembolsos são processados pelo <strong>Mercado Pago</strong>. O repasse ao
            estabelecimento é registrado em <strong>ledger interno</strong> e liquidado manualmente
            pela equipe JOGA — não há split automático nem crédito imediato na conta.
          </p>
          <p>
            Prazos e valores exibidos são referência operacional. O repasse só é liberado com CNPJ e
            chave Pix de titularidade do estabelecimento ativos.
          </p>
        </InfoNotice>

        {error ? (
          <ErrorNotice
            message={formatError(error)}
            requestId={requestIdOf(error)}
            onRetry={() => {
              void summaryQuery.refetch();
              void receivablesQuery.refetch();
              void statementQuery.refetch();
              void disputesQuery.refetch();
            }}
          />
        ) : null}

        <h3>Destino do repasse</h3>
        <div className="payout-status">
          <span
            className={organization.payout_ready ? "badge badge--active" : "badge badge--warning"}
          >
            {organization.payout_ready ? "Apto a receber" : "Repasse pendente"}
          </span>
          <span className="badge badge--muted">
            {payoutStatusLabel(organization.payout_status)}
          </span>
          <small>
            {organization.pix_key_type
              ? `${PIX_TYPE_LABELS[organization.pix_key_type as PixKeyType] ?? organization.pix_key_type}: ${
                  organization.pix_key_masked ?? "chave não cadastrada"
                }`
              : "Nenhuma chave Pix cadastrada"}
          </small>
        </div>
        <p className="muted">
          A reserva paga só é aberta com CNPJ e chave Pix de titularidade do estabelecimento ativos.
          O operador consulta o financeiro, mas apenas proprietário ou administrador altera o
          destino.
        </p>

        {canManage ? (
          <form className="form form--inline" onSubmit={savePayout} noValidate>
            <h3>Configurar repasse</h3>
            <div className="form-row">
              <TextField
                id="payout-document"
                label="CNPJ"
                value={cnpjInput}
                onChange={(event) => {
                  setCnpjInput(formatCnpj(event.target.value));
                  if (payoutErrors.document) {
                    setPayoutErrors((current) => ({ ...current, document: "" }));
                  }
                }}
                error={payoutErrors.document}
                placeholder="00.000.000/0000-00"
                hint="O CNPJ precisa ser válido e de titularidade do estabelecimento."
                inputMode="numeric"
                maxLength={18}
                autoComplete="off"
                required
              />
              <SelectField
                id="payout-key-type"
                label="Tipo de chave Pix"
                value={keyType}
                onChange={(event) => {
                  setKeyType(event.target.value as PixKeyType);
                  setKeyValue("");
                  setPhoneDigits("");
                  setPayoutErrors((current) => ({ ...current, key: "" }));
                }}
              >
                {(Object.keys(PIX_TYPE_LABELS) as PixKeyType[]).map((type) => (
                  <option key={type} value={type}>
                    {PIX_TYPE_LABELS[type]}
                  </option>
                ))}
              </SelectField>
            </div>

            {keyType === "phone" ? (
              <PhoneField
                id="payout-key"
                label="Chave Pix (telefone)"
                countryCode="BR"
                lockCountry
                onCountryCodeChange={() => undefined}
                value={phoneDigits}
                onChange={(digits) => {
                  setPhoneDigits(digits);
                  if (payoutErrors.key) {
                    setPayoutErrors((current) => ({ ...current, key: "" }));
                  }
                }}
                error={payoutErrors.key}
                hint="Somente números brasileiros. O +55 é aplicado automaticamente."
              />
            ) : (
              <TextField
                id="payout-key"
                label="Chave Pix"
                value={keyValue}
                onChange={(event) => {
                  const next =
                    keyType === "cnpj" ? formatCnpj(event.target.value) : event.target.value;
                  setKeyValue(next);
                  if (payoutErrors.key) {
                    setPayoutErrors((current) => ({ ...current, key: "" }));
                  }
                }}
                error={payoutErrors.key}
                placeholder={PIX_PLACEHOLDERS[keyType]}
                hint={
                  keyType === "cnpj"
                    ? "Pode ser o mesmo CNPJ informado acima."
                    : keyType === "random"
                      ? "Formato UUID, com 36 caracteres."
                      : "Chave de titularidade do CNPJ."
                }
                type={keyType === "email" ? "email" : "text"}
                inputMode={keyType === "cnpj" ? "numeric" : undefined}
                maxLength={keyType === "cnpj" ? 18 : keyType === "random" ? 36 : 77}
                required
              />
            )}

            {payoutError ? (
              <ErrorNotice
                message={formatError(payoutError)}
                requestId={requestIdOf(payoutError)}
              />
            ) : null}

            <button
              type="submit"
              className="button button--primary"
              disabled={payoutMutation.isPending}
              aria-busy={payoutMutation.isPending || undefined}
            >
              {payoutMutation.isPending ? "Salvando..." : "Salvar destino de repasse"}
            </button>
          </form>
        ) : (
          <p className="muted">Somente proprietário ou administrador altera o repasse.</p>
        )}
      </div>

      <div className="card">
        <SectionHeading
          title="Resumo financeiro"
          description="Valores calculados pelo servidor a partir do ledger interno."
        />
        {loading && !summary ? (
          <SkeletonList rows={1} label="Carregando resumo financeiro..." />
        ) : summary ? (
          <div className="financial-summary">
            <div>
              <span>Cobrado</span>
              <strong>{formatMoney(summary.charged_cents)}</strong>
            </div>
            <div>
              <span>Pago</span>
              <strong>{formatMoney(summary.paid_cents)}</strong>
            </div>
            <div>
              <span>A repassar</span>
              <strong>{formatMoney(summary.pending_release_cents)}</strong>
            </div>
            <div>
              <span>Repassado</span>
              <strong>{formatMoney(summary.released_cents)}</strong>
            </div>
            <div>
              <span>Em contestação</span>
              <strong>{formatMoney(summary.disputed_cents)}</strong>
            </div>
            <div>
              <span>Reembolsado</span>
              <strong>{formatMoney(summary.refunded_cents)}</strong>
            </div>
            <div>
              <span>Pendente</span>
              <strong>{formatMoney(summary.pending_cents)}</strong>
            </div>
          </div>
        ) : null}
      </div>

      <div className="card">
        <SectionHeading
          title="Repasses a receber"
          description="Valores liberáveis das reservas concluídas. A liquidação é manual, feita pela equipe JOGA sobre o ledger interno."
        />
        {receivablesQuery.isPending ? (
          <SkeletonList rows={2} label="Carregando repasses..." />
        ) : receivables.length === 0 ? (
          <EmptyState title="Nenhum repasse">
            Reservas concluídas aparecem aqui quando houver valor liberável.
          </EmptyState>
        ) : (
          <ul className="booking-list">
            {receivables.map((item) => (
              <li key={item.release_id} className="booking-card">
                <div className="booking-card__top">
                  <div>
                    <span
                      className={
                        item.status === "RELEASED"
                          ? "badge badge--success"
                          : item.has_open_dispute
                            ? "badge badge--warning"
                            : "badge badge--muted"
                      }
                    >
                      {releaseStatusLabel(item.status)}
                    </span>
                    <h3>{formatDateRange(item.starts_at, item.ends_at)}</h3>
                    <p className="muted">
                      Reserva <span className="mono">#{shortId(item.booking_id)}</span> · liberação
                      prevista em {formatDate(item.eligible_at)}
                    </p>
                  </div>
                  <div className="booking-card__price">
                    <strong>{formatMoney(item.amount_cents)}</strong>
                  </div>
                </div>
                {item.released_at ? (
                  <p className="hint">
                    Liberação registrada no ledger em {formatDate(item.released_at)}.
                  </p>
                ) : null}
                {item.has_open_dispute ? (
                  <p className="booking-card__reason">
                    Contestação em análise — o repasse fica suspenso até a decisão.
                  </p>
                ) : null}
                {canManage && item.status === "PENDING" && !item.has_open_dispute ? (
                  <div className="booking-card__actions">
                    <button
                      type="button"
                      className="button button--small button--danger"
                      onClick={() => openDispute(item)}
                    >
                      Contestar repasse
                    </button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <Pagination
          total={receivablesTotal}
          limit={PAGE_SIZE}
          offset={receivableOffset}
          onChange={setReceivableOffset}
          disabled={receivablesQuery.isFetching}
        />
      </div>

      <div className="card">
        <SectionHeading
          title="Contestações"
          description="Contestações abertas pelo estabelecimento e a decisão registrada."
        />
        {disputesQuery.isPending ? (
          <SkeletonList rows={2} label="Carregando contestações..." />
        ) : disputes.length === 0 ? (
          <EmptyState title="Nenhuma contestação">
            Contestações abertas pelo estabelecimento aparecem aqui com o histórico da decisão.
          </EmptyState>
        ) : (
          <ul className="booking-list">
            {disputes.map((item) => (
              <li key={item.id} className="booking-card">
                <div className="booking-card__top">
                  <div>
                    <span
                      className={
                        item.status === "OPEN"
                          ? "badge badge--warning"
                          : item.status === "ACCEPTED"
                            ? "badge badge--success"
                            : "badge badge--muted"
                      }
                    >
                      {disputeStatusLabel(item.status)}
                    </span>
                    <h3>{formatMoney(item.amount_cents)}</h3>
                    <p className="muted">
                      Reserva <span className="mono">#{shortId(item.booking_id)}</span> · aberta em{" "}
                      {formatDate(item.created_at)}
                    </p>
                  </div>
                </div>
                <p>
                  <strong>Motivo:</strong> {item.reason}
                </p>
                {item.evidence ? (
                  <p className="hint">
                    <strong>Evidência:</strong> {item.evidence}
                  </p>
                ) : null}
                {item.decision_reason ? (
                  <p className="hint">
                    <strong>Decisão:</strong> {item.decision_reason}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <Pagination
          total={disputesTotal}
          limit={PAGE_SIZE}
          offset={disputeOffset}
          onChange={setDisputeOffset}
          disabled={disputesQuery.isFetching}
        />
      </div>

      <div className="card">
        <SectionHeading
          title="Extrato"
          description="Cobranças, pagamentos, reembolsos e repasses registrados no ledger interno."
        />
        {statementQuery.isPending ? (
          <SkeletonList rows={2} label="Carregando extrato..." />
        ) : statement.length === 0 ? (
          <EmptyState title="Extrato vazio">
            Cobranças, pagamentos, reembolsos e repasses aparecem aqui.
          </EmptyState>
        ) : (
          <ul className="booking-list">
            {statement.map((entry) => (
              <li key={entry.id} className="booking-card booking-card--compact">
                <div className="booking-card__top">
                  <div>
                    <span
                      className={
                        entry.direction === "CREDIT"
                          ? "badge badge--success"
                          : "badge badge--danger"
                      }
                    >
                      {entry.direction === "CREDIT" ? "Crédito" : "Débito"}
                    </span>
                    <h3>{ledgerEntryLabel(entry.entry_type)}</h3>
                    <p className="muted">
                      Reserva <span className="mono">#{shortId(entry.booking_id)}</span> ·{" "}
                      {formatDate(entry.created_at)}
                    </p>
                  </div>
                  <div className="booking-card__price">
                    <strong>{formatMoney(entry.amount_cents)}</strong>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        <Pagination
          total={statementTotal}
          limit={PAGE_SIZE}
          offset={statementOffset}
          onChange={setStatementOffset}
          disabled={statementQuery.isFetching}
        />
      </div>

      <Modal
        open={Boolean(disputeTarget)}
        title="Contestar repasse"
        description={
          disputeTarget
            ? `Reserva #${shortId(disputeTarget.booking_id)} · ${formatMoney(disputeTarget.amount_cents)}. A contestação suspende o repasse até a análise.`
            : undefined
        }
        onClose={disputeMutation.isPending ? () => undefined : () => setDisputeTarget(null)}
        closeOnOverlay={!disputeMutation.isPending}
        size="md"
        footer={
          <>
            <button
              type="button"
              className="button button--ghost"
              onClick={() => setDisputeTarget(null)}
              disabled={disputeMutation.isPending}
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="dispute-form"
              className="button button--danger button--solid-danger"
              disabled={disputeMutation.isPending || !disputeReason.trim()}
              aria-busy={disputeMutation.isPending || undefined}
            >
              {disputeMutation.isPending ? "Registrando..." : "Registrar contestação"}
            </button>
          </>
        }
      >
        <form id="dispute-form" className="form" onSubmit={submitDispute} noValidate>
          <TextareaField
            id="dispute-reason"
            label="Motivo da contestação"
            value={disputeReason}
            onChange={(event) => {
              setDisputeReason(event.target.value);
              if (disputeErrors.reason) {
                setDisputeErrors((current) => ({ ...current, reason: "" }));
              }
            }}
            error={disputeErrors.reason}
            maxLength={500}
            rows={4}
            required
            data-autofocus
          />
          <TextareaField
            id="dispute-evidence"
            label="Evidência (opcional)"
            value={disputeEvidence}
            onChange={(event) => {
              setDisputeEvidence(event.target.value);
              if (disputeErrors.evidence) {
                setDisputeErrors((current) => ({ ...current, evidence: "" }));
              }
            }}
            error={disputeErrors.evidence}
            hint="Texto privado, com acesso restrito à análise. Não inclua dados pessoais desnecessários."
            maxLength={2000}
            rows={3}
          />
          {disputeActionError ? (
            <ErrorNotice
              message={formatError(disputeActionError)}
              requestId={requestIdOf(disputeActionError)}
            />
          ) : null}
        </form>
      </Modal>
    </section>
  );
}
