import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { EmptyState, SkeletonList } from "../../components/Feedback";
import { UsersIcon } from "../../components/ui/Icons";
import { PageHeader, SectionHeading } from "../../components/ui/PageHeader";
import { api } from "../../lib/api";
import {
  EMPTY_EVENT_FILTERS,
  eventFilterKey,
  formatCount,
  observabilityPollInterval,
  readEventFilters,
  writeEventFilters,
  type EventFilterFormState,
} from "../../lib/observability";
import { queryKeys } from "../../lib/query";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import {
  CopyableValue,
  EventFiltersForm,
  EventTable,
  ExportControls,
  ObservabilityQueryError,
  RefreshButton,
} from "./AdminObservabilityShared";

const PAGE_SIZE = 50;

export function AdminObservabilityUserPage() {
  useDocumentTitle("Monitoramento · Usuário");
  const { userId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = readEventFilters(searchParams);
  const activityFilters = {
    from: filters.from || undefined,
    to: filters.to || undefined,
    category: filters.category || undefined,
  };
  const filterKey = eventFilterKey(activityFilters);

  const filterSignature = searchParams.toString();
  const [draft, setDraft] = useState<EventFilterFormState>(filters);
  const [draftSignature, setDraftSignature] = useState(filterSignature);
  if (draftSignature !== filterSignature) {
    setDraftSignature(filterSignature);
    setDraft(readEventFilters(searchParams));
  }

  const activityQuery = useInfiniteQuery({
    queryKey: queryKeys.adminObservabilityUser(userId, filterKey),
    queryFn: ({ pageParam }) =>
      api.getObservabilityUserActivity(userId, {
        ...activityFilters,
        cursor: pageParam,
        limit: PAGE_SIZE,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
    enabled: Boolean(userId),
    refetchInterval: observabilityPollInterval,
    refetchIntervalInBackground: false,
  });

  const events = activityQuery.data?.pages.flatMap((page) => page.events) ?? [];

  function applyFilters() {
    setSearchParams(writeEventFilters(draft));
  }

  function clearFilters() {
    setDraft(EMPTY_EVENT_FILTERS);
    setSearchParams(new URLSearchParams());
  }

  return (
    <>
      <PageHeader
        eyebrow="JOGA y ADMINISTRAÇÃO"
        title="Atividade do usuário"
        description={
          <>
            Cronologia das ações registradas para a conta{" "}
            <CopyableValue value={userId} label="identificador do usuário" />.
          </>
        }
        actions={
          <div className="admin-actions admin-actions--inline">
            <Link
              className="button button--small"
              to={`/admin/observability/events?user_id=${encodeURIComponent(userId)}`}
            >
              Abrir no explorador
            </Link>
            <RefreshButton
              busy={activityQuery.isFetching}
              onClick={() => void activityQuery.refetch()}
            />
          </div>
        }
      />

      <section className="card">
        <SectionHeading
          title="Filtros"
          description="Restrinja a cronologia por período ou categoria."
          actions={
            <Link className="button button--small button--ghost" to="/admin/observability">
              Voltar à visão geral
            </Link>
          }
        />
        <EventFiltersForm
          value={draft}
          onChange={setDraft}
          onSubmit={applyFilters}
          onClear={clearFilters}
          busy={activityQuery.isFetching}
          mode="user"
        />

        {activityQuery.error ? (
          <ObservabilityQueryError
            error={activityQuery.error}
            onRetry={() => void activityQuery.refetch()}
          />
        ) : activityQuery.isPending ? (
          <SkeletonList rows={5} label="Carregando atividade..." />
        ) : events.length === 0 ? (
          <EmptyState title="Nenhum evento para esta conta" icon={<UsersIcon size={28} />}>
            Não há eventos registrados para esta conta no período selecionado.
          </EmptyState>
        ) : (
          <>
            <EventTable events={events} showUser={false} />
            <div className="obs-more">
              <span className="muted">
                {formatCount(events.length)}{" "}
                {events.length === 1 ? "evento carregado" : "eventos carregados"}
              </span>
              {activityQuery.hasNextPage ? (
                <button
                  type="button"
                  className="button button--small"
                  onClick={() => void activityQuery.fetchNextPage()}
                  disabled={activityQuery.isFetchingNextPage}
                  aria-busy={activityQuery.isFetchingNextPage || undefined}
                >
                  {activityQuery.isFetchingNextPage ? "Carregando..." : "Carregar mais"}
                </button>
              ) : (
                <span className="muted">Fim da lista.</span>
              )}
            </div>
          </>
        )}
      </section>

      {activityQuery.isSuccess ? (
        <section className="card">
          <ExportControls filters={{ ...activityFilters, userId }} />
        </section>
      ) : null}
    </>
  );
}
