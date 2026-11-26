import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { SkeletonList } from "../../components/Feedback";
import {
  AlertIcon,
  ClockIcon,
  InfoIcon,
  LockIcon,
  RefreshIcon,
  SearchIcon,
  ShieldIcon,
  UsersIcon,
} from "../../components/ui/Icons";
import { PageHeader, SectionHeading } from "../../components/ui/PageHeader";
import { api } from "../../lib/api";
import { formatDate, shortId } from "../../lib/format";
import {
  OBSERVABILITY_WINDOWS,
  formatCount,
  formatDuration,
  observabilityPollInterval,
  observabilityWindow,
  requestRateText,
  variationText,
} from "../../lib/observability";
import { queryKeys } from "../../lib/query";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import type { ObservabilitySummaryWindow } from "../../types";
import { ObservabilityQueryError, RefreshButton } from "./AdminObservabilityShared";

function levelCount(window: ObservabilitySummaryWindow, level: string): number {
  return window.by_level.find((item) => item.level === level)?.count ?? 0;
}

function StatCard({
  icon,
  tone,
  value,
  label,
  detail,
  comparison,
}: {
  icon: ReactNode;
  tone: string;
  value: string;
  label: string;
  detail?: string;
  comparison: string;
}) {
  return (
    <div className="stat-card">
      <span className={`stat-card__icon stat-card__icon--${tone}`} aria-hidden="true">
        {icon}
      </span>
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
        {detail ? <small className="obs-rate">{detail}</small> : null}
        <small className="obs-delta">{comparison}</small>
      </div>
    </div>
  );
}

