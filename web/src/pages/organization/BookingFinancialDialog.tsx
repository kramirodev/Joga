import { useQuery } from "@tanstack/react-query";

import { ErrorNotice, SkeletonList } from "../../components/Feedback";
import { Modal } from "../../components/ui/Modal";
import { api } from "../../lib/api";
import {
  disputeStatusLabel,
  fiscalStatusLabel,
  formatDate,
  formatDateRange,
  formatError,
  formatMoney,
  ledgerEntryLabel,
  releaseStatusLabel,
  requestIdOf,
  shortId,
} from "../../lib/format";
import { queryKeys } from "../../lib/query";

function feePercentLabel(basisPoints: number): string {
  return `${(basisPoints / 100).toFixed(2).replace(".", ",")}%`;
}

function receiptLabel(reference: string | null): string {
  if (!reference) return "Sem comprovante enquanto pendente";
  if (reference.startsWith("simulated:")) return `${reference} (comprovante simulado)`;
  if (reference.startsWith("bank:")) return `${reference} (comprovante bancário)`;
  return reference;
}

export function BookingFinancialDialog({
  organizationId,
  bookingId,
  onClose,
}: {
  organizationId: string;
  bookingId: string;
  onClose: () => void;
}) {
  const query = useQuery({
    queryKey: queryKeys.bookingFinancial(organizationId, bookingId),
    queryFn: () => api.getBookingFinancial(organizationId, bookingId),
    enabled: Boolean(bookingId),
  });

  const data = query.data;

  return (
    <Modal
      open
      title={`Detalhe financeiro da reserva #${shortId(bookingId)}`}
      description="Composição congelada na reserva, repasse e documentos. O valor do fornecedor não é receita do JOGA."
      onClose={onClose}
      size="lg"
    >
      {query.isPending ? (
        <SkeletonList rows={3} label="Carregando detalhe financeiro..." />
      ) : query.error ? (
        <ErrorNotice
          message={formatError(query.error)}
          requestId={requestIdOf(query.error)}
          onRetry={() => void query.refetch()}
        />
      ) : data ? (
        <div className="stack">
          <section aria-labelledby="booking-financial-pricing">
            <h3 id="booking-financial-pricing">Composição da reserva</h3>
            <dl className="dialog-summary">
              <div>
                <dt>Valor do espaço</dt>
                <dd>{formatMoney(data.pricing.venue_price_cents)}</dd>
              </div>
              <div>
                <dt>Valor do JOGA</dt>
                <dd>{formatMoney(data.pricing.fee_cents)}</dd>
              </div>
              <div>
                <dt>Total cobrado</dt>
                <dd>{formatMoney(data.pricing.total_cents)}</dd>
              </div>
              <div>
                <dt>Percentual de referência</dt>
                <dd>{feePercentLabel(data.pricing.fee_percent_applied)}</dd>
              </div>
              <div>
                <dt>Versão de preço</dt>
                <dd className="mono">{data.pricing.pricing_version}</dd>
              </div>
            </dl>
            <p className="muted">
              No caminho por tickets, o valor do JOGA é o restante de tickets × R$ 3,10 menos o
              valor do espaço. O percentual acima é referência, não o valor final.
            </p>
          </section>

          <section aria-labelledby="booking-financial-release">
            <h3 id="booking-financial-release">Repasse ao fornecedor</h3>
            {data.release ? (
              <dl className="dialog-summary">
                <div>
                  <dt>Status</dt>
                  <dd>{releaseStatusLabel(data.release.status)}</dd>
                </div>
                <div>
                  <dt>Valor do fornecedor</dt>
                  <dd>{formatMoney(data.release.amount_cents)}</dd>
                </div>
                <div>
                  <dt>Elegível em</dt>
                  <dd>{formatDate(data.release.eligible_at)}</dd>
                </div>
                <div>
                  <dt>Repassado em</dt>
                  <dd>{data.release.released_at ? formatDate(data.release.released_at) : "—"}</dd>
                </div>
                <div>
                  <dt>Contestação até</dt>
                  <dd>{formatDate(data.release.dispute_deadline)}</dd>
                </div>
                <div>
                  <dt>Comprovante</dt>
                  <dd>{receiptLabel(data.release.receipt_reference)}</dd>
                </div>
                {data.release.reason ? (
                  <div>
                    <dt>Motivo registrado</dt>
                    <dd>{data.release.reason}</dd>
                  </div>
                ) : null}
              </dl>
            ) : (
              <p className="muted">A reserva ainda não tem registro de repasse.</p>
            )}
          </section>

          <section aria-labelledby="booking-financial-dispute">
            <h3 id="booking-financial-dispute">Contestação</h3>
            {data.dispute ? (
              <>
                <dl className="dialog-summary">
                  <div>
                    <dt>Status</dt>
                    <dd>{disputeStatusLabel(data.dispute.status)}</dd>
                  </div>
                  <div>
                    <dt>Valor contestado</dt>
                    <dd>{formatMoney(data.dispute.amount_cents)}</dd>
                  </div>
                  <div>
                    <dt>Prazo</dt>
                    <dd>{formatDate(data.dispute.deadline_at)}</dd>
                  </div>
                  <div>
                    <dt>Decidida em</dt>
                    <dd>{data.dispute.decided_at ? formatDate(data.dispute.decided_at) : "—"}</dd>
                  </div>
                </dl>
                <p>
                  <strong>Motivo:</strong> {data.dispute.reason}
                </p>
                {data.dispute.evidence ? (
                  <p className="hint">
                    <strong>Evidência:</strong> {data.dispute.evidence}
                  </p>
                ) : null}
                {data.dispute.decision_reason ? (
                  <p className="hint">
                    <strong>Decisão da equipe JOGA:</strong> {data.dispute.decision_reason}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="muted">Nenhuma contestação registrada para esta reserva.</p>
            )}
          </section>

          <section aria-labelledby="booking-financial-fiscal">
            <h3 id="booking-financial-fiscal">NFS-e do espaço</h3>
            {data.fiscal_document ? (
              <dl className="dialog-summary">
                <div>
                  <dt>Status</dt>
                  <dd>{fiscalStatusLabel(data.fiscal_document.status)}</dd>
                </div>
                <div>
                  <dt>Valor</dt>
                  <dd>{formatMoney(data.fiscal_document.amount_cents)}</dd>
                </div>
                <div>
                  <dt>Número</dt>
                  <dd>{data.fiscal_document.number ?? "—"}</dd>
                </div>
                <div>
                  <dt>Emitida em</dt>
                  <dd>
                    {data.fiscal_document.issued_at
                      ? formatDate(data.fiscal_document.issued_at)
                      : "Não emitida"}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="muted">Nenhum documento fiscal registrado para esta reserva.</p>
            )}
            <p className="hint">
              Placeholder de exibição. Não há emissão fiscal operacional nesta fase.
            </p>
          </section>

          <section aria-labelledby="booking-financial-ledger">
            <h3 id="booking-financial-ledger">Lançamentos do ledger</h3>
            {data.ledger.length === 0 ? (
              <p className="muted">Nenhum lançamento para esta reserva.</p>
            ) : (
              <ul className="booking-list">
                {data.ledger.map((entry) => (
                  <li key={entry.id} className="booking-card booking-card--compact">
                    <div className="booking-card__top">
                      <div>
                        <strong>{ledgerEntryLabel(entry.entry_type)}</strong>
                        <p className="muted">
                          {formatDate(entry.created_at)} · {entry.status}
                        </p>
                        {entry.venue_price_cents !== null &&
                        entry.fee_cents !== null &&
                        entry.total_cents !== null ? (
                          <p className="hint">
                            Espaço {formatMoney(entry.venue_price_cents)} + JOGA{" "}
                            {formatMoney(entry.fee_cents)} = {formatMoney(entry.total_cents)}
                          </p>
                        ) : null}
                      </div>
                      <div className="booking-card__price">
                        <strong>{formatMoney(entry.amount_cents)}</strong>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="booking-financial-refunds">
            <h3 id="booking-financial-refunds">Reembolsos</h3>
            {data.refunds.length === 0 ? (
              <p className="muted">Nenhum reembolso registrado.</p>
            ) : (
              <ul className="booking-list">
                {data.refunds.map((refund) => (
                  <li key={refund.id} className="booking-card booking-card--compact">
                    <div className="booking-card__top">
                      <div>
                        <strong>{formatMoney(refund.amount_cents)}</strong>
                        <p className="muted">
                          {refund.status} ·{" "}
                          {refund.processed_at
                            ? formatDate(refund.processed_at)
                            : formatDate(refund.created_at)}
                        </p>
                        {refund.reason ? <p className="hint">{refund.reason}</p> : null}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {data.release ? (
            <p className="hint">
              Reserva de {formatDateRange(data.release.starts_at, data.release.ends_at)}.
            </p>
          ) : null}
        </div>
      ) : null}
    </Modal>
  );
}
