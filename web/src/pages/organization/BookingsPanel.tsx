import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { EmptyState, ErrorNotice, SkeletonList } from "../../components/Feedback";
import { CheckboxField, SelectField, TextField } from "../../components/ui/Field";
import {
  CalendarIcon,
  CheckIcon,
  ClockIcon,
  SearchIcon,
  WalletIcon,
} from "../../components/ui/Icons";
import { ConfirmDialog, ReasonDialog } from "../../components/ui/Modal";
import { Pagination } from "../../components/ui/Pagination";
import { SectionHeading } from "../../components/ui/PageHeader";
import { useToast } from "../../components/ui/toast-context";
import { api } from "../../lib/api";
import {
  bookingStatusLabel,
  formatDate,
  formatDateRange,
  formatError,
  formatMoney,
  holdStatusLabel,
  paymentStatusLabel,
  presenceStatusLabel,
  requestIdOf,
  settledWithLabel,
  shortId,
  timerStatusLabel,
  timerTypeLabel,
} from "../../lib/format";
import { queryKeys } from "../../lib/query";
import type { Booking, BookingListParams, Organization } from "../../types";

type DialogKind = "accept" | "decline" | "complete" | "cancel" | "refund";

interface DialogState {
  kind: DialogKind;
  booking: Booking;
}

function statusTone(status: string): string {
  switch (status) {
    case "REQUESTED":
    case "HOLD_CONFIRMED":
    case "PAYMENT_PENDING":
    case "PARTICIPANT_CONFIRMATION":
      return "warning";
    case "CONFIRMED":
      return "success";
    case "DECLINED":
    case "CANCELLED":
    case "CANCELLED_BY_VENUE":
    case "CANCELLED_BY_PLAYER":
      return "danger";
    case "COMPLETED":
      return "info";
    default:
      return "muted";
  }
}

const BOOKING_STATUS_OPTIONS = [
  "REQUESTED",
  "PARTICIPANT_CONFIRMATION",
  "HOLD_CONFIRMED",
  "PAYMENT_PENDING",
  "CONFIRMED",
  "SUBSTITUTING",
  "COMPLETED",
  "DECLINED",
  "EXPIRED",
  "CANCELLED",
  "CANCELLED_BY_VENUE",
  "CANCELLED_BY_PLAYER",
];