export function AdminObservabilityPage() {
  useDocumentTitle("Monitoramento");
  const [searchParams, setSearchParams] = useSearchParams();
  const window = observabilityWindow(searchParams.get("window"));

  const summaryQuery = useQuery({
    queryKey: queryKeys.adminObservabilitySummary(window),
    queryFn: () => api.getObservabilitySummary(window),
    refetchInterval: observabilityPollInterval,
    refetchIntervalInBackground: false,
  });

  const summary = summaryQuery.data ?? null;
  const current = summary?.current ?? null;
  const previous = summary?.previous ?? null;

  function selectWindow(next: string) {
    const params = new URLSearchParams(searchParams);
    params.set("window", next);
    setSearchParams(params);
  }

  return (
    <>
      <PageHeader
        eyebrow="JOGA y ADMINISTRAÇÃO"
        title="Monitoramento"
        description="Acompanhe erros, acessos e tarefas da plataforma. Os números comparam o período escolhido com o anterior."
        actions={
          <RefreshButton
            busy={summaryQuery.isFetching}
            onClick={() => void summaryQuery.refetch()}
          />
        }
      />

      <section className="card">
        <SectionHeading
          title="Visão geral"
          description="Resumo dos eventos registrados no período."
          actions={
            <div className="segmented" role="group" aria-label="Período do resumo">
              {OBSERVABILITY_WINDOWS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={
                    window === option.value ? "segmented__item is-active" : "segmented__item"
                  }
                  aria-pressed={window === option.value}
                  onClick={() => selectWindow(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          }
        />

        {summaryQuery.error ? (
          <ObservabilityQueryError
            error={summaryQuery.error}
            onRetry={() => void summaryQuery.refetch()}
          />
        ) : summaryQuery.isPending ? (
          <SkeletonList rows={4} label="Carregando resumo..." />
        ) : current && previous ? (
          <>
            <p className="muted obs-range">
              De {formatDate(current.from_at)} até {formatDate(current.to_at)} ·{" "}
              {formatCount(current.total_events)}{" "}
              {current.total_events === 1 ? "evento registrado" : "eventos registrados"}
            </p>

            <div className="stat-grid">
              <StatCard
                icon={<AlertIcon size={18} />}
                tone="danger"
                value={formatCount(levelCount(current, "error"))}
                label="Erros"
                comparison={variationText(
                  levelCount(current, "error"),
                  levelCount(previous, "error"),
                )}
              />
              <StatCard
                icon={<AlertIcon size={18} />}
                tone="danger"
                value={formatCount(levelCount(current, "fatal"))}
                label="Críticos"
                comparison={variationText(
                  levelCount(current, "fatal"),
                  levelCount(previous, "fatal"),
                )}
              />
              <StatCard
                icon={<AlertIcon size={18} />}
                tone="warning"
                value={formatCount(levelCount(current, "warn"))}
                label="Avisos"
                comparison={variationText(
                  levelCount(current, "warn"),
                  levelCount(previous, "warn"),
                )}
              />
              <StatCard
                icon={<RefreshIcon size={18} />}
                tone="info"
                value={formatCount(current.http.requests)}
                label="Requisições"
                comparison={variationText(current.http.requests, previous.http.requests)}
              />
              <StatCard
                icon={<InfoIcon size={18} />}
                tone="warning"
                value={formatCount(current.http.status_4xx)}
                label="Respostas 4xx"
                detail={requestRateText(current.http.status_4xx, current.http.requests)}
                comparison={variationText(current.http.status_4xx, previous.http.status_4xx)}
              />
              <StatCard
                icon={<AlertIcon size={18} />}
                tone="danger"
                value={formatCount(current.http.status_5xx)}
                label="Respostas 5xx"
                detail={requestRateText(current.http.status_5xx, current.http.requests)}
                comparison={variationText(current.http.status_5xx, previous.http.status_5xx)}
              />
              <StatCard
                icon={<ClockIcon size={18} />}
                tone="info"
                value={formatDuration(current.http.avg_duration_ms)}
                label="Tempo médio"
                comparison={variationText(
                  Math.round(current.http.avg_duration_ms ?? 0),
                  Math.round(previous.http.avg_duration_ms ?? 0),
                )}
              />
              <StatCard
                icon={<UsersIcon size={18} />}
                tone="danger"
                value={formatCount(current.suspicious_users.length)}
                label="Contas com eventos suspeitos"
                comparison={variationText(
                  current.suspicious_users.length,
                  previous.suspicious_users.length,
                )}
              />
              <StatCard
                icon={<LockIcon size={18} />}
                tone="warning"
                value={formatCount(current.auth.failed_logins)}
                label="Falhas de acesso"
                comparison={variationText(current.auth.failed_logins, previous.auth.failed_logins)}
              />
              <StatCard
                icon={<ShieldIcon size={18} />}
                tone="warning"
                value={formatCount(current.jobs.failed)}
                label="Tarefas com falha"
                comparison={variationText(current.jobs.failed, previous.jobs.failed)}
              />
            </div>

            {current.total_events === 0 ? (
              <p className="muted">
                Nenhum evento foi registrado neste período. Os números acima mostram a comparação
                com o período anterior.
              </p>
            ) : null}
          </>
        ) : null}
      </section>

      <section className="card">
        <SectionHeading
          title="Contas com mais eventos de segurança"
          description="Contas que geraram eventos de segurança no período. Abra a conta para ver a cronologia completa."
        />
        {summaryQuery.error ? (
          <ObservabilityQueryError
            error={summaryQuery.error}
            onRetry={() => void summaryQuery.refetch()}
          />
        ) : summaryQuery.isPending ? (
          <SkeletonList rows={3} label="Carregando contas..." />
        ) : current && current.suspicious_users.length > 0 ? (
          <ul className="admin-list">
            {current.suspicious_users.map((user) => (
              <li key={user.user_id}>
                <Link
                  to={`/admin/observability/users/${encodeURIComponent(user.user_id)}`}
                  className="admin-row"
                >
                  <span className="admin-row__identity">
                    <span>
                      <strong>{shortId(user.user_id)}</strong>
                      <small>
                        {formatCount(user.events)} eventos · {formatCount(user.security_events)} de
                        segurança · último em {formatDate(user.last_seen_at)}
                      </small>
                    </span>
                  </span>
                  <span className="badge badge--danger">{formatCount(user.security_events)}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nenhuma conta gerou eventos de segurança no período selecionado.</p>
        )}
      </section>

      <section className="card">
        <SectionHeading
          title="Explorar eventos"
          description="Filtre a cronologia por período, nível, categoria, conta, endereço IP, rota ou identificadores."
        />
        <div className="admin-actions">
          <Link className="button button--small" to="/admin/observability/events">
            <SearchIcon size={16} />
            Todos os eventos
          </Link>
          <Link className="button button--small" to="/admin/observability/events?level=error">
            <AlertIcon size={16} />
            Ver erros
          </Link>
          <Link className="button button--small" to="/admin/observability/events?level=warn">
            <AlertIcon size={16} />
            Ver avisos
          </Link>
          <Link className="button button--small" to="/admin/observability/events?category=security">
            <ShieldIcon size={16} />
            Ver segurança
          </Link>
        </div>
      </section>
    </>
  );
}
