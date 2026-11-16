import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { EmptyState, ErrorNotice, SkeletonList } from "../../components/Feedback";
import { TextField } from "../../components/ui/Field";
import { SearchIcon, ShieldIcon } from "../../components/ui/Icons";
import { Pagination } from "../../components/ui/Pagination";
import { SectionHeading } from "../../components/ui/PageHeader";
import { api } from "../../lib/api";
import {
  auditActionLabel,
  auditResourceLabel,
  formatDate,
  formatError,
  requestIdOf,
  shortId,
} from "../../lib/format";
import { queryKeys } from "../../lib/query";

const PAGE_SIZE = 50;

export function AuditPanel({ organizationId }: { organizationId: string }) {
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");

  const auditQuery = useQuery({
    queryKey: [...queryKeys.audit(organizationId), PAGE_SIZE, offset],
    queryFn: () => api.listAudit(organizationId, PAGE_SIZE, offset),
    placeholderData: keepPreviousData,
  });

  const events = useMemo(() => auditQuery.data?.audit ?? [], [auditQuery.data]);
  const total = auditQuery.data?.total ?? 0;
  const filtered = useMemo(() => {
    if (!search.trim()) return events;
    const query = search.toLowerCase();
    return events.filter((event) =>
      [
        auditActionLabel(event.action),
        auditResourceLabel(event.resource_type),
        event.resource_id ?? "",
        event.actor_user_id ?? "",
        JSON.stringify(event.details ?? {}),
      ]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [events, search]);

  return (
    <section className="card">
      <SectionHeading
        title="Auditoria"
        description="Trilha append-only das ações administrativas desta organização."
        actions={
          <div className="toolbar__search">
            <SearchIcon size={16} />
            <TextField
              id="audit-search"
              label="Buscar nesta página"
              className="field--search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar nesta página"
              inputClassName="input--search"
            />
          </div>
        }
      />
      {auditQuery.error ? (
        <ErrorNotice
          message={formatError(auditQuery.error)}
          requestId={requestIdOf(auditQuery.error)}
          onRetry={() => void auditQuery.refetch()}
        />
      ) : auditQuery.isPending ? (
        <SkeletonList rows={4} label="Carregando auditoria..." />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={events.length === 0 ? "Nenhum evento" : "Nenhum evento encontrado"}
          icon={<ShieldIcon size={28} />}
        >
          {events.length === 0
            ? "Ainda não há ações administrativas registradas nesta organização."
            : "Ajuste a busca para encontrar outro evento."}
        </EmptyState>
      ) : (
        <ul className="audit-list">
          {filtered.map((event) => (
            <li key={event.id} className="audit-row">
              <div className="audit-row__main">
                <strong>{auditActionLabel(event.action)}</strong>
                <small>
                  {auditResourceLabel(event.resource_type)}
                  {event.resource_id ? (
                    <>
                      {" "}
                      · <span className="mono">#{shortId(event.resource_id)}</span>
                    </>
                  ) : null}
                </small>
                <small>
                  Ator: {event.actor_user_id ? `#${shortId(event.actor_user_id)}` : "sistema"} ·{" "}
                  {formatDate(event.created_at)}
                </small>
              </div>
              {event.details ? (
                <details>
                  <summary>Detalhes técnicos</summary>
                  <pre>{JSON.stringify(event.details, null, 2)}</pre>
                </details>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      <Pagination
        total={total}
        limit={PAGE_SIZE}
        offset={offset}
        onChange={setOffset}
        disabled={auditQuery.isFetching}
      />
    </section>
  );
}
