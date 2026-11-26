import { useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { ErrorNotice, InfoNotice, InlineSpinner } from "../../components/Feedback";
import { CheckboxField, SelectField, TextField } from "../../components/ui/Field";
import { RefreshIcon, SearchIcon } from "../../components/ui/Icons";
import { SectionHeading } from "../../components/ui/PageHeader";
import { isForbidden } from "../../lib/admin";
import { api } from "../../lib/api";
import { formatDate, requestIdOf, shortId } from "../../lib/format";
import {
  CATEGORY_OPTIONS,
  LEVEL_OPTIONS,
  categoryLabel,
  copyToClipboard,
  eventSourceLabel,
  formatCount,
  formatDuration,
  isoToLocalInput,
  levelLabel,
  levelTone,
  localInputToIso,
  observabilityErrorMessage,
  statusTone,
  type EventFilterFormState,
} from "../../lib/observability";
import type {
  ObservabilityEvent,
  ObservabilityEventDetail,
  ObservabilityEventFilters,
  ObservabilityExportFile,
} from "../../types";
import { AdminForbiddenState } from "./AdminShared";

export function ObservabilityQueryError({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: () => void;
}) {
  if (isForbidden(error)) return <AdminForbiddenState />;
  return (
    <ErrorNotice
      message={observabilityErrorMessage(error)}
      requestId={requestIdOf(error)}
      onRetry={onRetry}
    />
  );
}

export function RefreshButton({ busy, onClick }: { busy: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      className="button button--small"
      onClick={onClick}
      disabled={busy}
      aria-busy={busy || undefined}
    >
      <RefreshIcon size={16} />
      Atualizar
    </button>
  );
}

export function LevelBadge({ level }: { level: string }) {
  return <span className={`badge badge--${levelTone(level)}`}>{levelLabel(level)}</span>;
}

export function CopyableValue({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    const ok = await copyToClipboard(value);
    if (!ok) return;
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <span className="obs-copy">
      <code>{value}</code>
      <button
        type="button"
        className="button button--small button--ghost"
        aria-label={`Copiar ${label}`}
        onClick={() => void handleCopy()}
      >
        {copied ? "Copiado" : "Copiar"}
      </button>
    </span>
  );
}

export function EventFiltersForm({
  value,
  onChange,
  onSubmit,
  onClear,
  busy = false,
  mode = "explorer",
}: {
  value: EventFilterFormState;
  onChange: (next: EventFilterFormState) => void;
  onSubmit: () => void;
  onClear: () => void;
  busy?: boolean;
  mode?: "explorer" | "user";
}) {
  function update<K extends keyof EventFilterFormState>(key: K, next: string) {
    onChange({ ...value, [key]: next });
  }

  return (
    <form
      className="filters-form obs-filters"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
      noValidate
    >
      <TextField
        id="obs-filter-from"
        label="De"
        type="datetime-local"
        value={isoToLocalInput(value.from)}
        onChange={(event) => update("from", localInputToIso(event.target.value))}
      />
      <TextField
        id="obs-filter-to"
        label="Até"
        type="datetime-local"
        value={isoToLocalInput(value.to)}
        onChange={(event) => update("to", localInputToIso(event.target.value))}
      />
      <SelectField
        id="obs-filter-category"
        label="Categoria"
        value={value.category}
        onChange={(event) => update("category", event.target.value)}
      >
        {CATEGORY_OPTIONS.map((option) => (
          <option key={option.value || "all"} value={option.value}>
            {option.label}
          </option>
        ))}
      </SelectField>
      {mode === "explorer" ? (
        <>
          <SelectField
            id="obs-filter-level"
            label="Nível"
            value={value.level}
            onChange={(event) => update("level", event.target.value)}
          >
            {LEVEL_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </SelectField>
          <TextField
            id="obs-filter-user"
            label="Usuário"
            value={value.userId}
            onChange={(event) => update("userId", event.target.value)}
            placeholder="Identificador da conta"
            maxLength={64}
          />
          <TextField
            id="obs-filter-ip"
            label="Endereço IP"
            value={value.ip}
            onChange={(event) => update("ip", event.target.value)}
            placeholder="192.0.2.10"
            maxLength={45}
          />
          <TextField
            id="obs-filter-endpoint"
            label="Rota"
            value={value.endpoint}
            onChange={(event) => update("endpoint", event.target.value)}
            placeholder="Ex.: /bookings"
            maxLength={255}
          />
          <TextField
            id="obs-filter-status"
            label="Situação"
            type="number"
            min={100}
            max={599}
            value={value.status}
            onChange={(event) => update("status", event.target.value)}
            placeholder="Ex.: 500"
          />
          <TextField
            id="obs-filter-request"
            label="ID da requisição"
            value={value.requestId}
            onChange={(event) => update("requestId", event.target.value)}
            maxLength={64}
          />
          <TextField
            id="obs-filter-correlation"
            label="ID de correlação"
            value={value.correlationId}
            onChange={(event) => update("correlationId", event.target.value)}
            maxLength={64}
          />
          <TextField
            id="obs-filter-q"
            label="Busca"
            value={value.q}
            onChange={(event) => update("q", event.target.value)}
            placeholder="Texto da mensagem ou do código de erro"
            maxLength={100}
          />
        </>
      ) : null}
      <div className="filters-form__actions">
        <button type="submit" className="button" disabled={busy}>
          <SearchIcon size={16} />
          Buscar
        </button>
        <button type="button" className="button button--ghost" onClick={onClear}>
          Limpar
        </button>
      </div>
    </form>
  );
}

function EventUser({ event }: { event: ObservabilityEvent }) {
  if (!event.user_id) return <span className="muted">—</span>;
  return (
    <Link
      to={`/admin/observability/users/${encodeURIComponent(event.user_id)}`}
      title={event.user_id}
    >
      {shortId(event.user_id)}
    </Link>
  );
}

function EventIp({ event }: { event: ObservabilityEvent }) {
  if (!event.ip) return <span className="muted">—</span>;
  if (event.ip_masked) return <span className="mono">{event.ip}</span>;
  return (
    <Link to={`/admin/observability/ips/${encodeURIComponent(event.ip)}`} className="mono">
      {event.ip}
    </Link>
  );
}

export function EventTable({
  events,
  showUser = true,
}: {
  events: ObservabilityEvent[];
  showUser?: boolean;
}) {
  const location = useLocation();
  const detailState = { from: `${location.pathname}${location.search}` };

  return (
    <div className="admin-table-wrap">
      <table className="admin-table">
        <caption className="sr-only">Eventos monitorados</caption>
        <thead>
          <tr>
            <th scope="col">Quando</th>
            <th scope="col">Nível</th>
            <th scope="col">Evento</th>
            <th scope="col">Rota</th>
            {showUser ? <th scope="col">Usuário</th> : null}
            <th scope="col">Endereço IP</th>
            <th scope="col">
              <span className="sr-only">Ações</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id}>
              <td>
                <span className="admin-table__cell">
                  <strong>{formatDate(event.occurred_at)}</strong>
                  <small>{eventSourceLabel(event.source)}</small>
                </span>
              </td>
              <td>
                <LevelBadge level={event.level} />
              </td>
              <td>
                <span className="admin-table__cell">
                  <strong>{event.message ?? event.error_code ?? "Sem descrição"}</strong>
                  <small>
                    {categoryLabel(event.category)}
                    {event.module ? ` · ${event.module}` : ""}
                  </small>
                </span>
              </td>
              <td>
                <span className="admin-table__cell">
                  <strong className="mono">{event.endpoint ?? "—"}</strong>
                  {event.status !== null ? (
                    <small>
                      Situação{" "}
                      <span className={`badge badge--${statusTone(event.status)}`}>
                        {event.status}
                      </span>
                    </small>
                  ) : null}
                </span>
              </td>
              {showUser ? (
                <td>
                  <EventUser event={event} />
                </td>
              ) : null}
              <td>
                <EventIp event={event} />
              </td>
              <td className="admin-table__actions">
                <Link
                  to={`/admin/observability/events/${encodeURIComponent(event.id)}`}
                  state={detailState}
                  className="button button--small button--ghost"
                  aria-label={`Ver detalhe do evento ${shortId(event.id)}`}
                >
                  Detalhe
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function filterLink(params: Record<string, string>): string {
  const query = new URLSearchParams(params);
  return `/admin/observability/events?${query.toString()}`;
}

export function EventDetailBody({ event }: { event: ObservabilityEventDetail }) {
  const requestTarget = event.request_id
    ? filterLink({ request_id: event.request_id })
    : event.correlation_id
      ? filterLink({ correlation_id: event.correlation_id })
      : null;
  const details = event.details ? JSON.stringify(event.details, null, 2) : null;

  return (
    <>
      <p className="obs-detail__message">{event.message ?? "Evento sem mensagem registrada."}</p>
      {event.error_code ? (
        <p className="muted">
          Código do erro: <code>{event.error_code}</code>
        </p>
      ) : null}

      <dl className="admin-meta">
        <div>
          <dt>Quando</dt>
          <dd>{formatDate(event.occurred_at)}</dd>
        </div>
        <div>
          <dt>Nível</dt>
          <dd>
            <LevelBadge level={event.level} />
          </dd>
        </div>
        <div>
          <dt>Categoria</dt>
          <dd>{categoryLabel(event.category)}</dd>
        </div>
        <div>
          <dt>Origem</dt>
          <dd>{eventSourceLabel(event.source)}</dd>
        </div>
        {event.module ? (
          <div>
            <dt>Módulo</dt>
            <dd className="mono">{event.module}</dd>
          </div>
        ) : null}
        {event.endpoint ? (
          <div>
            <dt>Rota</dt>
            <dd className="mono">{event.endpoint}</dd>
          </div>
        ) : null}
        {event.status !== null ? (
          <div>
            <dt>Situação</dt>
            <dd>{event.status}</dd>
          </div>
        ) : null}
        {event.duration_ms !== null ? (
          <div>
            <dt>Duração</dt>
            <dd>{formatDuration(event.duration_ms)}</dd>
          </div>
        ) : null}
        {event.user_agent ? (
          <div>
            <dt>Navegador</dt>
            <dd>{event.user_agent}</dd>
          </div>
        ) : null}
      </dl>

      <div className="admin-actions">
        {requestTarget ? (
          <Link className="button button--small" to={requestTarget}>
            Eventos da mesma requisição
          </Link>
        ) : null}
        {event.user_id ? (
          <Link
            className="button button--small"
            to={`/admin/observability/users/${encodeURIComponent(event.user_id)}`}
          >
            Eventos deste usuário
          </Link>
        ) : null}
        {event.ip && !event.ip_masked ? (
          <Link
            className="button button--small"
            to={`/admin/observability/ips/${encodeURIComponent(event.ip)}`}
          >
            Eventos deste IP
          </Link>
        ) : null}
      </div>

      <SectionHeading title="Identificadores" level={3} />
      <dl className="admin-meta">
        <div>
          <dt>Evento</dt>
          <dd>
            <CopyableValue value={event.id} label="identificador do evento" />
          </dd>
        </div>
        {event.request_id ? (
          <div>
            <dt>Requisição</dt>
            <dd>
              <CopyableValue value={event.request_id} label="identificador da requisição" />
            </dd>
          </div>
        ) : null}
        {event.correlation_id ? (
          <div>
            <dt>Correlação</dt>
            <dd>
              <CopyableValue value={event.correlation_id} label="identificador de correlação" />
            </dd>
          </div>
        ) : null}
        <div>
          <dt>Usuário</dt>
          <dd>{event.user_id ? <EventUser event={event} /> : "Não identificado"}</dd>
        </div>
        <div>
          <dt>Endereço IP</dt>
          <dd>
            <EventIp event={event} />
          </dd>
        </div>
      </dl>

      {details ? (
        <>
          <SectionHeading
            title="Metadados"
            description="Informações adicionais registradas junto do evento."
            level={3}
          />
          <pre className="obs-pre">{details}</pre>
        </>
      ) : null}

      {event.result ? (
        <>
          <SectionHeading title="Resultado" level={3} />
          <pre className="obs-pre">{event.result}</pre>
        </>
      ) : null}

      {event.stack ? (
        <>
          <SectionHeading
            title="Rastreamento técnico"
            description="Sequência de chamadas registrada no momento do evento."
            level={3}
          />
          <pre className="obs-pre obs-pre--stack">{event.stack}</pre>
        </>
      ) : null}
    </>
  );
}

function saveExportFile(file: ObservabilityExportFile) {
  const url = URL.createObjectURL(file.blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = file.filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ExportControls({ filters }: { filters: ObservabilityEventFilters }) {
  const [format, setFormat] = useState<"csv" | "json" | null>(null);
  const [lastFormat, setLastFormat] = useState<"csv" | "json">("csv");
  const [fullIp, setFullIp] = useState(false);
  const [result, setResult] = useState<ObservabilityExportFile | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function exportAs(nextFormat: "csv" | "json") {
    setFormat(nextFormat);
    setLastFormat(nextFormat);
    setResult(null);
    setError(null);
    try {
      const file = await api.exportObservability({ ...filters, format: nextFormat, fullIp });
      saveExportFile(file);
      setResult(file);
    } catch (caught) {
      setError(caught);
    } finally {
      setFormat(null);
    }
  }

  return (
    <section className="obs-export" aria-label="Exportar eventos">
      <SectionHeading
        title="Exportar"
        description="O arquivo respeita os filtros aplicados. Toda exportação fica registrada na auditoria."
        level={3}
      />
      <div className="obs-export__actions">
        <button
          type="button"
          className="button button--small"
          onClick={() => void exportAs("csv")}
          disabled={format !== null}
          aria-busy={format === "csv" || undefined}
        >
          {format === "csv" ? "Gerando CSV..." : "Exportar CSV"}
        </button>
        <button
          type="button"
          className="button button--small"
          onClick={() => void exportAs("json")}
          disabled={format !== null}
          aria-busy={format === "json" || undefined}
        >
          {format === "json" ? "Gerando JSON..." : "Exportar JSON"}
        </button>
        {format ? <InlineSpinner label="Gerando arquivo" /> : null}
      </div>
      <CheckboxField
        id="obs-export-full-ip"
        label="Incluir endereço IP completo"
        hint="Por padrão o arquivo traz o IP mascarado. A escolha fica registrada na auditoria."
        checked={fullIp}
        onChange={setFullIp}
      />
      {error ? (
        <ObservabilityQueryError error={error} onRetry={() => void exportAs(lastFormat)} />
      ) : null}
      {result ? (
        <InfoNotice>
          <p>
            Arquivo gerado com {formatCount(result.rows)} {result.rows === 1 ? "evento" : "eventos"}
            .
          </p>
          {result.truncated ? (
            <p>
              O limite de exportação foi atingido. O arquivo traz apenas os eventos mais recentes
              dentro do filtro.
            </p>
          ) : null}
        </InfoNotice>
      ) : null}
    </section>
  );
}
