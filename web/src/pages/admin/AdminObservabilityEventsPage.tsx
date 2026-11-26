import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { EmptyState, SkeletonList } from "../../components/Feedback";
import { SearchIcon } from "../../components/ui/Icons";
import { PageHeader, SectionHeading } from "../../components/ui/PageHeader";
import { api } from "../../lib/api";
import {
  EMPTY_EVENT_FILTERS,
  eventFilterKey,
  formatCount,
  observabilityPollInterval,
  readEventFilters,
  toApiFilters,
  writeEventFilters,
  type EventFilterFormState,
} from "../../lib/observability";
import { queryKeys } from "../../lib/query";
import { useDocumentTitle } from "../../lib/useDocumentTitle";

import {
  EventFiltersForm,
  EventTable,
  ExportControls,
  ObservabilityQueryError,
  RefreshButton,
} from "./AdminObservabilityShared";

const PAGE_SIZE = 50;

export function AdminObservabilityEventsPage() {
  useDocumentTitle("Monitoramento · Eventos");
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = readEventFilters(searchParams);
  const apiFilters = toApiFilters(filters);
  const filterKey = eventFilterKey(apiFilters);
  const activeFilterCount = Object.values(apiFilters).filter(
    (value) => value !== undefined && value !== "",
  ).length;

  const filterSignature = searchParams.toString();
  const [draft, setDraft] = useState<EventFilterFormState>(filters);
  const [draftSignature, setDraftSignature] = useState(filterSignature);
  if (draftSignature !== filterSignature) {
    setDraftSignature(filterSignature);
    setDraft(readEventFilters(searchParams));
  }

  const eventsQuery = useInfiniteQuery({
    queryKey: queryKeys.adminObservabilityEvents(filterKey),
    queryFn: ({ pageParam }) =>
      api.listObservabilityEvents({ ...apiFilters, cursor: pageParam, limit: PAGE_SIZE }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
    refetchInterval: observabilityPollInterval,
    refetchIntervalInBackground: false,
  });

  const events = eventsQuery.data?.pages.flatMap((page) => page.events) ?? [];

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
        title="Eventos"
        description="Explore a cronologia da plataforma, do mais recente para o mais antigo. Os endereços IP aparecem mascarados nas listas."
        actions={
          <RefreshButton busy={eventsQuery.isFetching} onClick={() => void eventsQuery.refetch()} />
        }
      />

      <section className="card">
        <SectionHeading
          title="Filtros"
          description="Combine os filtros para encontrar um evento específico."
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
          busy={eventsQuery.isFetching}
        />

        {eventsQuery.error ? (
          <ObservabilityQueryError
            error={eventsQuery.error}
            onRetry={() => void eventsQuery.refetch()}
          />
        ) : eventsQuery.isPending ? (
          <SkeletonList rows={5} label="Carregando eventos..." />
        ) : events.length === 0 ? (
          <EmptyState title="Nenhum evento encontrado" icon={<SearchIcon size={28} />}>
            {activeFilterCount > 0
              ? "Ajuste o período ou os demais filtros para encontrar outros eventos."
              : "Ainda não há eventos registrados no período consultado."}
          </EmptyState>
        ) : (
          <>
            <EventTable events={events} />
            <div className="obs-more">
              <span className="muted">
                {formatCount(events.length)}{" "}
                {events.length === 1 ? "evento carregado" : "eventos carregados"}
              </span>
              {eventsQuery.hasNextPage ? (
                <button
                  type="button"
                  className="button button--small"
                  onClick={() => void eventsQuery.fetchNextPage()}
                  disabled={eventsQuery.isFetchingNextPage}
                  aria-busy={eventsQuery.isFetchingNextPage || undefined}
                >
                  {eventsQuery.isFetchingNextPage ? "Carregando..." : "Carregar mais"}
                </button>
              ) : (
                <span className="muted">Fim da lista.</span>
              )}
            </div>
          </>
        )}
      </section>

      {eventsQuery.isSuccess ? (
        <section className="card">
          <ExportControls filters={apiFilters} />
        </section>
      ) : null}
    </>
  );
}
