import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useSearchParams } from "react-router-dom";

import { EmptyState, ErrorNotice, InfoNotice, SkeletonList } from "../components/Feedback";
import { SelectField, TextareaField, TextField } from "../components/ui/Field";
import { RefreshIcon, ShieldIcon } from "../components/ui/Icons";
import { ConfirmDialog, ReasonDialog } from "../components/ui/Modal";
import { PageHeader, SectionHeading } from "../components/ui/PageHeader";
import { useToast } from "../components/ui/toast-context";
import { ApiError, api } from "../lib/api";
import { formatDate, formatError, requestIdOf } from "../lib/format";
import { queryKeys } from "../lib/query";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import { positiveIntegerError, textError, uuidError } from "../lib/validation";
import type { ModerationAppeal } from "../types";

const CATEGORY_LABELS: Record<string, string> = {
  HARASSMENT: "Assédio",
  HATE: "Ódio ou discriminação",
  THREAT: "Ameaça",
  SEXUAL: "Conteúdo sexual",
  SPAM: "Spam",
  OTHER: "Outro",
};

const STATUS_LABELS: Record<string, string> = {
  OPEN: "Aberta",
  IN_REVIEW: "Em revisão",
  RESOLVED: "Resolvida",
  DISMISSED: "Improcedente",
  APPEALED: "Em recurso",
};

const DECISION_LABELS: Record<string, string> = {
  DISMISS: "Improcedente",
  WARN: "Aviso",
  RESTRICT_RANKED: "Restringir ranqueada",
  SUSPEND_TEMP: "Suspender temporariamente",
};

const SEVERITY_LABELS: Record<string, string> = {
  HIGH: "Alta",
  MEDIUM: "Média",
  LOW: "Baixa",
};

const ROLE_LABELS = { ADMIN: "Administrador", MODERATOR: "Moderador" } as const;

function severityTone(severity: string): string {
  if (severity === "HIGH") return "danger";
  if (severity === "MEDIUM") return "warning";
  return "muted";
}

