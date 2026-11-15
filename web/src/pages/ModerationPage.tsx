import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { AppHeader } from "../components/AppHeader";
import { EmptyState, ErrorNotice, LoadingBlock } from "../components/Feedback";
import { ApiError, api } from "../lib/api";
import { formatDate, formatError, requestIdOf } from "../lib/format";
import { queryKeys } from "../lib/query";

const CATEGORY_LABELS: Record<string, string> = {
  HARASSMENT: "Assédio",
  HATE: "Ódio/discriminação",
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

export function ModerationPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("OPEN");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [decision, setDecision] = useState("WARN");
  const [reason, setReason] = useState("");
  const [days, setDays] = useState(7);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [operatorId, setOperatorId] = useState("");
  const [operatorRole, setOperatorRole] = useState<"MODERATOR" | "ADMIN">("MODERATOR");

  const meQuery = useQuery({
    queryKey: queryKeys.moderatorMe,
    queryFn: () => api.getModeratorMe(),
    retry: false,
  });
  const isModerator = meQuery.isSuccess;
  const isAdmin = meQuery.data?.role === "ADMIN";

  const queueQuery = useQuery({
    queryKey: queryKeys.moderationQueue(status),
    queryFn: () => api.getModerationQueue(status),
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
  const selected = reports.find((item) => item.id === selectedId) ?? reports[0] ?? null;

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["moderation", "queue"] }),
      queryClient.invalidateQueries({ queryKey: queryKeys.moderationAppeals }),
    ]);
  };

  const decisionMutation = useMutation({
    mutationFn: () =>
      api.decideModerationReport(selected?.id ?? "", {
        decision,
        reason,
        days,
      }),
    onSuccess: async (updated) => {
      setNotice(`Denúncia decidida: ${STATUS_LABELS[updated.status] ?? updated.status}.`);
      setReason("");
      setSelectedId(null);
      setActionError(null);
      await invalidate();
    },
    onError: (caught) => {
      setNotice(null);
      setActionError(caught);
    },
  });

  const appealMutation = useMutation({
    mutationFn: ({ appealId, result }: { appealId: string; result: "ACCEPTED" | "REJECTED" }) => {
      const text = window.prompt("Justificativa da decisão do recurso (obrigatória):");
      if (!text) return Promise.reject(new Error("cancelled"));
      return api.decideModerationAppeal(appealId, { decision: result, reason: text });
    },
    onSuccess: async () => {
      setNotice("Recurso decidido.");
      await invalidate();
    },
    onError: (caught) => {
      if (caught instanceof Error && caught.message === "cancelled") return;
      setActionError(caught);
    },
  });

  const addOperatorMutation = useMutation({
    mutationFn: () => api.upsertModerationOperator(operatorId, operatorRole),
    onSuccess: async () => {
      setOperatorId("");
      setNotice("Moderador atualizado.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.moderationOperators });
    },
    onError: (caught) => setActionError(caught),
  });

  const removeOperatorMutation = useMutation({
    mutationFn: (userId: string) => api.removeModerationOperator(userId),
    onSuccess: async () => {
      setNotice("Moderador desativado.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.moderationOperators });
    },
    onError: (caught) => setActionError(caught),
  });

  if (meQuery.error instanceof ApiError && meQuery.error.status === 403) {
    return (
      <div className="app-shell">
        <AppHeader moderation subtitle="Acesso interno" />
        <main className="page">
          <EmptyState title="Acesso restrito">
            Sua conta não tem permissão de moderação. Peça a um administrador para incluí-la.
          </EmptyState>
        </main>
      </div>
    );
  }

  if (meQuery.isPending) {
    return (
      <div className="app-shell">
        <AppHeader moderation subtitle="Acesso interno" />
        <main className="page">
          <LoadingBlock label="Verificando permissão..." />
        </main>
      </div>
    );
  }

  if (meQuery.error) {
    return (
      <div className="app-shell">
        <AppHeader moderation subtitle="Acesso interno" />
        <main className="page">
          <ErrorNotice
            message={formatError(meQuery.error)}
            requestId={requestIdOf(meQuery.error)}
            onRetry={() => void meQuery.refetch()}
          />
        </main>
      </div>
    );
  }

  const stats = queueQuery.data?.stats;
  const error = queueQuery.error ?? appealsQuery.error ?? operatorsQuery.error ?? actionError;

  return (
    <div className="app-shell">
      <AppHeader moderation subtitle="Fila interna de denúncias" />
      <main className="page">
        <section className="page-heading">
          <div>
            <p className="eyebrow">JOGA y MODERAÇÃO</p>
            <h1>Denúncias e recursos</h1>
            <p className="muted">
              Área interna separada do painel de gestão. A triagem é determinística e a decisão é
              sempre humana.
            </p>
          </div>
        </section>

        {notice ? (
          <div className="notice notice--success" role="status">
            {notice}
          </div>
        ) : null}
        {error ? (
          <ErrorNotice
            message={formatError(error)}
            requestId={requestIdOf(error)}
            onRetry={() => void queueQuery.refetch()}
          />
        ) : null}

        <section className="moderation-stats">
          <div className="card">
            <span>Abertas</span>
            <strong>{stats?.open ?? 0}</strong>
          </div>
          <div className="card">
            <span>Alta prioridade</span>
            <strong>{stats?.high_priority ?? 0}</strong>
          </div>
          <div className="card">
            <span>Em recurso</span>
            <strong>{stats?.appealed ?? 0}</strong>
          </div>
        </section>

        <div className="moderation-layout">
          <section className="card moderation-queue">
            <div className="section-heading">
              <div>
                <h2>Fila</h2>
                <p className="muted">Atualiza a cada 30 segundos.</p>
              </div>
              <select value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="OPEN">Abertas</option>
                <option value="APPEALED">Em recurso</option>
                <option value="RESOLVED">Resolvidas</option>
                <option value="DISMISSED">Improcedentes</option>
              </select>
            </div>
            {queueQuery.isPending ? (
              <LoadingBlock label="Carregando denúncias..." />
            ) : reports.length === 0 ? (
              <EmptyState title="Fila vazia">Nenhuma denúncia neste status.</EmptyState>
            ) : (
              <ul className="moderation-list">
                {reports.map((report) => (
                  <li key={report.id}>
                    <button
                      type="button"
                      className={
                        selected?.id === report.id
                          ? "moderation-item moderation-item--active"
                          : "moderation-item"
                      }
                      onClick={() => setSelectedId(report.id)}
                    >
                      <span>
                        <strong>{CATEGORY_LABELS[report.category] ?? report.category}</strong>
                        <small>
                          {report.severity} · prioridade {report.priority} ·{" "}
                          {formatDate(report.created_at)}
                        </small>
                      </span>
                      <span className={`badge badge--${report.severity.toLowerCase()}`}>
                        {STATUS_LABELS[report.status] ?? report.status}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card moderation-detail">
            {selected ? (
              <>
                <div className="section-heading">
                  <div>
                    <h2>{CATEGORY_LABELS[selected.category] ?? selected.category}</h2>
                    <p className="muted">
                      {selected.severity} · prioridade {selected.priority} ·{" "}
                      {selected.classifier_version}
                    </p>
                  </div>
                  <span className="badge badge--muted">
                    {STATUS_LABELS[selected.status] ?? selected.status}
                  </span>
                </div>
                <p>{selected.description}</p>
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
                        <small>{formatDate(message.created_at)}</small>
                        <p>{message.body}</p>
                      </li>
                    ))}
                  </ul>
                )}

                {["OPEN", "IN_REVIEW"].includes(selected.status) ? (
                  <form
                    className="form form--inline"
                    onSubmit={(event) => {
                      event.preventDefault();
                      decisionMutation.mutate();
                    }}
                  >
                    <h3>Decisão</h3>
                    <div className="form-row">
                      <label className="field">
                        <span>Medida</span>
                        <select
                          value={decision}
                          onChange={(event) => setDecision(event.target.value)}
                        >
                          {Object.entries(DECISION_LABELS).map(([value, label]) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </label>
                      {["RESTRICT_RANKED", "SUSPEND_TEMP"].includes(decision) ? (
                        <label className="field field--short">
                          <span>Dias</span>
                          <input
                            type="number"
                            min={1}
                            max={decision === "SUSPEND_TEMP" ? 30 : 90}
                            value={days}
                            onChange={(event) => setDays(Number(event.target.value))}
                            required
                          />
                        </label>
                      ) : null}
                    </div>
                    <label className="field">
                      <span>Justificativa</span>
                      <textarea
                        value={reason}
                        onChange={(event) => setReason(event.target.value)}
                        maxLength={1000}
                        required
                      />
                    </label>
                    <button
                      type="submit"
                      className="button button--primary"
                      disabled={decisionMutation.isPending}
                    >
                      Registrar decisão
                    </button>
                  </form>
                ) : null}
              </>
            ) : (
              <EmptyState title="Selecione uma denúncia">
                A fila e o detalhe aparecem aqui.
              </EmptyState>
            )}
          </section>
        </div>

        <section className="card">
          <h2>Recursos pendentes</h2>
          {appealsQuery.isPending ? (
            <LoadingBlock label="Carregando recursos..." />
          ) : (appealsQuery.data ?? []).length === 0 ? (
            <EmptyState title="Nenhum recurso">Não há recurso aguardando decisão.</EmptyState>
          ) : (
            <ul className="moderation-list">
              {(appealsQuery.data ?? []).map((appeal) => (
                <li key={appeal.id} className="moderation-appeal">
                  <span>
                    <strong>{appeal.reason}</strong>
                    <small>{formatDate(appeal.created_at)}</small>
                  </span>
                  <div className="booking-card__actions">
                    <button
                      type="button"
                      className="button button--small"
                      onClick={() =>
                        appealMutation.mutate({ appealId: appeal.id, result: "ACCEPTED" })
                      }
                    >
                      Aceitar
                    </button>
                    <button
                      type="button"
                      className="button button--small button--danger"
                      onClick={() =>
                        appealMutation.mutate({ appealId: appeal.id, result: "REJECTED" })
                      }
                    >
                      Rejeitar
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {isAdmin ? (
          <section className="card">
            <h2>Moderadores</h2>
            {operatorsQuery.isPending ? (
              <LoadingBlock label="Carregando moderadores..." />
            ) : (
              <ul className="moderation-list">
                {(operatorsQuery.data ?? []).map((operator) => (
                  <li key={operator.user_id} className="moderation-appeal">
                    <span>
                      <strong className="mono">{operator.user_id}</strong>
                      <small>
                        {operator.role} · {operator.active ? "ativo" : "inativo"}
                      </small>
                    </span>
                    {operator.active ? (
                      <button
                        type="button"
                        className="button button--small button--danger"
                        onClick={() => removeOperatorMutation.mutate(operator.user_id)}
                      >
                        Desativar
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            <form
              className="form form--inline"
              onSubmit={(event) => {
                event.preventDefault();
                addOperatorMutation.mutate();
              }}
            >
              <h3>Adicionar moderador</h3>
              <div className="form-row">
                <label className="field">
                  <span>UUID da conta</span>
                  <input
                    value={operatorId}
                    onChange={(event) => setOperatorId(event.target.value)}
                    placeholder="00000000-0000-0000-0000-000000000000"
                    required
                  />
                </label>
                <label className="field field--short">
                  <span>Papel</span>
                  <select
                    value={operatorRole}
                    onChange={(event) =>
                      setOperatorRole(event.target.value as "MODERATOR" | "ADMIN")
                    }
                  >
                    <option value="MODERATOR">Moderador</option>
                    <option value="ADMIN">Administrador</option>
                  </select>
                </label>
              </div>
              <button type="submit" className="button button--primary">
                Salvar moderador
              </button>
            </form>
          </section>
        ) : null}
      </main>
    </div>
  );
}
