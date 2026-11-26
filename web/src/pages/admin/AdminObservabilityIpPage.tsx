import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { EmptyState, SkeletonList } from "../../components/Feedback";
import { MapPinIcon } from "../../components/ui/Icons";
import { PageHeader, SectionHeading } from "../../components/ui/PageHeader";
import { api } from "../../lib/api";
import { formatDate, shortId } from "../../lib/format";
import { formatCount, observabilityPollInterval } from "../../lib/observability";
import { queryKeys } from "../../lib/query";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import {
  CopyableValue,
  EventTable,
  ExportControls,
  ObservabilityQueryError,
  RefreshButton,
} from "./AdminObservabilityShared";

export function AdminObservabilityIpPage() {
  useDocumentTitle("Monitoramento · Endereço IP");
  const { ip = "" } = useParams();

  const ipQuery = useQuery({
    queryKey: queryKeys.adminObservabilityIp(ip),
    queryFn: () => api.getObservabilityIp(ip),
    enabled: Boolean(ip),
    refetchInterval: observabilityPollInterval,
    refetchIntervalInBackground: false,
  });

  const report = ipQuery.data ?? null;

  return (
    <>
      <PageHeader
        eyebrow="JOGA y ADMINISTRAÇÃO"
        title="Endereço IP"
        description={
          <>
            Eventos registrados para <CopyableValue value={ip} label="endereço IP" />.
          </>
        }
        actions={
          <div className="admin-actions admin-actions--inline">
            <Link
              className="button button--small"
              to={`/admin/observability/events?ip=${encodeURIComponent(ip)}`}
            >
              Abrir no explorador
            </Link>
            <RefreshButton busy={ipQuery.isFetching} onClick={() => void ipQuery.refetch()} />
          </div>
        }
      />

      {ipQuery.error ? (
        <section className="card">
          <ObservabilityQueryError error={ipQuery.error} onRetry={() => void ipQuery.refetch()} />
        </section>
      ) : ipQuery.isPending ? (
        <section className="card">
          <SkeletonList rows={5} label="Carregando endereço..." />
        </section>
      ) : report ? (
        <>
          <section className="card">
            <SectionHeading
              title="Resumo do endereço"
              description="Primeiro e último registro, volume de eventos e contas associadas."
            />
            <dl className="admin-meta">
              <div>
                <dt>Endereço</dt>
                <dd>
                  <CopyableValue value={report.ip} label="endereço IP" />
                </dd>
              </div>
              {report.ip_hash ? (
                <div>
                  <dt>Identificador do endereço</dt>
                  <dd className="mono">{report.ip_hash}</dd>
                </div>
              ) : null}
              <div>
                <dt>Primeiro registro</dt>
                <dd>{report.first_seen_at ? formatDate(report.first_seen_at) : "—"}</dd>
              </div>
              <div>
                <dt>Último registro</dt>
                <dd>{report.last_seen_at ? formatDate(report.last_seen_at) : "—"}</dd>
              </div>
              <div>
                <dt>Eventos</dt>
                <dd>{formatCount(report.total_events)}</dd>
              </div>
              <div>
                <dt>Eventos de segurança</dt>
                <dd>{formatCount(report.security_events)}</dd>
              </div>
              <div>
                <dt>Falhas de acesso</dt>
                <dd>{formatCount(report.failed_logins)}</dd>
              </div>
            </dl>

            <SectionHeading
              title="Contas associadas"
              description="Contas que usaram este endereço, da mais recente para a mais antiga."
              level={3}
            />
            {report.users.length === 0 ? (
              <p className="muted">Nenhuma conta identificada neste endereço.</p>
            ) : (
              <ul className="admin-list">
                {report.users.map((user) => (
                  <li key={user.user_id}>
                    <Link
                      to={`/admin/observability/users/${encodeURIComponent(user.user_id)}`}
                      className="admin-row"
                    >
                      <span className="admin-row__identity">
                        <span>
                          <strong>{shortId(user.user_id)}</strong>
                          <small>
                            {formatCount(user.events)} {user.events === 1 ? "evento" : "eventos"} ·
                            último em {formatDate(user.last_seen_at)}
                          </small>
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card">
            <SectionHeading
              title="Eventos registrados"
              description="Cronologia do mais recente para o mais antigo."
              actions={
                <Link className="button button--small button--ghost" to="/admin/observability">
                  Voltar à visão geral
                </Link>
              }
            />
            {report.events.length === 0 ? (
              <EmptyState title="Nenhum evento" icon={<MapPinIcon size={28} />}>
                Não há eventos registrados para este endereço.
              </EmptyState>
            ) : (
              <EventTable events={report.events} />
            )}
          </section>

          <section className="card">
            <ExportControls filters={{ ip: report.ip }} />
          </section>
        </>
      ) : null}
    </>
  );
}