function DecisionForm({
  onDecision,
  busy,
  error,
}: {
  onDecision: (payload: { decision: string; reason: string; days: number }) => void;
  busy: boolean;
  error: unknown;
}) {
  const [decision, setDecision] = useState("WARN");
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [days, setDays] = useState("7");
  const [daysError, setDaysError] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: Record<string, string> = {};
    const reasonValidation = textError(reason, { label: "a justificativa", max: 1000 });
    if (reasonValidation) next.reason = reasonValidation;
    if (["RESTRICT_RANKED", "SUSPEND_TEMP"].includes(decision)) {
      const dayError = positiveIntegerError(
        Number(days),
        1,
        decision === "SUSPEND_TEMP" ? 30 : 90,
        "o número de dias",
      );
      if (dayError) next.days = dayError;
    }
    if (Object.keys(next).length > 0) {
      if (next.reason) setReasonError(next.reason);
      if (next.days) setDaysError(next.days);
      document.getElementById(next.reason ? "moderation-reason" : "moderation-days")?.focus();
      return;
    }
    setReasonError(null);
    setDaysError(null);
    onDecision({ decision, reason: reason.trim(), days: Number(days) });
  }

  return (
    <form className="form form--inline" onSubmit={submit} noValidate>
      <h3>Decisão</h3>
      <div className="form-row">
        <SelectField
          id="moderation-decision"
          label="Medida"
          value={decision}
          onChange={(event) => setDecision(event.target.value)}
        >
          {Object.entries(DECISION_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </SelectField>
        {["RESTRICT_RANKED", "SUSPEND_TEMP"].includes(decision) ? (
          <TextField
            id="moderation-days"
            label="Dias"
            type="number"
            min={1}
            max={decision === "SUSPEND_TEMP" ? 30 : 90}
            value={days}
            onChange={(event) => {
              setDays(event.target.value);
              if (daysError) setDaysError(null);
            }}
            error={daysError}
            hint={
              decision === "SUSPEND_TEMP"
                ? "Suspensão temporária: 1 a 30 dias."
                : "Restrição ranqueada: 1 a 90 dias."
            }
            required
          />
        ) : null}
      </div>
      <TextareaField
        id="moderation-reason"
        label="Justificativa"
        value={reason}
        onChange={(event) => {
          setReason(event.target.value);
          if (reasonError) setReasonError(null);
        }}
        error={reasonError}
        hint="Obrigatória. Fica registrada na auditoria e fundamenta a medida."
        maxLength={1000}
        rows={4}
        required
      />
      {error ? <ErrorNotice message={formatError(error)} requestId={requestIdOf(error)} /> : null}
      <button
        type="submit"
        className="button button--primary"
        disabled={busy}
        aria-busy={busy || undefined}
      >
        {busy ? "Registrando..." : "Registrar decisão"}
      </button>
    </form>
  );
}

const PAGE_SIZE = 30;

export function ModerationPage() {
  useDocumentTitle("Moderação");
  const queryClient = useQueryClient();
  const toast = useToast();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const reportParam = searchParams.get("report");
  const appealParam = searchParams.get("appeal");
  const [status, setStatus] = useState("OPEN");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [appealTarget, setAppealTarget] = useState<{
    appeal: ModerationAppeal;
    result: "ACCEPTED" | "REJECTED";
  } | null>(null);
  const [appealReason, setAppealReason] = useState("");
  const [appealError, setAppealError] = useState<string | null>(null);
  const [operatorId, setOperatorId] = useState("");
  const [operatorIdError, setOperatorIdError] = useState<string | null>(null);
  const [operatorRole, setOperatorRole] = useState<"MODERATOR" | "ADMIN">("MODERATOR");
  const [removeOperatorTarget, setRemoveOperatorTarget] = useState<string | null>(null);

  const meQuery = useQuery({
    queryKey: queryKeys.moderatorMe,
    queryFn: () => api.getModeratorMe(),
    retry: false,
  });
  const isModerator = meQuery.isSuccess;
  const isAdmin = meQuery.data?.role === "ADMIN";

  const queueQuery = useQuery({
    queryKey: queryKeys.moderationQueue(status, PAGE_SIZE, offset),
    queryFn: () => api.getModerationQueue(status, PAGE_SIZE, offset),
    enabled: isModerator,
    refetchInterval: 30_000,
  });
  const appealsQuery = useQuery({
    queryKey: queryKeys.moderationAppeals,
    queryFn: () => api.listModerationAppeals(),
    enabled: isModerator,
  });
  const operatorsQuery = useQuery({
    queryKey: queryKeys.moderationOperators,
    queryFn: () => api.listModerationOperators(),
    enabled: isAdmin,
  });

  const reports = queueQuery.data?.reports ?? [];
  const queueHasReport = Boolean(reportParam && reports.some((item) => item.id === reportParam));
  const reportDetailQuery = useQuery({
    queryKey: queryKeys.moderationReport(reportParam ?? ""),
    queryFn: () => api.getModerationReport(reportParam ?? ""),
    enabled: isModerator && Boolean(reportParam) && !queueHasReport,
    retry: false,
  });
  const pinnedReport =
    reportDetailQuery.data && reportDetailQuery.data.id === reportParam
      ? reportDetailQuery.data
      : null;
  const selected =
    reports.find((item) => item.id === (selectedId ?? reportParam)) ??
    pinnedReport ??
    reports[0] ??
    null;
  const stats = queueQuery.data?.stats;

  useEffect(() => {
    const targetId = appealParam
      ? `appeal-${appealParam}`
      : location.hash === "#appeals"
        ? "appeals"
        : reportParam
          ? `report-${reportParam}`
          : null;
    if (!targetId) return;
    const timer = window.setTimeout(() => {
      document.getElementById(targetId)?.scrollIntoView?.({ block: "start" });
    }, 200);
    return () => window.clearTimeout(timer);
  }, [appealParam, location.hash, reportParam, queueQuery.data, appealsQuery.data]);

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["moderation", "queue"] }),
      queryClient.invalidateQueries({ queryKey: queryKeys.moderationAppeals }),
      queryClient.invalidateQueries({ queryKey: queryKeys.moderationOperators }),
      ...(reportParam
        ? [queryClient.invalidateQueries({ queryKey: queryKeys.moderationReport(reportParam) })]
        : []),
    ]);
  };

  const decisionMutation = useMutation({
    mutationFn: (payload: { decision: string; reason: string; days: number }) =>
      api.decideModerationReport(selected?.id ?? "", payload),
    onSuccess: async (updated) => {
      toast.push({
        title: `Denúncia decidida: ${STATUS_LABELS[updated.status] ?? updated.status}.`,
      });
      setActionError(null);
      setSelectedId(null);
      await invalidate();
    },
    onError: (caught) => setActionError(caught),
  });

  const appealMutation = useMutation({
    mutationFn: ({
      appealId,
      result,
      justification,
    }: {
      appealId: string;
      result: "ACCEPTED" | "REJECTED";
      justification: string;
    }) => api.decideModerationAppeal(appealId, { decision: result, reason: justification }),
    onSuccess: async (_item, variables) => {
      setAppealTarget(null);
      setAppealReason("");
      setAppealError(null);
      setActionError(null);
      toast.push({
        title: variables.result === "ACCEPTED" ? "Recurso aceito" : "Recurso rejeitado",
        description: "A decisão foi registrada na auditoria.",
      });
      await invalidate();
    },
    onError: (caught) => setActionError(caught),
  });

  const addOperatorMutation = useMutation({
    mutationFn: () => api.upsertModerationOperator(operatorId.trim(), operatorRole),
    onSuccess: async () => {
      setOperatorId("");
      setOperatorIdError(null);
      setActionError(null);
      toast.push({ title: "Moderador atualizado" });
      await queryClient.invalidateQueries({ queryKey: queryKeys.moderationOperators });
    },
    onError: (caught) => setActionError(caught),
  });

  const removeOperatorMutation = useMutation({
    mutationFn: (userId: string) => api.removeModerationOperator(userId),
    onSuccess: async () => {
      setRemoveOperatorTarget(null);
      setActionError(null);
      toast.push({ title: "Moderador desativado" });
      await queryClient.invalidateQueries({ queryKey: queryKeys.moderationOperators });
    },
    onError: (caught) => setActionError(caught),
  });

  function openAppeal(appeal: ModerationAppeal, result: "ACCEPTED" | "REJECTED") {
    setActionError(null);
    setAppealTarget({ appeal, result });
    setAppealReason("");
    setAppealError(null);
  }

  function confirmAppeal() {
    if (!appealTarget) return;
    if (!appealReason.trim()) {
      setAppealError("Informe a justificativa da decisão.");
      return;
    }
    if (appealReason.trim().length > 1000) {
      setAppealError("A justificativa deve ter no máximo 1.000 caracteres.");
      return;
    }
    appealMutation.mutate({
      appealId: appealTarget.appeal.id,
      result: appealTarget.result,
      justification: appealReason.trim(),
    });
  }

  function submitOperator(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validation = uuidError(operatorId, "o UUID da conta");
    if (validation) {
      setOperatorIdError(validation);
      document.getElementById("operator-id")?.focus();
      return;
    }
    addOperatorMutation.mutate();
  }

  const filteredReports = reports;

  if (meQuery.error instanceof ApiError && meQuery.error.status === 403) {
    return (
      <>
        <PageHeader eyebrow="JOGA y MODERAÇÃO" title="Moderação" />
        <EmptyState title="Acesso restrito" icon={<ShieldIcon size={30} />}>
          Sua conta não está habilitada como moderador. Peça para incluir seu UUID em{" "}
          <code>JOGA_MODERATION_ADMIN_USER_IDS</code> (ou cadastrá-lo como operador) e recarregue
          esta página.
        </EmptyState>
      </>
    );
  }

  if (meQuery.isPending) {
    return <SkeletonList rows={3} label="Verificando permissão de moderação..." />;
  }

  if (meQuery.error) {
    return (
      <ErrorNotice
        message={formatError(meQuery.error)}
        requestId={requestIdOf(meQuery.error)}
        onRetry={() => void meQuery.refetch()}
      />
    );
  }

  const displayError = appealsQuery.error ?? operatorsQuery.error ?? actionError;

  return (
    <>
      <PageHeader
        eyebrow="JOGA y MODERAÇÃO"
        title="Denúncias e recursos"
        description="Área interna separada do painel de gestão. A triagem é determinística e a decisão é sempre humana."
        actions={
          <button
            type="button"
            className="button button--ghost"
            onClick={() => void queueQuery.refetch()}
            disabled={queueQuery.isFetching}
          >
            <RefreshIcon size={16} />
            {queueQuery.isFetching ? "Atualizando..." : "Atualizar fila"}
          </button>
        }
      />

      <InfoNotice>
        <p>
          O acesso é restrito a operadores autorizados e cada decisão exige justificativa. Medidas
          preventivas precisam ser reversíveis e cabe recurso.
        </p>
      </InfoNotice>

      {displayError ? (
        <ErrorNotice
          message={formatError(displayError)}
          requestId={requestIdOf(displayError)}
          onRetry={() => void queueQuery.refetch()}
        />
      ) : null}

      <section className="moderation-stats" aria-label="Resumo da fila">
        <div className="stat-card">
          <span className="stat-card__icon stat-card__icon--warning" aria-hidden="true">
            <ShieldIcon size={18} />
          </span>
          <div>
            <strong>{stats?.open ?? 0}</strong>
            <span>Abertas</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-card__icon stat-card__icon--danger" aria-hidden="true">
            <ShieldIcon size={18} />
          </span>
          <div>
            <strong>{stats?.high_priority ?? 0}</strong>
            <span>Alta prioridade</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-card__icon stat-card__icon--info" aria-hidden="true">
            <ShieldIcon size={18} />
          </span>
          <div>
            <strong>{stats?.appealed ?? 0}</strong>
            <span>Em recurso</span>
          </div>
        </div>
      </section>

      <div className="moderation-layout">
        <section className="card moderation-queue">
          <SectionHeading title="Fila" description="Atualiza automaticamente a cada 30 segundos." />
          <div className="segmented segmented--wrap" role="group" aria-label="Filtrar denúncias">
            {(
              [
                ["OPEN", "Abertas"],
                ["IN_REVIEW", "Em revisão"],
                ["APPEALED", "Em recurso"],
                ["RESOLVED", "Resolvidas"],
                ["DISMISSED", "Improcedentes"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={status === value ? "segmented__item is-active" : "segmented__item"}
                aria-pressed={status === value}
                onClick={() => {
                  setStatus(value);
                  setOffset(0);
                  setSelectedId(null);
                }}
              >
                {label}
              </button>
            ))}
          </div>

          {queueQuery.isPending ? (
            <SkeletonList rows={3} label="Carregando denúncias..." />
          ) : queueQuery.error ? (
            <ErrorNotice
              message={formatError(queueQuery.error)}
              requestId={requestIdOf(queueQuery.error)}
              onRetry={() => void queueQuery.refetch()}
            />
          ) : filteredReports.length === 0 ? (
            <EmptyState title="Fila vazia" icon={<ShieldIcon size={26} />}>
              Nenhuma denúncia neste status.
            </EmptyState>
          ) : (
            <ul className="moderation-list">
              {filteredReports.map((report) => (
                <li key={report.id} id={`report-${report.id}`}>
                  <button
                    type="button"
                    className={
                      selected?.id === report.id
                        ? "moderation-item moderation-item--active"
                        : "moderation-item"
                    }
                    onClick={() => setSelectedId(report.id)}
                    aria-pressed={selected?.id === report.id}
                  >
                    <span>
                      <strong>{CATEGORY_LABELS[report.category] ?? report.category}</strong>
                      <small>
                        {SEVERITY_LABELS[report.severity] ?? report.severity} · prioridade{" "}
                        {report.priority} · {formatDate(report.created_at)}
                      </small>
                    </span>
                    <span className={`badge badge--${severityTone(report.severity)}`}>
                      {STATUS_LABELS[report.status] ?? report.status}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {queueQuery.error ? null : (
            <div className="pagination">
              <span className="pagination__info">
                Página {Math.floor(offset / PAGE_SIZE) + 1}
                {reports.length < PAGE_SIZE ? " · fim da fila" : ""}
              </span>
              <div className="pagination__actions">
                <button
                  type="button"
                  className="button button--small button--ghost"
                  onClick={() => {
                    setOffset(Math.max(0, offset - PAGE_SIZE));
                    setSelectedId(null);
                  }}
                  disabled={offset === 0 || queueQuery.isFetching}
                >
                  Anterior
                </button>
                <button
                  type="button"
                  className="button button--small button--ghost"
                  onClick={() => {
                    setOffset(offset + PAGE_SIZE);
                    setSelectedId(null);
                  }}
                  disabled={reports.length < PAGE_SIZE || queueQuery.isFetching}
                >
                  Próxima
                </button>
              </div>
            </div>
          )}
        </section>

        <section className="card moderation-detail">
          {selected ? (
            <>
              <SectionHeading
                title={CATEGORY_LABELS[selected.category] ?? selected.category}
                description={`${SEVERITY_LABELS[selected.severity] ?? selected.severity} · prioridade ${
                  selected.priority
                } · ${selected.classifier_version}`}
                actions={
                  <span className="badge badge--muted">
                    {STATUS_LABELS[selected.status] ?? selected.status}
                  </span>
                }
              />
              <p className="moderation-description">{selected.description}</p>
              <dl className="moderation-meta">
                <div>
                  <dt>Denunciante</dt>
                  <dd className="mono">{selected.reporter_id}</dd>
                </div>
                <div>
                  <dt>Alvo</dt>
                  <dd className="mono">{selected.target_user_id}</dd>
                </div>
                <div>
                  <dt>Lobby</dt>
                  <dd className="mono">{selected.lobby_id}</dd>
                </div>
              </dl>

              <h3>Contexto anexado</h3>
              {selected.context.length === 0 ? (
                <p className="muted">Nenhuma mensagem anexada.</p>
              ) : (
                <ul className="moderation-context">
                  {selected.context.map((message) => (
                    <li key={message.id}>
                      <small>
                        {message.sender_id === selected.target_user_id ? "Alvo" : "Participante"} ·{" "}
                        {formatDate(message.created_at)}
                      </small>
                      <p>{message.body}</p>
                    </li>
                  ))}
                </ul>
              )}

              {["OPEN", "IN_REVIEW"].includes(selected.status) ? (
                <DecisionForm
                  key={selected.id}
                  onDecision={(payload) => decisionMutation.mutate(payload)}
                  busy={decisionMutation.isPending}
                  error={actionError}
                />
              ) : null}
            </>
          ) : (
            <EmptyState title="Selecione uma denúncia" icon={<ShieldIcon size={28} />}>
              A fila e o detalhe aparecem aqui.
            </EmptyState>
          )}
        </section>
      </div>

      <section className="card anchor-target" id="appeals">
        <SectionHeading
          title="Recursos pendentes"
          description="Decisões de recurso exigem justificativa."
        />
        {appealsQuery.isPending ? (
          <SkeletonList rows={2} label="Carregando recursos..." />
        ) : (appealsQuery.data ?? []).length === 0 ? (
          <EmptyState title="Nenhum recurso">Não há recurso aguardando decisão.</EmptyState>
        ) : (
          <ul className="moderation-list">
            {(appealsQuery.data ?? []).map((appeal) => (
              <li
                key={appeal.id}
                id={`appeal-${appeal.id}`}
                className={
                  appealParam === appeal.id
                    ? "moderation-appeal is-highlighted"
                    : "moderation-appeal"
                }
              >
                <span>
                  <strong>{appeal.reason}</strong>
                  <small>{formatDate(appeal.created_at)}</small>
                </span>
                <div className="booking-card__actions">
                  <button
                    type="button"
                    className="button button--small button--ghost"
                    onClick={() => openAppeal(appeal, "ACCEPTED")}
                  >
                    Aceitar recurso
                  </button>
                  <button
                    type="button"
                    className="button button--small button--danger"
                    onClick={() => openAppeal(appeal, "REJECTED")}
                  >
                    Rejeitar recurso
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {isAdmin ? (
        <section className="card">
          <SectionHeading
            title="Moderadores"
            description="Administradores gerenciam quem pode acessar a fila interna."
          />
          {operatorsQuery.isPending ? (
            <SkeletonList rows={2} label="Carregando moderadores..." />
          ) : (operatorsQuery.data ?? []).length === 0 ? (
            <EmptyState title="Nenhum moderador cadastrado">
              Adicione a primeira conta autorizada abaixo.
            </EmptyState>
          ) : (
            <ul className="moderation-list">
              {(operatorsQuery.data ?? []).map((operator) => (
                <li key={operator.user_id} className="moderation-appeal">
                  <span>
                    <strong className="mono">{operator.user_id}</strong>
                    <small>
                      {ROLE_LABELS[operator.role]} · {operator.active ? "ativo" : "inativo"}
                    </small>
                  </span>
                  {operator.active ? (
                    <button
                      type="button"
                      className="button button--small button--danger"
                      onClick={() => {
                        setActionError(null);
                        setRemoveOperatorTarget(operator.user_id);
                      }}
                    >
                      Desativar
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          <form className="form form--inline" onSubmit={submitOperator} noValidate>
            <h3>Adicionar moderador</h3>
            <div className="form-row">
              <TextField
                id="operator-id"
                label="UUID da conta"
                value={operatorId}
                onChange={(event) => {
                  setOperatorId(event.target.value);
                  if (operatorIdError) setOperatorIdError(null);
                }}
                error={operatorIdError}
                placeholder="00000000-0000-0000-0000-000000000000"
                hint="A conta já precisa existir no JOGA."
                maxLength={36}
                autoComplete="off"
                required
              />
              <SelectField
                id="operator-role"
                label="Papel"
                value={operatorRole}
                onChange={(event) => setOperatorRole(event.target.value as "MODERATOR" | "ADMIN")}
              >
                <option value="MODERATOR">Moderador</option>
                <option value="ADMIN">Administrador</option>
              </SelectField>
            </div>
            <button
              type="submit"
              className="button button--primary"
              disabled={addOperatorMutation.isPending}
              aria-busy={addOperatorMutation.isPending || undefined}
            >
              {addOperatorMutation.isPending ? "Salvando..." : "Salvar moderador"}
            </button>
          </form>
        </section>
      ) : null}

      <ReasonDialog
        open={Boolean(appealTarget)}
        title={appealTarget?.result === "ACCEPTED" ? "Aceitar recurso" : "Rejeitar recurso"}
        description="A justificativa é obrigatória e fica registrada na auditoria."
        label="Justificativa da decisão"
        value={appealReason}
        onChange={(value) => {
          setAppealReason(value);
          if (appealError) setAppealError(null);
        }}
        error={appealError}
        maxLength={1000}
        confirmLabel={appealTarget?.result === "ACCEPTED" ? "Aceitar recurso" : "Rejeitar recurso"}
        tone={appealTarget?.result === "REJECTED" ? "danger" : "default"}
        busy={appealMutation.isPending}
        onConfirm={confirmAppeal}
        onClose={() => {
          setAppealTarget(null);
          setAppealReason("");
          setAppealError(null);
          setActionError(null);
        }}
      >
        {actionError ? (
          <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
        ) : null}
      </ReasonDialog>

      <ConfirmDialog
        open={Boolean(removeOperatorTarget)}
        title="Desativar moderador?"
        description="A conta perde o acesso à fila interna. O histórico de decisões permanece preservado."
        tone="danger"
        confirmLabel="Desativar moderador"
        busy={removeOperatorMutation.isPending}
        onConfirm={() => {
          if (removeOperatorTarget) removeOperatorMutation.mutate(removeOperatorTarget);
        }}
        onClose={() => {
          setRemoveOperatorTarget(null);
          setActionError(null);
        }}
      >
        {actionError ? (
          <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
        ) : null}
      </ConfirmDialog>
    </>
  );
}
