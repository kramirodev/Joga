import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";

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
import type { CommissionResponse, Organization, Receivable } from "../../types";
import { BookingFinancialDialog } from "./BookingFinancialDialog";

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

const RECEIVABLE_STATUS: Array<{ value: string | null; label: string }> = [
  { value: null, label: "Todos" },
  { value: "PENDING", label: "Pendentes" },
  { value: "RELEASED", label: "Repassados" },
  { value: "FAILED", label: "Falharam" },
  { value: "REVERSED", label: "Revertidos" },
];

const DISPUTE_STATUS: Array<{ value: string | null; label: string }> = [
  { value: null, label: "Todas" },
  { value: "OPEN", label: "Em análise" },
  { value: "ACCEPTED", label: "Procedentes" },
  { value: "REJECTED", label: "Improcedentes" },
  { value: "WITHDRAWN", label: "Retiradas" },
];

function dayBoundary(value: string, endOfDay: boolean): string | null {
  if (!value) return null;
  const date = new Date(`${value}T${endOfDay ? "23:59:59.999" : "00:00:00"}`);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function feePercentLabel(basisPoints: number): string {
  return `${(basisPoints / 100).toFixed(2).replace(".", ",")}%`;
}

function receiptLabel(reference: string): string {
  if (reference.startsWith("simulated:")) return `${reference} (comprovante simulado)`;
  if (reference.startsWith("bank:")) return `${reference} (comprovante bancário)`;
  return reference;
}

function deadlinePassed(value: string): boolean {
  const date = new Date(value);
  return !Number.isNaN(date.getTime()) && date.getTime() <= Date.now();
}

function Composition({
  venuePriceCents,
  feeCents,
  totalCents,
}: {
  venuePriceCents: number | null;
  feeCents: number | null;
  totalCents: number | null;
}) {
  if (venuePriceCents === null || feeCents === null || totalCents === null) return null;
  return (
    <p className="financial-composition">
      Espaço <strong>{formatMoney(venuePriceCents)}</strong> + JOGA{" "}
      <strong>{formatMoney(feeCents)}</strong> = <strong>{formatMoney(totalCents)}</strong>
    </p>
  );
}

export function FinancialPanel({ organization }: { organization: Organization }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [receivableStatus, setReceivableStatus] = useState<string | null>(null);
  const [receivableOffset, setReceivableOffset] = useState(0);
  const [statementOffset, setStatementOffset] = useState(0);
  const [disputeStatus, setDisputeStatus] = useState<string | null>(null);
  const [disputeOffset, setDisputeOffset] = useState(0);
  const [commissionFrom, setCommissionFrom] = useState("");
  const [commissionTo, setCommissionTo] = useState("");
  const [commissionOffset, setCommissionOffset] = useState(0);
  const [detailBookingId, setDetailBookingId] = useState<string | null>(null);

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
  const commissionFromIso = useMemo(() => dayBoundary(commissionFrom, false), [commissionFrom]);
  const commissionToIso = useMemo(() => dayBoundary(commissionTo, true), [commissionTo]);

  const summaryQuery = useQuery({
    queryKey: queryKeys.financialSummary(organization.id),
    queryFn: () => api.getOrganizationFinancialSummary(organization.id),
  });
  const receivablesQuery = useQuery({
    queryKey: [
      ...queryKeys.receivables(organization.id),
      receivableStatus,
      PAGE_SIZE,
      receivableOffset,
    ],
    queryFn: () =>
      api.listReceivables(organization.id, {
        status: receivableStatus,
        limit: PAGE_SIZE,
        offset: receivableOffset,
      }),
    placeholderData: keepPreviousData,
  });
  const statementQuery = useQuery({
    queryKey: [...queryKeys.statement(organization.id), PAGE_SIZE, statementOffset],
    queryFn: () => api.getFinancialStatement(organization.id, PAGE_SIZE, statementOffset),
    placeholderData: keepPreviousData,
  });
  const commissionQuery = useQuery<CommissionResponse>({
    queryKey: [
      ...queryKeys.commission(organization.id, commissionFromIso, commissionToIso),
      commissionOffset,
    ],
    queryFn: () =>
      api.getFinancialCommission(organization.id, {
        from: commissionFromIso,
        to: commissionToIso,
        limit: PAGE_SIZE,
        offset: commissionOffset,
      }),
    placeholderData: keepPreviousData,
  });
  const disputesQuery = useQuery({
    queryKey: [...queryKeys.disputes(organization.id), disputeStatus, PAGE_SIZE, disputeOffset],
    queryFn: () =>
      api.listFinancialDisputes(organization.id, {
        status: disputeStatus,
        limit: PAGE_SIZE,
        offset: disputeOffset,
      }),
    placeholderData: keepPreviousData,
  });

  const summary = summaryQuery.data;
  const receivables = receivablesQuery.data?.receivables ?? [];
  const receivablesTotal = receivablesQuery.data?.total ?? 0;
  const statement = statementQuery.data?.entries ?? [];
  const statementTotal = statementQuery.data?.total ?? 0;
  const commission = commissionQuery.data;
  const disputes = disputesQuery.data?.disputes ?? [];
  const disputesTotal = disputesQuery.data?.total ?? 0;
  const error =
    summaryQuery.error ??
    receivablesQuery.error ??
    statementQuery.error ??
    commissionQuery.error ??
    disputesQuery.error;
  const loading =
    summaryQuery.isPending ||
    receivablesQuery.isPending ||
    statementQuery.isPending ||
    commissionQuery.isPending ||
    disputesQuery.isPending;

  const invalidateFinancial = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.financialSummary(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.receivables(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.statement(organization.id) }),
      queryClient.invalidateQueries({
        queryKey: ["organizations", organization.id, "financial-commission"],
      }),
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
        description: "O repasse desta reserva fica suspenso até a análise da equipe JOGA.",
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
          description="Repasses ao fornecedor, comissão do JOGA e extrato das reservas."
        />
        <InfoNotice>
          <p>
            O ledger controla a substância financeira em reais. O ticket é a unidade de exibição e
            consumo (R$ 3,10); o valor jurídico é o valor do espaço mais a taxa.
          </p>
          <p>
            O valor do espaço pertence ao fornecedor e nunca é receita do JOGA. A receita do JOGA é
            a comissão de intermediação. Não há split nem transferência real nesta fase.
          </p>
          <p>
            O repasse fica elegível em <strong>início da reserva + 2 h</strong>. Uma contestação
            aberta suspende o repasse. A decisão é auditada pela equipe JOGA.
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
              void commissionQuery.refetch();
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
          description="Valores calculados pelo servidor a partir do ledger em reais."
        />
        {loading && !summary ? (
          <SkeletonList rows={1} label="Carregando resumo financeiro..." />
        ) : summary ? (
          <>
            <div className="financial-summary">
              <div>
                <span>Comissão do JOGA</span>
                <strong>{formatMoney(summary.joga_fee_cents)}</strong>
                <small>Receita de intermediação</small>
              </div>
              <div>
                <span>Valor do fornecedor</span>
                <strong>{formatMoney(summary.venue_price_cents)}</strong>
                <small>Não é receita do JOGA</small>
              </div>
              <div>
                <span>Cobrança total</span>
                <strong>{formatMoney(summary.charged_cents)}</strong>
                <small>Espaço + JOGA; não é receita</small>
              </div>
              <div>
                <span>Pago</span>
                <strong>{formatMoney(summary.paid_cents)}</strong>
              </div>
              <div>
                <span>Reembolsado</span>
                <strong>{formatMoney(summary.refunded_cents)}</strong>
              </div>
              <div>
                <span>Repasse pendente</span>
                <strong>{formatMoney(summary.pending_release_cents)}</strong>
              </div>
              <div>
                <span>Repassado</span>
                <strong>{formatMoney(summary.released_cents)}</strong>
              </div>
              <div>
                <span>Revertido após reembolso</span>
                <strong>{formatMoney(summary.reversed_cents)}</strong>
              </div>
              <div>
                <span>Repasse com falha</span>
                <strong>{formatMoney(summary.failed_cents)}</strong>
              </div>
              <div>
                <span>Em contestação</span>
                <strong>{formatMoney(summary.disputed_cents)}</strong>
              </div>
              <div>
                <span>Pagamento pendente</span>
                <strong>{formatMoney(summary.pending_cents)}</strong>
              </div>
            </div>
            <p className="hint">
              Cobrança total é o valor cobrado do jogador, não a receita do JOGA. A comissão do JOGA
              é o campo separado acima.
            </p>
          </>
        ) : null}
      </div>

      <div className="card">
        <SectionHeading
          title="Repasses ao fornecedor"
          description="O valor exibido é devido ao estabelecimento. A liquidação é simulada no ledger; não há transferência real."
        />
        <div className="segmented segmented--wrap" role="group" aria-label="Filtrar repasses">
          {RECEIVABLE_STATUS.map((option) => (
            <button
              key={option.value ?? "all"}
              type="button"
              className={
                receivableStatus === option.value ? "segmented__item is-active" : "segmented__item"
              }
              aria-pressed={receivableStatus === option.value}
              onClick={() => {
                setReceivableStatus(option.value);
                setReceivableOffset(0);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
        {receivablesQuery.isPending ? (
          <SkeletonList rows={2} label="Carregando repasses..." />
        ) : receivablesQuery.error ? (
          <ErrorNotice
            message={formatError(receivablesQuery.error)}
            requestId={requestIdOf(receivablesQuery.error)}
            onRetry={() => void receivablesQuery.refetch()}
          />
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
                          : item.status === "FAILED" || item.status === "REVERSED"
                            ? "badge badge--danger"
                            : item.has_open_dispute
                              ? "badge badge--warning"
                              : "badge badge--muted"
                      }
                    >
                      {releaseStatusLabel(item.status)}
                    </span>
                    <h3>{formatDateRange(item.starts_at, item.ends_at)}</h3>
                    <p className="muted">
                      Reserva <span className="mono">#{shortId(item.booking_id)}</span> · repasse
                      elegível em {formatDate(item.eligible_at)}
                    </p>
                    <p className="hint">Contestação até {formatDate(item.dispute_deadline)}.</p>
                    <Composition
                      venuePriceCents={item.venue_price_cents}
                      feeCents={item.fee_cents}
                      totalCents={item.total_cents}
                    />
                  </div>
                  <div className="booking-card__price">
                    <span>Valor do fornecedor</span>
                    <strong>{formatMoney(item.amount_cents)}</strong>
                  </div>
                </div>
                {item.released_at ? (
                  <p className="hint">
                    Repasse registrado no ledger em {formatDate(item.released_at)}.
                  </p>
                ) : null}
                {item.receipt_reference ? (
                  <p className="hint">
                    Comprovante:{" "}
                    <span className="mono">{receiptLabel(item.receipt_reference)}</span>
                  </p>
                ) : null}
                {item.has_open_dispute ? (
                  <p className="booking-card__reason">
                    Contestação em análise — o repasse fica suspenso até a decisão.
                  </p>
                ) : null}
                {item.reason ? <p className="hint">Motivo: {item.reason}</p> : null}
                <div className="booking-card__actions">
                  <button
                    type="button"
                    className="button button--small button--ghost"
                    onClick={() => setDetailBookingId(item.booking_id)}
                  >
                    Ver detalhe financeiro
                  </button>
                  {canManage && item.status === "PENDING" && !item.has_open_dispute ? (
                    deadlinePassed(item.dispute_deadline) ? (
                      <span className="hint">Prazo de contestação encerrado.</span>
                    ) : (
                      <button
                        type="button"
                        className="button button--small button--danger"
                        onClick={() => openDispute(item)}
                      >
                        Contestar repasse
                      </button>
                    )
                  ) : null}
                </div>
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
          title="Comissão do JOGA"
          description="Relatório por reserva confirmada. O valor do fornecedor e a comissão aparecem separados."
        />
        <div className="form-row form-row--three">
          <TextField
            id="commission-from"
            label="De"
            type="date"
            value={commissionFrom}
            onChange={(event) => {
              setCommissionFrom(event.target.value);
              setCommissionOffset(0);
            }}
          />
          <TextField
            id="commission-to"
            label="Até"
            type="date"
            value={commissionTo}
            onChange={(event) => {
              setCommissionTo(event.target.value);
              setCommissionOffset(0);
            }}
          />
          <div className="field">
            <span className="field__label" aria-hidden="true">
              &nbsp;
            </span>
            <button
              type="button"
              className="button button--ghost"
              onClick={() => {
                setCommissionFrom("");
                setCommissionTo("");
                setCommissionOffset(0);
              }}
              disabled={!commissionFrom && !commissionTo}
            >
              Limpar período
            </button>
          </div>
        </div>
        {commissionQuery.isPending ? (
          <SkeletonList rows={2} label="Carregando comissão..." />
        ) : commissionQuery.error ? (
          <ErrorNotice
            message={formatError(commissionQuery.error)}
            requestId={requestIdOf(commissionQuery.error)}
            onRetry={() => void commissionQuery.refetch()}
          />
        ) : commission ? (
          <>
            <div className="financial-summary">
              <div>
                <span>Reservas confirmadas</span>
                <strong>{commission.totals.bookings}</strong>
              </div>
              <div>
                <span>Comissão do JOGA</span>
                <strong>{formatMoney(commission.totals.joga_fee_cents)}</strong>
                <small>Receita de intermediação</small>
              </div>
              <div>
                <span>Valor do fornecedor</span>
                <strong>{formatMoney(commission.totals.venue_price_cents)}</strong>
                <small>Não é receita do JOGA</small>
              </div>
              <div>
                <span>Total das reservas</span>
                <strong>{formatMoney(commission.totals.total_cents)}</strong>
              </div>
            </div>
            {commission.rows.length === 0 ? (
              <EmptyState title="Nenhuma reserva no período">
                Ajuste as datas para consultar a comissão confirmada.
              </EmptyState>
            ) : (
              <ul className="booking-list">
                {commission.rows.map((row) => (
                  <li key={row.booking_id} className="booking-card booking-card--compact">
                    <div className="booking-card__top">
                      <div>
                        <h3>{formatDate(row.starts_at)}</h3>
                        <p className="muted">
                          Confirmada em {formatDate(row.confirmed_at)}
                          {row.release_status
                            ? ` · repasse: ${releaseStatusLabel(row.release_status)}`
                            : ""}
                        </p>
                        <Composition
                          venuePriceCents={row.venue_price_cents}
                          feeCents={row.fee_cents}
                          totalCents={row.total_cents}
                        />
                        <p className="hint">
                          Relação JOGA / espaço:{" "}
                          {row.venue_price_cents > 0
                            ? feePercentLabel(
                                Math.round((row.fee_cents / row.venue_price_cents) * 10000),
                              )
                            : "—"}
                        </p>
                      </div>
                      <div className="booking-card__price">
                        <span>Comissão do JOGA</span>
                        <strong>{formatMoney(row.fee_cents)}</strong>
                      </div>
                    </div>
                    <div className="booking-card__actions">
                      <button
                        type="button"
                        className="button button--small button--ghost"
                        onClick={() => setDetailBookingId(row.booking_id)}
                      >
                        Ver detalhe financeiro
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <div className="pagination">
              <span className="pagination__info">
                Página {Math.floor(commissionOffset / PAGE_SIZE) + 1}
                {commission.rows.length < PAGE_SIZE ? " · fim do período" : ""}
              </span>
              <div className="pagination__actions">
                <button
                  type="button"
                  className="button button--small button--ghost"
                  onClick={() => setCommissionOffset(Math.max(0, commissionOffset - PAGE_SIZE))}
                  disabled={commissionOffset === 0 || commissionQuery.isFetching}
                >
                  Anterior
                </button>
                <button
                  type="button"
                  className="button button--small button--ghost"
                  onClick={() => setCommissionOffset(commissionOffset + PAGE_SIZE)}
                  disabled={commission.rows.length < PAGE_SIZE || commissionQuery.isFetching}
                >
                  Próxima
                </button>
              </div>
            </div>
          </>
        ) : null}
      </div>

      <div className="card">
        <SectionHeading
          title="Contestações"
          description="Canal do estabelecimento. A decisão é da equipe JOGA e fica registrada com justificativa."
        />
        <div className="segmented segmented--wrap" role="group" aria-label="Filtrar contestações">
          {DISPUTE_STATUS.map((option) => (
            <button
              key={option.value ?? "all"}
              type="button"
              className={
                disputeStatus === option.value ? "segmented__item is-active" : "segmented__item"
              }
              aria-pressed={disputeStatus === option.value}
              onClick={() => {
                setDisputeStatus(option.value);
                setDisputeOffset(0);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
        {disputesQuery.isPending ? (
          <SkeletonList rows={2} label="Carregando contestações..." />
        ) : disputesQuery.error ? (
          <ErrorNotice
            message={formatError(disputesQuery.error)}
            requestId={requestIdOf(disputesQuery.error)}
            onRetry={() => void disputesQuery.refetch()}
          />
        ) : disputes.length === 0 ? (
          <EmptyState title="Nenhuma contestação">
            Contestações abertas pelo estabelecimento aparecem aqui com prazo e decisão.
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
                      {formatDate(item.created_at)} · prazo {formatDate(item.deadline_at)}
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
                {item.decided_at ? (
                  <p className="hint">
                    <strong>Decisão:</strong> {disputeStatusLabel(item.status)} em{" "}
                    {formatDate(item.decided_at)}
                    {item.decided_by ? (
                      <>
                        {" "}
                        por <span className="mono">#{shortId(item.decided_by)}</span>
                      </>
                    ) : null}
                    {item.decision_reason ? ` — ${item.decision_reason}` : ""}
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
          title="Extrato do fornecedor"
          description="Lançamentos que afetam a conta da quadra. A comissão do JOGA não é linha deste extrato."
        />
        {statementQuery.isPending ? (
          <SkeletonList rows={2} label="Carregando extrato..." />
        ) : statementQuery.error ? (
          <ErrorNotice
            message={formatError(statementQuery.error)}
            requestId={requestIdOf(statementQuery.error)}
            onRetry={() => void statementQuery.refetch()}
          />
        ) : statement.length === 0 ? (
          <EmptyState title="Extrato vazio">
            Pagamentos, reembolsos e repasses aparecem aqui.
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
                    {entry.entry_type === "VENUE_RELEASE" && entry.release_id ? (
                      <p className="hint">
                        Repasse <span className="mono">#{shortId(entry.release_id)}</span>
                      </p>
                    ) : null}
                    <Composition
                      venuePriceCents={entry.venue_price_cents}
                      feeCents={entry.fee_cents}
                      totalCents={entry.total_cents}
                    />
                  </div>
                  <div className="booking-card__price">
                    <strong>{formatMoney(entry.amount_cents)}</strong>
                  </div>
                </div>
                <div className="booking-card__actions">
                  <button
                    type="button"
                    className="button button--small button--ghost"
                    onClick={() => setDetailBookingId(entry.booking_id)}
                  >
                    Ver reserva
                  </button>
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

      {detailBookingId ? (
        <BookingFinancialDialog
          organizationId={organization.id}
          bookingId={detailBookingId}
          onClose={() => setDetailBookingId(null)}
        />
      ) : null}

      <Modal
        open={Boolean(disputeTarget)}
        title="Contestar repasse"
        description={
          disputeTarget
            ? `Reserva #${shortId(disputeTarget.booking_id)} · valor do fornecedor ${formatMoney(
                disputeTarget.amount_cents,
              )}. Prazo até ${formatDate(disputeTarget.dispute_deadline)}. A contestação suspende o repasse.`
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
