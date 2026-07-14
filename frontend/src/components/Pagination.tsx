import "./components.css";

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const lastPage = Math.max(0, Math.ceil(total / pageSize) - 1);
  return (
    <div className="pagination">
      <button
        className="btn btn-secondary"
        disabled={page === 0}
        onClick={() => onPageChange(page - 1)}
      >
        ← Prev
      </button>
      <span>
        Page {page + 1} of {lastPage + 1}
      </span>
      <button
        className="btn btn-secondary"
        disabled={page >= lastPage}
        onClick={() => onPageChange(page + 1)}
      >
        Next →
      </button>
    </div>
  );
}
