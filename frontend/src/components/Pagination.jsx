import { useEffect, useMemo, useState } from "react";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";

/**
 * Slices a list into pages and keeps the current page honest.
 *
 * Two things that only show up in real use are handled here rather than in
 * every caller: the page is clamped when the list shrinks underneath it (a
 * filter narrowed, a row was deleted), and it snaps back to page one whenever
 * `resetKey` changes, so applying a filter never lands the operator on an empty
 * page seven of a three-page result.
 */
export function usePagination(items, pageSize, resetKey = "") {
  const [page, setPage] = useState(1);
  const list = items ?? [];
  const total = list.length;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const current = Math.min(page, pageCount);

  useEffect(() => { setPage(1); }, [resetKey, pageSize]);
  useEffect(() => { if (page !== current) setPage(current); }, [page, current]);

  const start = (current - 1) * pageSize;
  const slice = useMemo(() => list.slice(start, start + pageSize), [list, start, pageSize]);

  return {
    slice,
    page: current,
    setPage,
    pageCount,
    total,
    from: total === 0 ? 0 : start + 1,
    to: Math.min(start + pageSize, total),
  };
}

/**
 * First, last, current and its neighbours — everything else collapses into an
 * ellipsis, so the control stays one line wide whether there are 4 pages or 400.
 */
function pageWindow(current, count) {
  if (count <= 7) return Array.from({ length: count }, (_, index) => index + 1);
  const wanted = [1, count, current, current - 1, current + 1]
    .filter((page) => page >= 1 && page <= count)
    .sort((a, b) => a - b);

  const out = [];
  let previous = 0;
  for (const page of wanted) {
    if (page === previous) continue;
    if (page - previous > 1) out.push("gap");
    out.push(page);
    previous = page;
  }
  return out;
}

export default function Pagination({
  page,
  pageCount,
  onPageChange,
  from,
  to,
  total,
  unit = "mục",
  pageSize,
  pageSizeOptions,
  onPageSizeChange,
}) {
  // One page and no size control means there is nothing to operate — showing an
  // inert widget would just be noise under the list.
  if (pageCount <= 1 && !pageSizeOptions) return null;

  return (
    <nav className="pagination" aria-label="Phân trang">
      <p className="pagination__summary">
        Hiển thị <strong>{from}–{to}</strong> trên <strong>{total}</strong> {unit}
      </p>

      {pageCount > 1 && (
        <div className="pagination__pages">
          <button
            type="button"
            className="pagination__step"
            onClick={() => onPageChange(page - 1)}
            disabled={page === 1}
            aria-label="Trang trước"
          >
            <CaretLeft size={14} weight="bold" />
          </button>

          {pageWindow(page, pageCount).map((entry, index) =>
            entry === "gap" ? (
              <span key={`gap-${index}`} className="pagination__gap" aria-hidden="true">…</span>
            ) : (
              <button
                key={entry}
                type="button"
                className={`pagination__page ${entry === page ? "is-active" : ""}`.trim()}
                onClick={() => onPageChange(entry)}
                aria-label={`Trang ${entry}`}
                aria-current={entry === page ? "page" : undefined}
              >
                {entry}
              </button>
            ),
          )}

          <button
            type="button"
            className="pagination__step"
            onClick={() => onPageChange(page + 1)}
            disabled={page === pageCount}
            aria-label="Trang sau"
          >
            <CaretRight size={14} weight="bold" />
          </button>
        </div>
      )}

      {pageSizeOptions && (
        <label className="pagination__size">
          Mỗi trang
          <select value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
            {pageSizeOptions.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
      )}
    </nav>
  );
}
