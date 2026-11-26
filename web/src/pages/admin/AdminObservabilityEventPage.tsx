import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";

import { EmptyState, SkeletonList } from "../../components/Feedback";
import { AlertIcon } from "../../components/ui/Icons";
import { PageHeader } from "../../components/ui/PageHeader";
import { ApiError, api } from "../../lib/api";
import { observabilityErrorMessage } from "../../lib/observability";
import { queryKeys } from "../../lib/query";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import {
  EventDetailBody,
  ObservabilityQueryError,
  RefreshButton,
} from "./AdminObservabilityShared";

interface DetailLocationState {
  from?: string;
}

export function AdminObservabilityEventPage() {
  useDocumentTitle("Monitoramento · Evento");
  const { eventId = "" } = useParams();
  const location = useLocation();
  const backTo =
    (location.state as DetailLocationState | null)?.from ?? "/admin/observability/events";

  const eventQuery = useQuery({
    queryKey: queryKeys.adminObservabilityEvent(eventId),
    queryFn: () => api.getObservabilityEvent(eventId),
    enabled: Boolean(eventId),
  });

  const missing =
    eventQuery.error instanceof ApiError && eventQuery.error.code === "event_not_found";

  return (
    <>
      <PageHeader
        eyebrow="JOGA y ADMINISTRAÇÃO"
        title="Detalhe do evento"
        description="Informações completas do registro, com identificadores para correlação."
        actions={
          <div className="admin-actions admin-actions--inline">
            <Link className="button button--small button--ghost" to={backTo}>
              Voltar
            </Link>
            <RefreshButton busy={eventQuery.isFetching} onClick={() => void eventQuery.refetch()} />
          </div>
        }
      />

      <section className="card">
        {eventQuery.error ? (
          missing ? (
            <EmptyState title="Evento não encontrado" icon={<AlertIcon size={28} />}>
              {observabilityErrorMessage(eventQuery.error)} Volte à lista para escolher outro
              registro.
            </EmptyState>
          ) : (
            <ObservabilityQueryError
              error={eventQuery.error}
              onRetry={() => void eventQuery.refetch()}
            />
          )
        ) : eventQuery.isPending ? (
          <SkeletonList rows={5} label="Carregando evento..." />
        ) : eventQuery.data ? (
          <EventDetailBody event={eventQuery.data} />
        ) : null}
      </section>
    </>
  );
}
