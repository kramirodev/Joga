export function Pagination({
  total,
  limit,
  offset,
  onChange,
  disabled = false,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
  disabled?: boolean;
}) {
  const pageCount = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.min(pageCount, Math.floor(offset / limit) + 1);
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + limit, total);
  const canGoBack = offset > 0;
  const canGoForward = offset + limit < total;

  if (total === 0) return null;

  return (
    <nav className="pagination" aria-label="Paginação">
      <span className="pagination__info">{`Mostrando ${first}–${last} de ${total}`}</span>
      <div className="pagination__actions">
        <button
          type="button"
          className="button button--small button--ghost"
          onClick={() => onChange(Math.max(0, offset - limit))}
          disabled={disabled || !canGoBack}
        >
          Anterior
        </button>
        <span className="pagination__page">
          Página {currentPage} de {pageCount}
        </span>
        <button
          type="button"
          className="button button--small button--ghost"
          onClick={() => onChange(offset + limit)}
          disabled={disabled || !canGoForward}
        >
          Próxima
        </button>
      </div>
    </nav>
  );
}