function toLocalInput(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function toIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function bookingMatches(booking: Booking, query: string): boolean {
  if (!query) return true;
  const haystack = [
    booking.id,
    booking.organization_venue_name,
    booking.venue_space_name,
    booking.format_name,
    booking.band_label,
    bookingStatusLabel(booking.status),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query.toLowerCase());
}

export function BookingsPanel({
  organization,
  bookings,
  total,
  limit,
  offset,
  filters,
  onParamsChange,
  loading,
  fetching,
  error,
  onRetry,
}: {
  organization: Organization;
  bookings: Booking[];
  total: number;
  limit: number;
  offset: number;
  filters: BookingListParams;
  onParamsChange: (params: BookingListParams) => void;
  loading: boolean;
  fetching: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [acceptAck, setAcceptAck] = useState(false);
  const [acceptError, setAcceptError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [search, setSearch] = useState("");
  const [draftStatus, setDraftStatus] = useState(filters.status ?? "");
  const [draftFrom, setDraftFrom] = useState(toLocalInput(filters.from));
  const [draftTo, setDraftTo] = useState(toLocalInput(filters.to));
  const [filterError, setFilterError] = useState<string | null>(null);

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.bookings(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.financialSummary(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.receivables(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.statement(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.disputes(organization.id) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.audit(organization.id) }),
    ]);
  };

  function resetDialogState() {
    setDialog(null);
    setReason("");
    setReasonError(null);
    setAcceptAck(false);
    setAcceptError(null);
  }

  function success(title: string, description?: string) {
    resetDialogState();
    setActionError(null);
    toast.push({ title, description });
  }

  const acceptMutation = useMutation({
    mutationFn: (bookingId: string) => api.acceptBooking(organization.id, bookingId),
    onSuccess: async () => {
      success(
        "Reserva aceita",
        "O bloqueio foi confirmado. Os jogadores seguem para o pagamento dentro do prazo.",
      );
      await invalidate();
    },
    onError: (caught) => setActionError(caught),
  });

  const declineMutation = useMutation({
    mutationFn: ({ bookingId, reason: text }: { bookingId: string; reason: string }) =>
      api.declineBooking(organization.id, bookingId, text),
    onSuccess: async () => {
      success("Reserva recusada", "O motivo foi registrado e a solicitação foi encerrada.");
      await invalidate();
    },
    onError: (caught) => setActionError(caught),
  });

  const completeMutation = useMutation({
    mutationFn: (bookingId: string) => api.completeBooking(organization.id, bookingId),
    onSuccess: async () => {
      success(
        "Reserva concluída",
        "A reserva entrou no histórico e segue para o fluxo financeiro.",
      );
      await invalidate();
    },
    onError: (caught) => setActionError(caught),
  });

  const cancelMutation = useMutation({
    mutationFn: ({ bookingId, reason: text }: { bookingId: string; reason: string }) =>
      api.cancelBookingByVenue(organization.id, bookingId, text),
    onSuccess: async () => {
      success("Reserva cancelada", "O cancelamento pelo estabelecimento foi registrado.");
      await invalidate();
    },
    onError: (caught) => setActionError(caught),
  });

  const refundMutation = useMutation({
    mutationFn: ({ bookingId, reason: text }: { bookingId: string; reason: string }) =>
      api.refundBooking(organization.id, bookingId, text),
    onSuccess: async (result, variables) => {
      let refundStatus: string | null = null;
      try {
        const financial = await api.getBookingFinancial(organization.id, variables.bookingId);
        refundStatus = financial.refunds[financial.refunds.length - 1]?.status ?? null;
      } catch {
        // Sem o detalhe financeiro, informamos apenas a solicitação.
      }
      const charges = `${result.refunded} cobrança(s) paga(s)`;
      if (refundStatus === "PROCESSED") {
        success("Reembolso processado", `${charges} estornada(s) pelo Mercado Pago.`);
      } else if (refundStatus === "FAILED") {
        resetDialogState();
        setActionError(null);
        toast.push({
          title: "Reembolso não concluído",
          description: `${charges} não foram estornadas: o provedor recusou a operação.`,
          tone: "error",
        });
      } else if (refundStatus === "PENDING") {
        resetDialogState();
        setActionError(null);
        toast.push({
          title: "Reembolso solicitado",
          description: `${charges} aguardando confirmação do Mercado Pago. O status aparece no extrato.`,
        });
      } else {
        resetDialogState();
        setActionError(null);
        toast.push({
          title: "Reembolso solicitado",
          description: `${charges} enviada(s) ao provedor. Confirme o status no extrato financeiro.`,
        });
      }
      await invalidate();
    },
    onError: (caught) => setActionError(caught),
  });

  const presenceMutation = useMutation({
    mutationFn: ({ bookingId, userId }: { bookingId: string; userId: string }) =>
      api.confirmPresence(bookingId, userId, "VENUE"),
    onSuccess: async () => {
      toast.push({
        title: "Presença confirmada",
        description: "O check-in foi registrado pelo estabelecimento.",
      });
      await invalidate();
    },
    onError: (caught) =>
      toast.push({
        title: "Não foi possível confirmar a presença",
        description: formatError(caught),
        tone: "error",
        requestId: requestIdOf(caught),
      }),
  });

  function openDialog(kind: DialogKind, booking: Booking) {
    setDialog({ kind, booking });
    setReason("");
    setReasonError(null);
    setAcceptAck(false);
    setAcceptError(null);
    setActionError(null);
  }

  function closeDialog() {
    if (dialogBusy) return;
    setDialog(null);
    setReason("");
    setReasonError(null);
    setAcceptAck(false);
    setAcceptError(null);
    setActionError(null);
  }

  function confirmAccept() {
    if (!dialog || dialog.kind !== "accept") return;
    if (!acceptAck) {
      setAcceptError("Confirme o bloqueio do horário na sua agenda antes de aceitar.");
      return;
    }
    setAcceptError(null);
    acceptMutation.mutate(dialog.booking.id);
  }

  function confirmReason() {
    if (!dialog) return;
    if (!reason.trim()) {
      setReasonError("Informe o motivo. Ele fica registrado na auditoria.");
      return;
    }
    if (reason.trim().length > 200) {
      setReasonError("O motivo deve ter no máximo 200 caracteres.");
      return;
    }
    setReasonError(null);
    if (dialog.kind === "decline") {
      declineMutation.mutate({ bookingId: dialog.booking.id, reason: reason.trim() });
    } else if (dialog.kind === "cancel") {
      cancelMutation.mutate({ bookingId: dialog.booking.id, reason: reason.trim() });
    } else if (dialog.kind === "refund") {
      refundMutation.mutate({ bookingId: dialog.booking.id, reason: reason.trim() });
    }
  }

  const dialogBusy =
    acceptMutation.isPending ||
    declineMutation.isPending ||
    completeMutation.isPending ||
    cancelMutation.isPending ||
    refundMutation.isPending;

  const filtered = bookings.filter((booking) => bookingMatches(booking, search));
  const currentPage = Math.floor(offset / limit) + 1;

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draftFrom && draftTo && new Date(draftTo) <= new Date(draftFrom)) {
      setFilterError("O fim do período deve ser depois do início.");
      document.getElementById("booking-from")?.focus();
      return;
    }
    setFilterError(null);
    onParamsChange({
      status: draftStatus || null,
      from: toIso(draftFrom),
      to: toIso(draftTo),
      limit,
      offset: 0,
    });
  }

  function clearFilters() {
    setDraftStatus("");
    setDraftFrom("");
    setDraftTo("");
    setFilterError(null);
    onParamsChange({ status: null, from: null, to: null, limit, offset: 0 });
  }

  const targetBooking = dialog?.booking;
  const paidPayments = targetBooking?.payments.filter((payment) => payment.status === "PAID") ?? [];
  const paidTotal = paidPayments.reduce((total, payment) => total + payment.amount_cents, 0);

  return (
    <section className="stack">
      <div className="card">
        <SectionHeading
          title="Reservas"
          description="Solicitações originadas no JOGA. Prazos, bloqueios e estados são controlados pelo servidor."
        />

        {error ? (
          <ErrorNotice
            message={formatError(error)}
            requestId={requestIdOf(error)}
            onRetry={onRetry}
          />
        ) : null}

        <div className="stat-grid">
          <div className="stat-card">
            <span className="stat-card__icon stat-card__icon--info" aria-hidden="true">
              <CalendarIcon size={18} />
            </span>
            <div>
              <strong>{total}</strong>
              <span>Reservas no filtro</span>
            </div>
          </div>
          <div className="stat-card">
            <span className="stat-card__icon stat-card__icon--success" aria-hidden="true">
              <CheckIcon size={18} />
            </span>
            <div>
              <strong>{bookings.length}</strong>
              <span>Reservas nesta página</span>
            </div>
          </div>
          <div className="stat-card">
            <span className="stat-card__icon stat-card__icon--warning" aria-hidden="true">
              <ClockIcon size={18} />
            </span>
            <div>
              <strong>{currentPage}</strong>
              <span>Página atual</span>
            </div>
          </div>
        </div>

        <div className="filters-panel">
          <form className="filters-form" onSubmit={applyFilters} noValidate>
            <SelectField
              id="booking-status-filter"
              label="Situação"
              value={draftStatus}
              onChange={(event) => setDraftStatus(event.target.value)}
              hint="Filtro aplicado pelo servidor."
            >
              <option value="">Todas</option>
              {BOOKING_STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {bookingStatusLabel(status)}
                </option>
              ))}
            </SelectField>
            <TextField
              id="booking-from"
              label="Início do período"
              type="datetime-local"
              value={draftFrom}
              onChange={(event) => {
                setDraftFrom(event.target.value);
                if (filterError) setFilterError(null);
              }}
              hint="Opcional. Interpretado no fuso do navegador."
            />
            <TextField
              id="booking-to"
              label="Fim do período"
              type="datetime-local"
              value={draftTo}
              onChange={(event) => {
                setDraftTo(event.target.value);
                if (filterError) setFilterError(null);
              }}
            />
            <div className="filters-form__actions">
              <button
                type="submit"
                className="button button--small button--primary"
                disabled={fetching}
              >
                {fetching ? "Aplicando..." : "Aplicar filtros"}
              </button>
              <button
                type="button"
                className="button button--small button--ghost"
                onClick={clearFilters}
              >
                Limpar
              </button>
            </div>
          </form>
          <div className="filters-panel__search toolbar__search">
            <SearchIcon size={16} />
            <TextField
              id="booking-search"
              label="Buscar nesta página"
              className="field--search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar nesta página"
              inputClassName="input--search"
            />
          </div>
        </div>

        {filterError ? (
          <p className="field__error" role="alert">
            {filterError}
          </p>
        ) : null}

        {loading ? (
          <SkeletonList rows={3} label="Carregando reservas..." />
        ) : filtered.length === 0 ? (
          <EmptyState
            title={total === 0 ? "Nenhuma reserva" : "Nenhuma reserva nesta página"}
            icon={<CalendarIcon size={28} />}
            action={
              search ? (
                <button
                  type="button"
                  className="button button--small button--ghost"
                  onClick={() => setSearch("")}
                >
                  Limpar busca
                </button>
              ) : offset > 0 ? (
                <button
                  type="button"
                  className="button button--small button--ghost"
                  onClick={() => onParamsChange({ ...filters, offset: 0 })}
                >
                  Voltar à primeira página
                </button>
              ) : undefined
            }
          >
            {total === 0
              ? "As solicitações aparecem aqui quando um lobby do JOGA pedir uma quadra."
              : search
                ? "A busca considera apenas as reservas desta página."
                : "Ajuste os filtros para ver outras reservas."}
          </EmptyState>
        ) : (
          <ul className="booking-list">
            {filtered.map((booking) => {
              const activeParticipants = booking.participants.filter(
                (participant) => participant.active,
              ).length;
              const hasPaid = booking.payments.some((payment) => payment.status === "PAID");
              const canManageFinances =
                organization.role === "OWNER" || organization.role === "ADMIN";
              return (
                <li
                  key={booking.id}
                  className={`booking-card booking-card--${statusTone(booking.status)}`}
                >
                  <div className="booking-card__top">
                    <div>
                      <span className={`badge badge--${statusTone(booking.status)}`}>
                        {bookingStatusLabel(booking.status)}
                      </span>
                      <h3>
                        {formatDateRange(booking.starts_at, booking.ends_at, booking.timezone)}
                      </h3>
                      <p className="muted">
                        {booking.organization_venue_name ?? "Estabelecimento"} ·{" "}
                        {booking.venue_space_name ?? "Quadra"} · reserva{" "}
                        <span className="mono">#{shortId(booking.id)}</span>
                      </p>
                    </div>
                    <div className="booking-card__price">
                      <strong>{formatMoney(booking.price_cents)}</strong>
                      <span>
                        {activeParticipants} de {booking.seats} vagas ativas
                      </span>
                    </div>
                  </div>

                  <dl className="booking-meta">
                    <div>
                      <dt>Modalidade</dt>
                      <dd>{booking.format_name ?? "Não informada"}</dd>
                    </div>
                    <div>
                      <dt>Faixa</dt>
                      <dd>
                        {booking.band_label ?? "Não informada"}
                        {booking.tickets_per_seat
                          ? ` · ${booking.tickets_per_seat} ingressos/vaga`
                          : ""}
                      </dd>
                    </div>
                    <div>
                      <dt>Pagamento</dt>
                      <dd>
                        {booking.status === "PAYMENT_PENDING"
                          ? "Aguardando jogadores"
                          : booking.payments.length === 0
                            ? "Ainda não aberto"
                            : booking.payments.filter((payment) => payment.status === "PAID")
                                .length + ` de ${booking.payments.length} pagos`}
                      </dd>
                    </div>
                    <div>
                      <dt>Bloqueio</dt>
                      <dd>
                        {booking.hold?.status === "ACTIVE" && booking.hold_expires_at
                          ? `Ativo até ${formatDate(booking.hold_expires_at, booking.timezone)}`
                          : booking.hold
                            ? holdStatusLabel(booking.hold.status)
                            : "Não informado"}
                      </dd>
                    </div>
                  </dl>

                  {booking.timers.length > 0 ? (
                    <ul className="timer-row" aria-label="Prazos da reserva">
                      {booking.timers.map((timer) => (
                        <li
                          key={`${timer.timer_type}:${timer.started_at}`}
                          className={
                            timer.status === "RUNNING"
                              ? "timer-chip timer-chip--live"
                              : "timer-chip"
                          }
                        >
                          <ClockIcon size={14} />
                          <span>
                            <strong>{timerTypeLabel(timer.timer_type)}</strong>{" "}
                            {timerStatusLabel(timer.status)} · até{" "}
                            {formatDate(timer.deadline_at, booking.timezone)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  {booking.cancellation_reason ? (
                    <p className="booking-card__reason">
                      Motivo do cancelamento: {booking.cancellation_reason}
                    </p>
                  ) : null}

                  <details className="booking-details">
                    <summary>
                      Participantes, pagamento e presença ({booking.participants.length})
                    </summary>
                    {booking.participants.length === 0 ? (
                      <p className="muted">Nenhum participante alocado ainda.</p>
                    ) : (
                      <ul className="booking-participants">
                        {booking.participants.map((participant) => (
                          <li key={participant.id}>
                            <span className="booking-participants__identity">
                              <span className="avatar avatar--small" aria-hidden="true">
                                {participant.seat}
                              </span>
                              <span>
                                <strong>Vaga {participant.seat}</strong>
                                <small className="mono">
                                  #{shortId(participant.user_id)}
                                  {participant.settled_with
                                    ? ` · ${settledWithLabel(participant.settled_with)}`
                                    : ""}
                                </small>
                              </span>
                            </span>
                            <span className="booking-participants__status">
                              <span
                                className={
                                  participant.payment_status === "PAID"
                                    ? "badge badge--success"
                                    : "badge badge--muted"
                                }
                              >
                                {paymentStatusLabel(participant.payment_status)}
                              </span>
                              <span
                                className={
                                  participant.presence_status === "PRESENT"
                                    ? "badge badge--success"
                                    : participant.presence_status === "NO_SHOW"
                                      ? "badge badge--danger"
                                      : "badge badge--muted"
                                }
                              >
                                {presenceStatusLabel(participant.presence_status)}
                              </span>
                              {!participant.active ? (
                                <span className="badge badge--muted">Inativo</span>
                              ) : null}
                              {booking.status === "CONFIRMED" &&
                              ["PENDING", "UNVERIFIED"].includes(participant.presence_status) ? (
                                <button
                                  type="button"
                                  className="button button--small"
                                  disabled={presenceMutation.isPending}
                                  onClick={() =>
                                    presenceMutation.mutate({
                                      bookingId: booking.id,
                                      userId: participant.user_id,
                                    })
                                  }
                                >
                                  Confirmar presença
                                </button>
                              ) : null}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </details>

                  <div className="booking-card__actions">
                    {booking.status === "REQUESTED" ? (
                      <>
                        <button
                          type="button"
                          className="button button--small button--primary"
                          onClick={() => openDialog("accept", booking)}
                        >
                          Aceitar solicitação
                        </button>
                        <button
                          type="button"
                          className="button button--small button--danger"
                          onClick={() => openDialog("decline", booking)}
                        >
                          Recusar
                        </button>
                      </>
                    ) : null}
                    {booking.status === "CONFIRMED" ? (
                      <button
                        type="button"
                        className="button button--small button--primary"
                        onClick={() => openDialog("complete", booking)}
                      >
                        Concluir reserva
                      </button>
                    ) : null}
                    {["HOLD_CONFIRMED", "PAYMENT_PENDING", "CONFIRMED"].includes(booking.status) ? (
                      <button
                        type="button"
                        className="button button--small button--danger"
                        onClick={() => openDialog("cancel", booking)}
                      >
                        Cancelar pela quadra
                      </button>
                    ) : null}
                    {canManageFinances && hasPaid ? (
                      <button
                        type="button"
                        className="button button--small button--danger"
                        onClick={() => openDialog("refund", booking)}
                      >
                        Reembolsar
                      </button>
                    ) : null}
                    {booking.status === "PAYMENT_PENDING" ? (
                      <span className="booking-card__hint">
                        <WalletIcon size={15} />
                        Aguardando o pagamento dos jogadores
                      </span>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <Pagination
          total={total}
          limit={limit}
          offset={offset}
          onChange={(nextOffset) => onParamsChange({ ...filters, offset: nextOffset })}
          disabled={fetching}
        />
      </div>

      <ConfirmDialog
        open={dialog?.kind === "accept"}
        title="Aceitar solicitação e confirmar bloqueio?"
        description="Ao aceitar, você assume o compromisso de que o horário está efetivamente bloqueado na sua agenda operacional."
        confirmLabel="Confirmar bloqueio"
        busy={acceptMutation.isPending}
        confirmDisabled={!acceptAck}
        onConfirm={confirmAccept}
        onClose={closeDialog}
      >
        {targetBooking ? (
          <div className="dialog-summary">
            <strong>{formatDateRange(targetBooking.starts_at, targetBooking.ends_at)}</strong>
            <span>
              {targetBooking.organization_venue_name} · {targetBooking.venue_space_name}
            </span>
            <span>{formatMoney(targetBooking.price_cents)}</span>
          </div>
        ) : null}
        <CheckboxField
          id="accept-ack"
          label="Confirmo que o horário já está bloqueado na minha agenda operacional, inclusive quando o controle é manual, por telefone ou planilha."
          checked={acceptAck}
          onChange={(checked) => {
            setAcceptAck(checked);
            if (acceptError) setAcceptError(null);
          }}
          error={acceptError}
          required
          autoFocus
        />
        {actionError ? (
          <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
        ) : null}
      </ConfirmDialog>

      <ConfirmDialog
        open={dialog?.kind === "complete"}
        title="Concluir esta reserva?"
        description={
          targetBooking
            ? `${formatDateRange(targetBooking.starts_at, targetBooking.ends_at)} · ${targetBooking.venue_space_name ?? "Quadra"}. Use esta ação apenas depois da realização da partida.`
            : undefined
        }
        confirmLabel="Concluir reserva"
        busy={completeMutation.isPending}
        onConfirm={() => {
          if (targetBooking) completeMutation.mutate(targetBooking.id);
        }}
        onClose={closeDialog}
      >
        {actionError ? (
          <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
        ) : null}
      </ConfirmDialog>

      <ReasonDialog
        open={dialog?.kind === "decline"}
        title="Recusar solicitação"
        description="Explique o motivo da recusa. A informação fica registrada na auditoria e ajuda o jogador a entender o que aconteceu."
        label="Motivo da recusa"
        value={reason}
        onChange={(value) => {
          setReason(value);
          if (reasonError) setReasonError(null);
        }}
        error={reasonError}
        placeholder="Ex.: horário já ocupado na agenda presencial"
        maxLength={200}
        confirmLabel="Recusar reserva"
        tone="danger"
        busy={declineMutation.isPending}
        onConfirm={confirmReason}
        onClose={closeDialog}
      >
        {actionError ? (
          <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
        ) : null}
      </ReasonDialog>

      <ReasonDialog
        open={dialog?.kind === "cancel"}
        title="Cancelar pela quadra"
        description="O cancelamento pelo estabelecimento é auditado e pode afetar os jogadores e o fluxo de reembolso. Use apenas quando o espaço não puder ser disponibilizado."
        label="Motivo do cancelamento"
        value={reason}
        onChange={(value) => {
          setReason(value);
          if (reasonError) setReasonError(null);
        }}
        error={reasonError}
        placeholder="Ex.: manutenção emergencial na quadra"
        maxLength={200}
        confirmLabel="Cancelar reserva"
        tone="danger"
        busy={cancelMutation.isPending}
        onConfirm={confirmReason}
        onClose={closeDialog}
      >
        {actionError ? (
          <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
        ) : null}
      </ReasonDialog>

      <ReasonDialog
        open={dialog?.kind === "refund"}
        title="Reembolsar cobranças pagas"
        description="O reembolso é enviado ao Mercado Pago e não pode ser desfeito por esta interface. O resultado final aparece no extrato financeiro."
        label="Motivo do reembolso"
        value={reason}
        onChange={(value) => {
          setReason(value);
          if (reasonError) setReasonError(null);
        }}
        error={reasonError}
        placeholder="Ex.: cancelamento solicitado pelo estabelecimento"
        maxLength={200}
        confirmLabel="Reembolsar"
        tone="danger"
        busy={refundMutation.isPending}
        onConfirm={confirmReason}
        onClose={closeDialog}
      >
        {paidPayments.length > 0 ? (
          <div className="dialog-summary">
            <strong>{formatMoney(paidTotal)}</strong>
            <span>{paidPayments.length} cobrança(s) paga(s) serão enviadas para reembolso.</span>
          </div>
        ) : null}
        {actionError ? (
          <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
        ) : null}
      </ReasonDialog>
    </section>
  );
}
